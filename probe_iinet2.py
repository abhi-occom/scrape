"""Probe iinet wireless page — find plan card container and all plan data."""
from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page
import re

with sync_playwright() as p:
    browser = create_stealth_browser(p)
    page = create_stealth_page(browser)
    page.goto('https://www.iinet.net.au/internet-product/broadband/nbn/plans/wireless', timeout=40000, wait_until='domcontentloaded')
    page.wait_for_timeout(8000)

    # Find the plan selector element
    selectors = [
        'select[name*="plan"]',
        'select',
        '[data-testid*="plan"]',
        'option',
        '.plan-list',
        '[class*="plan-list"]',
        '[class*="planList"]',
        '[class*="plan-selector"]',
    ]
    for sel in selectors:
        els = page.query_selector_all(sel)
        if els:
            for i, el in enumerate(els[:3]):
                txt = el.inner_text().strip()
                if txt:
                    print(f'[{sel}] ({len(els)} total) [{i}]: {repr(txt[:200])}')

    # Get ALL text content related to plans
    body_text = page.evaluate('() => document.body.innerText')
    # Find sections containing NBN plan names
    plan_names = ['NBN25', 'NBN50', 'NBN100', 'NBN250', 'NBN500', 'NBN Superfast', 'NBN Ultrafast']
    for name in plan_names:
        idx = body_text.find(name)
        if idx >= 0:
            snippet = body_text[max(0, idx-20):idx+250]
            print(f'\n[PLAN: {name}]')
            print(repr(snippet))

    # Check for the select dropdown
    select_els = page.query_selector_all('select')
    print(f'\nSelect dropdowns: {len(select_els)}')
    for i, sel_el in enumerate(select_els):
        options = sel_el.query_selector_all('option')
        print(f'  Select {i}: {len(options)} options')
        for opt in options[:5]:
            print(f'    option: value={opt.get_attribute("value")!r} text={opt.inner_text().strip()!r}')

    browser.close()
    print('\nProbe 2 complete.')
