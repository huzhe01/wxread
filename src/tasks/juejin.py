import os
import argparse
import logging
from playwright.sync_api import sync_playwright
from src.utils.push import push
from src.utils.github_api import GitHubAPI

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
JUEJIN_URL = "https://juejin.cn/"
CHECKIN_URL = "https://juejin.cn/user/center/signin?avatar_menu"
LOTTERY_URL = "https://juejin.cn/user/center/lottery?from=sign_in_success"
STATE_FILE = "juejin_state.json"
PUSH_METHOD = os.getenv('PUSH_METHOD')

def push_notification(content: str):
    """Send push notification"""
    if not PUSH_METHOD:
        logger.warning("⚠️ PUSH_METHOD not set, skipping notification")
        return
    try:
        push(content, PUSH_METHOD)
    except Exception as e:
        logger.error(f"❌ Failed to send notification: {e}")

def run_login():
    """Interactive login to save state"""
    logger.info("🚀 Starting login process...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        
        logger.info(f"🌐 Navigating to {JUEJIN_URL}")
        page.goto(JUEJIN_URL)
        
        logger.info("⏳ Please log in to Juejin in the browser...")
        
        try:
            # Wait for user to be logged in. 
            # A good indicator of login on Juejin is the avatar element or user menu
            # Selector for user avatar in top right: '.main-nav .avatar-wrapper' or similar
            # Since classes might change, maybe wait for cookie or URL change?
            # Juejin usually stays on same page or refreshes.
            # Let's verify by checking for specific element that only appears when logged in
            # e.g. "创作者中心" (Creator Center) text usually in header
            
            # User requested fixed wait time to manually complete login
            logger.info("⏳ Waiting 2 minutes for you to complete login manually...")
            page.wait_for_timeout(120000) # Wait 120 seconds
            logger.info("✅ Time up. Assuming login is complete.")
            
            page.wait_for_timeout(3000)
            context.storage_state(path=STATE_FILE)
            logger.info(f"💾 Login state saved to {STATE_FILE}")
            
        except Exception as e:
            logger.error(f"❌ Login timed out or failed: {e}")
        finally:
            browser.close()

def run_verify():
    """Verify saved login state"""
    logger.info("🔍 Verifying login state...")
    if not os.path.exists(STATE_FILE):
        logger.error(f"❌ State file {STATE_FILE} not found.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=STATE_FILE)
        page = context.new_page()
        
        logger.info(f"🌐 Navigating to {JUEJIN_URL}")
        page.goto(JUEJIN_URL)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(5000)
        
        # logic: if "登录" / "Login" related prompts are gone, or "Avatar" is present
        # User explicitly mentioned "登录掘金畅享更多权益" disappearing
        
        prompts = page.get_by_text("登录掘金畅享更多权益")
        if prompts.count() == 0 or not prompts.first.is_visible():
            logger.info("✅ '登录掘金畅享更多权益' is NOT visible. State appears VALID.")
        else:
            logger.warning("⚠️ '登录掘金畅享更多权益' is still visible. Login might have FAILED.")
            
        # Also check for positive indicator like Creator Center
        if page.get_by_text("创作者中心").is_visible():
             logger.info("✅ Found '创作者中心'. Confirmation: Logged in.")
        
        page.screenshot(path="juejin_verify.png")
        logger.info("📸 Screenshot saved to juejin_verify.png")
        
        browser.close()

def run_checkin():
    """Daily check-in and lottery"""
    logger.info("🚀 Starting check-in process...")
    
    if not os.path.exists(STATE_FILE):
        logger.error(f"❌ State file {STATE_FILE} not found. Please run login first.")
        return False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state=STATE_FILE,
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        
        checkin_msg = "Check-in: Not attempted"
        lottery_msg = "Lottery: Not attempted"
        
        try:
            # --- Step 1: Check-in ---
            logger.info(f"🌐 Navigating to Check-in page: {CHECKIN_URL}")
            page.goto(CHECKIN_URL)
            page.wait_for_load_state("networkidle")
            
            # Look for "今日签到" button. 
            # Based on user image, it's a big button "今日已签到" (Signed in) or "立即签到" (Sign in now)
            # The button text likely contains "签到"
            
            try:
                # Try finding the button
                # Be careful not to click "已签到" (Already signed in)
                # Usually class contains 'signin' and 'btn'
                # Let's look for text "立即签到" (Sign in immediately) or just "签到" inside a button
                signin_btn = page.get_by_text("今日签到", exact=True).or_(page.get_by_text("立即签到"))
                
                if signin_btn.count() > 0 and signin_btn.first.is_visible():
                     signin_btn.first.click()
                     page.wait_for_timeout(2000)
                     checkin_msg = "✅ Juejin Check-in Successful"
                     logger.info(checkin_msg)
                elif page.get_by_text("已签到").count() > 0:
                     checkin_msg = "ℹ️ Juejin Already Checked In"
                     logger.info(checkin_msg)
                else:
                     checkin_msg = "⚠️ Juejin Check-in Button Not Found"
                     logger.warning(checkin_msg)
                     # page.screenshot(path="debug_checkin.png")
            except Exception as e:
                checkin_msg = f"❌ Juejin Check-in Error: {str(e)}"
                logger.error(checkin_msg)

            # --- Step 2: Lottery ---
            logger.info(f"🌐 Navigating to Lottery page: {LOTTERY_URL}")
            page.goto(LOTTERY_URL)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)
            
            try:
                # Look for "免费抽奖" (Free Draw) or "单抽" (Single Draw) if free?
                # Usually there is a "免费抽奖" text if available.
                # If used up, it might accept ores (kost). User specifically said "Free Draw".
                free_draw_btn = page.get_by_text("免费抽奖")
                
                if free_draw_btn.count() > 0 and free_draw_btn.first.is_visible():
                    free_draw_btn.first.click()
                    page.wait_for_timeout(3000)
                    lottery_msg = "✅ Juejin Free Lottery Drawn"
                    logger.info(lottery_msg)
                else:
                    lottery_msg = "ℹ️ No Free Lottery Available"
                    logger.info(lottery_msg)
            except Exception as e:
                lottery_msg = f"❌ Juejin Lottery Error: {str(e)}"
                logger.error(lottery_msg)

            # Update Secret and Notify
            context.storage_state(path=STATE_FILE)
            with open(STATE_FILE, 'r') as f:
                state_content = f.read()
            
            gh = GitHubAPI()
            gh.update_secret("JUEJIN_STATE", state_content)
            
            push_notification(f"{checkin_msg}\n{lottery_msg}")
            
        except Exception as e:
            logger.error(f"❌ Script failed: {e}")
            push_notification(f"❌ Juejin Script Failed: {e}")
        finally:
            browser.close()

def main():
    parser = argparse.ArgumentParser(description="Juejin Automation")
    parser.add_argument("action", choices=["login", "checkin", "verify"], help="Action to perform")
    args = parser.parse_args()
    
    if args.action == "login":
        run_login()
    elif args.action == "checkin":
        run_checkin()
    elif args.action == "verify":
        run_verify()

if __name__ == "__main__":
    main()
