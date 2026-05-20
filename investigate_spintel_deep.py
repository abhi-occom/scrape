"""
Deep investigation script: dump detailed HTML structure from Spintel home internet NBN plans page
to understand the actual selectors for plan cards.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright

# Target URL
TARGET_URL = "https://www.spintel.net.au/home-internet/nbn"


def investigate_spintel_deep():
    print(f"\n{'='*60}")
    print("DEEP INVESTIGATION: Spintel NBN Plans")
    print(f"{'='*60}")
    
    with sync_playwright() as p:
        browser = create_stealth_browser(p)
        page = create_stealth_page(browser)
        
        try:
            # Navigate to the page
            page.goto(TARGET_URL, timeout=30000, wait_until='domcontentloaded')
            page.wait_for_timeout(8000)  # Give more time for content to load
            
            # Find plan-block elements
            print(f"\n=== PLAN BLOCKS ===")
            plan_blocks = page.query_selector_all('.plan-block')
            print(f"Total .plan-block elements: {len(plan_blocks)}")
            
            for i, block in enumerate(plan_blocks[:15]):
                cls = block.get_attribute('class') or ''
                # Get inner text (truncated)
                text = block.inner_text().strip()[:200].replace('\n', ' | ')
                print(f"\n[{i}] class='{cls}'")
                print(f"    text: {text}")
                
        except Exception as e:
            print(f"ERROR: {e}")
            
        finally:
            browser.close()


if __name__ == '__main__':
    investigate_spintel_deep()