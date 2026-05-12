"""Deep dive into wireless page plan data and fibre_upgrade page plan cards."""
from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page
import re

with sync_playwright() as p:
    browser = create_stealth_browser(p)

    # ── Wireless page: find the plan listing container ──────────────────
    print('=== WIRELESS PAGE ===')
    page = create_stealth_page(browser)
    page.goto('https://www.iinet.net.au/internet-product/broadband/nbn/plans/wireless', timeout=40000, wait_until='domcontentloaded')
    page.wait_for_timeout(8000)

    # The plan text lives inside .plans-wrapper > .inside_container
    inner = page.query_selector('.plans-wrapper .inside_container')
    if inner:
        children = inner.query_selector_all(':scope > *')
        print(f'inside_container children: {len(children)}')
        for i, child in enumerate(children[:15]):
            tag = child.evaluate('el => el.tagName')
            cls = child.get_attribute('class') or ''
            txt = child.inner_text().strip()[:120]
            print(f'  [{i}] <{tag}> class={cls!r}')
            if txt:
                print(f'       text={repr(txt)}')

    # Try plan-tab or plan-section classes
    for sel in ['[class*="plan-tab"]', '[class*="plan-section"]', '[class*="plan-row"]',
                '[class*="planRow"]', '[class*="plan-detail"]', '[ng-controller]']:
        els = page.query_selector_all(sel)
        if els:
            print(f'\n[{sel}] count={len(els)}')
            for i, el in enumerate(els[:3]):
                cls = el.get_attribute('class') or ''
                ng = el.get_attribute('ng-controller') or ''
                txt = el.inner_text().strip()[:100]
                if txt:
                    print(f'  [{i}] class={cls!r} ng-ctrl={ng!r} text={repr(txt)}')
    page.close()

    # ── Fibre upgrade page: find plan cards ─────────────────────────────
    print('\n\n=== FIBRE UPGRADE PAGE ===')
    page = create_stealth_page(browser)
    page.goto('https://www.iinet.net.au/internet-product/nbn/fibre-upgrade', timeout=40000, wait_until='domcontentloaded')
    page.wait_for_timeout(8000)

    # Full body text for context
    body_text = page.evaluate('() => document.body.innerText')
    # Look for plan pricing in body text
    # Find all $XX.XX/mth patterns and context
    price_matches = list(re.finditer(r'\$[\d]+\.?\d*\s*/mth', body_text))
    print(f'Price patterns found: {len(price_matches)}')
    for m in price_matches[:5]:
        start = max(0, m.start() - 100)
        end = min(len(body_text), m.end() + 100)
        print(f'  {repr(body_text[start:end])}')
        print()

    # Check for "Shop nbn plans" section
    idx = body_text.find('Shop nbn')
    if idx >= 0:
        print(f'Shop nbn section: {repr(body_text[idx:idx+300])}')

    # Inspect all .card elements
    cards = page.query_selector_all('.card')
    print(f'\n.card count: {len(cards)}')
    for i, card in enumerate(cards):
        h3s = [h.inner_text().strip() for h in card.query_selector_all('h3')]
        spans = [s.inner_text().strip() for s in card.query_selector_all('span')]
        txt = card.inner_text().strip()
        if '$' in txt and 'mth' in txt:
            print(f'\nCard {i} (has pricing):')
            print(f'  h3s: {h3s}')
            print(f'  spans: {spans[:6]}')
            print(f'  text: {repr(txt[:300])}')

    page.close()
    browser.close()
    print('\nProbe 5 complete.')
