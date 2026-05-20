"""
investigate_mate.py
-------------------
Diagnostic script: dump the HTML structure from MATE's NBN plans pages.
https://www.letsbemates.com.au/nbn/  -- landing page (links to individual plan sub-pages)
Each plan lives on its own sub-page under /mate/<plan-slug>/

Outputs per page:
  1. Lines containing $, Mbps, /mth, /month
  2. Hit-counts for every candidate CSS selector
  3. Per-element detail for the most promising selectors
  4. Raw HTML snippets around dollar-sign occurrences
  5. Card-by-card inner text + sub-selector drill-down for best candidates
  6. outerHTML of the first best-candidate card element
"""

import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright

# -- URLs to investigate -----------------------------------------------------
# Landing page first, then each individual plan sub-page
LANDING_URL = 'https://www.letsbemates.com.au/nbn/'

PLAN_URLS = [
    ('crikey',         'https://www.letsbemates.com.au/mate/crikey-nbn-25-10/'),
    ('ripper',         'https://www.letsbemates.com.au/mate/ripper-nbn-50-20/'),
    ('no_worries_100', 'https://www.letsbemates.com.au/mate/no-worries-100-20/'),
    ('you_beaut',      'https://www.letsbemates.com.au/mate/you-beaut-100-40/'),
    ('no_worries_500', 'https://www.letsbemates.com.au/mate/no-worries-500-50/'),
    ('fair_dinkum',    'https://www.letsbemates.com.au/mate/fair-dinkum-750-50/'),
    ('flamin_fast',    'https://www.letsbemates.com.au/mate/flamin-fast-1000-100/'),
]

# -- candidate selectors to count --------------------------------------------
SELECTORS_TO_COUNT = [
    # generic plan-card patterns
    '[class*="plan"]',
    '[class*="Plan"]',
    '[class*="card"]',
    '[class*="Card"]',
    '[class*="pricing"]',
    '[class*="Pricing"]',
    '[class*="package"]',
    '[class*="Package"]',
    '[class*="product"]',
    '[class*="Product"]',
    '[class*="tier"]',
    '[class*="Tier"]',
    '[class*="speed"]',
    '[class*="Speed"]',
    '[class*="price"]',
    '[class*="Price"]',
    '[class*="promo"]',
    '[class*="Promo"]',
    '[class*="offer"]',
    '[class*="Offer"]',
    '[class*="hero"]',
    '[class*="Hero"]',
    # structural
    'article',
    'section',
    'table',
    'tr',
    # data attributes
    '[data-plan]',
    '[data-product]',
    '[data-testid]',
    '[data-component]',
    '[data-cy]',
    # common React / Next.js / CMS patterns
    '.MuiCard-root',
    '.sc-plan',
    '.product-card',
    '.plan-card',
    '.nbn-plan',
    '.plan-tile',
    '.pricing-card',
    '.price-box',
]

# -- sub-selectors to drill into any matching card container -----------------
SUB_SELECTORS = [
    'h1', 'h2', 'h3', 'h4', 'h5',
    '[class*="title"]',
    '[class*="Title"]',
    '[class*="name"]',
    '[class*="Name"]',
    '[class*="price"]',
    '[class*="Price"]',
    '[class*="speed"]',
    '[class*="Speed"]',
    '[class*="promo"]',
    '[class*="Promo"]',
    '[class*="discount"]',
    '[class*="Discount"]',
    '[class*="badge"]',
    '[class*="Badge"]',
    '[class*="label"]',
    '[class*="Label"]',
    '[class*="period"]',
    '[class*="Period"]',
    '[class*="month"]',
    '[class*="Month"]',
    'button',
    'a',
    'span',
    'p',
]

# -- deep-dive selectors (subset to inspect in detail) -----------------------
DEEP_SELECTORS = [
    '[class*="plan"]',
    '[class*="Plan"]',
    '[class*="card"]',
    '[class*="Card"]',
    '[class*="pricing"]',
    '[class*="price"]',
    '[class*="Price"]',
    '[class*="product"]',
    'article',
    'section',
]


# ---------------------------------------------------------------------------
def investigate_page(page, url: str, label: str):
    """Run full investigation on a single page."""
    print(f"\n{'='*70}")
    print(f"INVESTIGATING [{label}]: {url}")
    print('='*70)

    print(f"\n[1/6] Navigating ...")
    try:
        resp = page.goto(url, timeout=45000, wait_until='networkidle')
        status = resp.status if resp else 'none'
        print(f"      HTTP status : {status}")
    except Exception as e:
        print(f"      goto() error: {e}")
        print("      Retrying with domcontentloaded ...")
        try:
            page.goto(url, timeout=45000, wait_until='domcontentloaded')
        except Exception as e2:
            print(f"      Retry failed: {e2}")
            return

    # Extra wait for React / Next.js hydration
    page.wait_for_timeout(5000)
    print(f"      Page title  : {page.title()}")
    print(f"      Final URL   : {page.url}")

    # -- 1. price/speed lines from body text ---------------------------------
    body_text = page.inner_text('body')
    lines = body_text.split('\n')
    plan_lines = [
        l.strip() for l in lines
        if (
            '$' in l or 'Mbps' in l or 'mbps' in l
            or '/mth' in l or '/month' in l or 'month' in l.lower()
            or 'promo' in l.lower() or 'discount' in l.lower()
            or 'speed' in l.lower() or 'upload' in l.lower()
            or 'download' in l.lower()
        )
        and l.strip()
    ]
    print(f"\n[2/6] Lines with $, Mbps, /mth, promo, speed  (first 80):")
    for l in plan_lines[:80]:
        print(f"      {repr(l)}")

    # -- 2. selector counts --------------------------------------------------
    print(f"\n[3/6] Selector hit-counts (non-zero only):")
    hits = {}
    for sel in SELECTORS_TO_COUNT:
        try:
            els = page.query_selector_all(sel)
            if els:
                hits[sel] = len(els)
                print(f"      {sel:45s}  {len(els)}")
        except Exception:
            pass

    if not hits:
        print("      (no selectors matched)")

    # -- 3. top-3 elements for deep selectors --------------------------------
    print(f"\n[4/6] Top-3 elements for promising selectors:")
    for sel in DEEP_SELECTORS:
        if sel not in hits:
            continue
        try:
            els = page.query_selector_all(sel)
            if not els:
                continue
            print(f"\n  === {sel}  ({len(els)} total) ===")
            for i, el in enumerate(els[:3]):
                txt = el.inner_text().strip()[:300].replace('\n', ' | ')
                cls = el.get_attribute('class') or ''
                tag = el.evaluate('e => e.tagName')
                print(f"    [{i}] <{tag}> class='{cls[:80]}'")
                print(f"         text={repr(txt)}")
        except Exception as e:
            print(f"  {sel}: ERROR {e}")

    # -- 4. raw HTML snippets around $ signs ---------------------------------
    print(f"\n[5/6] Raw HTML snippets near price values (first 6):")
    html = page.content()
    matches = list(re.finditer(r'.{200}\$\d+.{200}', html, re.DOTALL))
    for i, m in enumerate(matches[:6]):
        snippet = m.group(0).replace('\n', ' ')
        print(f"\n  [match {i}]  {snippet[:500]}")

    # -- 5. card-level deep dive ---------------------------------------------
    print(f"\n{'='*70}")
    print("CARD-LEVEL DEEP DIVE")
    print('='*70)

    # Candidates: selectors that matched 1-25 elements (likely plan cards)
    candidates = {
        sel: cnt for sel, cnt in hits.items()
        if 1 <= cnt <= 25
    }
    print(f"\nCandidates with 1-25 elements: {candidates}")

    for sel, cnt in list(candidates.items())[:5]:
        try:
            cards = page.query_selector_all(sel)
            print(f"\n\n>>> Diving into selector: {sel}  ({cnt} elements)")
            for i, card in enumerate(cards[:6]):
                cls  = card.get_attribute('class') or ''
                tag  = card.evaluate('e => e.tagName')
                full = card.inner_text().strip()
                print(f"\n  --- Card [{i}]  <{tag}> class='{cls[:100]}'")
                print(f"      FULL TEXT: {repr(full[:500])}")
                # Sub-selector drill-down
                for sub in SUB_SELECTORS:
                    try:
                        subs = card.query_selector_all(sub)
                        for j, sub_el in enumerate(subs[:3]):
                            stxt = sub_el.inner_text().strip()
                            scls = sub_el.get_attribute('class') or ''
                            if stxt:
                                print(f"      [{sub}][{j}] class='{scls[:60]}' => {repr(stxt[:150])}")
                    except Exception:
                        pass
        except Exception as e:
            print(f"  ERROR diving {sel}: {e}")

    # -- 6. outerHTML of first best-candidate card ---------------------------
    print(f"\n[6/6] outerHTML of first best-candidate card:")
    if candidates:
        best_sel = next(iter(candidates))
        try:
            cards = page.query_selector_all(best_sel)
            if cards:
                outer = cards[0].evaluate('el => el.outerHTML')
                print(f"\n  Selector: '{best_sel}'")
                print(f"  outerHTML (first 5000 chars):")
                print(outer[:5000])
        except Exception as e:
            print(f"  outerHTML error: {e}")
    else:
        print("  (no candidates found -- dumping full page text instead)")
        print(body_text[:3000])


# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("MATE NBN Investigation Script")
    print("=" * 70)
    print(f"Landing page : {LANDING_URL}")
    print(f"Plan pages   : {len(PLAN_URLS)} sub-pages to investigate")

    with sync_playwright() as p:
        browser = create_stealth_browser(p)

        # -- Step A: investigate the landing page to confirm plan links -------
        print(f"\n\n{'#'*70}")
        print("# STEP A -- LANDING PAGE")
        print(f"{'#'*70}")
        page = create_stealth_page(browser)
        try:
            investigate_page(page, LANDING_URL, 'landing')

            # Also extract all href links that look like plan sub-pages
            print(f"\n[BONUS] All /mate/ href links found on landing page:")
            links = page.query_selector_all('a[href*="/mate/"]')
            seen_hrefs = set()
            for link in links:
                href = link.get_attribute('href') or ''
                text = link.inner_text().strip()
                if href and href not in seen_hrefs:
                    seen_hrefs.add(href)
                    print(f"  {repr(text[:60]):55s}  {href}")
        finally:
            page.close()

        # -- Step B: investigate each individual plan sub-page ----------------
        print(f"\n\n{'#'*70}")
        print("# STEP B -- INDIVIDUAL PLAN PAGES (first 3 in full detail)")
        print(f"{'#'*70}")

        # Investigate first 3 plan pages in full detail to confirm selectors
        for label, url in PLAN_URLS[:3]:
            page = create_stealth_page(browser)
            try:
                investigate_page(page, url, label)
            finally:
                page.close()

        # -- Step C: quick text-only scan of remaining 4 plan pages ----------
        print(f"\n\n{'#'*70}")
        print("# STEP C -- QUICK SCAN: remaining 4 plan pages (text + prices only)")
        print(f"{'#'*70}")

        for label, url in PLAN_URLS[3:]:
            page = create_stealth_page(browser)
            try:
                print(f"\n--- [{label}] {url}")
                try:
                    resp = page.goto(url, timeout=45000, wait_until='networkidle')
                except Exception:
                    resp = page.goto(url, timeout=45000, wait_until='domcontentloaded')
                page.wait_for_timeout(4000)
                status = resp.status if resp else 'none'
                print(f"    HTTP {status} | title: {page.title()}")

                body = page.inner_text('body')
                price_lines = [
                    l.strip() for l in body.split('\n')
                    if ('$' in l or 'Mbps' in l or '/mth' in l or 'month' in l.lower())
                    and l.strip()
                ]
                print(f"    Price/speed lines ({len(price_lines)} found):")
                for l in price_lines[:30]:
                    print(f"      {repr(l)}")

                # Grab first $ value from raw HTML as a sanity check
                html = page.content()
                first_price = re.search(r'\$(\d+\.?\d*)', html)
                if first_price:
                    print(f"    First $ value in HTML: ${first_price.group(1)}")

            except Exception as e:
                print(f"    ERROR: {e}")
            finally:
                page.close()

        browser.close()

    print(f"\n\n{'='*70}")
    print("Investigation complete.")
    print("Next step: create providers/mate.py using confirmed selectors above.")
    print('='*70)


if __name__ == '__main__':
    main()
