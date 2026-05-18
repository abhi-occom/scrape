"""
Tangerine Probe Script - Extract exact plan structure
"""
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page

URL = 'https://www.tangerine.com.au/nbn/nbn-broadband'

def main():
    print(f'Probing: {URL}')
    with sync_playwright() as p:
        browser = create_stealth_browser(p)
        page = create_stealth_page(browser)
        try:
            resp = page.goto(URL, timeout=30000, wait_until='domcontentloaded')
            page.wait_for_timeout(3000)
            
            # Find all elements containing plan names and prices
            print('\n=== FINDING ALL PLAN CONTENT ===')
            
            # Get all text that contains plan info
            # Find the section with all plan details
            all_text = page.evaluate('''() => {
                // Find all elements and look for ones containing key phrases
                const plans = [];
                const headings = document.querySelectorAll("h2, h3, h4, h5");
                headings.forEach(h => {
                    const text = h.innerText.toLowerCase();
                    if (text.includes("value") || text.includes("speedy") || text.includes("ultra") || text.includes("mbps")) {
                        let parent = h.parentElement;
                        while (parent && plans.length < 20) {
                            if (parent.innerText.includes("$") && parent.innerText.includes("mbps")) {
                                plans.push(parent.innerText.substring(0, 1500));
                                break;
                            }
                            parent = parent.parentElement;
                        }
                    }
                });
                return plans;
            }''')
            
            for i, plan in enumerate(all_text):
                print(f'\n--- PLAN {i+1} ---')
                print(plan.replace(chr(10), ' '))
            
            # Now find all prices directly
            print('\n=== FINDING ALL PLAN PRICES ===')
            # Look for elements that contain $/MTH
            price_elements = page.query_selector_all('text=/\$/MTH/i')
            print(f'Found {len(price_elements)} elements with $/MTH')
            for i, el in enumerate(price_elements[:15]):
                try:
                    parent = el.query_selector('xpath=..')
                    if parent:
                        text = parent.inner_text()[:800].replace('\n', ' ')
                        print(f'\n[{i}]: {text}')
                except: pass
            
            # Get all Mbps values
            print('\n=== FINDING SPEEDS ===')
            mbps_elements = page.query_selector_all('text=/\d+Mbps/i')
            speeds = set()
            for el in mbps_elements[:30]:
                try:
                    text = el.inner_text()
                    if 'Download' in text or 'Upload' in text:
                        speeds.add(text)
                except: pass
            for speed in sorted(speeds):
                print(f'  {speed}')
            
        except Exception as e:
            print(f'Error: {e}')
            import traceback
            traceback.print_exc()
        finally:
            page.close()
            browser.close()

if __name__ == '__main__':
    main()
