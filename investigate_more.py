
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page

URL = 'https://more.com.au/personal/nbn-plans'

def main():
    print(f'Investigating: {URL}')
    with sync_playwright() as p:
        browser = create_stealth_browser(p)
        page = create_stealth_page(browser)
        try:
            resp = page.goto(URL, timeout=45000, wait_until='domcontentloaded')
            page.wait_for_timeout(8000)
            
            # Get the main plans container
            container = page.query_selector('#products-list')
            if container:
                print('Found #products-list container')
                
                # Look for plan items within
                for sel in ['.plan-item', '.plan-card', '.pricing-card', 'div[class*=item]', 'li']:
                    cards = container.query_selector_all(sel)
                    if cards:
                        print(f'\nIn container, selector {sel}: {len(cards)} elements')
                        for i, card in enumerate(cards):
                            try:
                                text = card.inner_text()[:600]
                                classes = card.get_attribute('class') or ''
                                print(f'  {i}: class={classes[:60]}')
                                print(f'      {text[:500]}')
                                print()
                            except: pass
                
                # Also look at direct children
                print('\n--- Direct children of #products-list ---')
                children = container.query_selector_all('>')
                print(f'Found {len(children)} direct children')
                
                # Get all text content
                all_text = container.inner_text()
                print('\n--- All text in container ---')
                print(all_text)
                            
        except Exception as e:
            print(f'Error: {e}')
        finally:
            page.close()
            browser.close()

if __name__ == '__main__':
    main()
