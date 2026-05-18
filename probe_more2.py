import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import re
from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page

URL = 'https://more.com.au/personal/nbn-plans'

def _parse_promo_info(text):
    promo_match = re.search(r'\$([0-9]+(?:\.[0-9]+)?)\s*/mth\s*for\s*([0-9]+)\s*months?', text, re.IGNORECASE)
    if promo_match:
        promo_price = float(promo_match.group(1))
        promo_period = promo_match.group(2) + ' months'
        then_match = re.search(r'then\s*\$([0-9]+(?:\.[0-9]+)?)\s*/mth', text, re.IGNORECASE)
        regular_price = float(then_match.group(1)) if then_match else None
        return promo_price, promo_period, regular_price
    
    rrp_match = re.search(r'RRP\s*\$([0-9]+(?:\.[0-9]+)?)', text, re.IGNORECASE)
    if rrp_match:
        rrp_price = float(rrp_match.group(1))
        price_match = re.search(r'\$([0-9]+(?:\.[0-9]+)?)\s*/mth', text, re.IGNORECASE)
        if price_match:
            display_price = float(price_match.group(1))
            if display_price < rrp_price:
                return display_price, 'Promo', rrp_price
            else:
                return None, None, display_price
        return None, None, rrp_price
    
    price_match = re.search(r'\$([0-9]+(?:\.[0-9]+)?)\s*/mth', text, re.IGNORECASE)
    if price_match:
        return None, None, float(price_match.group(1))
    
    return None, None, None

def _parse_speeds(text):
    dl = re.search(r'([0-9]+)\s*Mbps\s*Download', text, re.IGNORECASE)
    ul = re.search(r'([0-9]+)\s*Mbps\s*Upload', text, re.IGNORECASE)
    return int(dl.group(1)) if dl else 0, int(ul.group(1)) if ul else 0

with sync_playwright() as p:
    browser = create_stealth_browser(p)
    page = create_stealth_page(browser)
    
    page.goto(URL, timeout=40000, wait_until='domcontentloaded')
    page.wait_for_timeout(8000)
    
    container = page.query_selector('#products-list')
    cards = container.query_selector_all('.owl-item')
    
    valid_names = ['Value', 'Value Plus', 'Fast Max', 'Ultrafast']
    
    for i, card in enumerate(cards[:8]):
        text = card.inner_text()
        
        if not any(name in text for name in valid_names):
            continue
            
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        plan_name = lines[0] if lines else ''
        
        if plan_name not in valid_names:
            continue
        
        print(f'\n=== Processing: {plan_name} ===')
        
        promo_price, promo_period, regular_price = _parse_promo_info(text)
        print(f'promo_price={promo_price}, promo_period={promo_period}, regular_price={regular_price}')
        
        download_speed, upload_speed = _parse_speeds(text)
        print(f'download={download_speed}, upload={upload_speed}')
        
        if plan_name and regular_price:
            print('SUCCESS - would add plan')
        else:
            print(f'FAIL - plan_name={plan_name}, regular_price={regular_price}')
    
    page.close()
    browser.close()