"""
TPG ISP plan scraper — multi-page.
Scrapes 5 TPG product pages:
  - /nbn                      → 7 NBN plans (planLabels.nbnLabels cards)
  - /nbn/fibre-upgrade        → Informational only (no plans)
  - /home-wireless-broadband  → 1 plan (4G, div.plans text)
  - /5g-home-broadband        → 2 plans (5G, div.plans text)
  - /fttb                     → 3 plans (.plan-card elements)
Returns Dict[str, List[Dict]] keyed by page name.
"""

import re
import json
from typing import List, Dict, Any
from playwright.sync_api import sync_playwright, Page
import config
from utils.logger import log_info, log_error, log_success
from utils.stealth import create_stealth_browser, create_stealth_page


TPG_PAGES = {
    'nbn': {
        'url': 'https://www.tpg.com.au/nbn',
        'network_type': 'NBN',
        'method': 'nbn_cards',
    },
    'fibre_upgrade': {
        'url': 'https://www.tpg.com.au/nbn/fibre-upgrade',
        'network_type': 'NBN FTTP Upgrade',
        'method': 'info_only',
    },
    'home_wireless': {
        'url': 'https://www.tpg.com.au/home-wireless-broadband',
        'network_type': '4G Home Wireless',
        'method': 'wireless_plans',
    },
    '5g_home': {
        'url': 'https://www.tpg.com.au/5g-home-broadband',
        'network_type': '5G',
        'method': '5g_plans',
    },
    'fttb': {
        'url': 'https://www.tpg.com.au/fttb',
        'network_type': 'FTTB',
        'method': 'fttb_cards',
    },
}


def scrape_tpg_plans() -> Dict[str, List[Dict[str, Any]]]:
    """
    Scrape all TPG pages.
    Returns dict of {page_key: [plans]}.
    """
    all_results = {}

    with sync_playwright() as p:
        browser = create_stealth_browser(p)

        for page_key, page_cfg in TPG_PAGES.items():
            if page_cfg['method'] == 'info_only':
                all_results[page_key] = []
                log_info(f"Skipping {page_key} (informational)", provider="tpg")
                continue

            page = create_stealth_page(browser)
            try:
                url = page_cfg['url']
                log_info(f"Scraping {page_key}: {url}", provider="tpg")
                resp = page.goto(url, timeout=30000, wait_until="domcontentloaded")
                log_info(f"Status: {resp.status if resp else 'none'}", provider="tpg")
                page.wait_for_timeout(6000)

                method = page_cfg['method']
                if method == 'nbn_cards':
                    plans = extract_nbn_plans(page, page_cfg)
                elif method == 'wireless_plans':
                    plans = extract_wireless_plans(page, page_cfg)
                elif method == '5g_plans':
                    plans = extract_5g_plans(page, page_cfg)
                elif method == 'fttb_cards':
                    plans = extract_fttb_plans(page, page_cfg)
                else:
                    plans = []

                plans = deduplicate_plans(plans)
                all_results[page_key] = plans
                log_success(f"{page_key}: {len(plans)} plans", provider="tpg")

            except Exception as e:
                log_error(f"Error scraping {page_key}: {e}", provider="tpg")
                all_results[page_key] = []
            finally:
                page.close()

        browser.close()

    total = sum(len(v) for v in all_results.values())
    log_success(f"Total TPG plans: {total}", provider="tpg")
    return all_results


def scrape_via_playwright() -> List[Dict[str, Any]]:
    """Legacy single-list interface (backward-compatible)."""
    results = scrape_tpg_plans()
    flat = []
    for plans in results.values():
        flat.extend(plans)
    return flat


# ══════════════════════════════════════════════════════════════════
#  NBN EXTRACTION — /nbn page
# ══════════════════════════════════════════════════════════════════

def extract_nbn_plans(page: Page, page_cfg: Dict) -> List[Dict[str, Any]]:
    """
    Extract NBN plans from the /nbn page.
    Plans are in .planLabels.nbnLabels cards inside .planCards containers.
    The NBN page also contains FTTB cards — we filter those out (scraped separately).
    """
    plans = []
    source_url = page_cfg['url']

    cards = page.query_selector_all('.planLabels.nbnLabels')
    log_info(f"Found {len(cards)} nbnLabels cards", provider="tpg")

    for card in cards:
        try:
            name_el = card.query_selector('h3.name')
            if not name_el:
                continue
            name = name_el.inner_text().strip()

            # Skip FTTB plans — they'll be scraped from /fttb
            if name.upper().startswith('FTTB'):
                continue

            dl_el = card.query_selector('.download-speed')
            ul_el = card.query_selector('.upload-speed')
            download_speed = parse_speed(dl_el.inner_text()) if dl_el else 0
            upload_speed = parse_speed(ul_el.inner_text()) if ul_el else 0

            # Get price from parent .planCards container
            parent_handle = card.evaluate_handle('el => el.closest(".planCards")')
            parent_text = parent_handle.inner_text()

            promo_price = parse_promo_price(parent_text)
            regular_price = parse_regular_price(parent_text)
            promo_period = parse_promo_period(parent_text)

            price = regular_price if regular_price > 0 else promo_price

            if name and price > 0 and download_speed > 0:
                plans.append(build_plan(
                    name=name,
                    network_type='NBN',
                    download_speed=download_speed,
                    upload_speed=upload_speed,
                    price=price,
                    promo_price=promo_price if promo_price != price else None,
                    promo_period=promo_period,
                    source_url=source_url,
                ))
        except Exception as e:
            log_error(f"Error extracting NBN card: {e}", provider="tpg")

    return plans


# ══════════════════════════════════════════════════════════════════
#  5G EXTRACTION — /5g-home-broadband page
# ══════════════════════════════════════════════════════════════════

def extract_5g_plans(page: Page, page_cfg: Dict) -> List[Dict[str, Any]]:
    """
    Extract 5G plans from div.plans text on the /5g-home-broadband page.
    Two plans: PLUS and PREMIUM, separated by plan type labels.
    """
    plans = []
    source_url = page_cfg['url']

    plans_div = page.query_selector('div.plans')
    if not plans_div:
        log_error("No div.plans found on 5G page", provider="tpg")
        return plans

    text = plans_div.inner_text()

    # Split text by plan type markers
    plan_blocks = re.split(r'(?=\bPLUS\b|\bPREMIUM\b|\bSTANDARD\b)', text)

    for block in plan_blocks:
        block = block.strip()
        if not block:
            continue

        # Plan type name
        type_match = re.match(r'(PLUS|PREMIUM|STANDARD)', block)
        if not type_match:
            continue
        plan_type = type_match.group(1)
        plan_name = f"5G Home Broadband {plan_type.title()}"

        dl = parse_speed_from_text(block, 'Download')
        ul = parse_speed_from_text(block, 'Upload')
        promo_price = parse_promo_price(block)
        regular_price = parse_regular_price(block)
        promo_period = parse_promo_period(block)
        price = regular_price if regular_price > 0 else promo_price

        if price > 0 and dl > 0:
            plans.append(build_plan(
                name=plan_name,
                network_type='5G',
                download_speed=dl,
                upload_speed=ul,
                price=price,
                promo_price=promo_price if promo_price != price else None,
                promo_period=promo_period,
                source_url=source_url,
            ))

    return plans


# ══════════════════════════════════════════════════════════════════
#  HOME WIRELESS EXTRACTION — /home-wireless-broadband page
# ══════════════════════════════════════════════════════════════════

def extract_wireless_plans(page: Page, page_cfg: Dict) -> List[Dict[str, Any]]:
    """
    Extract the single 4G Home Wireless plan from div.plans text.
    """
    plans = []
    source_url = page_cfg['url']

    plans_div = page.query_selector('div.plans')
    if not plans_div:
        log_error("No div.plans found on Home Wireless page", provider="tpg")
        return plans

    text = plans_div.inner_text()

    dl = parse_speed_from_text(text, 'Download')
    ul = parse_speed_from_text(text, 'Upload')
    promo_price = parse_promo_price(text)
    regular_price = parse_regular_price(text)
    promo_period = parse_promo_period(text)
    price = regular_price if regular_price > 0 else promo_price

    if price > 0 and dl > 0:
        plans.append(build_plan(
            name='Home Wireless Broadband',
            network_type='4G Home Wireless',
            download_speed=dl,
            upload_speed=ul,
            price=price,
            promo_price=promo_price if promo_price != price else None,
            promo_period=promo_period,
            source_url=source_url,
        ))

    return plans


# ══════════════════════════════════════════════════════════════════
#  FTTB EXTRACTION — /fttb page
# ══════════════════════════════════════════════════════════════════

def extract_fttb_plans(page: Page, page_cfg: Dict) -> List[Dict[str, Any]]:
    """
    Extract FTTB plans from .plan-card elements on the /fttb page.
    3 plans: FTTB25, FTTB100, FTTB Max.
    """
    plans = []
    source_url = page_cfg['url']

    cards = page.query_selector_all('.plan-card')
    log_info(f"Found {len(cards)} FTTB plan-cards", provider="tpg")

    for card in cards:
        try:
            text = card.inner_text()

            # Plan name — look for FTTB pattern
            name_match = re.search(r'(FTTB\s*\w+)', text)
            plan_name = name_match.group(1).strip() if name_match else ''

            dl_el = card.query_selector('.download-speed')
            ul_el = card.query_selector('.upload-speed')
            download_speed = parse_speed(dl_el.inner_text()) if dl_el else 0
            upload_speed = parse_speed(ul_el.inner_text()) if ul_el else 0

            # FTTB price: regular from "then $XX.XX/mth", promo from "$0/mth for 3 months" banner
            regular_price = parse_regular_price(text)
            promo_period = parse_fttb_promo_period(text)

            # FTTB promo is $0/mth — check for explicit "$0/mth" or "$0 /mth" at start
            fttb_promo_match = re.search(r'\$\s*0\s*/mth', text)
            has_zero_promo = fttb_promo_match is not None and regular_price > 0

            if plan_name and regular_price > 0 and download_speed > 0:
                plans.append(build_plan(
                    name=plan_name,
                    network_type='FTTB',
                    download_speed=download_speed,
                    upload_speed=upload_speed,
                    price=regular_price,
                    promo_price=0.0 if has_zero_promo else None,
                    promo_period=promo_period if has_zero_promo else '',
                    source_url=source_url,
                ))
        except Exception as e:
            log_error(f"Error extracting FTTB card: {e}", provider="tpg")

    return plans


# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════

def build_plan(name, network_type, download_speed, upload_speed,
               price, promo_price, promo_period, source_url):
    """Build a standardised plan dict."""
    return {
        'provider_id': config.PROVIDERS.get('tpg', {}).get('id', 6),
        'plan_name': name,
        'network_type': network_type,
        'download_speed': download_speed,
        'upload_speed': upload_speed,
        'typical_evening_dl': download_speed,
        'typical_evening_ul': upload_speed,
        'price': price,
        'promo_price': promo_price,
        'promo_period': promo_period,
        'contract': 'No Lock-in',
        'source_url': source_url,
    }


def parse_speed(text: str) -> float:
    """Parse speed from text like '50Mbps' or '0.8Mbps'."""
    match = re.search(r'([\d.]+)\s*Mbps', text, re.IGNORECASE)
    return float(match.group(1)) if match else 0


def parse_speed_from_text(text: str, direction: str) -> float:
    """Parse speed from block text like '50Mbps\\nDownload'."""
    pattern = rf'([\d.]+)\s*Mbps\s*\n?\s*{direction}'
    match = re.search(pattern, text, re.IGNORECASE)
    return float(match.group(1)) if match else 0


def parse_promo_price(text: str) -> float:
    """
    Parse promo price. TPG formats:
      - "$64/mth.99" → 64.99 (split dollar/cents around /mth)
      - "64\n.99\n/mth" → 64.99 (whitespace-separated)
      - "$0 /mth" → 0.0
    """
    # Format: "XX\n.YY\n/mth" or "XX\nYY\n/Mth"
    m = re.search(r'(\d+)\s*\n\s*\.?(\d{2})\s*\n\s*/[Mm]th', text)
    if m:
        return float(f"{m.group(1)}.{m.group(2)}")

    # Format: "$XX/mth.YY"
    m = re.search(r'\$\s*(\d+)\s*/mth\s*\.(\d+)', text)
    if m:
        return float(f"{m.group(1)}.{m.group(2)}")

    # Format: "$XX.YY/mth"
    m = re.search(r'\$\s*(\d+\.\d+)\s*/mth', text)
    if m:
        return float(m.group(1))

    # Format: "$0 /mth"
    m = re.search(r'\$\s*(\d+)\s*/mth', text)
    if m:
        return float(m.group(1))

    return 0.0


def parse_regular_price(text: str) -> float:
    """Parse regular price from 'then $XX.YY/mth' or 'then$XX.YY/mth'."""
    m = re.search(r'then\s*\$?\s*([\d.]+)\s*/mth', text)
    return float(m.group(1)) if m else 0.0


def parse_promo_period(text: str) -> str:
    """Parse promo period from 'first N months' or 'for N months'."""
    m = re.search(r'(?:first|for)\s+(\d+)\s+months?', text, re.IGNORECASE)
    return f"{m.group(1)} months" if m else ''


def parse_fttb_promo_period(text: str) -> str:
    """Parse FTTB promo period — '$0/mth for 3 months' pattern."""
    m = re.search(r'(?:first|for)\s+(\d+)\s+months?', text, re.IGNORECASE)
    return f"{m.group(1)} months" if m else ''


def deduplicate_plans(plans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate plans by name+price key.
    When duplicates exist (e.g. different speed tiers for same plan name + price),
    keep the one with the higher download speed.
    """
    best = {}
    for plan in plans:
        key = f"{plan.get('plan_name')}_{plan.get('price')}"
        if key not in best or plan.get('download_speed', 0) > best[key].get('download_speed', 0):
            best[key] = plan
    return list(best.values())
