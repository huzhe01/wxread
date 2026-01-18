# read_playwright.py - Playwright 自动阅读脚本
"""
在 GitHub Actions 上运行，自动阅读微信读书
支持自动更新登录状态到 GitHub Secrets
"""

import os
import json
import time
import random
import base64
import logging
import requests
from playwright.sync_api import sync_playwright
from nacl import encoding, public

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)-8s - %(message)s')
logger = logging.getLogger(__name__)

# 配置
READ_MINUTES = int(os.getenv('READ_MINUTES', 5))
STATE_FILE = "state.json"
BOOK_URL = os.getenv('BOOK_URL', "https://weread.qq.com/web/reader/ce032b305a9bc1ce0b0dd2a")

# GitHub API 配置（用于自动更新 Secret）
GITHUB_TOKEN = os.getenv('GH_PAT')  # Personal Access Token
GITHUB_REPOSITORY = os.getenv('GITHUB_REPOSITORY')  # owner/repo 格式

# 推送配置
PUSH_METHOD = os.getenv('PUSH_METHOD')


def encrypt_secret(public_key: str, secret_value: str) -> str:
    """使用 GitHub 公钥加密 Secret 值"""
    public_key_bytes = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key_bytes)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def update_github_secret(secret_name: str, secret_value: str):
    """更新 GitHub Actions Secret"""
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        logger.warning("⚠️ 未配置 GH_PAT 或 GITHUB_REPOSITORY，跳过自动更新 Secret")
        return False
    
    try:
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        # 获取仓库公钥
        key_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/secrets/public-key"
        key_response = requests.get(key_url, headers=headers)
        key_response.raise_for_status()
        key_data = key_response.json()
        
        # 加密 Secret
        encrypted_value = encrypt_secret(key_data["key"], secret_value)
        
        # 更新 Secret
        secret_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/secrets/{secret_name}"
        update_response = requests.put(
            secret_url,
            headers=headers,
            json={
                "encrypted_value": encrypted_value,
                "key_id": key_data["key_id"]
            }
        )
        update_response.raise_for_status()
        
        logger.info(f"✅ 已自动更新 GitHub Secret: {secret_name}")
        return True
        
    except Exception as e:
        logger.error(f"❌ 更新 GitHub Secret 失败: {e}")
        return False


def push_notification(content: str):
    """发送推送通知"""
    if not PUSH_METHOD:
        logger.info("ℹ️ 未配置推送方式，跳过通知")
        return
    
    try:
        from push import push
        push(content, PUSH_METHOD)
    except Exception as e:
        logger.error(f"❌ 推送失败: {e}")


def read_book():
    """执行自动阅读"""
    logger.info(f"📖 开始自动阅读，目标时长：{READ_MINUTES} 分钟")
    
    with sync_playwright() as p:
        # 启动无头浏览器
        browser = p.chromium.launch(headless=True)
        
        # 加载登录状态
        if not os.path.exists(STATE_FILE):
            logger.error(f"❌ 找不到 {STATE_FILE}，请先运行 login.py 进行登录")
            push_notification(f"❌ 微信读书自动阅读失败：找不到登录状态文件")
            return False
        
        context = browser.new_context(
            storage_state=STATE_FILE,
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            # 打开书籍页面
            logger.info(f"🌐 正在打开书籍页面...")
            page.goto(BOOK_URL, wait_until="networkidle", timeout=30000)
            
            # 等待页面加载
            page.wait_for_timeout(3000)
            
            # 检查是否需要重新登录
            if "login" in page.url.lower() or page.query_selector(".login"):
                logger.error("❌ 登录状态已失效，需要重新扫码登录")
                push_notification("❌ 微信读书登录状态已失效，请重新运行 login.py 扫码登录")
                return False
            
            logger.info("✅ 成功进入阅读页面")
            
            # 计算需要翻页的次数
            # 每次翻页间隔 10-15 秒，总时长 = READ_MINUTES * 60 秒
            total_seconds = READ_MINUTES * 60
            flip_interval = 12  # 平均翻页间隔
            flip_count = total_seconds // flip_interval
            
            logger.info(f"⏱️ 开始阅读，预计翻页 {flip_count} 次...")
            
            start_time = time.time()
            
            for i in range(flip_count):
                # 模拟翻页（右箭头键）
                page.keyboard.press("ArrowRight")
                
                # 随机等待时间（8-15秒）
                wait_time = random.uniform(8, 15)
                
                elapsed = time.time() - start_time
                remaining = total_seconds - elapsed
                
                if remaining <= 0:
                    break
                
                if (i + 1) % 10 == 0:
                    logger.info(f"📖 已阅读 {elapsed/60:.1f} 分钟，剩余 {remaining/60:.1f} 分钟")
                
                page.wait_for_timeout(int(wait_time * 1000))
            
            elapsed_minutes = (time.time() - start_time) / 60
            logger.info(f"🎉 阅读完成！实际阅读时长：{elapsed_minutes:.1f} 分钟")
            
            # 保存更新后的状态
            context.storage_state(path=STATE_FILE)
            logger.info(f"💾 已保存更新后的登录状态")
            
            # 自动更新 GitHub Secret
            with open(STATE_FILE, 'r') as f:
                state_content = f.read()
            update_github_secret("WXREAD_STATE", state_content)
            
            # 发送成功通知
            push_notification(f"🎉 微信读书自动阅读完成！\n⏱️ 阅读时长：{elapsed_minutes:.1f} 分钟")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 阅读过程出错: {e}")
            push_notification(f"❌ 微信读书自动阅读失败: {str(e)}")
            return False
            
        finally:
            browser.close()


if __name__ == "__main__":
    success = read_book()
    exit(0 if success else 1)
