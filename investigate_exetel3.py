"""Deep inspection of Exetel CMSPlanCardBroadband and mobile page."""
from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page

PAGES = {
    'nbn': 'https://www.exetel.com.au/broadband/nbn',
    'fibre_upgrade': 'https://www.exetel.com.au/broadband/nbn-fibre-upgrade',
    'mobile': 'https://www.exetel.com.au/mobilephone',
}

with sync_playwright() as p:
    browser = create_stealth_browser(p)

    for key, url in PAGES.items():
        print(f'\n{"="*60}')
        print(f'PAGE: {key} — {url}')
        print('='*60)
        page = create_stealth_page(browser)
        page.goto(url, timeout=40000, wait_until='domcontentloaded')
        page.wait_for_timeout(6000)

        # Try broadband cards
        bb_cards = page.query_selector_all('[data-component="CMSPlanCardBroadband"]')
        mob_cards = page.query_selector_all('[data-component="CMSPlanMobile"]')
        print(f'CMSPlanCardBroadband: {len(bb_cards)} | CMSPlanMobile: {len(mob_cards)}')

        for label, cards in [('BROADBAND', bb_cards), ('MOBILE', mob_cards)]:
            for i, card in enumerate(cards[:8]):
                text = card.inner_text().strip()
                if not text:
                    continue
                print(f'\n  [{label} Card {i}]')
                print(f'  text: {repr(text[:300])}')
                
                # Sub-selectors
                h3_els = card.query_selector_all('h3')
                h4_els = card.query_selector_all('h4')
                span_els = card.query_selector_all('span')
                p_els = card.query_selector_all('p')
                
                if h3_els:
                    print(f'  h3: {[e.inner_text().strip()[:60] for e in h3_els]}')
                if h4_els:
                    print(f'  h4: {[e.inner_text().strip()[:60] for e in h4_els]}')
                if span_els:
                    print(f'  spans: {[e.inner_text().strip()[:40] for e in span_els[:6]]}')
                if p_els:
                    print(f'  p: {[e.inner_text().strip()[:60] for e in p_els[:3]]}')

        page.close()

    browser.close()
    print('\nDone.')
