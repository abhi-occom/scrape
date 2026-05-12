"""
Find actual plan data on wireless page (Angular app rendering plans)
and look for embedded plan data in script tags across all iinet pages.
"""
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
            page.wait_for_timeout(8000)

            # Search all script tags for plan data
            scripts = page.query_selector_all('script')
            print(f'Script tags: {len(scripts)}')
            for i, s in enumerate(scripts):
                src = s.get_attribute('src') or ''
                txt = s.inner_text()
                # Look for plan/price data embedded inline
                if txt and ('monthlyCost' in txt or 'planName' in txt or 'speedDescription' in txt
                            or 'NBN25' in txt or 'NBN50' in txt):
                    print(f'\n  [Script {i}] len={len(txt)}')
                    # Try to find JSON blob
                    # Pattern: window.XX = {...} or var XX = {...}
                    for pattern in [r'window\.\w+\s*=\s*(\{.+?\});', r'var \w+\s*=\s*(\{.+?\});']:
                        m = re.search(pattern, txt, re.DOTALL)
                        if m:
                            try:
                                blob = json.loads(m.group(1))
                                print(f'    JSON blob keys: {list(blob.keys())[:10]}')
                            except:
                                pass
                    # Print raw excerpt
                    idx = txt.find('NBN25')
                    if idx < 0:
                        idx = txt.find('monthlyCost')
                    if idx >= 0:
                        print(f'    Excerpt: {repr(txt[max(0,idx-50):idx+300])}')

            # For wireless: check sqResultContainer content more carefully
            if key == 'wireless':
                sq = page.query_selector('.sqResultContainer')
                if sq:
                    print(f'\n.sqResultContainer text: {repr(sq.inner_text().strip()[:500])}')
                    # Look for ng-repeat children that are plan cards
                    plan_els = sq.query_selector_all('[ng-repeat]')
                    print(f'  ng-repeat elements inside: {len(plan_els)}')
                    for i, el in enumerate(plan_els[:5]):
                        attr = el.get_attribute('ng-repeat')
                        txt = el.inner_text().strip()[:100]
                        print(f'  [{i}] ng-repeat={attr!r} text={repr(txt)}')

            # Look for JSON-LD
            ld_scripts = page.query_selector_all('script[type="application/ld+json"]')
            print(f'\nJSON-LD scripts: {len(ld_scripts)}')
            for s in ld_scripts:
                try:
                    data = json.loads(s.inner_text())
                    t = data.get('@type', '') if isinstance(data, dict) else ''
                    print(f'  Type: {t}')
                    if 'Product' in t or 'Offer' in t:
                        print(f'  Data: {json.dumps(data)[:500]}')
                except:
                    pass

        except Exception as e:
            print(f'ERROR: {e}')
        finally:
            page.close()

    browser.close()
    print('\nProbe 6 complete.')
