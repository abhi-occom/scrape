"""
Deep investigation: extract detailed structure of each plan block
to understand how to parse prices, speeds, and plan names.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright

TARGET_URL = "https://www.spintel.net.au/home-internet/nbn"


def investigate_structure():
    print(f"\n{'='*60}")
    print("DETAILED STRUCTURE INVESTIGATION")
    print(f"{'='*60}")
    
    with sync_playwright() as p:
        browser = create_stealth_browser(p)
        page = create_stealth_page(browser)
        
        try:
            page.goto(TARGET_URL, timeout=30000, wait_until='domcontentloaded')
            page.wait_for_timeout(8000)
            
            # Get all plan-block with product-option class (these are the actual plans)
            plan_blocks = page.query_selector_all('.plan-block.product-option')
            print(f"\nFound {len(plan_blocks)} .plan-block.product-option elements\n")
            
            for i, block in enumerate(plan_blocks[:20]):
                cls = block.get_attribute('class') or ''
                
                # Skip non-plan elements
                if 'options' in cls or 'heading' not in cls:
                    continue
                    
                print(f"\n{'='*50}")
                print(f"[{i}] CLASS: {cls}")
                print(f"{'='*50}")
                
                # Try to find plan name/heading
                heading = block.query_selector('.heading-6')
                if heading:
                    print(f"  .heading-6: {heading.inner_text().strip()[:100]}")
                
                heading2 = block.query_selector('.plan-heading')
                if heading2:
                    print(f"  .plan-heading: {heading2.inner_text().strip()[:100]}")
                
                # Look for price
                price_block = block.query_selector('.plan-price')
                if price_block:
                    print(f"  .plan-price: {price_block.inner_text().strip()[:100]}")
                
                # Look for description
                desc = block.query_selector('.plan-description')
                if desc:
                    print(f"  .plan-description: {desc.inner_text().strip()[:150]}")
                
                # Look for speed info
                speed_el = block.query_selector('[class*="speed"]')
                if speed_el:
                    print(f"  [class*='speed']: {speed_el.inner_text().strip()[:100]}")
                
                # Get all text
                full_text = block.inner_text().strip()
                print(f"\n  FULL TEXT:\n  {full_text[:500].replace(chr(10), ' | ')}")
                
                # Look for specific patterns in HTML
                html = block.inner_html()
                # Find price patterns
                import re
                prices = re.findall(r'\$\d+\.?\d*', html)
                if prices:
                    print(f"  Prices found in HTML: {prices}")
                
        except Exception as e:
            print(f"ERROR: {e}")
            
        finally:
            browser.close()


if __name__ == '__main__':
    investigate_structure()
