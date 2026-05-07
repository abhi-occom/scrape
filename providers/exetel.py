"""
Exetel ISP plan scraper — multi-page.
Scrapes 3 Exetel pages:
  - /broadband/nbn               → NBN plan(s) (One Plan 500/50 @ $80/mth)
  - /broadband/nbn-fibre-upgrade → FTTP Upgrade plan(s)
  - /mobilephone                 → 5G Mobile prepaid plans
Uses data-component attribute selectors:
  - [data-component="CMSPlanCardBroadband"] for broadband
  - [data-component="CMSPlanMobile"] for mobile
Returns Dict[str, List[Dict]] keyed by page name.
"""

import re
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright
import config
from utils.logger import log_info, log_error, log_success
from utils.stealth import create_stealth_browser, create_stealth_page


EXETEL_PAGES = {
    'nbn': {
        'url': 'https://www.exetel.com.au/broadband/nbn',
        'network_type': 'NBN',
        'method': 'broadband',
    },
    'nbn_fibre_upgrade': {
        'url': 'https://www.exetel.com.au/broadband/nbn-fibre-upgrade',
        'network_type': 'NBN FTTP Upgrade',
        'method': 'broadband',
    },
    'mobile': {
        'url': 'https://www.exetel.com.au/mobilephone',
        'network_type': '5G Mobile',
        'method': 'mobile',
    },
}

PROVIDER_ID = config.PROVIDERS.get('exetel', {}).get('id', 7)


def scrape_exetel_plans() -> Dict[str, List[Dict[str, Any]]]:
    """
    Scrape all Exetel pages.
    Returns dict of {page_key: [plans]}.
    """
    all_results = {}

    with sync_playwright() as p:
        browser = create_stealth_browser(p)

        for page_key, page_cfg in EXETEL_PAGES.items():
            page = create_stealth_page(browser)
            try:
                url = page_cfg['url']
                log_info(f"Scraping {page_key}: {url}", provider="exetel")
                resp = page.goto(url, timeout=30000, wait_until='domcontentloaded')
                log_info(f"Status: {resp.status if resp else 'none'}", provider="exetel")
                page.wait_for_timeout(6000)

                method = page_cfg['method']
                if method == 'broadband':
                    plans = extract_broadband_plans(page, page_cfg)
                elif method == 'mobile':
                    plans = extract_mobile_plans(page, page_cfg)
                else:
                    plans = []

                plans = deduplicate_plans(plans)
                all_results[page_key] = plans
                log_success(f"{page_key}: {len(plans)} plans", provider="exetel")

            except Exception as e:
                log_error(f"Error scraping {page_key}: {e}", provider="exetel")
                all_results[page_key] = []
            finally:
                page.close()

        browser.close()

    total = sum(len(v) for v in all_results.values())
    log_success(f"Total Exetel plans: {total}", provider="exetel")
    return all_results


def scrape_via_playwright() -> List[Dict[str, Any]]:
    """Legacy single-list interface (backward-compatible). Flattens all pages."""
    results = scrape_exetel_plans()
    flat = []
    for plans in results.values():
        flat.extend(plans)
    return flat


# ══════════════════════════════════════════════════════════════════
#  BROADBAND EXTRACTION — /broadband/nbn and /broadband/nbn-fibre-upgrade
# ══════════════════════════════════════════════════════════════════

def extract_broadband_plans(page, page_cfg: Dict) -> List[Dict[str, Any]]:
    """
    Extract broadband plans using [data-component="CMSPlanCardBroadband"].
    Each card structure:
      h3       → plan name  e.g. "One Plan 500/50"
      span[0]  → evening speed  e.g. "500/40Mbps"
      span[1]  → price amount   e.g. "$80"
      span[2]  → price period   e.g. "/mth"
    """
    plans = []
    source_url = page_cfg['url']
    network_type = page_cfg['network_type']

    cards = page.query_selector_all('[data-component="CMSPlanCardBroadband"]')
    log_info(f"Found {len(cards)} CMSPlanCardBroadband cards", provider="exetel")

    for card in cards:
        try:
            plan = extract_single_broadband_plan(card, network_type, source_url)
            if plan:
                plans.append(plan)
        except Exception as e:
            log_error(f"Error parsing broadband card: {e}", provider="exetel")

    return plans


def extract_single_broadband_plan(card, network_type: str, source_url: str) -> Optional[Dict[str, Any]]:
    """Extract data from a single broadband plan card."""
    full_text = card.inner_text().strip()
    if not full_text:
        return None

    # Plan name from h3
    h3_el = card.query_selector('h3')
    plan_name = h3_el.inner_text().strip() if h3_el else ''
    if not plan_name:
        return None

    # Price from span elements: span[1] = "$80", span[2] = "/mth"
    spans = card.query_selector_all('span')
    span_texts = [s.inner_text().strip() for s in spans]

    price = 0.0
    for i, txt in enumerate(span_texts):
        if txt.startswith('$') and i + 1 < len(span_texts) and 'mth' in span_texts[i + 1]:
            price = parse_price(txt)
            break
    if price == 0.0:
        # Fallback: parse price from full text
        price = parse_price_from_text(full_text)

    # Evening speed from span[0] — "500/40Mbps"
    evening_dl, evening_ul = 0, 0
    for txt in span_texts:
        m = re.search(r'(\d+)/(\d+)\s*Mbps', txt, re.IGNORECASE)
        if m:
            evening_dl = int(m.group(1))
            evening_ul = int(m.group(2))
            break

    # Nominal speed from plan name — "One Plan 500/50"
    download_speed, upload_speed = evening_dl, evening_ul
    name_speed = re.search(r'(\d+)/(\d+)', plan_name)
    if name_speed:
        download_speed = int(name_speed.group(1))
        upload_speed = int(name_speed.group(2))

    if price <= 0 or download_speed <= 0:
        return None

    return build_plan(
        name=plan_name,
        network_type=network_type,
        download_speed=download_speed,
        upload_speed=upload_speed,
        typical_evening_dl=evening_dl,
        typical_evening_ul=evening_ul,
        price=price,
        promo_price=None,
        promo_period='',
        contract='No Lock-in',
        source_url=source_url,
    )


# ══════════════════════════════════════════════════════════════════
#  MOBILE EXTRACTION — /mobilephone
# ══════════════════════════════════════════════════════════════════

def extract_mobile_plans(page, page_cfg: Dict) -> List[Dict[str, Any]]:
    """
    Extract mobile plans using [data-component="CMSPlanMobile"].
    Each card structure:
      h3[0]  → plan name   e.g. "PLUS ONE"
      h3[1]  → data        e.g. "130GB"
      span[0] → price      e.g. "$40"
      span[1] → period     e.g. "/recharge"
      text   → "capped at 150 Mbps" for speed
    """
    plans = []
    source_url = page_cfg['url']
    network_type = page_cfg['network_type']

    cards = page.query_selector_all('[data-component="CMSPlanMobile"]')
    log_info(f"Found {len(cards)} CMSPlanMobile cards", provider="exetel")

    for card in cards:
        try:
            plan = extract_single_mobile_plan(card, network_type, source_url)
            if plan:
                plans.append(plan)
        except Exception as e:
            log_error(f"Error parsing mobile card: {e}", provider="exetel")

    return plans


def extract_single_mobile_plan(card, network_type: str, source_url: str) -> Optional[Dict[str, Any]]:
    """Extract data from a single mobile plan card."""
    full_text = card.inner_text().strip()
    if not full_text:
        return None

    h3_els = card.query_selector_all('h3')
    h3_texts = [el.inner_text().strip() for el in h3_els]

    # Plan name: first h3
    plan_name = h3_texts[0] if h3_texts else ''
    if not plan_name:
        return None

    # Data allowance: second h3 (e.g. "130GB")
    data_allowance = h3_texts[1] if len(h3_texts) > 1 else ''
    if data_allowance:
        plan_name = f"{plan_name} {data_allowance}"

    # Price from spans
    spans = card.query_selector_all('span')
    span_texts = [s.inner_text().strip() for s in spans]
    price = 0.0
    for txt in span_texts:
        if txt.startswith('$'):
            price = parse_price(txt)
            if price > 0:
                break
    if price == 0.0:
        price = parse_price_from_text(full_text)

    # Speed from text: "capped at NNN Mbps" or "NNN Mbps"
    speed_match = re.search(r'capped\s+at\s+([\d,]+)\s*Mbps', full_text, re.IGNORECASE)
    if not speed_match:
        speed_match = re.search(r'([\d,]+)\s*Mbps', full_text, re.IGNORECASE)
    download_speed = int(speed_match.group(1).replace(',', '')) if speed_match else 0

    if price <= 0:
        return None

    return build_plan(
        name=plan_name,
        network_type=network_type,
        download_speed=download_speed,
        upload_speed=0,
        typical_evening_dl=download_speed,
        typical_evening_ul=0,
        price=price,
        promo_price=None,
        promo_period='',
        contract='No Lock-in',
        source_url=source_url,
    )


# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════

def build_plan(name, network_type, download_speed, upload_speed,
               typical_evening_dl, typical_evening_ul,
               price, promo_price, promo_period, contract, source_url) -> Dict[str, Any]:
    """Build a standardised plan dict."""
    return {
        'provider_id': PROVIDER_ID,
        'provider': 'exetel',
        'plan_name': name,
        'network_type': network_type,
        'download_speed': download_speed,
        'upload_speed': upload_speed,
        'typical_evening_dl': typical_evening_dl,
        'typical_evening_ul': typical_evening_ul,
        'price': price,
        'promo_price': promo_price,
        'promo_period': promo_period,
        'contract': contract,
        'source_url': source_url,
    }


def parse_price(text: str) -> float:
    """Parse price from text like '$80' or '$40.99'."""
    m = re.search(r'\$\s*([\d]+(?:\.\d+)?)', text)
    return float(m.group(1)) if m else 0.0


def parse_price_from_text(text: str) -> float:
    """Fallback: parse price from full card text."""
    m = re.search(r'\$\s*([\d]+(?:\.\d+)?)\s*/(?:mth|month|recharge)', text, re.IGNORECASE)
    return float(m.group(1)) if m else 0.0


def deduplicate_plans(plans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate plans by (plan_name, price)."""
    seen = set()
    unique = []
    for plan in plans:
        key = (plan.get('plan_name', ''), plan.get('price', 0))
        if key not in seen:
            seen.add(key)
            unique.append(plan)
    return unique
