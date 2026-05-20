"""
Investigation: Check if Origin Energy has multiple network types (NBN, Opticomm, etc.)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright


def investigate_origin_networks():
    print(f"\n{'='*60}")
    print("INVESTIGATION: Origin Energy Network Types")
    print(f"{'='*60}")
    
    with sync_playwright() as p:
        browser = create_stealth_browser(p)
        page = create_stealth_page(browser)
        
        try:
            # Main plans page
            url = "https://www.originenergy.com.au/internet/plans/"
            print(f"\nNavigating to: {url}")
            
            page.goto(url, timeout=30000, wait_until='domcontentloaded')
            page.wait_for_timeout(10000)
            
            # Look for network type selectors or tabs
            print(f"\n=== LOOKING FOR NETWORK TYPE SELECTORS ===")
            
            # Check for tabs/buttons with network types
            selectors = [
                'button:has-text("NBN")',
                'button:has-text("Opticomm")',
                'button:has-text("nbn")',
                'button:has-text("opticomm")',
                'a:has-text("NBN")',
                'a:has-text("Opticomm")',
                '[role="tab"]',
                '.tab',
                '[data-testid*="tab"]',
            ]
            
            for sel in selectors:
                try:
                    els = page.query_selector_all(sel)
                    if els:
                        print(f"\n{sel}: {len(els)} elements")
                        for el in els[:10]:
                            text = el.inner_text().strip()
                            href = el.get_attribute('href') or ''
                            print(f"  - {text} {href}")
                except Exception as e:
                    pass
            
            # Look for any links on the page
            print(f"\n=== ALL LINKS WITH 'PLAN', 'NBN', 'OPTICOMM' ===")
            links = page.query_selector_all('a')
            for link in links:
                try:
                    href = link.get_attribute('href') or ''
                    text = link.inner_text().strip()[:100]
                    if any(word in text.lower() or word in href.lower() 
                           for word in ['plan', 'nbn', 'opticomm', 'internet']):
                        print(f"  {text} -> {href}")
                except:
                    pass
            
            # Get page title
            print(f"\n=== PAGE INFO ===")
            print(f"Title: {page.title()}")
            print(f"URL: {page.url}")
            
            # Check HTML for network type mentions
            print(f"\n=== SEARCHING HTML FOR NETWORK TYPES ===")
            html = page.content().lower()
            
            keywords = ['opticomm', 'nbn', 'fibre', 'fttp', 'fttb', 'hfc', 'fixed wireless']
            for keyword in keywords:
                count = html.count(keyword)
                if count > 0:
                    print(f"  '{keyword}': {count} occurrences")
            
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            browser.close()


if __name__ == '__main__':
    investigate_origin_networks()
