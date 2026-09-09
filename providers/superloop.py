"""
Superloop ISP plan scraper — multi-page.
Scrapes 4 Superloop product pages:
  - /internet/nbn/            → JSON-LD extraction
  - /internet/fibre/          → JSON-LD extraction
  - /internet/flip-to-fibre/  → card extraction
  - /internet/fixed-wireless/ → card extraction
Returns Dict[str, List[Dict]] keyed by page name.
"""

import re
import json
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright
import config
from utils.logger import log_info, log_error, log_success
from utils.stealth import create_stealth_browser, create_stealth_page


SUPERLOOP_PAGES = {
    'nbn': {
        'url': 'https://www.superloop.com/internet/nbn/',
        'network_type': 'NBN',
        'method': 'json_ld',
    },
    'fibre': {
        'url': 'https://www.superloop.com/internet/fibre/',
        'network_type': 'Fibre',
        'method': 'json_ld',
    },
    'flip_to_fibre': {
        'url': 'https://www.superloop.com/internet/flip-to-fibre/',
        'network_type': 'FTTP Upgrade',
        'method': 'cards',
    },
    'fixed_wireless': {
        'url': 'https://www.superloop.com/internet/fixed-wireless/',
        'network_type': 'Fixed Wireless',
        'method': 'cards',
    },
}


def scrape_superloop_plans() -> Dict[str, List[Dict[str, Any]]]:
    """
    Scrape all Superloop pages.
    Returns dict of {page_key: [plans]}.
    """
    all_results = {}

    with sync_playwright() as p:
        browser = create_stealth_browser(p)

        for page_key, page_cfg in SUPERLOOP_PAGES.items():
            page = create_stealth_page(browser)
            try:
                log_info(f"Scraping {page_key}: {page_cfg['url']}", provider="superloop")
                resp = page.goto(page_cfg['url'], timeout=30000, wait_until="domcontentloaded")
                log_info(f"Status: {resp.status if resp else 'none'}", provider="superloop")
                page.wait_for_timeout(5000)

                method = page_cfg['method']
                network = page_cfg['network_type']
                name_prefix = 'Fixed Wireless ' if page_key == 'fixed_wireless' else ''

                if method == 'json_ld':
                    plans = extract_from_json_ld(page, network, page_cfg['url'])
                elif method == 'cards':
                    plans = extract_from_cards(page, network, page_cfg['url'], name_prefix)
                else:
                    plans = []

                all_results[page_key] = plans
                log_success(f"{page_key}: {len(plans)} plans", provider="superloop")

            except Exception as e:
                log_error(f"Error scraping {page_key}: {e}", provider="superloop")
                all_results[page_key] = []
            finally:
                page.close()

        browser.close()

    total = sum(len(v) for v in all_results.values())
    log_success(f"Total Superloop plans: {total}", provider="superloop")
    return all_results


def scrape_via_playwright() -> List[Dict[str, Any]]:
    """
    Legacy single-list interface (backward-compatible).
    """
    results = scrape_superloop_plans()
    flat = []
    for plans in results.values():
        flat.extend(plans)
    return flat


# ══════════════════════════════════════════════════════════════════
#  JSON-LD EXTRACTION (nbn + fibre pages)
# ══════════════════════════════════════════════════════════════════

MONTH_WORDS = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
    'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,
}


def parse_promo_period(description: str) -> Optional[str]:
    """Extract promo duration from JSON-LD description text, e.g. 'first six months'."""
    match = re.search(r'first\s+(\w+)\s+months?', description, re.I)
    if not match:
        return None
    word = match.group(1).lower()
    months = MONTH_WORDS.get(word) or (int(word) if word.isdigit() else None)
    return f"{months} months" if months else None


def extract_from_json_ld(page, network_type: str, source_url: str) -> List[Dict[str, Any]]:
    """Extract plan data from JSON-LD ProductGroup → hasVariant."""
    plans = []
    try:
        scripts = page.query_selector_all('script[type="application/ld+json"]')
        for script in scripts:
            try:
                data = json.loads(script.inner_text())
            except Exception:
                continue
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get('@type') != 'ProductGroup':
                    continue
                for variant in item.get('hasVariant', []):
                    plan = parse_json_ld_variant(variant, network_type, source_url)
                    if plan:
                        plans.append(plan)
    except Exception as e:
        log_error(f"JSON-LD extraction failed: {e}", provider="superloop")
    if not plans:
        plans = extract_from_cards(page, network_type, source_url)
    return plans


def parse_json_ld_variant(variant: Dict, network_type: str, source_url: str) -> Optional[Dict[str, Any]]:
    """Parse a JSON-LD Product variant into standardized plan format.

    offers.price is the current (often discounted) price; offers.priceSpecification.price
    is the ongoing/strikethrough price once any promo period ends.
    """
    try:
        name = variant.get('name', '')
        size = variant.get('size', '')
        description = variant.get('description', '')
        offers = variant.get('offers', {})
        offer_price = float(offers.get('price', 0) or 0)
        price_spec = offers.get('priceSpecification') or {}
        strike_price = float(price_spec.get('price', 0) or 0)

        download_speed, upload_speed = 0, 0
        if size:
            parts = size.split('/')
            if len(parts) == 2:
                download_speed = int(parts[0])
                upload_speed = int(parts[1])

        typical_dl, typical_ul = 0, 0
        m = re.search(r'Typical evening speed is (\d+)/(\d+(?:\.\d+)?)', description)
        if m:
            typical_dl = int(float(m.group(1)))
            typical_ul = int(float(m.group(2)))

        if not name or offer_price <= 0:
            return None

        if strike_price > offer_price:
            price = strike_price
            promo_price = offer_price
            promo_period = parse_promo_period(description)
        else:
            price = offer_price
            promo_price = None
            promo_period = None

        return {
            'provider_id': config.PROVIDERS['superloop']['id'],
            'plan_name': name,
            'network_type': network_type,
            'download_speed': download_speed,
            'upload_speed': upload_speed,
            'typical_evening_dl': typical_dl,
            'typical_evening_ul': typical_ul,
            'price': price,
            'promo_price': promo_price,
            'promo_period': promo_period,
            'contract': 'No Contract',
            'source_url': source_url,
        }
    except Exception as e:
        log_error(f"JSON-LD variant parse failed: {e}", provider="superloop")
        return None


# ══════════════════════════════════════════════════════════════════
#  CARD EXTRACTION — Flip to Fibre + Fixed Wireless
#  Both pages share the same plan-card component:
#    div.block.text-left.w-full.relative.group  (tier name in <h3>)
#  Each plan renders as two elements (front face with pricing, and a
#  flip-side detail panel with no price) — filter to the priced ones.
# ══════════════════════════════════════════════════════════════════

CARD_SELECTOR = 'div.block.text-left.w-full.relative.group'


def extract_from_cards(page, network_type: str, source_url: str, name_prefix: str = '') -> List[Dict[str, Any]]:
    plans = []
    cards = [c for c in page.query_selector_all(CARD_SELECTOR) if '$' in c.inner_text()]
    log_info(f"Plan cards found: {len(cards)}", provider="superloop")

    for card in cards:
        try:
            plan = parse_plan_card(card, network_type, source_url, name_prefix)
            if plan:
                plans.append(plan)
        except Exception as e:
            log_error(f"Card parse error: {e}", provider="superloop")
    return plans


def parse_plan_card(card, network_type: str, source_url: str, name_prefix: str = '') -> Optional[Dict[str, Any]]:
    """Parse a Superloop plan card (flip-to-fibre or fixed-wireless layout)."""
    full_text = card.inner_text()

    tier_el = card.query_selector('h3')
    plan_tier = tier_el.inner_text().strip() if tier_el else ''

    download_speed = 0
    upload_speed = 0
    dl_match = re.search(r'Download\s*\D*?(\d+)\s*Mbps', full_text, re.I)
    if dl_match:
        download_speed = int(dl_match.group(1))
    ul_match = re.search(r'Upload\s*\D*?(?:(\d+)-)?(\d+)\s*Mbps', full_text, re.I)
    if ul_match:
        upload_speed = int(ul_match.group(2))

    typical_dl, typical_ul = 0, 0
    typical_match = re.search(r'Typical evening speed\D*?(\d+)/(\d+(?:\.\d+)?)', full_text, re.I)
    if typical_match:
        typical_dl = int(float(typical_match.group(1)))
        typical_ul = int(float(typical_match.group(2)))

    # Price — promo price is immediately followed by "/mth" (possibly across a
    # line break); the ongoing/regular price follows "then $X/mth".
    promo_price = None
    regular_price = 0.0

    promo_match = re.search(r'\$(\d+(?:\.\d+)?)\s*/mth', full_text, re.I)
    if promo_match:
        promo_price = float(promo_match.group(1))

    then_match = re.search(r'then\s+\$(\d+(?:\.\d+)?)\s*/mth', full_text, re.I)
    if then_match:
        regular_price = float(then_match.group(1))

    if regular_price <= 0 and promo_price:
        regular_price = promo_price
        promo_price = None

    promo_period = None
    period_m = re.search(r'(\d+)\s*months?', full_text)
    if period_m and promo_price:
        promo_period = f"{period_m.group(1)} months"

    if not plan_tier or regular_price <= 0 or download_speed <= 0:
        return None

    plan_name = f"{name_prefix}{plan_tier} {download_speed}/{upload_speed}"

    return {
        'provider_id': config.PROVIDERS['superloop']['id'],
        'plan_name': plan_name,
        'network_type': network_type,
        'download_speed': download_speed,
        'upload_speed': upload_speed,
        'typical_evening_dl': typical_dl,
        'typical_evening_ul': typical_ul,
        'price': regular_price,
        'promo_price': promo_price,
        'promo_period': promo_period,
        'contract': 'No Contract',
        'source_url': source_url,
    }


# ── Utility ──────────────────────────────────────────────────────

def extract_price(text: str) -> float:
    """Extract dollar amount from text."""
    match = re.search(r'\$?\s*(\d+(?:\.\d+)?)', text)
    return float(match.group(1)) if match else 0.0
