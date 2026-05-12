"""
Final probe: determine what to do with each page.
- fibre: 8 .card elements (NBN + 5G + wireless)
- wireless: Angular address-lookup app, shows 1 plan card at a time (NBN25 by default)
- fibre_upgrade: informational page, find if it has any plan cards with pricing
"""
from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page
import re

with sync_playwright() as p:
    browser = create_stealth_browser(p)

    # ── Fibre page: full card data including spans breakdown ────────────
    print('=== FIBRE PAGE — All Cards ===')
    page = create_stealth_page(browser)
    page.goto('https://www.iinet.net.au/internet-product/broadband/nbn/plans/fibre', timeout=40000, wait_until='domcontentloaded')
    page.wait_for_timeout(7000)

    cards = page.query_selector_all('.card')
    print(f'Cards: {len(cards)}')
    for i, card in enumerate(cards):
        h3s = [h.inner_text().strip() for h in card.query_selector_all('h3')]
        spans = [s.inner_text().strip() for s in card.query_selector_all('span')]
        txt = card.inner_text().strip()
        print(f'\n--- Card {i} ---')
        print(f'h3s:   {h3s}')
        print(f'spans: {spans}')
        print(f'text:  {repr(txt)}')

    page.close()

    # ── Wireless page: what is the single displayed plan? ────────────────
    print('\n\n=== WIRELESS PAGE — Single Plan Display ===')
    page = create_stealth_page(browser)
    page.goto('https://www.iinet.net.au/internet-product/broadband/nbn/plans/wireless', timeout=40000, wait_until='domcontentloaded')
    page.wait_for_timeout(8000)

    # Full plan section text
    body = page.evaluate('() => document.body.innerText')
    idx = body.find('Select a plan')
    end = body.find('Do you need a modem?')
    plan_text = body[idx:end] if idx >= 0 and end >= 0 else body[idx:idx+500]
    print(f'Plan section:\n{repr(plan_text)}')
    page.close()

    # ── Fibre upgrade: confirm it is info-only ───────────────────────────
    print('\n\n=== FIBRE UPGRADE — Plan Pricing Check ===')
    page = create_stealth_page(browser)
    page.goto('https://www.iinet.net.au/internet-product/nbn/fibre-upgrade', timeout=40000, wait_until='domcontentloaded')
    page.wait_for_timeout(7000)

    body = page.evaluate('() => document.body.innerText')
    # Check for any pricing
    prices = re.findall(r'\$\d+\.?\d*\s*/mth', body)
    print(f'Price patterns: {prices}')
    # Check for NBN plan names
    nbn_plans = re.findall(r'NBN\d+|NBN \w+', body)
    print(f'NBN plan names: {nbn_plans}')

    # Check .card elements for plan pricing
    cards = page.query_selector_all('.card')
    for i, card in enumerate(cards):
        txt = card.inner_text().strip()
        h3s = [h.inner_text().strip() for h in card.query_selector_all('h3')]
        spans = [s.inner_text().strip() for s in card.query_selector_all('span')]
        if '$' in txt and 'mth' in txt.lower():
            print(f'\nCard {i} with pricing:')
            print(f'  h3s: {h3s}')
            print(f'  spans: {spans[:6]}')
            print(f'  text: {repr(txt[:300])}')

    page.close()
    browser.close()
    print('\nProbe 8 complete.')
