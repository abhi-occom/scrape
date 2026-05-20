"""
Debug Origin scraper - check extraction
"""
import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright


URL = 'https://www.originenergy.com.au/internet/plans/'

with sync_playwright() as p:
    browser = create_stealth_browser(p)
    page = create_stealth_page(browser)
    page.goto(URL, timeout=30000, wait_until='domcontentloaded')
    page.wait_for_timeout(10000)
    
    cards = page.query_selector_all('div[class*="PlanCard"]')
    print(f'Found {len(cards)} cards')
    
    for i, card in enumerate(cards):
        text = card.inner_text()
        # Clean the text
        text = text.replace(chr(0x200b), '')
        print(f'\n=== Card {i} ===')
        print(f'Full text (first 300): {repr(text[:300])}')
        
        # Find lines with nbn
        lines = text.split('\n')
        for line in lines:
            if 'nbn' in line.lower():
                print(f'  Plan line: {repr(line)}')
        
        # Find prices
        prices = re.findall(r'\$(\d+\.?\d*)', text)
        print(f'  Prices found: {prices}')
        
        # Find mbps
        mbps = re.findall(r'(\d+)\s*mbps', text, re.IGNORECASE)
        print(f'  Mbps found: {mbps}')
    
    browser.close()
