"""Deep-inspect Vodafone plan card structures."""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page


def inspect_page(browser, url, label):
    print(f"\n{'='*60}")
    print(f"{label}: {url}")
    print(f"{'='*60}")
    page = create_stealth_page(browser)
    page.goto(url, timeout=30000, wait_until='domcontentloaded')
    page.wait_for_timeout(6000)

    # data-testid plan cards
    plan_cards = page.query_selector_all('[data-testid*="plan-card"]')
    print(f"data-testid plan-card elements: {len(plan_cards)}")
    for i, card in enumerate(plan_cards[:8]):
        testid = card.get_attribute('data-testid') or ''
        text = card.inner_text()[:300].replace('\n', ' | ')
        print(f"  [{i}] testid={testid}")
        print(f"      text: {text}")

    # Look for plan tiles more broadly
    if not plan_cards:
        cards = page.query_selector_all('.card')
        print(f"\n.card elements: {len(cards)}")
        for i, card in enumerate(cards[:8]):
            text = card.inner_text()[:300].replace('\n', ' | ')
            cls = card.get_attribute('class') or ''
            print(f"  [{i}] class={cls[:80]}")
            print(f"      text: {text}")

    # Check for specific data-testid patterns
    all_testids = page.evaluate("""() => {
        const results = {};
        document.querySelectorAll('[data-testid]').forEach(el => {
            const tid = el.getAttribute('data-testid');
            if (tid && (tid.includes('plan') || tid.includes('price') || tid.includes('speed'))) {
                const tag = el.tagName.toLowerCase();
                const key = `${tag}[data-testid="${tid}"]`;
                results[key] = (results[key] || 0) + 1;
            }
        });
        return results;
    }""")
    if all_testids:
        print(f"\nRelevant data-testid elements:")
        for k, v in sorted(all_testids.items(), key=lambda x: -x[1])[:30]:
            print(f"  {k}: {v}")

    # Extract first plan card in detail
    first_card = page.query_selector('[data-testid="plan-card-0"]') or page.query_selector('[data-testid*="plan-card"]')
    if first_card:
        print(f"\nFirst plan card detail:")
        # Speed
        speed_el = first_card.query_selector('[data-testid*="speed"]')
        if speed_el:
            print(f"  Speed element: {speed_el.inner_text().strip()[:100]}")

        # Price
        price_el = first_card.query_selector('[data-testid*="price"]')
        if price_el:
            print(f"  Price element: {price_el.inner_text().strip()[:100]}")

        # Plan name
        name_el = first_card.query_selector('[data-testid*="name"]') or first_card.query_selector('[data-testid*="title"]')
        if name_el:
            print(f"  Name element: {name_el.inner_text().strip()[:100]}")

        # All child data-testid elements
        children = first_card.evaluate("""el => {
            const results = [];
            el.querySelectorAll('[data-testid]').forEach(child => {
                results.push({
                    testid: child.getAttribute('data-testid'),
                    tag: child.tagName.toLowerCase(),
                    text: child.innerText.substring(0, 80).replace(/\\n/g, ' | ')
                });
            });
            return results;
        }""")
        print(f"\n  Child data-testid elements ({len(children)}):")
        for c in children[:20]:
            print(f"    {c['tag']}[data-testid=\"{c['testid']}\"] = \"{c['text']}\"")

    page.close()


with sync_playwright() as p:
    browser = create_stealth_browser(p)
    inspect_page(browser, 'https://www.vodafone.com.au/home-internet/nbn', 'NBN')
    inspect_page(browser, 'https://www.vodafone.com.au/home-internet/opticomm', 'OPTICOMM')
    inspect_page(browser, 'https://www.vodafone.com.au/home-internet/4g-5g-plans', '4G/5G')
    inspect_page(browser, 'https://www.vodafone.com.au/home-internet/super-wifi', 'SUPER WIFI')
    browser.close()
