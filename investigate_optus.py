"""Investigate Optus website structure at the new URL."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page

URL = "https://www.optus.com.au/internet/nbn"

with sync_playwright() as p:
    browser = create_stealth_browser(p)
    page = create_stealth_page(browser)

    print(f"Navigating to {URL} ...")
    try:
        resp = page.goto(URL, timeout=30000, wait_until="domcontentloaded")
        print(f"Status: {resp.status if resp else 'no response'}")
    except Exception as e:
        print(f"Navigation error: {e}")
        # Try continuing even on error
    
    page.wait_for_timeout(8000)  # Wait for JS rendering
    
    title = page.title()
    url = page.url
    print(f"Title: {title}")
    print(f"Final URL: {url}")
    
    html = page.content()
    print(f"HTML length: {len(html)}")
    
    # Save full HTML for analysis
    with open("output/optus_page.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Saved full HTML to output/optus_page.html")
    
    # Check for JSON-LD
    json_ld = page.query_selector_all('script[type="application/ld+json"]')
    print(f"\nJSON-LD scripts: {len(json_ld)}")
    for i, el in enumerate(json_ld):
        content = el.inner_text()[:500]
        print(f"  [{i}] {content}")
    
    # Check for common plan selectors
    selectors_to_try = [
        '[data-testid*="plan"]', '[data-testid*="Plan"]',
        '[class*="plan-card"]', '[class*="PlanCard"]', '[class*="planCard"]',
        '[class*="nbn-plan"]', '[class*="NbnPlan"]',
        '[data-component*="plan"]', '[data-component*="Plan"]',
        '.plan-card', '.broadband-plan',
        '[class*="ProductCard"]', '[class*="product-card"]',
        '[class*="speed-tier"]', '[class*="SpeedTier"]',
        '[class*="offer"]', '[class*="Offer"]',
        'article', '.card',
        '[class*="pricing"]', '[class*="Pricing"]',
    ]
    
    print("\n--- Selector probe ---")
    for sel in selectors_to_try:
        try:
            els = page.query_selector_all(sel)
            if els:
                print(f"  {sel}: {len(els)} matches")
                # Show first match's tag and class
                tag = els[0].evaluate("el => el.tagName")
                cls = els[0].evaluate("el => el.className")
                txt = els[0].inner_text()[:120].replace('\n', ' | ')
                print(f"    tag={tag} class={cls[:100]}")
                print(f"    text: {txt}")
        except:
            pass

    # Look for __NEXT_DATA__ or similar
    next_data = page.query_selector('script#__NEXT_DATA__')
    if next_data:
        content = next_data.inner_text()[:1000]
        print(f"\n__NEXT_DATA__ found: {content}")
    
    # Search for price patterns in HTML
    import re
    prices = re.findall(r'\$\d+(?:\.\d{2})?(?:/m(?:th|onth)?)?', html)
    unique_prices = sorted(set(prices))
    print(f"\nPrice patterns found: {unique_prices[:30]}")
    
    # Search for speed patterns
    speeds = re.findall(r'\b\d+\s*(?:Mbps|mbps|GB)', html)
    unique_speeds = sorted(set(speeds))
    print(f"Speed patterns found: {unique_speeds[:30]}")
    
    browser.close()
    print("\nDone.")
