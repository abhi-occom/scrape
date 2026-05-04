"""Deep-inspect TPG NBN, 5G, and FTTB page plan card structures."""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page


def inspect_nbn(browser):
    print("\n=== NBN PAGE ===")
    page = create_stealth_page(browser)
    page.goto('https://www.tpg.com.au/nbn', timeout=30000, wait_until='domcontentloaded')
    page.wait_for_timeout(6000)

    # JSON-LD
    scripts = page.query_selector_all('script[type="application/ld+json"]')
    for s in scripts:
        data = json.loads(s.inner_text())
        if 'offers' in data:
            print(f"JSON-LD offers: {json.dumps(data['offers'], indent=2)[:800]}")

    # NBN plan cards
    nbn_cards = page.query_selector_all('.planLabels.nbnLabels')
    print(f"\nnbnLabels cards: {len(nbn_cards)}")

    for card in nbn_cards:
        parent = card.evaluate_handle('el => el.closest(".planCards")')
        name_el = card.query_selector('h3.name')
        name = name_el.inner_text().strip() if name_el else '?'

        dl_el = card.query_selector('.download-speed')
        ul_el = card.query_selector('.upload-speed')
        dl = dl_el.inner_text().strip() if dl_el else '?'
        ul = ul_el.inner_text().strip() if ul_el else '?'

        # Get price from the planCards parent
        parent_text = parent.inner_text()
        # Price pattern: "$ XX /mth .YY" or promo + regular
        price_match = re.search(r'then\s*\$?([\d.]+)/mth', parent_text)
        promo_match = re.search(r'\$?\s*(\d+)\s*/mth\s*\.(\d+)', parent_text)
        regular = price_match.group(1) if price_match else '?'
        promo = f"{promo_match.group(1)}.{promo_match.group(2)}" if promo_match else '?'

        period_match = re.search(r'(?:first|for)\s+(\d+)\s+months?', parent_text, re.I)
        period = f"{period_match.group(1)} months" if period_match else '?'

        print(f"  {name}: dl={dl} ul={ul} promo=${promo} regular=${regular} period={period}")

    page.close()


def inspect_5g(browser):
    print("\n=== 5G PAGE ===")
    page = create_stealth_page(browser)
    page.goto('https://www.tpg.com.au/5g-home-broadband', timeout=30000, wait_until='domcontentloaded')
    page.wait_for_timeout(6000)

    # JSON-LD
    scripts = page.query_selector_all('script[type="application/ld+json"]')
    for s in scripts:
        data = json.loads(s.inner_text())
        if 'offers' in data:
            print(f"JSON-LD offers: {json.dumps(data['offers'], indent=2)[:800]}")

    # Plans div content
    plans_div = page.query_selector('div.plans')
    if plans_div:
        text = plans_div.inner_text()
        print(f"\nPlans div text ({len(text)} chars):\n{text[:800]}")

    # Check plntbl elements
    plan_types = page.query_selector_all('p.plntbl__planType')
    for pt in plan_types:
        container = pt.evaluate_handle('el => el.closest("div[class*=plntbl]") || el.parentElement.parentElement')
        ct = container.inner_text()
        print(f"\nPlan type: {pt.inner_text().strip()}")
        print(f"  Container text: {ct[:300]}")

    page.close()


def inspect_home_wireless(browser):
    print("\n=== HOME WIRELESS PAGE ===")
    page = create_stealth_page(browser)
    page.goto('https://www.tpg.com.au/home-wireless-broadband', timeout=30000, wait_until='domcontentloaded')
    page.wait_for_timeout(6000)

    # JSON-LD
    scripts = page.query_selector_all('script[type="application/ld+json"]')
    for s in scripts:
        data = json.loads(s.inner_text())
        if 'offers' in data:
            print(f"JSON-LD offers: {json.dumps(data['offers'], indent=2)[:800]}")

    # Plans div
    plans_div = page.query_selector('div.plans')
    if plans_div:
        text = plans_div.inner_text()
        print(f"\nPlans div text ({len(text)} chars):\n{text[:600]}")

    # Speeds
    speeds = page.query_selector_all('.plntbl__speeds')
    for sp in speeds:
        print(f"Speed: {sp.inner_text().strip()}")

    page.close()


def inspect_fttb(browser):
    print("\n=== FTTB PAGE ===")
    page = create_stealth_page(browser)
    page.goto('https://www.tpg.com.au/fttb', timeout=30000, wait_until='domcontentloaded')
    page.wait_for_timeout(6000)

    cards = page.query_selector_all('.plan-card')
    print(f"Plan cards: {len(cards)}")

    for card in cards:
        text = card.inner_text()
        # Extract name
        name_el = card.query_selector('h3') or card.query_selector('.plan-name') or card.query_selector('strong')
        dl_el = card.query_selector('.download-speed')
        ul_el = card.query_selector('.upload-speed')

        name = '?'
        if name_el:
            name = name_el.inner_text().strip()
        else:
            m = re.search(r'(FTTB\w+)', text)
            name = m.group(1) if m else '?'

        dl = dl_el.inner_text().strip() if dl_el else '?'
        ul = ul_el.inner_text().strip() if ul_el else '?'

        promo_match = re.search(r'\$\s*(\d+)\s*/mth', text)
        regular_match = re.search(r'then\s*\$?([\d.]+)/mth', text)
        promo = promo_match.group(1) if promo_match else '?'
        regular = regular_match.group(1) if regular_match else '?'

        print(f"\n  {name}: dl={dl} ul={ul} promo=${promo} regular=${regular}")
        print(f"  Full text: {text[:250].replace(chr(10), ' | ')}")

    page.close()


with sync_playwright() as p:
    browser = create_stealth_browser(p)
    inspect_nbn(browser)
    inspect_5g(browser)
    inspect_home_wireless(browser)
    inspect_fttb(browser)
    browser.close()
