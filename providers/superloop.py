"""
Superloop ISP plan scraper — multi-page.
Scrapes 4 Superloop product pages:
  - /internet/nbn/        → JSON-LD extraction (9 plans)
  - /internet/fibre/      → JSON-LD extraction (7 plans)
  - /flip-to-fibre/       → card extraction via border rounded cards
  - /internet/fixed-wireless/ → card extraction via .card elements
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
        'url': 'https://www.superloop.com/flip-to-fibre/',
        'network_type': 'FTTP Upgrade',
        'method': 'cards_rounded',
    },
    'fixed_wireless': {
        'url': 'https://www.superloop.com/internet/fixed-wireless/',
        'network_type': 'Fixed Wireless',
        'method': 'cards_fw',
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

                if method == 'json_ld':
                    plans = extract_from_json_ld(page, network, page_cfg['url'])
                elif method == 'cards_rounded':
                    plans = extract_from_rounded_cards(page, network, page_cfg['url'])
                elif method == 'cards_fw':
                    plans = extract_from_fw_cards(page, network, page_cfg['url'])
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
    Scrapes only the NBN page.
    """
    results = scrape_superloop_plans()
    # Flatten all pages into single list
    flat = []
    for plans in results.values():
        flat.extend(plans)
    return flat


# ══════════════════════════════════════════════════════════════════
#  JSON-LD EXTRACTION (nbn + fibre pages)
# ══════════════════════════════════════════════════════════════════

def extract_from_json_ld(page, network_type: str, source_url: str) -> List[Dict[str, Any]]:
    """Extract plan data from JSON-LD ProductGroup → hasVariant."""
    plans = []
    try:
        scripts = page.query_selector_all('script[type="application/ld+json"]')
        for script in scripts:
            data = json.loads(script.inner_text())
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
    return plans


def parse_json_ld_variant(variant: Dict, network_type: str, source_url: str) -> Optional[Dict[str, Any]]:
    """Parse a JSON-LD Product variant into standardized plan format."""
    try:
        name = variant.get('name', '')
        size = variant.get('size', '')
        description = variant.get('description', '')
        offers = variant.get('offers', {})
        price = float(offers.get('price', 0))

        # Parse download/upload from size (e.g. "50/20")
        download_speed, upload_speed = 0, 0
        if size:
            parts = size.split('/')
            if len(parts) == 2:
                download_speed = int(parts[0])
                upload_speed = int(parts[1])

        # Parse typical evening speed from description
        typical_dl, typical_ul = 0, 0
        m = re.search(r'Typical evening speed is (\d+)/(\d+)', description)
        if m:
            typical_dl = int(m.group(1))
            typical_ul = int(m.group(2))

        if not name or price <= 0:
            return None

        return {
            'provider_id': config.PROVIDERS['superloop']['id'],
            'plan_name': name,
            'network_type': network_type,
            'download_speed': download_speed,
            'upload_speed': upload_speed,
            'typical_evening_dl': typical_dl,
            'typical_evening_ul': typical_ul,
            'price': price,
            'promo_price': None,
            'promo_period': None,
            'contract': 'No Contract',
            'source_url': source_url,
        }
    except Exception as e:
        log_error(f"JSON-LD variant parse failed: {e}", provider="superloop")
        return None


# ══════════════════════════════════════════════════════════════════
#  CARD EXTRACTION — Flip to Fibre (border rounded cards)
# ══════════════════════════════════════════════════════════════════

def extract_from_rounded_cards(page, network_type: str, source_url: str) -> List[Dict[str, Any]]:
    """
    Extract plans from flip-to-fibre page.
    Cards: border rounded-[1.25rem] inside #plans, contain speed, price, tier name.
    """
    plans = []
    cards = page.query_selector_all('#plans .border.rounded-\\[1\\.25rem\\]')
    log_info(f"Rounded cards found: {len(cards)}", provider="superloop")

    for card in cards:
        try:
            plan = parse_rounded_card(card, network_type, source_url)
            if plan:
                plans.append(plan)
        except Exception as e:
            log_error(f"Card parse error: {e}", provider="superloop")
    return plans


def parse_rounded_card(card, network_type: str, source_url: str) -> Optional[Dict[str, Any]]:
    """Parse a rounded plan card from flip-to-fibre or nbn fallback."""
    full_text = card.inner_text()

    # Plan tier name — first h3 with font-Avenir95Black
    name_el = card.query_selector('h3.font-Avenir95Black')
    plan_tier = name_el.inner_text().strip() if name_el else ''

    # Download speed — look for number before "Mbps" near "Download"
    download_speed = 0
    upload_speed = 0
    # The layout is: Download | 25 | Mbps | Upload | 10 | Mbps
    dl_match = re.search(r'Download\s*\D*?(\d+)\s*Mbps', full_text, re.I)
    if dl_match:
        download_speed = int(dl_match.group(1))
    ul_match = re.search(r'Upload\s*\D*?(\d+)\s*Mbps', full_text, re.I)
    if ul_match:
        upload_speed = int(ul_match.group(1))

    # Price — look for promo price (green) and regular (strikethrough)
    promo_price = None
    regular_price = 0

    # Try green/promo price element
    promo_el = card.query_selector('span.text-green-500, span.text-green-600')
    strikethrough_el = card.query_selector('span.line-through')

    if promo_el:
        promo_price = extract_price(promo_el.inner_text())
    if strikethrough_el:
        regular_price = extract_price(strikethrough_el.inner_text())

    # Fallback: extract from text  "$72 $45 /mth" or "$45/mth"
    if not promo_price and not regular_price:
        prices = re.findall(r'\$(\d+(?:\.\d+)?)', full_text)
        if len(prices) >= 2:
            regular_price = float(prices[0])
            promo_price = float(prices[1])
        elif len(prices) == 1:
            regular_price = float(prices[0])

    if regular_price <= 0 and promo_price:
        regular_price = promo_price
        promo_price = None

    # Promo period
    promo_period = ''
    period_m = re.search(r'(\d+)\s*months?', full_text)
    if period_m and promo_price:
        promo_period = f"{period_m.group(1)} months"

    if not plan_tier or regular_price <= 0:
        return None

    plan_name = f"{plan_tier} {download_speed}/{upload_speed}"

    return {
        'provider_id': config.PROVIDERS['superloop']['id'],
        'plan_name': plan_name,
        'network_type': network_type,
        'download_speed': download_speed,
        'upload_speed': upload_speed,
        'typical_evening_dl': 0,
        'typical_evening_ul': 0,
        'price': regular_price,
        'promo_price': promo_price,
        'promo_period': promo_period,
        'contract': 'No Contract',
        'source_url': source_url,
    }


# ══════════════════════════════════════════════════════════════════
#  CARD EXTRACTION — Fixed Wireless (.card elements)
# ══════════════════════════════════════════════════════════════════

def extract_from_fw_cards(page, network_type: str, source_url: str) -> List[Dict[str, Any]]:
    """
    Extract plans from fixed-wireless page.
    Cards: .card elements inside #plans with speed/price info.
    """
    plans = []
    # Each plan is a top-level .card with min-h inside #plans
    # Use CSS attribute selector to match class containing "min-h"
    cards = page.query_selector_all('#plans [class*="min-h"][class*="card"]')
    if not cards:
        # Broader fallback — all .card with _md:w-fit
        cards = page.query_selector_all('#plans [class*="_md:w-fit"]')
    if not cards:
        cards = page.query_selector_all('#plans > div .card')

    log_info(f"Fixed wireless cards found: {len(cards)}", provider="superloop")

    seen = set()
    for card in cards:
        try:
            plan = parse_fw_card(card, network_type, source_url)
            if plan:
                key = f"{plan['plan_name']}_{plan['price']}"
                if key not in seen:
                    seen.add(key)
                    plans.append(plan)
        except Exception as e:
            log_error(f"FW card parse error: {e}", provider="superloop")
    return plans


def parse_fw_card(card, network_type: str, source_url: str) -> Optional[Dict[str, Any]]:
    """Parse a fixed-wireless plan card."""
    full_text = card.inner_text()

    # Plan name — e.g. "Fixed Wireless Plus 100/20" or "Fixed Wireless Home Fast 250/20"
    name_match = re.search(r'Fixed Wireless\s+((?:(?:Plus|Premium|Max|Basic|Home Fast|Super Fast|Home Superfast)\s+)?\d+/\d+)', full_text)
    plan_name = name_match.group(1).strip() if name_match else ''

    if not plan_name:
        # Fallback: grab text between "Fixed Wireless" and "Typical"
        fw_match = re.search(r'Fixed Wireless\s+(.+?)(?:Typical|$)', full_text, re.S)
        if fw_match:
            plan_name = fw_match.group(1).strip().split('\n')[0].strip()

    # Download/Upload — "Download | 100 Mbps | Upload | 20 Mbps" or "8-20 Mbps"
    download_speed = 0
    upload_speed = 0
    dl_match = re.search(r'Download\s*\D*?(\d+)\s*Mbps', full_text, re.I)
    if dl_match:
        download_speed = int(dl_match.group(1))
    # Upload can be range like "8-20 Mbps" — take the higher number
    ul_match = re.search(r'Upload\s*\D*?(?:(\d+)-)?(\d+)\s*Mbps', full_text, re.I)
    if ul_match:
        upload_speed = int(ul_match.group(2))

    # Typical evening speed — "Typical evening speed: 50/8 Mbps"
    typical_dl, typical_ul = 0, 0
    typical_match = re.search(r'Typical evening speed:\s*(\d+)/(\d+)', full_text)
    if typical_match:
        typical_dl = int(typical_match.group(1))
        typical_ul = int(typical_match.group(2))

    # Price — "$75/mth" for promo, "then $89/mth" for regular
    promo_price = None
    regular_price = 0

    price_match = re.search(r'\$(\d+(?:\.\d+)?)/mth', full_text)
    if price_match:
        promo_price = float(price_match.group(1))

    then_match = re.search(r'then\s+\$(\d+(?:\.\d+)?)/mth', full_text)
    if then_match:
        regular_price = float(then_match.group(1))

    if regular_price <= 0 and promo_price:
        regular_price = promo_price
        promo_price = None

    # Promo period
    promo_period = ''
    period_m = re.search(r'(\d+)\s*months?', full_text)
    if period_m and promo_price:
        promo_period = f"{period_m.group(1)} months"

    if not plan_name or regular_price <= 0:
        return None

    return {
        'provider_id': config.PROVIDERS['superloop']['id'],
        'plan_name': f"Fixed Wireless {plan_name}",
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
