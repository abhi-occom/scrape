"""Probe the .plans-wrapper element structure for wireless and fibre_upgrade pages."""
from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page
import re

PAGES = {
    'wireless': 'https://www.iinet.net.au/internet-product/broadband/nbn/plans/wireless',
    'fibre_upgrade': 'https://www.iinet.net.au/internet-product/nbn/fibre-upgrade',
}

with sync_playwright() as p:
    browser = create_stealth_browser(p)

    for key, url in PAGES.items():
        print(f'\n{"="*70}')
        print(f'PAGE: {key}')
        print('='*70)
        page = create_stealth_page(browser)
        try:
            page.goto(url, timeout=40000, wait_until='domcontentloaded')
            page.wait_for_timeout(8000)

            if key == 'wireless':
                # Examine .plans-wrapper and children
                wrapper = page.query_selector('.plans-wrapper')
                if wrapper:
                    children = wrapper.query_selector_all(':scope > *')
                    print(f'.plans-wrapper direct children: {len(children)}')
                    for i, child in enumerate(children[:10]):
                        tag = child.evaluate('el => el.tagName')
                        cls = child.get_attribute('class') or ''
                        txt = child.inner_text().strip()[:100]
                        print(f'  child {i}: <{tag}> class={cls!r} text={repr(txt)}')

                    # Try finding plan items inside
                    items = wrapper.query_selector_all('[class*="plan"]')
                    print(f'\n.plans-wrapper [class*=plan] count: {len(items)}')
                    for i, item in enumerate(items[:5]):
                        cls = item.get_attribute('class') or ''
                        txt = item.inner_text().strip()[:150]
                        if 'Mbps' in txt or '$' in txt:
                            print(f'  [{i}] class={cls!r}')
                            print(f'       text={repr(txt)}')

                    # Look for the single selected plan card
                    plan_items = wrapper.query_selector_all('[class*="plan-item"]')
                    print(f'\n[class*=plan-item] count: {len(plan_items)}')
                    for i, item in enumerate(plan_items[:5]):
                        cls = item.get_attribute('class') or ''
                        txt = item.inner_text().strip()[:200]
                        print(f'  [{i}] class={cls!r}')
                        print(f'       text={repr(txt)}')

            if key == 'fibre_upgrade':
                # Check for any plan cards on fibre upgrade page
                body_text = page.evaluate('() => document.body.innerText')
                print('Body text (first 1500 chars):')
                print(repr(body_text[:1500]))

                # Check .card elements
                cards = page.query_selector_all('.card')
                print(f'\n.card count: {len(cards)}')
                for i, card in enumerate(cards[:5]):
                    h3s = [h.inner_text().strip() for h in card.query_selector_all('h3')]
                    txt = card.inner_text().strip()[:100]
                    if 'NBN' in txt or 'Mbps' in txt or '$' in txt:
                        print(f'  [{i}] h3={h3s} text={repr(txt)}')

        except Exception as e:
            print(f'ERROR: {e}')
        finally:
            page.close()

    browser.close()
    print('\nProbe 4 complete.')
