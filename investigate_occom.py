"""Investigate Occom nbn page structure for plan selectors."""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output', 'investigation')
os.makedirs(OUTPUT_DIR, exist_ok=True)

url = "https://staging.occominternet.com/nbn-plans/"

with sync_playwright() as p:
    browser = create_stealth_browser(p)
    page = create_stealth_page(browser)

    response = page.goto(url, timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)

    html = page.content()
    status = response.status if response else 0
    title_elem = page.query_selector('title')
    title = title_elem.inner_text() if title_elem else 'N/A'

    print(f"Status: {status}")
    print(f"Title: {title}")
    print(f"HTML length: {len(html)}")

    # Save HTML + screenshot
    with open(os.path.join(OUTPUT_DIR, "occom.html"), "w", encoding="utf-8") as f:
        f.write(html)
    page.screenshot(path=os.path.join(OUTPUT_DIR, "occom.png"), full_page=True)
    print(f"Saved HTML and screenshot")

    # Check for JSON-LD
    scripts = page.query_selector_all('script[type="application/ld+json"]')
    print(f"\nJSON-LD scripts: {len(scripts)}")
    for i, s in enumerate(scripts):
        text = s.inner_text()[:500]
        print(f"  LD+JSON {i}: {text[:200]}...")

    # Price patterns
    price_selectors = [
        '[class*="price"]', '[class*="Price"]',
        '[data-price]', '[data-plan-price]',
    ]
    for sel in price_selectors:
        elems = page.query_selector_all(sel)
        if elems:
            texts = [e.inner_text().strip()[:60] for e in elems[:8]]
            print(f"\nPRICE '{sel}' ({len(elems)}): {texts}")

    # Card containers
    card_selectors = [
        '[class*="plan"]', '[class*="Plan"]',
        '[class*="card"]', '[class*="Card"]',
        '[class*="product"]', '[class*="Product"]',
        '[class*="tile"]', '[class*="Tile"]',
        '[class*="package"]', '[class*="Package"]',
    ]
    for sel in card_selectors:
        elems = page.query_selector_all(sel)
        if elems:
            info = []
            for e in elems[:4]:
                cls = e.get_attribute("class") or ""
                info.append(cls[:80])
            print(f"\nCARD '{sel}' ({len(elems)}): {info}")

    # Speed patterns
    speed_selectors = [
        '[class*="speed"]', '[class*="Speed"]',
        '[class*="mbps"]', '[class*="Mbps"]',
    ]
    for sel in speed_selectors:
        elems = page.query_selector_all(sel)
        if elems:
            texts = [e.inner_text().strip()[:60] for e in elems[:8]]
            print(f"\nSPEED '{sel}' ({len(elems)}): {texts}")

    # Dollar amounts
    dollar_matches = re.findall(r'\$[\d,.]+(?:/\w+)?', html)
    unique_prices = list(dict.fromkeys(dollar_matches))[:20]
    print(f"\nDollar amounts: {unique_prices}")

    # Headings
    headings = page.query_selector_all("h1, h2, h3, h4")
    h_texts = [h.inner_text().strip()[:80] for h in headings[:20]]
    print(f"\nHeadings: {h_texts}")

    browser.close()
