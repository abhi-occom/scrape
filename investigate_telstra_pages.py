"""Investigate all 4 Telstra pages for plan data structure."""
import sys, os, json, re
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
        print(f"\n{'='*70}")
        print(f"  {key}: {url}")
        print(f"{'='*70}")

        try:
            resp = page.goto(url, timeout=30000, wait_until="domcontentloaded")
            print(f"  Status: {resp.status if resp else 'none'}")
            page.wait_for_timeout(6000)
            print(f"  Title: {page.title()}")
            print(f"  Final URL: {page.url}")

            html = page.content()
            print(f"  HTML length: {len(html)}")

            # Save HTML
            fname = f"output/telstra_{key}.html"
            with open(fname, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"  Saved: {fname}")

            # Check JSON-LD
            scripts = page.query_selector_all('script[type="application/ld+json"]')
            print(f"\n  JSON-LD scripts: {len(scripts)}")
            for i, s in enumerate(scripts):
                try:
                    data = json.loads(s.inner_text())
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        t = item.get('@type', '?')
                        print(f"    [{i}] @type={t}")
                        if t in ('Product', 'ProductGroup'):
                            variants = item.get('hasVariant', [])
                            print(f"      {len(variants)} variants")
                except Exception as e:
                    print(f"    [{i}] parse error: {e}")

            # Probe Telstra-specific selectors
            selectors = {
                'planCardHeader': '.planCardHeader',
                'h3 headline': 'h3.tcom-fixed-plan-card-header__headline',
                'data-fixed-plan-card-price': '[data-fixed-plan-card-price]',
                'data-dsq-evening-download': '[data-tcom-fixed-plancard-dsq-evening-download]',
                'data-dsq-evening-upload': '[data-tcom-fixed-plancard-dsq-evening-upload]',
                'planCardCarouselContainer': '.planCardCarouselContainer',
                'data-testid plan': '[data-testid*="plan"]',
                '[class*=plan-card]': '[class*="plan-card"]',
                '[class*=PlanCard]': '[class*="PlanCard"]',
                'h3': 'h3',
                'article': 'article',
                '.card': '.card',
                '[class*=price]': '[class*="price"]',
                '[class*=speed]': '[class*="speed"]',
                '[class*=Price]': '[class*="Price"]',
            }

            print(f"\n  Selector probe:")
            for desc, sel in selectors.items():
                try:
                    els = page.query_selector_all(sel)
                    if els:
                        first_txt = els[0].inner_text()[:120].replace('\n', ' | ')
                        print(f"    {desc}: {len(els)} → {first_txt}")
                except:
                    pass

            # Price patterns
            prices = re.findall(r'\$\d+(?:\.\d{2})?(?:/m(?:th|onth)?)?', html)
            unique_prices = sorted(set(prices))
            print(f"\n  Prices: {unique_prices[:25]}")

            # Speed patterns
            speeds = re.findall(r'\b\d+(?:/\d+)?\s*(?:Mbps|mbps|Gbps)', html)
            unique_speeds = sorted(set(speeds))
            print(f"  Speeds: {unique_speeds[:25]}")

        except Exception as e:
            print(f"  ERROR: {e}")
        finally:
            page.close()

    browser.close()
    print("\nDone.")
