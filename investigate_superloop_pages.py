"""Investigate all 4 Superloop pages for plan data structure."""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page

URLS = {
    "flip_to_fibre": "https://www.superloop.com/flip-to-fibre/",
    "nbn": "https://www.superloop.com/internet/nbn/",
    "fibre": "https://www.superloop.com/internet/fibre/",
    "fixed_wireless": "https://www.superloop.com/internet/fixed-wireless/",
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
            page.wait_for_timeout(5000)
            print(f"  Title: {page.title()}")
            print(f"  Final URL: {page.url}")

            html = page.content()
            print(f"  HTML length: {len(html)}")

            # Save HTML
            fname = f"output/superloop_{key}.html"
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
                        if t == 'ProductGroup':
                            variants = item.get('hasVariant', [])
                            print(f"    [{i}] ProductGroup with {len(variants)} variants")
                            if variants:
                                print(f"      First: {json.dumps(variants[0], indent=2)[:300]}")
                        else:
                            print(f"    [{i}] @type={t}")
                except Exception as e:
                    print(f"    [{i}] parse error: {e}")

            # Check for plan cards with common selectors
            plan_selectors = [
                '[data-testid*="plan"]',
                '.plan-card', '[class*="PlanCard"]',
                '#plans',
                '[class*="price"]',
                'h3',
            ]
            print(f"\n  Selector probe:")
            for sel in plan_selectors:
                try:
                    els = page.query_selector_all(sel)
                    if els:
                        print(f"    {sel}: {len(els)} matches")
                        for el in els[:3]:
                            txt = el.inner_text()[:100].replace('\n', ' | ')
                            print(f"      → {txt}")
                except:
                    pass

            # Price patterns
            prices = re.findall(r'\$\d+(?:\.\d{2})?(?:/m(?:th|onth)?)?', html)
            unique_prices = sorted(set(prices))
            print(f"\n  Price patterns: {unique_prices[:20]}")

            # Speed patterns
            speeds = re.findall(r'\b\d+(?:/\d+)?\s*(?:Mbps|mbps)', html)
            unique_speeds = sorted(set(speeds))
            print(f"  Speed patterns: {unique_speeds[:20]}")

        except Exception as e:
            print(f"  ERROR: {e}")
        finally:
            page.close()

    browser.close()
    print("\nDone.")
