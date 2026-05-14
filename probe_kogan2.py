"""Probe each .planItem card's full text structure."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright

URL = 'https://www.koganinternet.com.au/plans/'

with sync_playwright() as p:
    browser = create_stealth_browser(p)
    page = create_stealth_page(browser)
    page.goto(URL, timeout=40000, wait_until='domcontentloaded')
    page.wait_for_timeout(8000)

    cards = page.query_selector_all('.planItem')
    print(f'Found {len(cards)} .planItem cards\n')

    for i, card in enumerate(cards):
        txt = (card.evaluate('el => el.innerText') or '').strip()
        lines = [l.strip() for l in txt.split('\n') if l.strip()]
        print(f'=== CARD {i} ===')
        for j, l in enumerate(lines):
            print(f'  [{j:2d}] {repr(l)}')
        print()

    # Also get outerHTML of first card for selector intelligence
    print('=== outerHTML of CARD 0 (first 3000 chars) ===')
    html0 = cards[0].evaluate('el => el.outerHTML')
    print(html0[:3000])

    browser.close()
    print('\n[Done]')
