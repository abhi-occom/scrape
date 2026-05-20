"""
Investigation: Check how to switch between NBN and Opticomm tabs on Origin Energy
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright


def investigate_origin_tabs():
    print(f"\n{'='*60}")
    print("INVESTIGATION: Origin Energy Tabs (NBN vs Opticomm)")
    print(f"{'='*60}")
    
    with sync_playwright() as p:
        browser = create_stealth_browser(p)
        page = create_stealth_page(browser)
        
        try:
            url = "https://www.originenergy.com.au/internet/plans/"
            print(f"\nNavigating to: {url}")
            
            page.goto(url, timeout=30000, wait_until='domcontentloaded')
            page.wait_for_timeout(10000)
            
            # Find tab buttons
            print(f"\n=== TABS ===")
            tabs = page.query_selector_all('[role="tab"]')
            print(f"Found {len(tabs)} tabs")
            
            for i, tab in enumerate(tabs):
                text = tab.inner_text().strip()
                aria_selected = tab.get_attribute('aria-selected')
                print(f"  Tab {i}: '{text}' - selected: {aria_selected}")
            
            # Test clicking each tab
            for i, tab in enumerate(tabs):
                text = tab.inner_text().strip()
                print(f"\n{'='*60}")
                print(f"CLICKING TAB: {text}")
                print(f"{'='*60}")
                
                tab.click()
                page.wait_for_timeout(3000)
                
                # Find plan cards after clicking
                cards = page.query_selector_all('div[class*="PlanCard"]')
                print(f"Found {len(cards)} plan cards")
                
                for j, card in enumerate(cards[:3]):
                    full_text = card.inner_text()
                    lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                    
                    # Get plan name
                    plan_name = ''
                    for line in lines[:10]:
                        if 'nbn' in line.lower() or 'opticomm' in line.lower():
                            if 'mbps' in line.lower() or '/' in line:
                                plan_name = line
                                break
                    
                    print(f"\n  Card {j}: {plan_name}")
                    
                    # Show first few lines
                    for line in lines[:8]:
                        print(f"    {line}")
                
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            browser.close()


if __name__ == '__main__':
    investigate_origin_tabs()
