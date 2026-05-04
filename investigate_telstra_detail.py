"""Extract plan details from all 4 Telstra pages using existing selectors."""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page

URLS = {
    "plans": "https://www.telstra.com.au/internet/plans",
    "5g_home": "https://www.telstra.com.au/internet/5g-home-internet",
    "starlink": "https://www.telstra.com.au/internet/starlink",
    "small_business": "https://www.telstra.com.au/small-business/internet",
}

with sync_playwright() as p:
    browser = create_stealth_browser(p)

    for key, url in URLS.items():
        page = create_stealth_page(browser)
        print(f"\n{'='*90}")
        print(f"  {key}: {url}")
        print(f"{'='*90}")

        try:
            resp = page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(6000)

            # Extract using data attributes
            headers = page.query_selector_all('h3.tcom-fixed-plan-card-header__headline')
            prices = page.query_selector_all('[data-fixed-plan-card-price]')
            downloads = page.query_selector_all('[data-tcom-fixed-plancard-dsq-evening-download]')
            uploads = page.query_selector_all('[data-tcom-fixed-plancard-dsq-evening-upload]')

            print(f"  headers={len(headers)} prices={len(prices)} downloads={len(downloads)} uploads={len(uploads)}")
            print()

            for i, h in enumerate(headers):
                name = h.get_attribute('data-tcom-fixed-plan-card-header-label') or h.inner_text().strip().split('\n')[0]
                name = name.replace('Online exclusive offer', '').strip()

                price_val = ''
                if i < len(prices):
                    price_val = prices[i].get_attribute('data-fixed-plan-card-price') or prices[i].inner_text().strip()[:50]

                dl_val = ''
                if i < len(downloads):
                    dl_val = downloads[i].get_attribute('data-tcom-fixed-plancard-dsq-evening-download') or downloads[i].inner_text().strip()[:30]

                ul_val = ''
                if i < len(uploads):
                    ul_val = uploads[i].get_attribute('data-tcom-fixed-plancard-dsq-evening-upload') or uploads[i].inner_text().strip()[:30]

                # Check for data cap
                data_cap = ''
                # Look at the parent planCardHeader for data info
                parent_header = h.evaluate_handle('el => el.closest(".planCardHeader")')
                if parent_header:
                    try:
                        header_text = parent_header.inner_text()
                        data_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:GB|TB)\s*DATA', header_text)
                        if data_match:
                            data_cap = data_match.group(0)
                        if 'UNLIMITED' in header_text.upper():
                            data_cap = 'UNLIMITED'
                    except:
                        pass

                print(f"  [{i:2d}] name='{name}' | price={price_val} | dl={dl_val} | ul={ul_val} | data={data_cap}")

        except Exception as e:
            print(f"  ERROR: {e}")
        finally:
            page.close()

    browser.close()
    print("\nDone.")
