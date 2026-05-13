"""
Swoop ISP Provider Scraper
Scrapes internet plans from Swoop Broadband's three service types:
- NBN plans
- Fixed Wireless plans
- Opticomm plans

Uses direct Playwright automation — plans are rendered via JavaScript
and the generic renderer abstraction cannot extract per-card structured data.
"""

import re
import sys
import os
from typing import List, Dict, Any, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from utils.logger import log_info, log_error, log_success, log_warning
from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright, Page

PROVIDER_ID = config.PROVIDERS.get('swoop', {}).get('id', 10)

# Pages to scrape
SWOOP_PAGES = {
    'nbn': {
        'url': 'https://www.swoop.com.au/nbn/',
        'network_type': 'NBN',
    },
    'fixed_wireless': {
        'url': 'https://www.swoop.com.au/fixed-wireless/',
        'network_type': 'Fixed Wireless',
    },
    'opticomm': {
        'url': 'https://www.swoop.com.au/opticomm/',
        'network_type': 'Opticomm',
    },
}


def extract_speed(text: str) -> int:
    """Extract numeric Mbps value from a string like '100 Mbps' or '100/20'."""
    match = re.search(r'(\d+)', text)
    return int(match.group(1)) if match else 0


def extract_price(text: str) -> float:
    """Extract dollar amount from a string like '$89' or '$89.00/mth'."""
    match = re.search(r'\$?([\d]+(?:\.\d+)?)', text)
    return float(match.group(1)) if match else 0.0


def scrape_page(browser, url: str, network_type: str) -> List[Dict[str, Any]]:
    """
    Scrape plans from a single Swoop page using Playwright.

    Swoop uses a WordPress theme. Plan cards are rendered as:
      .vc_tta-panel  (tab panels — one per speed tier on NBN)
      or table rows / pricing-table blocks on other pages.

    We try multiple card selectors in order of specificity.
    """
    plans = []
    page = None

    try:
        page = create_stealth_page(browser)
        page.goto(url, timeout=30000, wait_until='domcontentloaded')
        page.wait_for_timeout(5000)

        # --- Strategy 1: .plan-card or .vc_tta-panel (NBN uses tabs) ---
        # NBN plans are in tab panels: .vc_tta-panel > .vc_tta-panel-header
        cards = page.query_selector_all(
            '.plan-card, [class*="plan-card"], [class*="planCard"], '
            '.vc_tta-panel, .et_pb_pricing_table, .pricing-table'
        )

        log_info(f"Found {len(cards)} candidate elements on {url}", provider="swoop")

        seen = set()
        for card in cards:
            try:
                # Try to extract plan name from heading
                name = ''
                for sel in ('h2', 'h3', 'h4', '[class*="title"]', '[class*="name"]'):
                    el = card.query_selector(sel)
                    if el:
                        name = el.inner_text().strip()
                        if name:
                            break
                if not name:
                    continue

                # Extract speed (100 Mbps, 100/20 Mbps, NBN 100)
                speed_match = re.search(
                    r'(NBN\s+\d+|\d+\s*Mbps|\d+\s*Mbps|\d+.*?Mbps)',
                    name, re.IGNORECASE
                )
                if not speed_match:
                    speed_match = re.search(
                        r'(\d+)\s*[\s/]*\s*(\d+)\s*[Mm]bps',
                        card.inner_text(),
                        re.IGNORECASE
                    )
                if not speed_match:
                    speed_match = re.search(
                        r'(\d+)\s*[Mm]bps',
                        card.inner_text(),
                        re.IGNORECASE
                    )

                download_speed = 0
                upload_speed = 0
                if speed_match:
                    match = speed_match.group(1)
                    if match:
                        download_speed = int(match)
                    if speed_match.group(2):
                        upload_speed = int(speed_match.group(2))

                # Extract price: $X, $X.XX, $X/mth
                price_match = re.search(r'\$([\d]+(?:\.\d+)?)', card.inner_text())
                price = extract_price(card.inner_text())

                # Promo price: if two prices exist, lower is promo
                promo_price = None
                price_matches = re.findall(r'\$([\d]+(?:\.\d+)?)', card.inner_text())
                prices = [float(p) for p in price_matches if float(p) > 0]
                if len(prices) >= 2:
                    promo_price = min(prices)
                    price = max(prices)
                elif len(prices) == 1:
                    price = prices[0]

                # Build plan only if valid
                key = f"{name}_{price}"
                if key in seen:
                    continue
                seen.add(key)

                plans.append(build_plan(
                    name=name,
                    network_type=network_type,
                    download_speed=download_speed,
                    upload_speed=upload_speed,
                    price=price,
                    promo_price=promo_price,
                    promo_period='6 months',
                    source_url=url,
                ))

            except Exception as e:
                log_error(f"Error extracting plan from card: {str(e)}", provider="swoop")
                continue

        # --- Fallback: parse full page text if no cards found ---
        if not plans:
            log_warning(f"Card selectors found nothing on {url}, trying text parse", provider="swoop")
            plans = parse_plans_from_page_text(page, network_type, url)

    except Exception as e:
        log_error(f"Error scraping {url}: {str(e)}", provider="swoop")
    finally:
        if page:
            page.close()

    return plans


def parse_plans_from_page_text(page: Page, network_type: str, source_url: str) -> List[Dict[str, Any]]:
    """
    Fallback: scrape the full page text and extract plans using regex.
    Targets patterns like:
      NBN 50      $59/mth    50/20 Mbps
      NBN 100     $79/mth    100/20 Mbps
    """
    plans = []
    try:
        body_text = page.inner_text('body')

        # Match blocks: plan name, price, speed
        # Use more flexible pattern: NBN 50, 100 Mbps, 50 Mbps, Basic Plan, etc.
        blocks = re.finditer(
            r'(NBN\s+\d+|NBN\s*\d+|NBN\s*\d+ Mbps|NBN\s*\d+.*?Mbps|'
            r'\d+\s*Mbps|\d+\s*Mbps|Basic|Standard|Premium|Ultrafast|Superfast)'
            r'[\s\S]{0,100}?\$([\d]+(?:\.\d+)?)[^\n]*/(?:mth|month)'
            r'[\s\S]{0,100}?(?:\s*[\d]+(?:\s*/\s*\d+)?\s*[Mm]bps)',
            body_text,
            re.IGNORECASE
        )

        seen = set()
        for m in blocks:
            name = m.group(1).strip()
            price = float(m.group(2))
            speed_match = re.search(r'(\d+)\s*/\s*(\d+)\s*[Mm]bps', m.group(0))
            download_speed = extract_speed(speed_match.group(1)) if speed_match else 0
            upload_speed = extract_speed(speed_match.group(2)) if speed_match else 0

            key = f"{name}_{price}"
            if key in seen:
                continue
            seen.add(key)

            plans.append(build_plan(
                name=name,
                network_type=network_type,
                download_speed=download_speed,
                upload_speed=upload_speed,
                price=price,
                promo_price=None,
                promo_period=None,
                source_url=source_url,
            ))

    except Exception as e:
        log_error(f"Text parse fallback failed on {source_url}: {str(e)}", provider="swoop")

    return plans


def build_plan(
    name: str,
    network_type: str,
    download_speed: int,
    upload_speed: int,
    price: float,
    promo_price: Optional[float],
    promo_period: Optional[str],
    source_url: str,
) -> Dict[str, Any]:
    """Build a standardised Swoop plan dict."""
    return {
        'provider_id': PROVIDER_ID,
        'provider': 'swoop',
        'plan_name': name,
        'network_type': network_type,
        'download_speed': download_speed,
        'upload_speed': upload_speed,
        'speed_label': download_speed,
        'price': price,
        'promo_price': promo_price,
        'promo_period': promo_period,
        'contract': 'No Contract',
        'source_url': source_url,
    }


def scrape_swoop_nbn_plans() -> List[Dict[str, Any]]:
    """Scrape Swoop NBN plans from https://www.swoop.com.au/nbn/"""
    log_info("Starting Swoop NBN scraper", provider="swoop")
    cfg = SWOOP_PAGES['nbn']
    plans = []
    with sync_playwright() as p:
        browser = create_stealth_browser(p)
        plans = scrape_page(browser, cfg['url'], cfg['network_type'])
        browser.close()
    log_success(f"Swoop NBN: {len(plans)} plans", provider="swoop")
    return plans


def scrape_swoop_fixed_wireless_plans() -> List[Dict[str, Any]]:
    """Scrape Swoop Fixed Wireless plans from https://www.swoop.com.au/fixed-wireless/"""
    log_info("Starting Swoop Fixed Wireless scraper", provider="swoop")
    cfg = SWOOP_PAGES['fixed_wireless']
    plans = []
    with sync_playwright() as p:
        browser = create_stealth_browser(p)
        plans = scrape_page(browser, cfg['url'], cfg['network_type'])
        browser.close()
    log_success(f"Swoop Fixed Wireless: {len(plans)} plans", provider="swoop")
    return plans


def scrape_swoop_opticomm_plans() -> List[Dict[str, Any]]:
    """Scrape Swoop Opticomm plans from https://www.swoop.com.au/opticomm/"""
    log_info("Starting Swoop Opticomm scraper", provider="swoop")
    cfg = SWOOP_PAGES['opticomm']
    plans = []
    with sync_playwright() as p:
        browser = create_stealth_browser(p)
        plans = scrape_page(browser, cfg['url'], cfg['network_type'])
        browser.close()
    log_success(f"Swoop Opticomm: {len(plans)} plans", provider="swoop")
    return plans


def scrape_swoop_plans() -> List[Dict[str, Any]]:
    """
    Scrape all Swoop plans (NBN, Fixed Wireless, Opticomm) in a single
    browser session to avoid the overhead of three separate launches.
    """
    log_info("Starting Swoop scraper (all service types)", provider="swoop")
    all_plans = []

    try:
        with sync_playwright() as p:
            browser = create_stealth_browser(p)
            for page_key, cfg in SWOOP_PAGES.items():
                log_info(f"Scraping {page_key}: {cfg['url']}", provider="swoop")
                plans = scrape_page(browser, cfg['url'], cfg['network_type'])
                if plans:
                    log_success(f"{page_key}: {len(plans)} plans", provider="swoop")
                else:
                    log_warning(f"{page_key}: no plans found", provider="swoop")
                all_plans.extend(plans)
            browser.close()
    except Exception as e:
        log_error(f"Swoop scraper failed: {str(e)}", provider="swoop")

    log_success(f"Swoop total: {len(all_plans)} plans across all service types", provider="swoop")
    return all_plans


if __name__ == "__main__":
    print("Testing Swoop scraper...")
    plans = scrape_swoop_plans()
    print(f"\nTotal plans found: {len(plans)}")
    for plan in plans[:10]:
        promo = f" (promo: ${plan['promo_price']})" if plan['promo_price'] else ""
        print(f"  - {plan['plan_name']} [{plan['network_type']}]: ${plan['price']}/mth{promo}")