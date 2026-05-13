# scrape/providers/dodo.py
"""
Dodo ISP provider scraper.

Scrapes https://www.dodo.com/nbn — a Drupal-rendered page (no SPA framework)
that inlines all NBN plan cards in the initial HTML payload.

DOM structure confirmed via investigate_dodo.py / probe_dodo.py:
─────────────────────────────────────────────────────────────────
Card root:   div.plan-tile
  Attributes:
    data-plan-id        — unique plan UUID
    data-plan-name      — internal Dodo SKU code
    data-fibre-eligible — "true" / "false"

  Sub-selectors (all stable data-component-id anchors):
    [data-component-id*="plan_tile_offer_badge"]  → "$30 MTH OFF FOR 6 MONTHS"
    .plan-speed                                    → "25 Mbps", "50 Mbps" …
    .original-price.discounted                     → regular (crossed-out) price "$71.99"
    .price-amount                                  → promo/current price "$41.99"
    [data-component-id*="plan_tile_target_user_info"] .main-text
                                                   → "25 Mbps download, 9 Mbps upload."
    [data-component-id*="plan_tile_terms"] .plan-terms
                                                   → "Offer ends 30 Jun 2026"

Pricing logic:
  • When a promo is active both .original-price.discounted AND .price-amount exist.
    regular_price  = .original-price.discounted  (the struck-through value)
    promo_price    = .price-amount               (the highlighted promo value)
  • When no promo, only .price-amount exists.
    regular_price  = .price-amount
    promo_price    = None

Cards 0-5  → standard NBN tiers (25 / 50 / 100 / 500 / 700 / 840 Mbps)
Cards 6-7  → FTTN-only plans (23 / 63 Mbps) – still NBN technology

All plans are month-to-month (no lock-in contract).

Strategy:
  1. Query all div.plan-tile elements.
  2. Extract speed, prices, promo badge, and speed-detail text from each.
  3. Derive upload speed from the "Xd Mbps download, Y Mbps upload" detail line.
  4. Derive promo_period from the badge text (e.g. "6 MONTHS").
  5. Build standardised plan dict and deduplicate by (plan_name, download_speed).
"""
import re
import sys
import os
from typing import List, Dict, Any, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from utils.logger import log_info, log_error, log_success, log_warning
from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright, ElementHandle

PROVIDER_ID: int = config.PROVIDERS.get('dodo', {}).get('id', 12)
URL: str = 'https://www.dodo.com/nbn'


# ── helpers ──────────────────────────────────────────────────────────────────

def _parse_price(raw: str) -> Optional[float]:
    """Extract the first dollar-amount from a string like '$71.99' or '$41.99/mth'."""
    m = re.search(r'\$([\d]+(?:\.[\d]+)?)', raw)
    return float(m.group(1)) if m else None


def _parse_speed_detail(text: str) -> Tuple[int, int]:
    """
    Parse the Typical-evening-speeds detail line.
    Examples:
      "25 Mbps download, 9 Mbps upload."
      "500 Mbps download, 48 Mbps upload."
    Returns (download_mbps, upload_mbps).
    """
    dl = re.search(r'(\d+)\s*Mbps\s+download', text, re.IGNORECASE)
    ul = re.search(r'(\d+)\s*Mbps\s+upload',   text, re.IGNORECASE)
    download = int(dl.group(1)) if dl else 0
    upload   = int(ul.group(1)) if ul else 0
    return download, upload


def _parse_plan_speed(text: str) -> int:
    """
    Parse the headline speed shown in .plan-speed e.g. "25 Mbps" → 25.
    Used as the primary download-speed value and plan-name suffix.
    """
    m = re.search(r'(\d+)', text)
    return int(m.group(1)) if m else 0


def _parse_promo_period(badge_text: str) -> Optional[str]:
    """
    Extract promo duration from badge text like '$30 MTH OFF FOR 6 MONTHS'.
    Returns normalised string e.g. '6 months', or None if no period found.
    """
    m = re.search(r'(\d+)\s*MONTHS?', badge_text, re.IGNORECASE)
    return f"{m.group(1)} months" if m else None


def _plan_name_from_speed(download_mbps: int) -> str:
    """Build a canonical plan name like 'Dodo NBN 25' from the speed value."""
    return f"Dodo NBN {download_mbps}"


def _extract_card(card: ElementHandle) -> Optional[Dict[str, Any]]:
    """
    Extract a single plan dict from a .plan-tile Playwright element.

    Returns a plan dict or None if essential data is missing.
    """
    try:
        # ── data attributes ─────────────────────────────────────────────────
        plan_id    = card.get_attribute('data-plan-id')    or ''
        plan_sku   = card.get_attribute('data-plan-name')  or ''
        fibre_raw  = card.get_attribute('data-fibre-eligible') or 'false'
        fibre_eligible = fibre_raw.lower() == 'true'

        # ── headline speed (.plan-speed) ─────────────────────────────────────
        speed_el  = card.query_selector('.plan-speed')
        speed_raw = speed_el.inner_text().strip() if speed_el else ''
        download_speed = _parse_plan_speed(speed_raw)
        if download_speed == 0:
            log_warning(f'Dodo: could not parse speed from "{speed_raw}", skipping card', provider='dodo')
            return None

        # ── pricing ──────────────────────────────────────────────────────────
        # Regular (struck-through) price — only present when a promo is active
        orig_el    = card.query_selector('.original-price.discounted')
        orig_raw   = orig_el.inner_text().strip() if orig_el else ''
        orig_price = _parse_price(orig_raw) if orig_raw else None

        # Displayed price (promo when orig_price exists, otherwise regular)
        amount_el    = card.query_selector('.price-amount')
        amount_raw   = amount_el.inner_text().strip() if amount_el else ''
        amount_price = _parse_price(amount_raw) if amount_raw else None

        if amount_price is None:
            log_warning(f'Dodo: no price found for {download_speed} Mbps card, skipping', provider='dodo')
            return None

        if orig_price and orig_price > amount_price:
            # Promo is active: orig_price is the regular price, amount_price is promo
            regular_price = orig_price
            promo_price   = amount_price
        else:
            # No promo or same price
            regular_price = amount_price
            promo_price   = None

        # ── promo badge ───────────────────────────────────────────────────────
        badge_el   = card.query_selector('[data-component-id*="plan_tile_offer_badge"]')
        badge_text = badge_el.inner_text().strip() if badge_el else ''
        promo_period = _parse_promo_period(badge_text) if badge_text else None

        # If promo price exists but we couldn't get a period from the badge,
        # default to the standard Dodo promo window
        if promo_price and not promo_period:
            promo_period = '6 months'

        # ── upload speed from detail line ─────────────────────────────────────
        # "[data-component-id*='plan_tile_target_user_info'] .main-text"
        detail_el   = card.query_selector(
            '[data-component-id*="plan_tile_target_user_info"] .main-text'
        )
        detail_text = detail_el.inner_text().strip() if detail_el else ''
        detail_dl, upload_speed = _parse_speed_detail(detail_text)

        # Cross-check: if detail_dl differs from headline speed, trust headline
        if detail_dl and detail_dl != download_speed:
            log_warning(
                f'Dodo: headline speed {download_speed} Mbps ≠ detail speed {detail_dl} Mbps '
                f'— keeping headline value',
                provider='dodo',
            )

        # ── plan terms (offer end date) ───────────────────────────────────────
        terms_el   = card.query_selector('[data-component-id*="plan_tile_terms"] .plan-terms')
        terms_text = terms_el.inner_text().strip() if terms_el else ''

        # ── network type ──────────────────────────────────────────────────────
        # All plans on this page are NBN; fibre_eligible distinguishes FTTP/HFC
        # capable tiers from FTTN/FTTC/FTTB ones, but they are all "NBN".
        network_type = 'NBN'

        # ── plan name ─────────────────────────────────────────────────────────
        plan_name = _plan_name_from_speed(download_speed)

        return {
            'provider_id':    PROVIDER_ID,
            'provider':       'dodo',
            'plan_name':      plan_name,
            'plan_id':        plan_id,
            'plan_sku':       plan_sku,
            'network_type':   network_type,
            'download_speed': download_speed,
            'upload_speed':   upload_speed,
            'speed':          download_speed,
            'price':          regular_price,
            'promo_price':    promo_price,
            'promo_period':   promo_period,
            'fibre_eligible': fibre_eligible,
            'contract':       'No Contract',
            'source_url':     URL,
            'terms':          terms_text,
        }

    except Exception as exc:
        log_error(f'Dodo: error extracting card — {exc}', provider='dodo')
        return None


# ── main scraper ─────────────────────────────────────────────────────────────

def scrape_dodo_plans() -> List[Dict[str, Any]]:
    """
    Scrape all Dodo NBN plans from https://www.dodo.com/nbn.

    Returns a flat list of standardised plan dicts sorted by download speed.
    """
    log_info('Starting Dodo scraper', provider='dodo')
    all_plans: List[Dict[str, Any]] = []

    try:
        with sync_playwright() as p:
            browser = create_stealth_browser(p)
            page    = create_stealth_page(browser)

            page.goto(URL, timeout=40000, wait_until='domcontentloaded')
            page.wait_for_timeout(6000)

            cards = page.query_selector_all('.plan-tile')
            log_info(f'Found {len(cards)} .plan-tile cards', provider='dodo')

            seen: set = set()

            for card in cards:
                plan = _extract_card(card)
                if plan is None:
                    continue

                # Deduplicate by (plan_name, download_speed) — the page sometimes
                # renders duplicate tiles for FTTN vs FTTP audiences
                key = f"{plan['plan_name']}|{plan['download_speed']}"
                if key in seen:
                    log_warning(
                        f'Dodo: duplicate card for {plan["plan_name"]} ({plan["download_speed"]} Mbps), skipping',
                        provider='dodo',
                    )
                    continue
                seen.add(key)
                all_plans.append(plan)

            browser.close()

    except Exception as exc:
        log_error(f'Dodo scraper failed: {exc}', provider='dodo')

    # Sort ascending by download speed
    all_plans.sort(key=lambda x: x['download_speed'])

    log_success(
        f'Dodo scraper complete: {len(all_plans)} plans '
        f'({sum(1 for p in all_plans if p["promo_price"]) } with active promo)',
        provider='dodo',
    )
    return all_plans


# ── standalone test ───────────────────────────────────────────────────────────

if __name__ == '__main__':
    plans = scrape_dodo_plans()
    print(f'\nTotal plans: {len(plans)}\n')
    for plan in plans:
        promo = (
            f'  (promo ${plan["promo_price"]}/mth for {plan["promo_period"]})'
            if plan['promo_price'] else ''
        )
        fibre = ' [fibre-eligible]' if plan['fibre_eligible'] else ''
        print(
            f"  {plan['plan_name']:20}  "
            f"{plan['download_speed']:4}/{plan['upload_speed']:<3} Mbps  "
            f"${plan['price']:.2f}/mth"
            f"{promo}{fibre}"
        )
