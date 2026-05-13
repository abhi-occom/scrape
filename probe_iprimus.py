"""
Deep probe of iprimus.com.au/nbn-plans to understand plan_tile DOM structure.
"""
import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright

URL = 'https://www.iprimus.com.au/nbn-plans'

SUB_SELECTORS = [
    '.plan_tile__heading',
    '.plan_tile__price',
    '.plan_tile__price--discount',
    '.plan_tile__upgrade__title',
    '.plan_tile__footer__text',
    '[class*="speed"]',
    '[class*="connection"]',
    '.plan_tile__header',
]

with sync_playwright() as p:
    browser = create_stealth_browser(p)
    page = create_stealth_page(browser)
    page.goto(URL, timeout=30000, wait_until='domcontentloaded')
    page.wait_for_timeout(6000)

    cards = page.query_selector_all('.plan_tile')
    print(f'plan_tile cards found: {len(cards)}')

    for i, card in enumerate(cards):
        print(f'\n{"="*60}')
        print(f'CARD {i}')
        print('='*60)
        full_text = card.inner_text()
        print('FULL TEXT:')
        print(repr(full_text[:800]))
        print()
        for sel in SUB_SELECTORS:
            try:
                els = card.query_selector_all(sel)
                if els:
                    for j, el in enumerate(els):
                        txt = el.inner_text().strip()
                        cls = el.get_attribute('class') or ''
                        print(f'  [{sel}][{j}] class="{cls}" => {repr(txt[:150])}')
            except Exception as e:
                print(f'  [{sel}] ERROR: {e}')

    # Also check the HTML of first card
    if cards:
        print('\n\n=== FIRST CARD OUTER HTML ===')
        html = cards[0].evaluate('el => el.outerHTML')
        print(html[:3000])

    browser.close()
