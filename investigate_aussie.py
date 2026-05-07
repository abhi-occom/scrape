"""
Investigate Aussie Broadband website structure using Firefox.
Aussie Broadband uses Cloudflare Turnstile which blocks Chromium — Firefox bypasses it.
Saves HTML and prints selector findings for scraper planning.
"""
import os, sys
sys.path.insert(0, r'C:\Users\IS-ABHISHEK-IN\Desktop\scrape')
os.chdir(r'C:\Users\IS-ABHISHEK-IN\Desktop\scrape')

from playwright.sync_api import sync_playwright

OUT_DIR = os.path.join('output', 'investigation')
os.makedirs(OUT_DIR, exist_ok=True)

PAGES = {
    'aussie_nbn':      'https://www.aussiebroadband.com.au/broadband/nbn/',
    'aussie_wireless': 'https://www.aussiebroadband.com.au/broadband/home-wireless/',
    'aussie_5g':       'https://www.aussiebroadband.com.au/broadband/home-5g/',
}

SELECTORS = [
    '[class*="PlanCard"]', '[class*="plan-card"]', '[class*="planCard"]',
    '[class*="PricingCard"]', '[class*="pricing-card"]',
    '[class*="ProductCard"]', '[class*="product-card"]',
    '[class*="plan-tile"]', '[class*="plan-item"]',
    '[class*="nbn-plan"]', '[class*="broadband"]',
    '[data-testid*="plan"]', '[data-component*="plan"]',
    '[class*="tier"]', '[class*="package"]',
    '[class*="card"]', '[class*="Card"]',
    '[class*="price"]', '[class*="speed"]',
    'article',
]

with sync_playwright() as p:
    browser = p.firefox.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
        viewport={"width": 1280, "height": 720},
        locale="en-AU",
        timezone_id="Australia/Sydney",
    )

    for key, url in PAGES.items():
        page = context.new_page()
        print(f'\n{"="*60}')
        print(f'PAGE: {key}')
        print(f'URL:  {url}')
        print('='*60)

        try:
            resp = page.goto(url, timeout=40000, wait_until='domcontentloaded')
            print(f'Status: {resp.status if resp else "none"}')
            page.wait_for_timeout(12000)  # Extra wait for Cloudflare to clear
            title = page.title()
            print(f'Title: {title}')

            if 'moment' in title.lower() or 'cloudflare' in title.lower():
                print('  ⚠ Still on Cloudflare challenge page — blocked')
                page.close()
                continue

            # Save HTML
            html = page.content()
            html_path = os.path.join(OUT_DIR, f'{key}.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f'HTML saved: {len(html)} chars → {html_path}')

            # Check __NEXT_DATA__ (Next.js embedded JSON)
            next_data_el = page.query_selector('#__NEXT_DATA__')
            if next_data_el:
                text = next_data_el.inner_text()
                print(f'  ✓ __NEXT_DATA__ found: {len(text)} chars')
                # Save it
                nd_path = os.path.join(OUT_DIR, f'{key}_next_data.json')
                with open(nd_path, 'w', encoding='utf-8') as f:
                    f.write(text)
                print(f'    Saved → {nd_path}')
            else:
                print('  ✗ No __NEXT_DATA__')

            # Try selectors
            found = []
            for sel in SELECTORS:
                try:
                    els = page.query_selector_all(sel)
                    if els:
                        sample = els[0].inner_text().strip()[:120].replace('\n', ' | ')
                        print(f'  ✓ {sel}: {len(els)} elements | {repr(sample)}')
                        found.append((sel, els))
                except Exception:
                    pass

            # Deep inspect best candidate (most specific / smallest count)
            if found:
                # Pick the most specific (fewest elements, but > 0)
                best_sel, best_els = min(found, key=lambda x: len(x[1]))
                print(f'\n  --- Deep inspect: {best_sel} ---')
                for i, card in enumerate(best_els[:5]):
                    text = card.inner_text().strip()
                    if not text:
                        continue
                    cls = (card.get_attribute('class') or '')[:80]
                    print(f'\n  [Card {i}] class: {cls}')
                    print(f'  text: {repr(text[:300])}')
                    for sub in ['h2','h3','h4','p','strong','span',
                                '[class*="price"]','[class*="speed"]',
                                '[class*="name"]','[class*="data"]']:
                        try:
                            sub_els = card.query_selector_all(sub)
                            txts = [e.inner_text().strip()[:50]
                                    for e in sub_els[:4] if e.inner_text().strip()]
                            if txts:
                                print(f'    {sub}: {txts}')
                        except Exception:
                            pass

        except Exception as e:
            print(f'  ERROR: {e}')
        finally:
            page.close()

    browser.close()

print('\n✅ Investigation complete. Check output/investigation/')
