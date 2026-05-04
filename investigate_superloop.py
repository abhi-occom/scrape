"""Investigate Superloop nbn page structure for plan selectors."""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output', 'investigation')
os.makedirs(OUTPUT_DIR, exist_ok=True)

url = "https://www.superloop.com/internet/nbn/"

with sync_playwright() as p:
    browser = create_stealth_browser(p)
    page = create_stealth_page(browser)

    page.goto(url, timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)

    html = page.content()

    # Save HTML
    with open(os.path.join(OUTPUT_DIR, "superloop_nbn.html"), "w", encoding="utf-8") as f:
        f.write(html)

    # Save screenshot
    page.screenshot(path=os.path.join(OUTPUT_DIR, "superloop_nbn.png"), full_page=True)

    print(f"HTML length: {len(html)}")

    # Look for price patterns
    price_selectors = [
        '[class*="price"]', '[class*="Price"]',
        '[data-price]', '[data-plan-price]',
    ]
    for sel in price_selectors:
        elems = page.query_selector_all(sel)
        if elems:
            texts = [e.inner_text().strip()[:60] for e in elems[:8]]
            print(f"PRICE '{sel}' ({len(elems)}): {texts}")

    # Look for card containers
    card_selectors = [
        '[class*="plan"]', '[class*="Plan"]',
        '[class*="card"]', '[class*="Card"]',
        '[class*="product"]', '[class*="Product"]',
        '[class*="tile"]', '[class*="Tile"]',
    ]
    for sel in card_selectors:
        elems = page.query_selector_all(sel)
        if elems:
            info = []
            for e in elems[:4]:
                cls = e.get_attribute("class") or ""
                info.append(cls[:80])
            print(f"CARD '{sel}' ({len(elems)}): {info}")

    # Look for speed
    speed_selectors = [
        '[class*="speed"]', '[class*="Speed"]',
        '[class*="mbps"]', '[class*="Mbps"]',
    ]
    for sel in speed_selectors:
        elems = page.query_selector_all(sel)
        if elems:
            texts = [e.inner_text().strip()[:60] for e in elems[:8]]
            print(f"SPEED '{sel}' ({len(elems)}): {texts}")

    # Dollar amounts
    dollar_matches = re.findall(r'\$[\d,.]+(?:/\w+)?', html)
    unique_prices = list(dict.fromkeys(dollar_matches))[:20]
    print(f"Dollar amounts: {unique_prices}")

    # Headings
    headings = page.query_selector_all("h1, h2, h3, h4")
    h_texts = [h.inner_text().strip()[:80] for h in headings[:15]]
    print(f"Headings: {h_texts}")

    browser.close()
