"""Try multiple approaches to access Optus website."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page

URL = "https://www.optus.com.au/internet/nbn"

# ── Approach 1: Firefox (not Chromium) ──────────────────────────
print("=" * 60)
print("Approach 1: Firefox browser")
print("=" * 60)
try:
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
            viewport={"width": 1280, "height": 720},
            locale="en-AU",
        )
        page = context.new_page()
        resp = page.goto(URL, timeout=30000, wait_until="domcontentloaded")
        print(f"Status: {resp.status if resp else 'none'}")
        page.wait_for_timeout(5000)
        title = page.title()
        print(f"Title: {title}")
        print(f"Final URL: {page.url}")
        html = page.content()
        print(f"HTML length: {len(html)}")
        if len(html) > 500:
            with open("output/optus_firefox.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("Saved HTML to output/optus_firefox.html")
        browser.close()
except Exception as e:
    print(f"Firefox error: {e}")

# ── Approach 2: WebKit (Safari-like) ────────────────────────────
print("\n" + "=" * 60)
print("Approach 2: WebKit browser")
print("=" * 60)
try:
    with sync_playwright() as p:
        browser = p.webkit.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
            viewport={"width": 1280, "height": 720},
            locale="en-AU",
        )
        page = context.new_page()
        resp = page.goto(URL, timeout=30000, wait_until="domcontentloaded")
        print(f"Status: {resp.status if resp else 'none'}")
        page.wait_for_timeout(5000)
        title = page.title()
        print(f"Title: {title}")
        print(f"Final URL: {page.url}")
        html = page.content()
        print(f"HTML length: {len(html)}")
        if len(html) > 500:
            with open("output/optus_webkit.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("Saved HTML to output/optus_webkit.html")
        browser.close()
except Exception as e:
    print(f"WebKit error: {e}")

# ── Approach 3: Chromium with HTTP/1.1 forced ───────────────────
print("\n" + "=" * 60)
print("Approach 3: Chromium with HTTP/1.1")
print("=" * 60)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-http2",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        page = create_stealth_page(browser)
        resp = page.goto(URL, timeout=30000, wait_until="domcontentloaded")
        print(f"Status: {resp.status if resp else 'none'}")
        page.wait_for_timeout(5000)
        title = page.title()
        print(f"Title: {title}")
        print(f"Final URL: {page.url}")
        html = page.content()
        print(f"HTML length: {len(html)}")
        if len(html) > 500:
            with open("output/optus_http1.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("Saved HTML to output/optus_http1.html")
        browser.close()
except Exception as e:
    print(f"HTTP/1.1 error: {e}")

# ── Approach 4: requests library (no browser) ──────────────────
print("\n" + "=" * 60)
print("Approach 4: Python requests (no browser)")
print("=" * 60)
try:
    import requests
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-AU,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
    }
    resp = requests.get(URL, headers=headers, timeout=30, allow_redirects=True)
    print(f"Status: {resp.status_code}")
    print(f"Final URL: {resp.url}")
    print(f"HTML length: {len(resp.text)}")
    if resp.status_code == 200 and len(resp.text) > 500:
        with open("output/optus_requests.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
        print("Saved HTML to output/optus_requests.html")
except Exception as e:
    print(f"Requests error: {e}")

# ── Approach 5: Try Google cached version ───────────────────────
print("\n" + "=" * 60)
print("Approach 5: Fetch via web cache / alternative URLs")
print("=" * 60)
alt_urls = [
    "https://www.optus.com.au/broadband/nbn",
    "https://www.optus.com.au/internet",
    "https://www.optus.com.au/internet/home-internet",
]
try:
    import requests
    for alt_url in alt_urls:
        try:
            resp = requests.get(alt_url, headers=headers, timeout=15, allow_redirects=True)
            print(f"  {alt_url} -> {resp.status_code} (len={len(resp.text)})")
        except Exception as e:
            print(f"  {alt_url} -> ERROR: {e}")
except Exception as e:
    print(f"Alt URL error: {e}")

print("\nDone.")
