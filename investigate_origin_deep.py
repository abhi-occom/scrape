"""
Deep investigation: find exact structure of Origin Energy plan cards.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright


TARGET_URL = "https://www.originenergy.com.au/internet/plans/"


def clean_text(text):
    """Remove problematic characters."""
    return text.replace('\u200b', '').replace('\n', ' | ').strip()


def investigate_deep():
    print(f"\n{'='*60}")
    print("DEEP INVESTIGATION: Origin Energy Internet Plans")
    print(f"{'='*60}")
    
    with sync_playwright() as p:
        browser = create_stealth_browser(p)
        page = create_stealth_page(browser)
        
        try:
            page.goto(TARGET_URL, timeout=30000, wait_until='domcontentloaded')
            page.wait_for_timeout(10000)
            
            # Try specific selectors
            print(f"\n=== PLAN CARDS ===")
            
            # Try .card elements
            cards = page.query_selector_all('[class*="card"]')
            print(f"[class*='card']: {len(cards)} elements")
            
            for i, card in enumerate(cards[:10]):
                try:
                    cls = (card.get_attribute('class') or '')[:80]
                    text = clean_text(card.inner_text()[:200])
                    print(f"\n[{i}] class={cls}...")
                    print(f"    text: {text}")
                except:
                    pass
            
            # Try sections
            print(f"\n\n=== SECTIONS with $/mbps ===")
            sections = page.query_selector_all('section')
            print(f"section: {len(sections)} elements")
            
            for i, sec in enumerate(sections[:20]):
                try:
                    cls = (sec.get_attribute('class') or '')[:80]
                    text = clean_text(sec.inner_text()[:200])
                    if '$' in text or 'mbps' in text.lower():
                        print(f"\n[{i}] class={cls}...")
                        print(f"    text: {text}")
                except:
                    pass
            
            # Look for specific plan containers
            print(f"\n\n=== LOOKING FOR NBN PLAN CARDS ===")
            
            # Try common patterns
            selectors = [
                'div[data-component="PlanCard"]',
                'div[class*="PlanCard"]',
                'div[class*="planCard"]',
                '[data-testid*="plan"]',
                '.MuiCard-root',
            ]
            
            for sel in selectors:
                els = page.query_selector_all(sel)
                if els:
                    print(f"\n{sel}: {len(els)} elements")
                    for i, el in enumerate(els[:5]):
                        try:
                            text = clean_text(el.inner_text()[:200])
                            print(f"  [{i}]: {text}")
                        except:
                            pass
            
            # Get full page innerHTML for analysis
            print(f"\n\n=== HTML ANALYSIS ===")
            import re
            html = page.content()
            
            # Find plan-related elements
            plan_patterns = [
                r'data-component="[^"]*plan[^"]*"',
                r'data-testid="[^"]*plan[^"]*"',
                r'class="[^"]*plan[^"]*"',
            ]
            
            for pattern in plan_patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    print(f"\nPattern: {pattern}")
                    for m in set(matches)[:10]:
                        print(f"  {m}")
            
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            browser.close()


if __name__ == '__main__':
    investigate_deep()
