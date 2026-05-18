"""
Tangerine Probe Script - Find exact plan structure
"""
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page

URL = 'https://www.tangerine.com.au/nbn/nbn-broadband'

def main():
    print(f'Probing: {URL}')
    with sync_playwright() as p:
        browser = create_stealth_browser(p)
        page = create_stealth_page(browser)
        try:
            resp = page.goto(URL, timeout=30000, wait_until='domcontentloaded')
            page.wait_for_timeout(3000)
            
            # Look for elements with plan data
            print('\n=== LOOKING FOR PLAN CONTAINER ===')
            # Try to find the main plans section
            for container_sel in ['.plan', '#plans', '[class*=container]', 'main', 'section']:
                els = page.query_selector_all(container_sel)
                if els:
                    print(f'{container_sel}: {len(els)} elements')
            
            # Find all elements with $ and numbers (price patterns)
            print('\n=== FINDING PRICE ELEMENTS ===')
            # Look for $ followed by numbers
            price_cards = page.query_selector_all('[class*=price]')
            print(f'[class*=price] elements: {len(price_cards)}')
            for i, card in enumerate(price_cards[:10]):
                try:
                    text = card.inner_text()[:300].replace('\n', ' ')
                    print(f'  [{i}]: {text}')
                except: pass
            
            # Look for specific plan names
            print('\n=== FINDING PLAN NAMES ===')
            for name in ['Value', 'Value Plus', 'Speedy Max', 'UltraSpeedy']:
                matches = page.query_selector_all(f'text={name}')
                print(f'{name}: {len(matches)} matches')
                if matches:
                    for m in matches[:2]:
                        try:
                            parent = m.query_selector('xpath=..')
                            if parent:
                                print(f'  Parent text: {parent.inner_text()[:400].replace(chr(10), " ")}')
                        except: pass
            
            # Get text content of all .plan elements
            print('\n=== DUMPING .plan ELEMENTS TEXT ===')
            plan_elements = page.query_selector_all('.plan')
            for i, el in enumerate(plan_elements[:20]):
                try:
                    text = el.inner_text()[:500].replace('\n', ' ')
                    if '$' in text or 'Mbps' in text:
                        print(f'\n--- Plan element {i} ---')
                        print(text)
                except: pass
            
            # Look for the actual price values
            print('\n=== FINDING EXACT PRICES ===')
            # Use regex to find prices
            page_content = page.content()
            prices = re.findall(r'\$[0-9]+\.[0-9]+', page_content)
            unique_prices = sorted(set(prices))
            print(f'Unique prices found: {unique_prices}')
            
        except Exception as e:
            print(f'Error: {e}')
            import traceback
            traceback.print_exc()
        finally:
            page.close()
            browser.close()

if __name__ == '__main__':
    main()
