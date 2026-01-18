# login.py - 本地登录脚本，生成 state.json
"""
使用方法：
1. 运行此脚本：python login.py
2. 在弹出的浏览器中扫码登录微信读书
3. 登录成功后，脚本会自动保存 state.json
4. 将 state.json 的内容复制到 GitHub Secrets 的 WXREAD_STATE 中
"""

import logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)-8s - %(message)s')
logger = logging.getLogger(__name__)

WEREAD_URL = "https://weread.qq.com/"
STATE_FILE = "state.json"


def login():
    """启动浏览器，等待用户扫码登录，保存登录状态"""
    with sync_playwright() as p:
        # 启动有头浏览器（用户需要看到二维码）
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        logger.info("🌐 正在打开微信读书...")
        page.goto(WEREAD_URL)
        
        logger.info("📱 请使用微信扫码登录...")
        logger.info("⏳ 等待登录成功（最长等待 2 分钟）...")
        
        try:
            # 等待登录成功的标志：用户头像出现
            # 微信读书登录后会显示用户头像
            page.wait_for_selector(".wr_avatar, .navBar_avatar, [class*='avatar']", timeout=120000)
            logger.info("✅ 登录成功！")
            
            # 等待页面完全加载
            page.wait_for_timeout(3000)
            
            # 保存浏览器状态
            context.storage_state(path=STATE_FILE)
            logger.info(f"💾 登录状态已保存到 {STATE_FILE}")
            logger.info("")
            logger.info("=" * 50)
            logger.info("📋 接下来请完成以下步骤：")
            logger.info("1. 复制 state.json 文件的全部内容")
            logger.info("2. 打开 GitHub 仓库 → Settings → Secrets → Actions")
            logger.info("3. 添加一个新的 Secret：")
            logger.info("   - Name: WXREAD_STATE")
            logger.info("   - Value: 粘贴 state.json 的内容")
            logger.info("=" * 50)
            
        except Exception as e:
            logger.error(f"❌ 登录超时或失败: {e}")
            logger.info("请确保在 2 分钟内完成扫码登录")
        finally:
            browser.close()


if __name__ == "__main__":
    login()
