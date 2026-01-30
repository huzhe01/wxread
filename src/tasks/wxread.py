import os
import time
import random
import logging
from playwright.sync_api import sync_playwright
from src.utils.push import push
from src.utils.github_api import GitHubAPI

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)-8s - %(message)s')
logger = logging.getLogger(__name__)

# 配置
# 随机阅读时长（5-10分钟）
READ_MINUTES = random.randint(5, 10)
STATE_FILE = "state.json"

# 书籍列表（三体、明朝那些事儿等）
BOOK_LIST = [
    "https://weread.qq.com/web/reader/ce032b305a9bc1ce0b0dd2a", # 三体
    "https://weread.qq.com/web/reader/9ad32d40727950039add092",
    "https://weread.qq.com/web/reader/1b7320d0813ab7e55g0195ca"
]
# 优先使用环境变量指定的书，否则从列表中随机选择
BOOK_URL = os.getenv('BOOK_URL') or random.choice(BOOK_LIST)
PUSH_METHOD = os.getenv('PUSH_METHOD')


def push_notification(content: str):
    """发送推送通知"""
    if not PUSH_METHOD:
        logger.info("ℹ️ 未配置推送方式，跳过通知")
        return
    
    try:
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
            # 1. 尝试访问主页以激活/刷新 Session
            logger.info("🏠 正在访问微信读书主页以刷新 Session...")
            page.goto("https://weread.qq.com/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)

            # 2. 严格的登录状态检查
            # 检查 URL、特定元素以及页面文本
            page_content = page.content()
            if (
                "login" in page.url.lower() 
                or page.query_selector(".login_dialog") 
                or "扫码登录" in page_content
                or (page.query_selector(".navBar_link_Login") and "登录" in page.query_selector(".navBar_link_Login").inner_text())
            ):
                logger.error("❌ 检测到未登录状态 (在主页)")
                push_notification("❌ 微信读书 Cookie 已失效 (IP变动或自然过期)，请重新运行 wxread_login.py")
                return False

            logger.info("✅ 主页访问成功，Session 有效")

            # 3. 打开书籍页面
            logger.info(f"🌐 正在打开书籍页面...")
            page.goto(BOOK_URL, wait_until="domcontentloaded", timeout=60000)
            
            # 等待页面加载 (网络请求可能还在继续，给予足够时间渲染)
            page.wait_for_timeout(5000)
            
            # 再次检查登录状态 (防止书籍页有特殊的权限验证)
            if "login" in page.url.lower() or "扫码登录" in page.content():
                 logger.error("❌ 检测到未登录状态 (在书籍页)")
                 push_notification("❌ 微信读书 Cookie 已失效，请重新运行 wxread_login.py")
                 return False
            
            logger.info("✅ 成功进入阅读页面")
            # page.screenshot(path="debug_entered_page.png")
            
            # 按时间控制阅读时长（确保至少达到目标时长）
            # 每次翻页间隔 8-15 秒，总时长 = READ_MINUTES * 60 秒
            total_seconds = READ_MINUTES * 60
            logger.info(f"⏱️ 开始阅读，目标时长：{READ_MINUTES} 分钟")
            
            start_time = time.time()
            flip_count = 0
            
            while True:
                elapsed = time.time() - start_time
                remaining = total_seconds - elapsed
                
                if remaining <= 0:
                    break
                
                # 模拟翻页（右箭头键）
                page.keyboard.press("ArrowRight")
                flip_count += 1
                
                # 随机等待时间（8-15秒）
                wait_time = random.uniform(8, 15)
                
                if flip_count % 10 == 0:
                    logger.info(f"📖 已阅读 {elapsed/60:.1f} 分钟，剩余 {remaining/60:.1f} 分钟")
                    # Debug: Take screenshot to verify reading state
                    try:
                        # 仅在调试时开启
                        # page.screenshot(path=f"debug_reading_{flip_count}.png")
                        pass
                    except:
                        pass
                
                page.wait_for_timeout(int(wait_time * 1000))
            
            elapsed_minutes = (time.time() - start_time) / 60
            logger.info(f"🎉 阅读完成！实际阅读时长：{elapsed_minutes:.1f} 分钟")
            
            # 保存更新后的状态
            context.storage_state(path=STATE_FILE)
            logger.info(f"💾 已保存更新后的登录状态")
            
            # 自动更新 GitHub Secret (Roll update to keep session fresh)
            try:
                with open(STATE_FILE, 'r') as f:
                    state_content = f.read()
                gh = GitHubAPI()
                gh.update_secret("WXREAD_STATE", state_content)
            except Exception as e:
                 logger.warning(f"⚠️ 自动更新 Secret 失败 (可能是本地运行或网络问题): {e}")

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
