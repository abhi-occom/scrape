
# scrape/investigate_activ8me.py
"""Deep inspection of activ8me plan pages to understand structure. Updates to extract structured data for 2-4 plan cards."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright

URL = 'https://www.activ8me.net.au/internet/nbn-fibre-fttp-hfc'

print(f'\n{"="*70}')
print(f'DEEP INVESTIGATION: {URL}')
print(f'{"="*70}')

with sync_playwright() as p:
    browser = create_stealth_browser(p)
    page = create_stealth_page(browser)

    try:
        # Navigate to the page
        page.goto(URL, timeout=40000, wait_until='domcontentloaded')
        page.wait_for_timeout(8000)
        
        
        # Get the full page text to understand structure
        page_text = page.inner_text('body')
        lines = page_text.split('\n')
        
        print('\n[1] Looking for plan info patterns:\n')
        # Find lines with plan names, speeds, and prices
        plan_indicators = []
        for i, line in enumerate(lines):
            line_strip = line.strip()
            if ('Mbps' in line or 'NBN' in line or 'fibre' in line or 'FTTP' in line) and (i < len(lines) - 1):
                plan_indicators.append((i, line_strip))
        
        print(f'Found {len(plan_indicators)} lines with plan indicators')
        for idx, (i, line) in enumerate(plan_indicators[:20]):
            print(f'  [{idx}] {repr(line[:100])}')

        # Look for divs with specific class patterns
        print('\n[2] All divs within class:\n')
        divs = page.query_selector_all('div')
        
        class_patterns = {}
        for div in divs:
            cls = div.get_attribute('class') or ''
            if any(x in cls.lower() for x in ['plan', 'card', 'price', 'product', 'speed', 'internet']):
                if cls not in class_patterns:
                    class_patterns[cls] = 0
                class_patterns[cls] += 1
        
        for cls, count in sorted(class_patterns.items(), key=lambda x: x[1], reverse=True)[:20]:
            print(f'  {count:3d}x: {cls[:80]}')

        # Look for rows/containers
        print('\n[3] Main container structure - looking for div containers:\n')
        main_containers = page.query_selector_all('div[class*="row"], div[class*="container"], div[class*="grid"]')
        print(f'Found {len(main_containers)} potential row/container divs')
        
        # Look for specific high-level divs
        print('\n[4] Top-level structure under body:\n')
        direct_divs = page.query_selector_all('body > div')
        print(f'Found {len(direct_divs)} direct child divs of body')
        
        for idx, div in enumerate(direct_divs[:8]):
            cls = div.get_attribute('class') or 'no-class'
            child_count = div.evaluate('el => el.children.length')
            text_preview = div.inner_text().strip()[:100]
            print(f'  [{idx}] class=\'{cls[:60]}\' children={child_count} text={repr(text_preview)}')

        # Get the actual HTML to see structure
        print('\n[5] Raw HTML (first 3000 chars):\n')
        html = page.content()
        print(html[:3000])

        # Search for specific plan elements
        print('\n[6] Searching page content for actual plan names:\n')
        if '30-day' in page_text.lower():
            print("  ✓ Found '30-day' plans")
            # Find context around 30-day
            idx = page_text.lower().find('30-day')
            context = page_text[max(0, idx-200):idx+300]
            print(f'  Context: {repr(context)}')

        if '90-day' in page_text.lower():
            print("  ✓ Found '90-day' plans")

        if '4G' in page_text:
            print('  ✓ Found 4G references')
            idx = page_text.find('4G')
            context = page_text[max(0, idx-100):idx+200]
            print(f'  Context: {repr(context)}')

        # Look for plan cards specifically
        print('\n[7] Looking for specific plan card elements:\n')
        plan_cards = page.query_selector_all('.plan-card, .plan-item, div[class*="plan"]')
        print(f'Found {len(plan_cards)} potential plan cards')
        
        if plan_cards:
            for i, card in enumerate(plan_cards[:5]):
                cls = card.get_attribute('class') or ''
                text_preview = card.inner_text().strip()[:100]
                print(f'  [{i}] class=\'{cls[:60]}\' text={repr(text_preview)}')

        # ✅ Extract structured data for 2-4 cards
        print('\n[8] EXTRACTED STRUCTURED PLAN DATA (2-4 CARDS):\n')
        structured_data = []
        for i, card in enumerate(plan_cards[:4]):  # Limit to 4 cards
            cls = card.get_attribute('class') or ''
            text = card.inner_text().strip()
            # Parse text: e.g., 'nbn Standard 50 100GB – 50Mbps – 100GB – $64.95'
            parts = text.split(' – ')
            if len(parts) >= 4:
                name = parts[0]
                speed = parts[1]
                data_allowance = parts[2]
                price = parts[3]
                structured_data.append({
                    'name': name,
                    'speed': speed,
                    'data_allowance': data_allowance,
                    'price': price
                })
            else:
                structured_data.append({
                    'name': 'Unknown',
                    'speed': 'Unknown',
                    'data_allowance': 'Unknown',
                    'price': 'Unknown'
                })
        
        for idx, plan in enumerate(structured_data):
            print(f'  [{idx}] {plan}')

    except Exception as e:
        print(f'❌ Error during investigation: {str(e)}')
    
    browser.close()
    print(f'\n{("="*70)}')
    print('Investigation complete.')