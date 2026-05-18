"""
Tangerine Investigation Script
Explores the Tangerine NBN page to find plan selectors.
"""
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page

URL = 'https://www.tangerine.com.au/nbn/nbn-broadband'

def main():
    print(f'Investigating: {URL}')
    with sync_playwright() as p:
        browser = create_stealth_browser(p)
        page = create_stealth_page(browser)
        try:
            resp = page.goto(URL, timeout=30000, wait_until='domcontentloaded')
            print(f'Response status: {resp.status if resp else None}')
            page.wait_for_timeout(3000)
            
            # Get page title
            print(f'Page title: {page.title()}')
            
            # Try different selectors
            print('\n=== TRYING SELECTORS ===')
            for sel in ['.plan', '.pricing', '[class*=plan]', '.card', 'h2', 'h3', 'h4']:
                els = page.query_selector_all(sel)
                if els:
                    print(f'{sel}: {len(els)} elements')
                    for i, el in enumerate(els[:3]):
                        text = el.inner_text()[:150].replace('\n', ' ').strip()
                        if text:
                            print(f'  [{i}] {text}')
            
            # Look for price patterns
            print('\n=== LOOKING FOR PRICES ===')
            # Find elements with $ and /MTH
            all_els = page.query_selector_all('*')
            price_els = []
            for el in all_els:
                try:
                    text = el.inner_text()
                    if '$' in text and ('/MTH' in text.upper() or 'MONTH' in text.upper()):
                        price_els.append(el)
                except: pass
            print(f'Found {len(price_els)} price elements')
            for i, el in enumerate(price_els[:15]):
                text = el.inner_text()[:200].replace('\n', ' ').strip()
                print(f'  [{i}] {text}')
            
            # Get full page text
            print('\n=== FULL PAGE TEXT (first 3000 chars) ===')
            full = page.inner_text()
            print(full[:3000])
            
        except Exception as e:
            print(f'Error: {e}')
        finally:
            page.close()
            browser.close()

if __name__ == '__main__':
    main()
