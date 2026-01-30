import requests
import json

def test_detail_api(post_id):
    url = "https://careers.tencent.com/tencentcareer/api/post/GetByPostId"
    params = {
        "postId": post_id,
        "timestamp": 123456789 # Sometimes needed
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
             post = data.get("Data", {})
             if post:
                 print("✅ Detail API Works!")
                 print(f"Responsibility: {post.get('Responsibility')[:50]}...")
                 return True
    except Exception as e:
        print(f"❌ API Failed: {e}")
        return False

if __name__ == "__main__":
    # Use the PostId from previous step: 1976557865858650112
    test_detail_api("1976557865858650112")
