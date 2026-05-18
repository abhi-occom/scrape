import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page

URL = 'https://more.com.au/personal/nbn-plans'

with sync_playwright() as p:
    browser = create_stealth_browser(p)
    page = create_stealth_page(browser)
    
    page.goto(URL, timeout=40000, wait_until='domcontentloaded')
    page.wait_for_timeout(8000)
    
    container = page.query_selector('#products-list')
    print('Container #products-list:', container is not None)
    
    if not container:
        container = page.query_selector('#speeds')
        print('Container #speeds:', container is not None)
    
    if container:
        cards = container.query_selector_all('.owl-item')
        print(f'Found {len(cards)} owl-item cards')
        
        for i, card in enumerate(cards[:8]):
            text = card.inner_text()
            print(f'=== Card {i} ===')
            print(text[:300])
            
            valid_names = ['Value', 'Value Plus', 'Fast Max', 'Ultrafast']
            has_valid = any(name in text for name in valid_names)
            print(f'Has valid: {has_valid}')
    else:
        print('No container - checking page')
        body = page.inner_text('body')
        print(body[:1500])
    
    page.close()
    browser.close()