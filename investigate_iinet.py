"""Deep inspection of iinet plan pages to identify selectors and data structure."""
from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page

PAGES = {
    'fibre': 'https://www.iinet.net.au/internet-product/broadband/nbn/plans/fibre',
    'fibre_upgrade': 'https://www.iinet.net.au/internet-product/nbn/fibre-upgrade',
    'wireless': 'https://www.iinet.net.au/internet-product/broadband/nbn/plans/wireless',
}

with sync_playwright() as p:
    browser = create_stealth_browser(p)

    for key, url in PAGES.items():
        print(f'\n{"="*70}')
        print(f'PAGE: {key} -- {url}')
        print('='*70)
        page = create_stealth_page(browser)

        try:
            page.goto(url, timeout=40000, wait_until='domcontentloaded')
            page.wait_for_timeout(6000)

            # Try common plan card selectors
            selectors_to_try = [
                '[data-component*="plan"]',
                '[data-component*="card"]',
                '.plan-card',
                '.plan',
                '.card',
                '[class*="plan"]',
                '[class*="card"]',
                '.pricing-card',
                '.price-card',
                'div[class*="plan-"]',
                '[role="group"]',
                '.product-card',
            ]

            print('\nSearching for plan card containers...')
            found_containers = False

            for selector in selectors_to_try:
                try:
                    cards = page.query_selector_all(selector)
                    if cards and len(cards) > 0:
                        print(f'\n[OK] Found {len(cards)} elements with selector: {selector}')
                        found_containers = True

                        for i, card in enumerate(cards[:3]):
                            text = card.inner_text().strip()
                            if text and len(text) > 20:
                                print(f'\n  [Card {i}]')
                                print(f'  Text preview: {repr(text[:250])}...')

                                # Check for common nested elements
                                headers = card.query_selector_all('h2, h3, h4')
                                spans = card.query_selector_all('span')
                                p_els = card.query_selector_all('p')

                                if headers:
                                    h_text = [e.inner_text().strip()[:50] for e in headers[:3]]
                                    print(f'  Headers: {h_text}')

                                if spans:
                                    sp_text = [e.inner_text().strip()[:40] for e in spans[:5]]
                                    print(f'  Spans: {sp_text}')

                                if p_els:
                                    p_text = [e.inner_text().strip()[:60] for e in p_els[:2]]
                                    print(f'  Paragraphs: {p_text}')

                                # Check for price/speed patterns
                                if '$' in text:
                                    price_lines = [line.strip() for line in text.split('\n') if '$' in line]
                                    print(f'  Price lines: {price_lines[:2]}')

                                if 'Mbps' in text or 'mbps' in text:
                                    speed_lines = [line.strip() for line in text.split('\n') if 'mbps' in line.lower()]
                                    print(f'  Speed lines: {speed_lines[:2]}')
                except:
                    pass

            if not found_containers:
                print('\n[WARN] No plan containers found with common selectors.')
                print('Page structure analysis:')
                page_text = page.evaluate('() => document.body.innerText')
                print(f'Page text (first 500 chars): {repr(page_text[:500])}...')

        except Exception as e:
            print(f'[ERROR] Error loading page: {str(e)}')

        finally:
            page.close()

    browser.close()
    print('\n' + '='*70)
    print('Investigation complete.')
