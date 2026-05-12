"""
Find the plan data for the wireless page by waiting for network requests
and intercepting API calls that return plan data.
Also check for src attributes of scripts that may host plan data.
"""
from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page
import re
import json

captured_responses = []

def handle_response(response):
    url = response.url
    if any(k in url for k in ['plan', 'product', 'price', 'speed', 'nbn', 'broadband']):
        try:
            ct = response.headers.get('content-type', '')
            if 'json' in ct or 'javascript' in ct:
                body = response.text()
                if len(body) > 50:
                    captured_responses.append({
                        'url': url,
                        'ct': ct,
                        'body': body[:800]
                    })
        except:
            pass

with sync_playwright() as p:
    browser = create_stealth_browser(p)

    # ── Wireless page network intercept ─────────────────────────────────
    print('=== WIRELESS PAGE — Network Intercept ===')
    page = create_stealth_page(browser)
    page.on('response', handle_response)
    page.goto('https://www.iinet.net.au/internet-product/broadband/nbn/plans/wireless', timeout=40000, wait_until='domcontentloaded')
    page.wait_for_timeout(10000)

    print(f'Captured {len(captured_responses)} matching responses:')
    for r in captured_responses:
        print(f'\nURL: {r["url"]}')
        print(f'Content-Type: {r["ct"]}')
        print(f'Body: {repr(r["body"][:400])}')

    # Check external script sources for plan data
    scripts = page.query_selector_all('script[src]')
    print(f'\nExternal scripts: {len(scripts)}')
    for s in scripts:
        src = s.get_attribute('src')
        if src and any(k in src for k in ['plan', 'product', 'iinet', 'nbn']):
            print(f'  {src}')

    # Check the HTML source for any embedded angular model data
    html = page.content()
    # Find all var declarations with objects
    var_matches = re.findall(r'(?:var|let|const|window)\s+[\w.]+\s*=\s*\{[^;]{20,200}', html)
    for v in var_matches[:5]:
        if any(k in v for k in ['plan', 'price', 'speed', 'nbn', 'NBN']):
            print(f'\nVar declaration: {repr(v[:300])}')

    # Check data attributes on Angular root element
    ng_app = page.query_selector('[ng-app]')
    if ng_app:
        print(f'\nng-app element: {ng_app.get_attribute("ng-app")}')

    page.close()
    browser.close()
    print('\nProbe 7 complete.')
