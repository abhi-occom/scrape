"""Deep-dive into plan card structure for pages without JSON-LD."""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page
from bs4 import BeautifulSoup

def analyze_page(page, label):
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")

    html = page.content()
    soup = BeautifulSoup(html, 'lxml')

    # Find the #plans section
    plans_sections = soup.find_all(id='plans')
    print(f"  #plans sections: {len(plans_sections)}")

    if not plans_sections:
        return

    # Look at the last #plans (usually the actual plan grid)
    plans_section = plans_sections[-1]

    # Find plan card containers
    # Look for repeating card-like structures with price + speed info
    # Try various card selectors
    for sel_desc, sel in [
        ("border rounded cards", {"class": re.compile(r"border.*rounded|rounded.*border")}),
        ("divs with Mbps text", lambda tag: tag.name == 'div' and tag.find(string=re.compile(r'\d+\s*Mbps'))),
    ]:
        if callable(sel):
            cards = plans_section.find_all(sel)
        else:
            cards = plans_section.find_all(**sel)
        print(f"\n  {sel_desc}: {len(cards)} cards")
        if cards:
            for i, card in enumerate(cards[:3]):
                txt = card.get_text(' | ', strip=True)[:200]
                cls = ' '.join(card.get('class', []))[:80]
                print(f"    [{i}] class='{cls}'")
                print(f"        text: {txt}")

    # Look for h3 elements in #plans (plan tier names)
    h3s = plans_section.find_all('h3')
    print(f"\n  h3 in #plans: {len(h3s)}")
    for h in h3s[:10]:
        cls = ' '.join(h.get('class', []))[:60]
        txt = h.get_text(strip=True)[:60]
        print(f"    <h3 class='{cls}'> {txt}")

    # Find plan card wrapper - look for repeated sibling containers
    # within #plans with Download/Upload/price
    children = plans_section.find_all('div', recursive=False)
    print(f"\n  Direct div children of #plans: {len(children)}")

    # Check for grid/flex containers
    for child in children[:5]:
        cls = ' '.join(child.get('class', []))[:100]
        sub_divs = child.find_all('div', recursive=False)
        print(f"    <div class='{cls}'> ({len(sub_divs)} direct divs)")

    # Try to find individual plan columns
    # Looking for elements that contain BOTH speed AND price info
    all_divs = plans_section.find_all('div')
    plan_divs = []
    for div in all_divs:
        text = div.get_text(' ', strip=True)
        has_speed = bool(re.search(r'\d+\s*Mbps', text))
        has_price = bool(re.search(r'\$\d+', text))
        has_download = 'Download' in text
        # Only if it's a reasonably sized block (not the whole section)
        if has_speed and has_price and has_download and len(text) < 800:
            plan_divs.append(div)

    # Deduplicate by picking only the smallest container for each plan
    print(f"\n  Plan-containing divs (speed+price+download): {len(plan_divs)}")
    # Show unique ones by class
    seen = set()
    for d in plan_divs[:10]:
        cls = ' '.join(d.get('class', []))[:80]
        if cls not in seen:
            seen.add(cls)
            txt = d.get_text(' | ', strip=True)[:200]
            print(f"    class='{cls}'")
            print(f"    text: {txt}")


with sync_playwright() as p:
    browser = create_stealth_browser(p)

    # Flip to Fibre
    page = create_stealth_page(browser)
    page.goto("https://www.superloop.com/flip-to-fibre/", timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    analyze_page(page, "FLIP TO FIBRE")
    page.close()

    # Fixed Wireless
    page = create_stealth_page(browser)
    page.goto("https://www.superloop.com/internet/fixed-wireless/", timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    analyze_page(page, "FIXED WIRELESS")
    page.close()

    # Also check Fibre JSON-LD detail to see network_type
    page = create_stealth_page(browser)
    page.goto("https://www.superloop.com/internet/fibre/", timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    scripts = page.query_selector_all('script[type="application/ld+json"]')
    for s in scripts:
        try:
            data = json.loads(s.inner_text())
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get('@type') == 'ProductGroup':
                    print(f"\n{'='*70}")
                    print("  FIBRE JSON-LD variants")
                    print(f"{'='*70}")
                    for v in item.get('hasVariant', []):
                        print(f"  {v.get('name')}: size={v.get('size')} price=${v.get('offers',{}).get('price')} material={v.get('material',[])} desc={v.get('description','')[:80]}")
        except:
            pass
    page.close()

    browser.close()
print("\nDone.")
