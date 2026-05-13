"""
Deep probe of iprimus.com.au/nbn-plans to extract tiq-data, connection types, and speeds per card.
"""
import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright

URL = 'https://www.iprimus.com.au/nbn-plans'

# Known speed mapping by plan name (from NBN standards)
SPEED_MAP = {
    # NBN
    'nbn standard':        (25,  5),
    'nbn standard plus':   (50,  17),
    'nbn premium':         (100, 17),
    'nbn premium plus':    (500, 47),
    'nbn home superfast':  (700, 49),
    'nbn home ultrafast':  (840, 94),
    # Fixed Wireless
    'fixed wireless standard': (25, 5),
    'fixed wireless plus':     (50, 17),
    # Fibre (Opticomm/iprimus fibre)
    'fibre standard':           (50,  17),
    'fibre standard plus':      (100, 17),
    'fibre premium':            (500, 47),
    'fibre home superfast':     (700, 49),
    'fibre home ultrafast':     (840, 94),
}

with sync_playwright() as p:
    browser = create_stealth_browser(p)
    page = create_stealth_page(browser)
    page.goto(URL, timeout=30000, wait_until='domcontentloaded')
    page.wait_for_timeout(6000)

    cards = page.query_selector_all('.plan_tile')
    print(f'Total .plan_tile cards: {len(cards)}')
    print()

    for i, card in enumerate(cards):
        tiq = card.get_attribute('tiq-data') or ''
        cls = card.get_attribute('class') or ''

        # Plan heading
        heading_el = card.query_selector('.plan_tile__heading')
        heading = heading_el.inner_text().strip() if heading_el else 'N/A'

        # Price (current)
        price_el = card.query_selector('.plan_tile__price')
        price_raw = price_el.inner_text().strip() if price_el else ''
        price_match = re.search(r'\$([\d]+(?:\.\d+)?)', price_raw)
        price = float(price_match.group(1)) if price_match else None

        # Discount / was price
        disc_el = card.query_selector('.plan_tile__price--discount')
        disc_raw = disc_el.inner_text().strip() if disc_el else ''
        disc_match = re.search(r'\$([\d]+(?:\.\d+)?)', disc_raw)
        was_price = float(disc_match.group(1)) if disc_match else None
        # filter out '0' placeholder
        if disc_raw in ('', '0'):
            was_price = None

        # Speed text
        speed_el = card.query_selector('.plan_tile__content__speed__text')
        speed_text = speed_el.inner_text().strip() if speed_el else ''

        # Upgrade promo text
        promo_el = card.query_selector('.plan_tile__upgrade__title')
        promo_text = promo_el.inner_text().strip() if promo_el else ''

        # Connection types
        tech_el = card.query_selector('.plan_tile__tech--type')
        tech_text = tech_el.inner_text().strip() if tech_el else ''

        print(f"[{i:02d}] heading={repr(heading)}")
        print(f"       price={price}  was_price={was_price}  promo={repr(promo_text)}")
        print(f"       speed_text={repr(speed_text)}")
        print(f"       tiq={repr(tiq)}")
        print(f"       class_snippet={repr(cls[:80])}")
        print()

    browser.close()
