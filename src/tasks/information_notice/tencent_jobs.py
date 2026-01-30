import os
import time
import json
import csv
import logging
import requests
from datetime import datetime
from src.utils.push import push

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Config
KEYWORD = "算法"
MAX_PAGES = 20
OUTPUT_DIR = "information_notice"
PUSH_METHOD = os.getenv('PUSH_METHOD')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://careers.tencent.com/search.html"
}

def get_job_list(page_index):
    """Fetch job list for a specific page"""
    url = "https://careers.tencent.com/tencentcareer/api/post/Query"
    params = {
        "timestamp": int(time.time() * 1000),
        "keyword": KEYWORD,
        "pageIndex": page_index,
        "pageSize": 10
    }
    
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("Code") == 200:
            return data.get("Data", {}).get("Posts", [])
        else:
            logger.error(f"❌ List API Error: {data.get('Code')} - {data.get('Message')}")
            return []
    except Exception as e:
        logger.error(f"❌ Failed to fetch list page {page_index}: {e}")
        return []

def get_job_detail(post_id):
    """Fetch job details including Requirement"""
    url = "https://careers.tencent.com/tencentcareer/api/post/ByPostId"
    params = {
        "timestamp": int(time.time() * 1000),
        "postId": post_id,
        "language": "zh-cn"
    }
    
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("Code") == 200:
            return data.get("Data", {})
        return {}
    except Exception as e:
        logger.error(f"❌ Failed to fetch detail for {post_id}: {e}")
        return {}

def run_scraper():
    logger.info(f"🚀 Starting Tencent Jobs Scraper for '{KEYWORD}'...")
    
    all_jobs = []
    
    for page in range(1, MAX_PAGES + 1):
        logger.info(f"📄 Fetching page {page}/{MAX_PAGES}...")
        posts = get_job_list(page)
        
        if not posts:
            logger.warning(f"⚠️ No posts found on page {page}. Stopping.")
            break
            
        for post in posts:
            post_id = post.get("PostId")
            title = post.get("RecruitPostName")
            
            # Fetch detail
            # logger.info(f"  🔍 Fetching details for {title} ({post_id})...")
            detail = get_job_detail(post_id)
            
            job_data = {
                "Title": title,
                "Values": post.get("Values"), # ??? Maybe Location? List has 'LocationName'
                "Location": post.get("LocationName"),
                "UpdateDate": post.get("LastUpdateTime"),
                "Link": post.get("PostURL"),
                "Responsibility": post.get("Responsibility", "").replace('\r', '').replace('\n', ' '),
                "Requirement": detail.get("Requirement", "").replace('\r', '').replace('\n', ' ')
            }
            all_jobs.append(job_data)
            
            # Be nice to API
            time.sleep(0.2)
        
        # Be nice between pages
        time.sleep(1)

    # Save to CSV
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    date_str = datetime.now().strftime("%Y%m%d")
    filename = os.path.join(OUTPUT_DIR, f"tencent_jobs_{date_str}.csv")
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = ["Title", "Location", "UpdateDate", "Link", "Responsibility", "Requirement"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
            
            writer.writeheader()
            for job in all_jobs:
                writer.writerow(job)
                
        logger.info(f"✅ Saved {len(all_jobs)} jobs to {filename}")
        
        # Notification
        if PUSH_METHOD:
            push(f"✅ Tencent Jobs Scraper Finished.\nSaved {len(all_jobs)} jobs to {filename}", PUSH_METHOD)
            
    except Exception as e:
        logger.error(f"❌ Failed to save CSV: {e}")

if __name__ == "__main__":
    run_scraper()
