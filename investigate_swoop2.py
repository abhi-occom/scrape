"""
Deep-dive: dump ALL 4 card--plan elements for each page,
and understand the full inner text / HTML structure.
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright

URLS = {
    'nbn': 'https://www.swoop.com.au/nbn/',
    'fixed_wireless': 'https://www.swoop.com.au/fixed-wireless/',
    'opticomm': 'https://www.swoop.com.au/opticomm/',
}

def investigate(url, label):
    print(f"\n{'='*60}")
    print(f"{label} — {url}")
    print('='*60)
    with sync_playwright() as p:
        browser = create_stealth_browser(p)
        page = create_stealth_page(browser)
        page.goto(url, timeout=30000, wait_until='domcontentloaded')
        page.wait_for_timeout(5000)

        cards = page.query_selector_all('.card--plan')
        print(f"  card--plan count: {len(cards)}")
        for i, card in enumerate(cards):
            txt = card.inner_text().strip()
            html = card.inner_html()
            print(f"\n  --- Card {i} ---")
            print(f"  TEXT: {repr(txt[:500])}")

            # Try specific sub-elements
            heading = card.query_selector('.heading, h1, h2, h3, h4, h5')
            subheading = card.query_selector('.subheading')
            price_els = card.query_selector_all('.price span, .card__price span')
            coupon = card.query_selector('.coupon')
            speeds = card.query_selector_all('.card__speeds .speed-value, .speed-number, [class*="speed"]')

            print(f"  heading: {repr(heading.inner_text().strip()) if heading else None}")
            print(f"  subheading: {repr(subheading.inner_text().strip()) if subheading else None}")
            print(f"  price spans: {[s.inner_text().strip() for s in price_els]}")
            print(f"  coupon: {repr(coupon.inner_text().strip()) if coupon else None}")
            print(f"  speed elements: {[s.inner_text().strip() for s in speeds]}")

        # Also check if there are more cards in a carousel or hidden
        all_cards = page.query_selector_all('[class*="card"]')
        plan_cards = [c for c in all_cards if 'plan' in (c.get_attribute('class') or '')]
        print(f"\n  All cards with 'plan' in class: {len(plan_cards)}")

        browser.close()

if __name__ == '__main__':
    for label, url in URLS.items():
        investigate(url, label)
