"""Probe iinet page structure to find embedded JSON and plan selectors."""
from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page
import re
import json
import html as html_module

PAGES = {
    'fibre': 'https://www.iinet.net.au/internet-product/broadband/nbn/plans/fibre',
    'wireless': 'https://www.iinet.net.au/internet-product/broadband/nbn/plans/wireless',
    'fibre_upgrade': 'https://www.iinet.net.au/internet-product/nbn/fibre-upgrade',
}

with sync_playwright() as p:
    browser = create_stealth_browser(p)

    for key, url in PAGES.items():
        print(f'\n{"="*70}')
        print(f'PAGE: {key}')
        print('='*70)
        page = create_stealth_page(browser)
        try:
            page.goto(url, timeout=40000, wait_until='domcontentloaded')
            page.wait_for_timeout(7000)

            raw_html = page.evaluate('() => document.body.innerHTML')
            decoded = html_module.unescape(raw_html)

            # 1) Look for embedded plans JSON blob
            m = re.search(r'"plans"\s*:\s*(\[.+?\])\s*,\s*"pageType"', decoded, re.DOTALL)
            if m:
                try:
                    plans_data = json.loads(m.group(1))
                    print(f'[JSON] Found {len(plans_data)} plans in embedded JSON')
                    for plan in plans_data[:2]:
                        print(json.dumps(plan, indent=2)[:800])
                        print('---')
                except Exception as e:
                    print(f'[JSON] Parse error: {e}')
                    print('Raw:', repr(m.group(1)[:300]))
            else:
                print('[JSON] No embedded plans JSON found')

            # 2) Look in <script> tags for plan data
            scripts = page.query_selector_all('script')
            for i, s in enumerate(scripts):
                txt = s.inner_text()
                if 'monthlyCost' in txt and len(txt) > 100:
                    print(f'[SCRIPT {i}] Contains monthlyCost — length {len(txt)}')
                    m2 = re.search(r'"monthlyCost"\s*:\s*([\d.]+)', txt)
                    if m2:
                        print(f'  Sample monthlyCost: {m2.group(1)}')
                    # Try to find whole plan object
                    m3 = re.search(r'(\{[^{}]*"monthlyCost"[^{}]*\})', txt)
                    if m3:
                        print(f'  Plan object: {repr(m3.group(1)[:400])}')

            # 3) On fibre page — re-confirm .card selector structure
            if key == 'fibre':
                cards = page.query_selector_all('.card')
                print(f'\n[CARDS] .card count: {len(cards)}')
                for i, card in enumerate(cards):
                    text = card.inner_text().strip()
                    if 'NBN' in text or '5G' in text or 'Wireless' in text:
                        h3s = [h.inner_text().strip() for h in card.query_selector_all('h3')]
                        spans = [s.inner_text().strip() for s in card.query_selector_all('span')]
                        print(f'\nCard {i}:')
                        print(f'  h3s: {h3s}')
                        print(f'  spans: {spans}')
                        print(f'  text: {repr(text[:200])}')

        except Exception as e:
            print(f'[ERROR] {e}')
        finally:
            page.close()

    browser.close()
    print('\nProbe complete.')
