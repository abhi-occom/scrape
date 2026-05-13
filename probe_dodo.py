"""
probe_dodo.py
-------------
Deep-dive into each .plan-tile card on https://www.dodo.com/nbn
Mirrors the structure of probe_iprimus2.py.

For every card prints:
  - data-plan-id, data-plan-name, data-fibre-eligible
  - Full inner text
  - Each confirmed sub-selector result
  - Outer HTML of the first card
"""
import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright

URL = 'https://www.dodo.com/nbn'

# Sub-selectors to drill into every card — refined from HTML snippet evidence
SUB_SELECTORS = [
    # plan name / speed heading
    '.plan-speed',
    '[data-component-id*="plan_tile_plan_title"]',
    # pricing
    '[data-component-id*="plan_tile_pricing"]',
    '.pricing-amount',
    '.pricing-duration',
    'span.amount',
    # promo / offer badge
    '[data-component-id*="plan_tile_offer_badge"]',
    # speed detail text
    '[data-component-id*="plan_tile_detail"]',
    '[data-component-id*="speed"]',
    # generic fallbacks
    '[class*="price"]',
    '[class*="speed"]',
    '[class*="badge"]',
    '[class*="offer"]',
    '[class*="promo"]',
    '[class*="discount"]',
    '[class*="title"]',
    'h1','h2','h3','h4',
]


def probe(url: str):
    with sync_playwright() as p:
        browser = create_stealth_browser(p)
        page = create_stealth_page(browser)

        print(f"Navigating to {url} …")
        page.goto(url, timeout=40000, wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        print(f"Title: {page.title()}\n")

        # ── primary card selector confirmed from HTML match ──────────────────
        cards = page.query_selector_all('.plan-tile')
        print(f"Found {len(cards)} .plan-tile cards\n")

        for i, card in enumerate(cards):
            plan_id    = card.get_attribute('data-plan-id') or ''
            plan_name  = card.get_attribute('data-plan-name') or ''
            fibre_elig = card.get_attribute('data-fibre-eligible') or ''
            cls        = card.get_attribute('class') or ''

            full_text = card.inner_text().strip()

            print(f"{'='*70}")
            print(f"CARD [{i:02d}]  data-plan-id={repr(plan_id)}")
            print(f"          data-plan-name={repr(plan_name)}  fibre-eligible={repr(fibre_elig)}")
            print(f"          class={repr(cls[:80])}")
            print(f"FULL TEXT: {repr(full_text[:500])}")
            print()

            for sel in SUB_SELECTORS:
                try:
                    els = card.query_selector_all(sel)
                    for j, el in enumerate(els[:3]):
                        txt = el.inner_text().strip()
                        scls = el.get_attribute('class') or ''
                        dcomp = el.get_attribute('data-component-id') or ''
                        if txt:
                            label = dcomp if dcomp else scls[:60]
                            print(f"  [{sel}][{j}]  comp='{label}'  => {repr(txt[:150])}")
                except Exception:
                    pass
            print()

        # ── outer HTML of first card for full structural reference ────────────
        if cards:
            outer = cards[0].evaluate('el => el.outerHTML')
            print('\n' + '='*70)
            print("OUTER HTML – first .plan-tile (full):")
            print('='*70)
            print(outer)

        # ── also dump pricing spans globally to confirm amount selectors ──────
        print('\n' + '='*70)
        print("ALL .pricing-amount elements on the page:")
        pricing_els = page.query_selector_all('.pricing-amount')
        for i, el in enumerate(pricing_els):
            cls  = el.get_attribute('class') or ''
            txt  = el.inner_text().strip()
            print(f"  [{i}] class='{cls}'  text={repr(txt)}")

        browser.close()
        print("\nProbe complete.")


if __name__ == '__main__':
    probe(URL)
