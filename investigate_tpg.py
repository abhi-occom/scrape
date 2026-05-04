"""
Investigate TPG website structure for plan scraping.
Dumps HTML and inspects selectors across all 5 TPG plan pages.
"""
import sys
import os
import json
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page

TPG_PAGES = {
    'nbn': 'https://www.tpg.com.au/nbn',
    'fibre_upgrade': 'https://www.tpg.com.au/nbn/fibre-upgrade',
    'home_wireless': 'https://www.tpg.com.au/home-wireless-broadband',
    '5g_home': 'https://www.tpg.com.au/5g-home-broadband',
    'fttb': 'https://www.tpg.com.au/fttb',
}

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output', 'investigation')
os.makedirs(OUTPUT_DIR, exist_ok=True)


def investigate():
    with sync_playwright() as p:
        browser = create_stealth_browser(p)

        for page_key, url in TPG_PAGES.items():
            print(f"\n{'='*60}")
            print(f"Investigating: {page_key} -- {url}")
            print(f"{'='*60}")

            page = create_stealth_page(browser)
            try:
                resp = page.goto(url, timeout=30000, wait_until="domcontentloaded")
                print(f"Status: {resp.status if resp else 'none'}")
                page.wait_for_timeout(6000)

                # Save full HTML
                html = page.content()
                html_path = os.path.join(OUTPUT_DIR, f"tpg_{page_key}.html")
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html)
                print(f"HTML saved: {html_path} ({len(html)} chars)")

                # Check for JSON-LD
                json_ld_scripts = page.query_selector_all('script[type="application/ld+json"]')
                print(f"\nJSON-LD scripts: {len(json_ld_scripts)}")
                for i, script in enumerate(json_ld_scripts):
                    text = script.inner_text()
                    try:
                        data = json.loads(text)
                        dtype = data.get('@type', 'unknown')
                        print(f"  [{i}] type={dtype}, keys={list(data.keys())[:8]}")
                        if dtype in ('Product', 'ProductGroup', 'ItemList', 'OfferCatalog'):
                            print(f"       Full data: {json.dumps(data, indent=2)[:800]}")
                    except Exception:
                        print(f"  [{i}] parse error: {text[:100]}")

                # Look for common plan card patterns
                selectors_to_try = [
                    '.plan-card', '.product-card',
                    '[class*="plan-card"]', '[class*="product-card"]',
                    '[class*="PlanCard"]', '[class*="ProductCard"]',
                    '[data-testid*="plan"]', '[data-testid*="product"]',
                    '[class*="nbn-plan"]', '[class*="broadband"]',
                    '.card', '[class*="pricing"]', '[class*="tier"]',
                    'div[class*="plan"]', 'div[class*="price"]',
                    # Drupal-style field wrappers (TPG uses Drupal)
                    '.field--name-field-plans',
                    '.paragraph--type--plan',
                    '.paragraph--type--plan-card',
                    '[class*="paragraph--type"]',
                    '.node--type-plan',
                    '.views-row',
                ]

                print(f"\nSelector scan:")
                for sel in selectors_to_try:
                    try:
                        els = page.query_selector_all(sel)
                        if els:
                            first_text = els[0].inner_text()[:150].replace('\n', ' | ')
                            print(f"  YES {sel}: {len(els)} elements -- \"{first_text}\"")
                    except Exception:
                        pass

                # Find h3 headings (plan names on TPG)
                for tag in ['h3']:
                    headings = page.query_selector_all(tag)
                    if headings:
                        print(f"\n{tag} headings ({len(headings)}):")
                        for h in headings[:12]:
                            text = h.inner_text().strip()[:80]
                            cls = h.get_attribute('class') or ''
                            parent_cls = h.evaluate('el => el.parentElement?.className || ""')
                            grandparent_cls = h.evaluate('el => el.parentElement?.parentElement?.className || ""')
                            print(f"  \"{text}\" | class={cls} | parent={parent_cls[:60]} | gp={grandparent_cls[:60]}")

                # Dump all class names containing plan/price/speed/card keywords
                interesting_classes = page.evaluate("""() => {
                    const results = {};
                    const keywords = ['plan', 'price', 'speed', 'card', 'tier', 'product', 'offer', 'paragraph'];
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

                # Find the container around h3 plan names to understand card structure
                print(f"\nH3-ancestor analysis (first plan-like h3):")
                plan_h3s = page.query_selector_all('h3')
                for h3 in plan_h3s[:8]:
                    text = h3.inner_text().strip()
                    if any(kw in text.upper() for kw in ['NBN', 'FTTB', '5G', 'WIRELESS', 'SUPERFAST', 'ULTRAFAST']):
                        ancestor_info = h3.evaluate("""el => {
                            let info = [];
                            let cur = el;
                            for (let i = 0; i < 5; i++) {
                                cur = cur.parentElement;
                                if (!cur) break;
                                info.push({
                                    tag: cur.tagName.toLowerCase(),
                                    cls: (cur.className || '').substring(0, 80),
                                    childCount: cur.children.length
                                });
                            }
                            return info;
                        }""")
                        print(f"  \"{text}\":")
                        for a in ancestor_info:
                            print(f"    {a['tag']}.{a['cls']} (children={a['childCount']})")
                        break

            except Exception as e:
                print(f"ERROR: {e}")
            finally:
                page.close()

        browser.close()


if __name__ == '__main__':
    investigate()
