"""investigate_kogan.py 
-------------------
Diagnostic script: dump the HTML structure from Kogan's internet plans page
https://www.koganinternet.com.au/plans/  — mirrors the pattern of probe_iprimus2.py.

Outputs:
  1. Lines containing $, Mbps, /mth, /month
  2. Hit-counts for every candidate CSS selector
  3. Per-element detail for the most promising selectors
  4. Raw HTML snippets around dollar-sign occurrences
  5. Card-by-card inner text + sub-selector drill-down for .plan_tile / card variants
"""
import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright

URL = 'https://www.koganinternet.com.au/plans/'

# ── candidate selectors to count ────────────────────────────────────────────
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
    # common React/CMS patterns
    '.MuiCard-root',
    '.sc-plan',
    '.product-card',
    '.plan-card',
    '.nbn-plan',
]

# ── sub-selectors to drill into any matching card container ──────────────────
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
    'button',
    'a',
]


def investigate(url: str):
    print(f"\n\n{'='*70}") # type: ignore
    print(f"INVESTIGATING: {url}")
    print('='*70)

    with sync_playwright() as p:
        browser = create_stealth_browser(p)
        page = create_stealth_page(browser)

        print(f"\n[1/5] Navigating …)")
        page.goto(url, timeout=40000, wait_until='domcontentloaded')
        page.wait_for_timeout(6000)   # let JS render
        print(f"      Title: {page.title()}")

        # ── 1. price/speed lines from body text ──────────────────────────────
        body_text = page.inner_text('body')
        lines = body_text.split('\n')
        plan_lines = [
            l.strip() for l in lines
            if ('$' in l or 'Mbps' in l or 'mbps' in l or '/mth' in l or '/month' in l)
            and l.strip()
        ]
        print(f"\n[2/5] Lines containing $ / Mbps / /mth  (first 60):")
        for l in plan_lines[:60]:
            print(f"      {repr(l)}")

        # ── 2. selector counts ───────────────────────────────────────────────
        print(f"\n[3/5] Selector hit-counts (non-zero only):")
        hits = {}
        for sel in SELECTORS_TO_COUNT:
            try:
                els = page.query_selector_all(sel)
                if els:
                    hits[sel] = len(els)
                    print(f"      {sel}: {len(els)}")
            except Exception:
                pass

        # ── 3. top-3 elements for best selectors ────────────────────────────
        DEEP_SELECTORS = [
            '[class*="plan"]', '[class*="card"]', '[class*="pricing"]',
            '[class*="package"]', '[class*="product"]', 'article',
        ]
        print(f"\n[4/5] Top-3 elements for promising selectors:")
        for sel in DEEP_SELECTORS:
            if sel not in hits:
                continue
            try:
                els = page.query_selector_all(sel)
                if not els:
                    continue
                print(f"\n  === {sel}  ({len(els)} total) ===")
                for i, el in enumerate(els[:3]):
                    txt = el.inner_text().strip()[:300].replace('\n', ' ↵ ')
                    cls = el.get_attribute('class') or ''
                    tag = el.evaluate('e => e.tagName')
                    print(f"    [{i}] <{tag}> class='{cls[:80]}'")
                    print(f"         text={repr(txt)}")
            except Exception as e:
                print(f"  {sel}: ERROR {e}")

        # ── 4. raw HTML snippets around $ signs ──────────────────────────────
        print(f"\n[5/5] Raw HTML snippets near price values (first 6):")
        html = page.content()
        matches = list(re.finditer(r'.{300}\$\d+.{300}', html, re.DOTALL))
        for i, m in enumerate(matches[:6]):
            snippet = m.group(0).replace('\n', ' ')
            print(f"\n  [match {i}]  {snippet[:600]}")

        # ── 5. card-level deep dive ──────────────────────────────────────────
        print(f"\n{'='*70}")
        print("CARD-LEVEL DEEP DIVE")
        print('='*70)

        # pick the selector with a "reasonable" count (2-20 elements, likely plan cards)
        candidates = {
            sel: cnt for sel, cnt in hits.items()
            if 2 <= cnt <= 30
        }
        print(f"\nCandidates with 2–30 elements: {candidates}")

        for sel, cnt in list(candidates.items())[:4]:
            try:
                cards = page.query_selector_all(sel)
                print(f"\n\n>>> Diving into selector: {sel}  ({cnt} elements)")
                for i, card in enumerate(cards[:6]):
                    cls   = card.get_attribute('class') or ''
                    tag   = card.evaluate('e => e.tagName')
                    full  = card.inner_text().strip()
                    print(f"\n  --- Card [{i}]  <{tag}> class='{cls[:100]}'")
                    print(f"      FULL TEXT: {repr(full[:400])}")
                    for sub in SUB_SELECTORS:
                        try:
                            subs = card.query_selector_all(sub)
                            for j, sel_el in enumerate(subs[:2]):
                                stxt = sel_el.inner_text().strip()
                                scls = sel_el.get_attribute('class') or ''
                                if stxt:
                                    print(f"      [{sub}][{j}] class='{scls[:60]}' => {repr(stxt[:120])}")
                        except Exception:
                            pass
            except Exception as e:
                print(f"  ERROR diving {sel}: {e}")

        # ── 6. outer HTML of first matching card ─────────────────────────────
        if candidates:
            best_sel = next(iter(candidates))
            try:
                cards = page.query_selector_all(best_sel)
                if cards:
                    outer = cards[0].evaluate('el => el.outerHTML')
                    print(f"\n\n=== OUTER HTML of first '{best_sel}' card (first 4000 chars) ===")
                    print(outer[:4000])
            except Exception as e:
                print(f"  outerHTML error: {e}")

        browser.close()
        print(f"\n{'='*70}")
        print("Investigation complete.")

if __name__ == '__main__':
    investigate(URL)