"""Test stealth mode against all ISP sites."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output', 'stealth_test')
os.makedirs(OUTPUT_DIR, exist_ok=True)

SITES = {
    'superloop': 'https://www.superloop.com/internet/nbn/',
    'aussie': 'https://www.aussiebroadband.com.au/nbn-plans/',
    'optus': 'https://www.optus.com.au/broadband/nbn',
}

with sync_playwright() as p:
    browser = create_stealth_browser(p)
    
    for name, url in SITES.items():
        print(f"\n{'='*50}")
        print(f"Testing: {name} ({url})")
        page = create_stealth_page(browser)
        
        try:
            response = page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            
            status = response.status if response else 0
            html = page.content()
            title_elem = page.query_selector('title')
            title = title_elem.inner_text() if title_elem else 'N/A'
            
            # Check for Cloudflare challenge
            is_cloudflare = 'Just a moment' in title or 'challenge-platform' in html[:5000]
            
            print(f"  Status: {status}")
            print(f"  Title: {title}")
            print(f"  HTML length: {len(html)}")
            print(f"  Cloudflare block: {is_cloudflare}")
            
            # Save screenshot
            screenshot_path = os.path.join(OUTPUT_DIR, f"{name}.png")
            page.screenshot(path=screenshot_path, full_page=False)
            print(f"  Screenshot: {screenshot_path}")
            
            # Save HTML
            html_path = os.path.join(OUTPUT_DIR, f"{name}.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html)
                
            if status == 200 and not is_cloudflare:
                print(f"  ✅ SUCCESS")
            else:
                print(f"  ❌ BLOCKED")
                
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
        finally:
            page.close()
    
    browser.close()

print("\nDone!")
