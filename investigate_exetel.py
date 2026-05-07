"""
Investigation script for Exetel website structure.
Saves HTML of all 3 pages to output/investigation/ for selector analysis.
"""
import os
import json
from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page

PAGES = {
    'exetel_nbn': 'https://www.exetel.com.au/broadband/nbn',
    'exetel_fibre_upgrade': 'https://www.exetel.com.au/broadband/nbn-fibre-upgrade',
    'exetel_mobile': 'https://www.exetel.com.au/mobilephone',
}

OUT_DIR = os.path.join('output', 'investigation')
os.makedirs(OUT_DIR, exist_ok=True)

with sync_playwright() as p:
    browser = create_stealth_browser(p)

    for key, url in PAGES.items():
        page = create_stealth_page(browser)
        try:
            print(f"\n[{key}] Navigating to {url}")
            resp = page.goto(url, timeout=40000, wait_until='domcontentloaded')
            print(f"  Status: {resp.status if resp else 'none'}")
            page.wait_for_timeout(6000)

            # Save full HTML
            html = page.content()
            html_path = os.path.join(OUT_DIR, f'{key}.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"  HTML saved → {html_path} ({len(html)} chars)")

            # Try common plan-card selectors and report what's found
            selectors_to_try = [
                '[class*="plan-card"]',
                '[class*="PlanCard"]',
                '[class*="plan_card"]',
                '[class*="planCard"]',
                '[class*="product-card"]',
                '[class*="plan-tile"]',
                '[class*="plan-item"]',
                '[class*="broadband-plan"]',
                '[class*="nbn-plan"]',
                '.plan',
                'article',
                '[class*="price"]',
                '[class*="speed"]',
            ]

            findings = {}
            for sel in selectors_to_try:
                try:
                    els = page.query_selector_all(sel)
                    if els:
                        findings[sel] = len(els)
                        sample = els[0].inner_text()[:120].replace('\n', ' ')
                        print(f"  ✓ {sel}: {len(els)} elements | sample: {sample!r}")
                except Exception:
                    pass

            # Save findings
            findings_path = os.path.join(OUT_DIR, f'{key}_selectors.json')
            with open(findings_path, 'w') as f:
                json.dump(findings, f, indent=2)

        except Exception as e:
            print(f"  ERROR: {e}")
        finally:
            page.close()

    browser.close()

print("\n✅ Investigation complete. Check output/investigation/ for HTML files.")
