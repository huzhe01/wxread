import os
import json
import time
import argparse
import logging
import base64
import requests
from playwright.sync_api import sync_playwright
from nacl import encoding, public

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
AIXINWU_URL = "https://aixinwu.sjtu.edu.cn/"
STATE_FILE = "aixinwu_state.json"
GITHUB_TOKEN = os.getenv('GH_PAT')
GITHUB_REPOSITORY = os.getenv('GITHUB_REPOSITORY')
PUSH_METHOD = os.getenv('PUSH_METHOD')

def push_notification(content: str):
    """Send push notification"""
    if not PUSH_METHOD:
        logger.warning("⚠️ PUSH_METHOD not set, skipping notification")
        return
    
    try:
        from push import push
        push(content, PUSH_METHOD)
    except Exception as e:
        logger.error(f"❌ Failed to send notification: {e}")

def encrypt_secret(public_key: str, secret_value: str) -> str:
    """Encrypt secret value using GitHub public key"""
    public_key_bytes = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key_bytes)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")

def update_github_secret(secret_name: str, secret_value: str):
    """Update GitHub Actions Secret"""
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        logger.warning("⚠️ GH_PAT or GITHUB_REPOSITORY not set, skipping secret update")
        return False
    
    try:
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        # Get public key
        key_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/secrets/public-key"
        key_response = requests.get(key_url, headers=headers)
        key_response.raise_for_status()
        key_data = key_response.json()
        
        # Encrypt value
        encrypted_value = encrypt_secret(key_data["key"], secret_value)
        
        # Update secret
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
        logger.info(f"✅ Successfully updated GitHub Secret: {secret_name}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to update GitHub Secret: {e}")
        return False

def run_login():
    """Interactive login to save state"""
    logger.info("🚀 Starting login process...")
    with sync_playwright() as p:
        # Launch headed browser for user interaction
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        
        logger.info(f"🌐 Navigating to {AIXINWU_URL}")
        page.goto(AIXINWU_URL)
        
        # Give some time for redirects to happen (e.g. valid session -> home, or invalid -> jaccount)
        page.wait_for_timeout(3000)
        
        if "jaccount" in page.url:
            logger.info("🔒 Redirected to JAccount login page.")
            logger.info("⏳ Please log in via JAccount in the browser...")
            
            # Wait until we are redirected back to aixinwu AND not on jaccount anymore
            try:
                # Wait indefinitely (or long timeout) for the user to complete login
                page.wait_for_url(lambda url: "aixinwu.sjtu.edu.cn" in url and "jaccount" not in url, timeout=300000)
                logger.info("✅ Login successful! Detected return to Aixinwu.")
            except Exception as e:
                logger.error(f"❌ Login timed out: {e}")
                return
        else:
            logger.info("ℹ️ Already on Aixinwu domain (or no redirect detected).")
            # Maybe already logged in, or user needs to click login manually
            logger.info("⏳ If you see the login button, please click it. Script will wait for 10 seconds to confirm state.")
            page.wait_for_timeout(50000)

        # Final verification: Check if we are really on Aixinwu
        if "aixinwu.sjtu.edu.cn" in page.url:
             # Wait a bit more to ensure cookies are set
            page.wait_for_timeout(3000)
            context.storage_state(path=STATE_FILE)
            logger.info(f"💾 Login state saved to {STATE_FILE}")
        else:
            logger.warning(f"⚠️ Current URL is {page.url}, might not be correct.")

        browser.close()

def run_verify():
    """Verify if saved state works"""
    logger.info("🔍 Verifying saved login state...")
    if not os.path.exists(STATE_FILE):
        logger.error(f"❌ State file {STATE_FILE} not found.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # Use headed to see what happens
        context = browser.new_context(storage_state=STATE_FILE)
        page = context.new_page()
        
        logger.info(f"🌐 Navigating to {AIXINWU_URL}")
        page.goto(AIXINWU_URL)
        page.wait_for_timeout(10000) # Wait for redirects
        
        if "jaccount" in page.url:
             logger.error("❌ Redirected to JAccount! Login state is INVALID or EXPIRED.")
        else:
             logger.info(f"✅ Stayed on {page.url}. Login state appears VALID.")
             # Optionally check for a 'Logout' button or user name if we knew the selector
        
        logger.info("Taking screenshot to 'verify_state.png'...")
        page.screenshot(path="verify_state.png")
        page.wait_for_timeout(1000) # give usage chance to see
        browser.close()

def run_checkin():
    """Daily check-in using saved state"""
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
        
        try:
            logger.info(f"🌐 Navigating to {AIXINWU_URL}")
            page.goto(AIXINWU_URL)
            page.wait_for_load_state("networkidle")
            
            # Take screenshot for debug
            # page.screenshot(path="debug_home.png")
            
            # Check if logged in (look for login button or user profile)
            # User confirmed that just visiting the page is enough for check-in
            if "jaccount" in page.url:
                logger.error("❌ Redirected to JAccount! Login state is INVALID or EXPIRED.")
                push_notification("❌ SJTU Aixinwu Check-in Failed: Login Expired")
            else:
                logger.info("✅ Successfully visited Aixinwu. Check-in should be complete.")
                push_notification("✅ SJTU Aixinwu Login/Check-in Successful")

            # Save updated state (keep session alive)
            context.storage_state(path=STATE_FILE)
            
            # Update GitHub Secret
            with open(STATE_FILE, 'r') as f:
                state_content = f.read()
            update_github_secret("AIXINWU_STATE", state_content)
            
        except Exception as e:
            logger.error(f"❌ Check-in failed: {e}")
            push_notification(f"❌ SJTU Aixinwu Check-in Failed: {e}")
        finally:
            browser.close()

def main():
    parser = argparse.ArgumentParser(description="SJTU Aixinwu Automation")
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
