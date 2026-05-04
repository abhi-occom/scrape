"""Investigate Vodafone website structure for plan scraping."""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page

VODAFONE_PAGES = {
    'nbn': 'https://www.vodafone.com.au/home-internet/nbn',
    'opticomm': 'https://www.vodafone.com.au/home-internet/opticomm',
    'super_wifi': 'https://www.vodafone.com.au/home-internet/super-wifi',
    '4g_5g': 'https://www.vodafone.com.au/home-internet/4g-5g-plans',
}

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output', 'investigation')
os.makedirs(OUTPUT_DIR, exist_ok=True)


def investigate():
    with sync_playwright() as p:
        browser = create_stealth_browser(p)

        for page_key, url in VODAFONE_PAGES.items():
            print(f"\n{'='*60}")
            print(f"Investigating: {page_key} -- {url}")
            print(f"{'='*60}")

            page = create_stealth_page(browser)
            try:
                resp = page.goto(url, timeout=30000, wait_until="domcontentloaded")
                print(f"Status: {resp.status if resp else 'none'}")
                page.wait_for_timeout(6000)

                html = page.content()
                html_path = os.path.join(OUTPUT_DIR, f"vodafone_{page_key}.html")
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html)
                print(f"HTML saved: ({len(html)} chars)")

                # JSON-LD
                json_ld_scripts = page.query_selector_all('script[type="application/ld+json"]')
                print(f"\nJSON-LD scripts: {len(json_ld_scripts)}")
                for i, script in enumerate(json_ld_scripts):
                    text = script.inner_text()
                    try:
                        data = json.loads(text)
                        dtype = data.get('@type', data[0].get('@type', '?') if isinstance(data, list) else '?')
                        print(f"  [{i}] type={dtype}")
                        if 'offers' in (data if isinstance(data, dict) else {}):
                            print(f"       offers: {json.dumps(data['offers'], indent=2)[:600]}")
                        if isinstance(data, list):
                            for item in data[:3]:
                                print(f"       item: {json.dumps(item, indent=2)[:300]}")
                    except Exception:
                        print(f"  [{i}] parse error: {text[:100]}")

                # Selector scan
                selectors_to_try = [
                    '.plan-card', '.product-card',
                    '[class*="plan-card"]', '[class*="product-card"]',
                    '[class*="PlanCard"]', '[class*="ProductCard"]',
                    '[data-testid*="plan"]', '[data-testid*="product"]',
                    '.card', '[class*="pricing"]', '[class*="tier"]',
                    'div[class*="plan"]', 'div[class*="price"]',
                    '[class*="paragraph--type"]', '.views-row',
                    # Vodafone-specific guesses
                    '[class*="Plan"]', '[class*="nbn"]', '[class*="speed"]',
                    '[class*="offer"]', '[class*="Offer"]',
                    '[class*="tile"]', '[class*="Tile"]',
                ]
                print(f"\nSelector scan:")
                for sel in selectors_to_try:
                    try:
                        els = page.query_selector_all(sel)
                        if els:
                            first_text = els[0].inner_text()[:150].replace('\n', ' | ')
                            print(f"  YES {sel}: {len(els)} -- \"{first_text}\"")
                    except Exception:
                        pass

                # H3 headings
                for tag in ['h2', 'h3']:
                    headings = page.query_selector_all(tag)
                    if headings:
                        texts = [h.inner_text().strip()[:80] for h in headings[:15]]
                        print(f"\n{tag} headings ({len(headings)}): {texts}")

                # Interesting classes
                interesting_classes = page.evaluate("""() => {
                    const results = {};
                    const keywords = ['plan', 'price', 'speed', 'card', 'tier', 'product', 'offer', 'tile', 'nbn'];
                    document.querySelectorAll('*').forEach(el => {
                        const cls = el.className;
                        if (typeof cls === 'string') {
                            for (const kw of keywords) {
                                if (cls.toLowerCase().includes(kw)) {
                                    const tag = el.tagName.toLowerCase();
                                    const key = `${tag}.${cls.split(' ').filter(c => c.toLowerCase().includes(kw)).join('.')}`;
                                    results[key] = (results[key] || 0) + 1;
                                    break;
                                }
                            }
                        }
                    });
                    return results;
                }""")
                if interesting_classes:
                    print(f"\nInteresting class patterns:")
                    for cls, count in sorted(interesting_classes.items(), key=lambda x: -x[1])[:25]:
                        print(f"  {cls}: {count}")

                # Price and speed patterns in body text
                body_text = page.inner_text('body')
                prices = re.findall(r'\$\s*(\d+(?:\.\d{2})?)\s*/?\s*(?:mth|month|mo)', body_text, re.IGNORECASE)
                print(f"\nPrices ($X/mth): {prices[:15]}")
                speeds = re.findall(r'(\d+)\s*(?:Mbps|mbps)', body_text)
                print(f"Speeds (X Mbps): {speeds[:15]}")

            except Exception as e:
                print(f"ERROR: {e}")
            finally:
                page.close()

        browser.close()


if __name__ == '__main__':
    investigate()
