# scrape/providers/iprimus.py
"""
iPrimus ISP provider scraper.

Scrapes https://www.iprimus.com.au/nbn-plans which renders plan tiles for:
  - NBN plans      (nbn® Standard Plus / Premium / Premium plus / Home Superfast / Home Ultrafast)
  - Fixed Wireless (Fixed Wireless Standard / Plus)
  - Fibre          (Fibre Standard / Standard Plus / Premium / Home Superfast / Home Ultrafast)

DOM structure confirmed via probe_iprimus.py / probe_iprimus2.py:
  - Primary plan cards:  .plan_tile  (has tiq-data attribute, has speed text)
  - Modal-only cards:    .plan_tile.plan_tile--modal  (no tiq-data, no speed text — duplicates + extras)

Strategy:
  1. Collect all .plan_tile cards that are NOT .plan_tile--modal (cards 0-4, the NBN main view).
  2. Collect all .plan_tile--modal cards (cards 5-17), which include Fixed Wireless + Fibre + nbn Standard.
  3. For primary cards: read speed from .plan_tile__content__speed__text and promo from .plan_tile__upgrade__title.
  4. For modal cards (no speed text): derive speed from KNOWN_SPEEDS lookup keyed on normalised plan name.
  5. Deduplicate by (plan_name, network_type) across both sets.
"""
import re
import sys
import os
from typing import List, Dict, Any, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from utils.logger import log_info, log_error, log_success, log_warning
from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright

PROVIDER_ID = config.PROVIDERS.get('iprimus', {}).get('id', 11)
URL = 'https://www.iprimus.com.au/nbn-plans'

# ---------------------------------------------------------------------------
# Speed lookup: keyed on lower-cased, stripped plan heading.
# Derived from NBN speed tier standards + investigation output.
# Values: (download_mbps, upload_mbps)
# ---------------------------------------------------------------------------
KNOWN_SPEEDS: Dict[str, Tuple[int, int]] = {
    # NBN
    'nbn standard':              (25,  5),
    'nbn standard plus':         (50,  17),
    'nbn premium':               (100, 17),
    'nbn premium plus':          (500, 47),
    'nbn home superfast':        (700, 49),
    'nbn home ultrafast':        (840, 94),
    # Fixed Wireless
    'fixed wireless standard':   (25,  5),
    'fixed wireless plus':       (50,  17),
    # Fibre (iPrimus own-network)
    'fibre standard':            (50,  17),
    'fibre standard plus':       (100, 17),
    'fibre premium':             (500, 47),
    'fibre home superfast':      (700, 49),
    'fibre home ultrafast':      (840, 94),
}

# Network type derived from plan name prefix
NETWORK_TYPE_MAP: Dict[str, str] = {
    'nbn':            'NBN',
    'fixed wireless': 'Fixed Wireless',
    'fibre':          'Fibre',
}


def _normalise_heading(text: str) -> str:
    """Lowercase, strip special chars (®, ™, \xa0) and collapse spaces."""
    text = text.lower()
    for ch in ('®', '™', '\xa0', '\u00ae'):
        text = text.replace(ch, '')
    return re.sub(r'\s+', ' ', text).strip()


def _network_type_from_name(name_normalised: str) -> str:
    """Determine network type from normalised plan heading."""
    for prefix, ntype in NETWORK_TYPE_MAP.items():
        if name_normalised.startswith(prefix):
            return ntype
    return 'NBN'  # safe fallback


def _parse_price(raw: str) -> Optional[float]:
    """Extract dollar amount from strings like '$67 /month', '$67\n/month', '$87/month'."""
    m = re.search(r'\$([\d]+(?:\.\d+)?)', raw)
    return float(m.group(1)) if m else None


def _parse_speed_text(text: str) -> Tuple[int, int]:
    """
    Parse speed text like '50Mbps download & 17Mbps upload typical evening speeds'.
    Returns (download_mbps, upload_mbps).
    """
    dl = re.search(r'(\d+)\s*Mbps\s+download', text, re.IGNORECASE)
    ul = re.search(r'(\d+)\s*Mbps\s+upload', text, re.IGNORECASE)
    download = int(dl.group(1)) if dl else 0
    upload = int(ul.group(1)) if ul else 0
    return download, upload


def _parse_promo(promo_text: str, was_price: Optional[float], current_price: Optional[float]) -> Tuple[Optional[float], Optional[str]]:
    """
    Determine promo_price and promo_period from the upgrade banner and was/current prices.

    - If there is a 'Was $X/month' discount el and a promo banner with a period,
      the was_price is the regular price, current_price is the promotional price.
    - promo_period extracted from text like 'Save $30/month for first 6 months'.
    """
    promo_price = None
    promo_period = None

    if was_price and current_price and was_price > current_price:
        promo_price = current_price
        # Parse period from upgrade title, e.g. "Save $30/month for first 6 months"
        period_m = re.search(r'for\s+(?:the\s+)?(?:first\s+)?(\d+\s*months?)', promo_text, re.IGNORECASE)
        if period_m:
            promo_period = period_m.group(1).strip()
        else:
            promo_period = '6 months'  # iprimus default promo length

    return promo_price, promo_period


def _extract_card(card, is_modal: bool) -> Optional[Dict[str, Any]]:
    """
    Extract a single plan dict from a .plan-block Playwright element.

    Args:
        card: Playwright element handle
        is_modal: True if this card carries class plan-block.modal

    Returns:
        Plan dict or None if the card should be skipped.
    """
    try:
        # --- Heading --- 
        heading_el = card.query_selector('.plan_tile__heading')
        if not heading_el:
            return None
        heading_raw = heading_el.inner_text().strip()
        heading_norm = _normalise_heading(heading_raw)

        if not heading_norm:
            return None

        # --- Network type ---
        network_type = _network_type_from_name(heading_norm)

        # --- Price ---
        price_el = card.query_selector('.plan_tile__price')
        price_raw = price_el.inner_text().strip() if price_el else ''
        current_price = _parse_price(price_raw) if price_raw else None
        if current_price is None:
            return None

        # --- Was price (discount element) ---
        disc_el = card.query_selector('.plan_tile__price--discount')
        disc_raw = disc_el.inner_text().strip() if disc_el else ''
        was_price = _parse_price(disc_raw) if disc_raw and disc_raw != '0' else None

        # Regular price (was price if exists, otherwise current)
        regular_price = was_price if was_price else current_price

        # --- Speed ---
        speed_el = card.query_selector('.plan_tile__content__speed__text')
        speed_raw = speed_el.inner_text().strip() if speed_el else ''
        download_speed, upload_speed = _parse_speed_text(speed_raw)
        if not download_speed:
            download_speed, upload_speed = KNOWN_SPEEDS.get(heading_norm, (0, 0))
        if not download_speed:
            return None

        # --- Promo period ---
        promo_el = card.query_selector('.plan_tile__upgrade__title')
        promo_text = promo_el.inner_text().strip() if promo_el else ''
        promo_price, promo_period = _parse_promo(promo_text, was_price, current_price)
        if not promo_period:
            promo_match = re.search(
                r'for\s+(?:the\s+)?(?:first\s+)?(\d+\s*months?)',
                f'{promo_text} {card.inner_text()}',
                re.IGNORECASE,
            )
            promo_period = promo_match.group(1).strip() if promo_match else None

        plan_name = re.sub(
            r'\s+',
            ' ',
            heading_raw.replace('\u00ae', '').replace('®', ''),
        ).strip()

        return {
            'provider_id': PROVIDER_ID,
            'provider': 'iprimus',
            'plan_name': plan_name,
            'network_type': network_type,
            'download_speed': download_speed,
            'upload_speed': upload_speed,
            'speed': download_speed,
            'price': regular_price,
            'promo_price': promo_price,
            'promo_period': promo_period,
            'contract': 'No Contract',
            'typical_evening_dl': download_speed,
            'typical_evening_ul': upload_speed,
            'source_url': URL,
        }

    except Exception as e:
        log_error(f'Error extracting iPrimus card: {e}', provider='iprimus')
        return None

def scrape_iprimus_plans() -> List[Dict[str, Any]]:
    """
    Scrape all iPrimus internet plans from /nbn-plans.

    Returns a flat list of plan dicts covering NBN, Fixed Wireless and Fibre tiers.
    """
    log_info('Starting iPrimus scraper', provider='iprimus')
    all_plans: List[Dict[str, Any]] = []

    try:
        with sync_playwright() as p:
            browser = create_stealth_browser(p)
            page = create_stealth_page(browser)

            page.goto(URL, timeout=30000, wait_until='domcontentloaded')
            page.wait_for_timeout(6000)

            # ----------------------------------------------------------------
            # 1. Primary visible cards (no plan_tile--modal class, have tiq-data)
            #    These are the NBN plans shown in the default "All" tab view.
            # ----------------------------------------------------------------
            primary_cards = page.query_selector_all(
                '.plan_tile:not(.plan_tile--modal)'
            )
            log_info(f'Found {len(primary_cards)} primary plan_tile cards', provider='iprimus')

            seen: set = set()

            for card in primary_cards:
                plan = _extract_card(card, is_modal=False)
                if plan:
                    key = f"{plan['plan_name']}|{plan['network_type']}"
                    if key not in seen:
                        seen.add(key)
                        all_plans.append(plan)

            # ----------------------------------------------------------------
            # 2. Modal-only cards (.plan_tile--modal)
            #    These include Fixed Wireless, Fibre, and nbn Standard which
            #    don't appear in the primary default view.
            # ----------------------------------------------------------------
            modal_cards = page.query_selector_all('.plan_tile--modal')
            log_info(f'Found {len(modal_cards)} modal plan_tile cards', provider='iprimus')

            for card in modal_cards:
                plan = _extract_card(card, is_modal=True)
                if plan:
                    key = f"{plan['plan_name']}|{plan['network_type']}"
                    if key not in seen:
                        seen.add(key)
                        all_plans.append(plan)

            browser.close()

    except Exception as e:
        log_error(f'iPrimus scraper failed: {e}', provider='iprimus')

    # Sort: NBN first, then Fixed Wireless, then Fibre; within each by download speed
    ORDER = {'NBN': 0, 'Fixed Wireless': 1, 'Fibre': 2}
    all_plans.sort(key=lambda x: (ORDER.get(x['network_type'], 9), x['download_speed']))

    log_success(
        f'iPrimus scraper complete: {len(all_plans)} plans '
        f'({sum(1 for p in all_plans if p["network_type"]=="NBN")} NBN, '
        f'{sum(1 for p in all_plans if p["network_type"]=="Fixed Wireless")} Fixed Wireless, '
        f'{sum(1 for p in all_plans if p["network_type"]=="Fibre")} Fibre)',
        provider='iprimus',
    )
    return all_plans


if __name__ == '__main__':
    plans = scrape_iprimus_plans()
    print(f'\nTotal plans: {len(plans)}')
    for plan in plans:
        promo = f" (promo: ${plan['promo_price']}/mth for {plan['promo_period']})" if plan['promo_price'] else ''
        print(
            f"  [{plan['network_type']:15}] {plan['plan_name']:30}  "
            f"{plan['download_speed']:4}/{plan['upload_speed']:3} Mbps  "
            f"${plan['price']}/mth{promo}"
        )
