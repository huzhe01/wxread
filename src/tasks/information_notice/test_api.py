import requests
import json

def test_tencent_api():
    url = "https://careers.tencent.com/tencentcareer/api/post/Query"
    params = {
        "keyword": "算法",
        "pageIndex": 1,
        "pageSize": 10
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
        if data.get("Code") == 200:
             posts = data.get("Data", {}).get("Posts", [])
             if posts:
                 print(f"✅ API Works! Found {len(posts)} posts.")
                 print(f"First post Keys: {posts[0].keys()}")
                 print(f"First post Data: {json.dumps(posts[0], indent=2, ensure_ascii=False)}")
                 return True
    except Exception as e:
        print(f"❌ API Failed: {e}")
        return False

if __name__ == "__main__":
    test_tencent_api()
