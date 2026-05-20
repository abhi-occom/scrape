"""
Investigation script: dump HTML structure from Origin Energy internet plans page.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright

TARGET_URL = "https://www.originenergy.com.au/internet/plans/"


def investigate_origin():
    print(f"\n{'='*60}")
    print("INVESTIGATING: Origin Energy Internet Plans")
    print(f"{'='*60}")
    
    with sync_playwright() as p:
        browser = create_stealth_browser(p)
        page = create_stealth_page(browser)
        
        try:
            page.goto(TARGET_URL, timeout=30000, wait_until='domcontentloaded')
            page.wait_for_timeout(10000)  # Wait for JS to render
            
            # Get page title
            title = page.title()
            print(f"\nPage title: {title}")
            
            # Get body text
            body_text = page.inner_text('body')
            lines = body_text.split('\n')
            
            # Find lines with prices or speeds
            plan_lines = [l.strip() for l in lines if ('$' in l or 'Mbps' in l or 'mbps' in l) and l.strip()]
            
            print(f"\n--- Lines with $ or Mbps ---")
            for l in plan_lines[:30]:
                print(f"  {repr(l[:100])}")
            
            # Try common selectors
            selectors = [
                '[class*="plan"]',
                '[class*="card"]',
                '[class*="pricing"]',
                '[data-testid*="plan"]',
                'article',
                'section',
                'div[class*="product"]',
                'div[class*="tile"]',
            ]
            
            print(f"\n--- Selector counts ---")
            for sel in selectors:
                try:
                    els = page.query_selector_all(sel)
                    if els:
                        print(f"  {sel}: {len(els)} elements")
                except Exception as e:
                    print(f"  {sel}: ERROR")
            
            # Get HTML snippet
            print(f"\n--- HTML snippet (first 5000 chars) ---")
            html = page.content()[:5000]
            print(html)
            
        except Exception as e:
            print(f"ERROR: {e}")
            
        finally:
            browser.close()


if __name__ == '__main__':
    investigate_origin()
