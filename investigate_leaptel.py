"""Deep inspection of Leaptel plan pages to identify selectors and data structure."""
from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page

PAGES = {
    'nbn': 'https://leaptel.com.au/plans/?provider=nbn',
    'optus_wholesale': 'https://leaptel.com.au/plans/?provider=opt',
    'redline_wholesale': 'https://leaptel.com.au/plans/?provider=red',
    'fixed_wireless': 'https://leaptel.com.au/fixed-wireless/',
    'free_fibre_upgrade': 'https://leaptel.com.au/free-fibre-upgrade/',
}

with sync_playwright() as p:
    browser = create_stealth_browser(p)

    for key, url in PAGES.items():
        print(f'\n{"="*70}')
        print(f'PAGE: {key} — {url}')
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
            ]

            print('\nSearching for plan card containers...')
            found_containers = False

            for selector in selectors_to_try:
                try:
                    cards = page.query_selector_all(selector)
                    if cards and len(cards) > 0:
                        print(f'\n[OK] Found {len(cards)} elements with selector: {selector}')
                        found_containers = True

                        for i, card in enumerate(cards[:5]):
                            text = card.inner_text().strip()
                            if text:
                                print(f'\n  [Card {i}]')
                                print(f'  Text preview: {repr(text[:200])}...')

                                # Check for common nested elements
                                h2_els = card.query_selector_all('h2, h3, h4')
                                span_els = card.query_selector_all('span')
                                button_els = card.query_selector_all('button')
                                p_els = card.query_selector_all('p')

                                if h2_els or h3_els or h4_els:
                                    headers = [e.inner_text().strip()[:50] for e in h2_els]
                                    print(f'  Headers: {headers}')

                                if span_els:
                                    spans = [e.inner_text().strip()[:40] for e in span_els[:8]]
                                    print(f'  Spans: {spans}')

                                if p_els:
                                    paragraphs = [e.inner_text().strip()[:60] for e in p_els[:3]]
                                    print(f'  Paragraphs: {paragraphs}')

                                # Check for price/speed patterns
                                all_text = card.inner_text()
                                if '$' in all_text:
                                    price_lines = [line.strip() for line in all_text.split('\n') if '$' in line]
                                    print(f'  Price lines: {price_lines[:3]}')

                                if 'Mbps' in all_text or 'mbps' in all_text:
                                    speed_lines = [line.strip() for line in all_text.split('\n') if 'mbps' in line.lower()]
                                    print(f'  Speed lines: {speed_lines[:3]}')
                except:
                    pass

            if not found_containers:
                print('\n[WARN] No plan containers found with common selectors.')
                print('Showing general page structure:')
                main_content = page.query_selector('main')
                if main_content:
                    print(f'Found <main> tag')
                    main_text = main_content.inner_text()[:500]
                    print(f'Content preview: {repr(main_text)}')

        except Exception as e:
            print(f'[ERROR] Error loading page: {str(e)}')

        finally:
            page.close()

    browser.close()
    print('\n' + '='*70)
    print('Investigation complete.')
