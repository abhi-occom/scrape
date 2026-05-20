
"""
Diagnostic script: dump HTML structure from Spintel home internet NBN plans page to understand
the actual selectors for plan cards.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright

# Target URL
TARGET_URL = "https://www.spintel.net.au/home-internet/nbn"

# List of CSS selectors to try (adapted from IPrimus approach)
SELECTORS_TO_TRY = [
    '.plan',
    '.pricing-item',
    '[class*="plan"]',
    '[class*="pricing"]',
    '[class*="package"]',
    '.vc_tta-panel',
    'table',
    'tr',
    '.wp-block-column',
    '.elementor-widget-container',
    '[class*="speed"]',
    '[class*="card"]',
    '[class*="tier"]',
    'article',
    '.plan-card',
    '.swoop-plan',
    'section',
    'div[data-testid="plan"]',  # Common pattern for plan cards
    'div[data-qa="plan"]',     # Common pattern for plan cards
    'div.plan-item',           # Common pattern for plan items
]


def investigate_spintel():
    print(f"\n{'='*60}")
    print("INVESTIGATING: Spintel NBN Plans — https://www.spintel.net.au/home-internet/nbn")
    print(f'{'='*60}')
    
    with sync_playwright() as p:
        browser = create_stealth_browser(p)
        page = create_stealth_page(browser)
        
        try:
            # Navigate to the page
            page.goto(TARGET_URL, timeout=30000, wait_until='domcontentloaded')
            page.wait_for_timeout(5000)  # Give time for content to load
            
            # Dump body text snippet
            body_text = page.inner_text('body')
            lines = body_text.split('\n')
            
            # Find lines mentioning prices or speeds
            plan_lines = [l.strip() for l in lines if ('$' in l or 'Mbps' in l or 'mbps' in l or '/mth' in l) and l.strip()]
            
            print(f"\n--- Lines containing $ / Mbps / mth ---")
            for l in plan_lines[:60]:
                print(f"  {repr(l)}")
            
            # Try each selector
            print(f"\n--- Selector counts ---")
            for sel in SELECTORS_TO_TRY:
                try:
                    els = page.query_selector_all(sel)
                    if els:
                        print(f"  {sel}: {len(els)} elements")
                except Exception as e:
                    print(f"  {sel}: ERROR {e}")
            
            # Dump detailed HTML of promising selectors
            print(f"\n--- Detailed HTML for matching selectors ---")
            promising_selectors = [
                '[class*="pricing"]', 
                '[class*="plan"]', 
                '[class*="package"]', 
                'table', 
                '.vc_tta-panel',
                'div[data-testid="plan"]',
                'div[data-qa="plan"]'
            ]
            
            for sel in promising_selectors:
                try:
                    els = page.query_selector_all(sel)
                    if els:
                        print(f"\n  === {sel} ({len(els)} found) ===")
                        for i, el in enumerate(els[:3]):
                            txt = el.inner_text().strip()[:300]
                            cls = el.get_attribute('class') or ''
                            print(f"    [{i}] class='{cls}' text={repr(txt)}")
                except Exception as e:
                    print(f"  {sel}: ERROR {e}")
            
            # Dump full page HTML snippet around prices
            print(f"\n--- Full page HTML (first 8000 chars) ---")
            html = page.content()
            
            # Find regions near dollar signs
            import re
            matches = list(re.finditer(r'.{200}\$\d+.{200}', html, re.DOTALL))
            
            for i, m in enumerate(matches[:5]):
                print(f"\n  [match {i}]")
                snippet = m.group(0).replace('\n', ' ')
                print(f"  {snippet[:500]}")
                
        except Exception as e:
            print(f"ERROR during investigation: {e}")
            
        finally:
            browser.close()


if __name__ == '__main__':
    investigate_spintel()
