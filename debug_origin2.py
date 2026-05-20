"""
Debug Origin scraper - check extraction logic
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
        full_text = card.inner_text()
        lines = full_text.split('\n')
        
        plan_name = ''
        for line in lines:
            line = line.strip()
            # Check if line has nbn and speed info
            if line and 'nbn' in line.lower():
                # Check if it has mbps pattern or number/number pattern
                if 'mbps' in line.lower() or re.search(r'\d+/\d+', line):
                    plan_name = line
                    break
        
        print(f'Card {i}: plan_name={repr(plan_name)}')
        
        # Now test full extraction
        all_prices = re.findall(r'\$(\d+\.?\d*)', full_text)
        all_prices = [float(p) for p in all_prices if float(p) > 0]
        print(f'  Prices: {all_prices}')
        
        # Speed
        match = re.search(r'(\d+)\s*mbps\s*download', full_text, re.IGNORECASE)
        download = int(match.group(1)) if match else 0
        match = re.search(r'(\d+\.?\d*)\s*mbps\s*upload', full_text, re.IGNORECASE)
        upload = int(float(match.group(1))) if match else 0
        print(f'  Speed: {download}/{upload}')
        
    browser.close()
