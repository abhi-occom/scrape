"""
Telstra ISP plan scraper — multi-page.
Scrapes 4 Telstra product pages:
  - /internet/plans           → 17 plans (NBN + 5G, Internet Only & with modem)
  - /internet/5g-home-internet → 1 plan (5G Internet)
  - /internet/starlink        → 1 plan (Satellite, powered by Starlink)
  - /small-business/internet  → 11 plans (Business tiers)
All pages use the same data-attribute selectors for consistent extraction.
Returns Dict[str, List[Dict]] keyed by page name.
"""

import re
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright
import config
from utils.logger import log_info, log_error, log_success
from utils.stealth import create_stealth_browser, create_stealth_page


TELSTRA_PAGES = {
    'plans': {
        'url': 'https://www.telstra.com.au/internet/plans',
        'network_type': 'NBN',      # default; overridden per-plan if 5G detected
    },
    '5g_home': {
        'url': 'https://www.telstra.com.au/internet/5g-home-internet',
        'network_type': '5G',
    },
    'starlink': {
        'url': 'https://www.telstra.com.au/internet/starlink',
        'network_type': 'Satellite (Starlink)',
    },
    'small_business': {
        'url': 'https://www.telstra.com.au/small-business/internet',
        'network_type': 'Business NBN',  # default; overridden if 5G detected
    },
}


def scrape_telstra_plans() -> Dict[str, List[Dict[str, Any]]]:
    """
    Scrape all Telstra pages.
    Returns dict of {page_key: [plans]}.
    """
    all_results = {}

    with sync_playwright() as p:
        browser = create_stealth_browser(p)

        for page_key, page_cfg in TELSTRA_PAGES.items():
            page = create_stealth_page(browser)
            try:
                url = page_cfg['url']
                log_info(f"Scraping {page_key}: {url}", provider="telstra")
                resp = page.goto(url, timeout=30000, wait_until="domcontentloaded")
                log_info(f"Status: {resp.status if resp else 'none'}", provider="telstra")
                page.wait_for_timeout(6000)

                plans = extract_plans_from_page(page, page_cfg)
                plans = deduplicate_plans(plans)
                all_results[page_key] = plans
                log_success(f"{page_key}: {len(plans)} plans", provider="telstra")

            except Exception as e:
                log_error(f"Error scraping {page_key}: {e}", provider="telstra")
                all_results[page_key] = []
            finally:
                page.close()

        browser.close()

    total = sum(len(v) for v in all_results.values())
    log_success(f"Total Telstra plans: {total}", provider="telstra")
    return all_results


def scrape_via_playwright() -> List[Dict[str, Any]]:
    """
    Legacy single-list interface (backward-compatible).
    Flattens all pages into one list.
    """
    results = scrape_telstra_plans()
    flat = []
    for plans in results.values():
        flat.extend(plans)
    return flat


def extract_plans_from_page(page, page_cfg: Dict) -> List[Dict[str, Any]]:
    """
    Extract plans from a Telstra page using data-attribute selectors.
    Works consistently across all 4 page types.
    """
    plans = []

    headers = page.query_selector_all('h3.tcom-fixed-plan-card-header__headline')
    prices = page.query_selector_all('[data-fixed-plan-card-price]')
    downloads = page.query_selector_all('[data-tcom-fixed-plancard-dsq-evening-download]')
    uploads = page.query_selector_all('[data-tcom-fixed-plancard-dsq-evening-upload]')

    source_url = page_cfg['url']
    default_network = page_cfg['network_type']

    for i, header in enumerate(headers):
        # Plan name from data attribute or inner text
        plan_name = header.get_attribute('data-tcom-fixed-plan-card-header-label') or ''
        if not plan_name:
            raw = header.inner_text().strip()
            plan_name = raw.split('\n')[0].replace('Online exclusive offer', '').strip()

        # Price
        price = 0.0
        if i < len(prices):
            price_val = prices[i].get_attribute('data-fixed-plan-card-price') or '0'
            try:
                price = float(re.sub(r'[^\d.]', '', price_val))
            except ValueError:
                price = 0.0

        # Download speed
        download_speed = 0
        if i < len(downloads):
            dl_val = downloads[i].get_attribute('data-tcom-fixed-plancard-dsq-evening-download') or '0'
            download_speed = extract_first_number(dl_val)

        # Upload speed
        upload_speed = 0
        if i < len(uploads):
            ul_val = uploads[i].get_attribute('data-tcom-fixed-plancard-dsq-evening-upload') or '0'
            upload_speed = extract_first_number(ul_val)

        # Network type — detect from plan name
        network_type = default_network
        if '5G' in plan_name:
            network_type = '5G'
        elif 'Satellite' in plan_name or 'Starlink' in plan_name.lower():
            network_type = 'Satellite (Starlink)'

        if plan_name and price > 0:
            plans.append({
                'provider_id': config.PROVIDERS['telstra']['id'],
                'plan_name': plan_name,
                'network_type': network_type,
                'download_speed': download_speed,
                'upload_speed': upload_speed,
                'typical_evening_dl': download_speed,
                'typical_evening_ul': upload_speed,
                'price': price,
                'promo_price': None,
                'promo_period': None,
                'contract': 'No Lock-in',
                'source_url': source_url,
            })

    return plans


def deduplicate_plans(plans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate plans by name+price combination."""
    seen = set()
    unique = []
    for plan in plans:
        key = f"{plan.get('plan_name')}_{plan.get('price')}_{plan.get('download_speed')}"
        if key not in seen:
            seen.add(key)
            unique.append(plan)
    return unique


def extract_first_number(text: str) -> int:
    """Extract first integer from text like '2-23' or '300'."""
    # For ranges like "2-23", take the higher number (typical evening)
    range_match = re.match(r'(\d+)-(\d+)', text.strip())
    if range_match:
        return int(range_match.group(2))
    match = re.search(r'(\d+)', text)
    return int(match.group(1)) if match else 0
