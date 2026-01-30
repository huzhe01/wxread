from playwright.sync_api import sync_playwright

def intercept_api():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Log all requests
        page.on("request", lambda request: print(f">> {request.method} {request.url}") if "api" in request.url else None)
        
        # Go to a detail page
        url = "http://careers.tencent.com/jobdesc.html?postId=1976557865858650112"
        print(f"Navigating to {url}")
        page.goto(url)
        page.wait_for_timeout(5000)
        
        browser.close()

if __name__ == "__main__":
    intercept_api()
