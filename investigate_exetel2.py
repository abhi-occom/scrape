"""Detailed inspection of Exetel PlanCard structure."""
from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page

with sync_playwright() as p:
    browser = create_stealth_browser(p)
    page = create_stealth_page(browser)
    page.goto('https://www.exetel.com.au/broadband/nbn', timeout=40000, wait_until='domcontentloaded')
    page.wait_for_timeout(6000)

    cards = page.query_selector_all('[class*="PlanCard"]')
    print(f'Total PlanCard elements: {len(cards)}')

    sub_selectors = [
        '[class*="price"]', '[class*="Price"]',
        '[class*="speed"]', '[class*="Speed"]',
        '[class*="name"]',  '[class*="Name"]',
        '[class*="download"]', '[class*="upload"]',
        '[class*="Download"]', '[class*="Upload"]',
        'h2', 'h3', 'h4', 'strong', 'span',
    ]

    for i, card in enumerate(cards[:5]):
        print(f'\n=== Card {i} ===')
        cls = card.get_attribute('class') or ''
        print(f'class: {cls[:120]}')
        text = card.inner_text().strip()[:300]
        print(f'text: {repr(text)}')

        for sel in sub_selectors:
            try:
                els = card.query_selector_all(sel)
                if els:
                    txts = [e.inner_text().strip()[:60] for e in els[:3]]
                    print(f'  {sel} ({len(els)}): {txts}')
            except Exception:
                pass

    browser.close()
    print('\nDone.')
