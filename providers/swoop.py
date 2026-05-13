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

    Swoop renders plan cards as <div class="card card--plan fixed consumer">.
    Each card contains:
      - .subheading  → speed tier string e.g. "25/10 Mbps", "500/50 Mbps"
      - .card__price → two <span>s: first is strikethrough (original), second is promo price
      - .coupon      → promo description e.g. "$15/mth off for 6 months"
    The plan type label ("nbn", "Swoop Fixed Wireless", "Opticomm Fibre") is in
    the first text node / .card__header area above the subheading.
    """
    plans = []
    page = None

    try:
        page = create_stealth_page(browser)
        page.goto(url, timeout=30000, wait_until='domcontentloaded')
        page.wait_for_timeout(5000)

        # Target the precise card selector confirmed via investigation
        plan_cards = page.query_selector_all('.card--plan')
        log_info(f"Found {len(plan_cards)} .card--plan elements on {url}", provider="swoop")

        seen = set()
        for card in plan_cards:
            try:
                card_text = card.inner_text()

                # --- Plan name: first line of card text (e.g. "nbn", "Swoop Fixed Wireless") ---
                first_line = card_text.strip().split('\n')[0].strip()

                # --- Speed tier from .subheading (e.g. "25/10 Mbps", "500/50 Mbps") ---
                subheading_el = card.query_selector('.subheading')
                speed_str = subheading_el.inner_text().strip() if subheading_el else ''

                # Build a descriptive plan name: "<type> <speed_tier>"
                if speed_str:
                    plan_name = f"{first_line} {speed_str}".strip()
                else:
                    plan_name = first_line

                # --- Parse download/upload from "DL/UL Mbps" pattern in speed_str ---
                # e.g. "25/10 Mbps", "1000/100 Mbps", "250/100 Mbps"
                download_speed = 0
                upload_speed = 0
                speed_pair = re.search(r'(\d+)\s*/\s*(\d+)', speed_str)
                if speed_pair:
                    download_speed = int(speed_pair.group(1))
                    upload_speed = int(speed_pair.group(2))
                else:
                    # Single speed value fallback
                    single = re.search(r'(\d+)\s*[Mm]bps', speed_str)
                    if single:
                        download_speed = int(single.group(1))

                # --- Prices from .card__price spans ---
                # Structure: <span class="discount strikethrough">$69</span>
                #            <span class="discount-price">$54</span>
                price_spans = card.query_selector_all('.card__price span')
                prices_raw = []
                for span in price_spans:
                    span_text = span.inner_text().strip()
                    m = re.search(r'\$?([\d]+(?:\.\d+)?)', span_text)
                    if m:
                        val = float(m.group(1))
                        if val > 0:
                            prices_raw.append(val)

                if len(prices_raw) >= 2:
                    # First span = original (higher) price, second span = promo (lower) price
                    original_price = prices_raw[0]
                    promo_price = prices_raw[1]
                elif len(prices_raw) == 1:
                    original_price = prices_raw[0]
                    promo_price = None
                else:
                    # Fallback: regex whole card text but exclude the "min. cost" line
                    card_no_mincost = re.sub(r'\$[\d,]+\s*min\.\s*cost[^\n]*', '', card_text)
                    all_prices = [float(x) for x in re.findall(r'\$([\d]+(?:\.\d+)?)', card_no_mincost) if float(x) > 0]
                    if len(all_prices) >= 2:
                        original_price = max(all_prices)
                        promo_price = min(all_prices)
                    elif all_prices:
                        original_price = all_prices[0]
                        promo_price = None
                    else:
                        log_warning(f"No price found for card: {repr(card_text[:80])}", provider="swoop")
                        continue

                # --- Promo period from .coupon (e.g. "$15/mth off for 6 months") ---
                coupon_el = card.query_selector('.coupon')
                promo_period = None
                if coupon_el:
                    coupon_text = coupon_el.inner_text().strip()
                    period_match = re.search(r'for\s+(\d+\s*months?)', coupon_text, re.IGNORECASE)
                    if period_match:
                        promo_period = period_match.group(1)

                # Deduplicate
                key = f"{plan_name}_{original_price}"
                if key in seen:
                    continue
                seen.add(key)

                plans.append(build_plan(
                    name=plan_name,
                    network_type=network_type,
                    download_speed=download_speed,
                    upload_speed=upload_speed,
                    price=original_price,
                    promo_price=promo_price,
                    promo_period=promo_period,
                    source_url=url,
                ))

            except Exception as e:
                log_error(f"Error extracting plan from card: {str(e)}", provider="swoop")
                continue

        # --- Fallback: parse full page text if no cards found ---
        if not plans:
            log_warning(f"No .card--plan elements found on {url}, trying text parse fallback", provider="swoop")
            plans = parse_plans_from_page_text(page, network_type, url)

    except Exception as e:
        log_error(f"Error scraping {url}: {str(e)}", provider="swoop")
    finally:
        if page:
            page.close()

    return plans


def parse_plans_from_page_text(page: Page, network_type: str, source_url: str) -> List[Dict[str, Any]]:
    """
    Fallback: parse the full page text when .card--plan elements are not found.
    Looks for speed-tier + dual-price patterns matching Swoop's card layout:
      '25/10 Mbps ... $69 $54 ... per month'
    """
    plans = []
    try:
        body_text = page.inner_text('body')

        # Match blocks anchored on a "DL/UL Mbps" speed string, then two consecutive prices
        # Pattern: <speed> ... $<original> $<promo> ... per month
        blocks = re.finditer(
            r'(\d+/\d+\s*Mbps)'              # speed tier
            r'[\s\S]{0,300}?'               # card content
            r'\$(\d+(?:\.\d+)?)\s+'         # original price
            r'\$(\d+(?:\.\d+)?)'            # promo price
            r'[\s\S]{0,50}?per\s*month',    # anchor on 'per month'
            body_text,
            re.IGNORECASE,
        )

        seen = set()
        for m in blocks:
            speed_str = m.group(1).strip()
            original_price = float(m.group(2))
            promo_price = float(m.group(3))

            # Skip if promo >= original (likely mis-matched)
            if promo_price >= original_price:
                original_price, promo_price = promo_price, original_price

            speed_pair = re.search(r'(\d+)/(\d+)', speed_str)
            download_speed = int(speed_pair.group(1)) if speed_pair else 0
            upload_speed = int(speed_pair.group(2)) if speed_pair else 0

            plan_name = f"{network_type} {speed_str}"
            key = f"{plan_name}_{original_price}"
            if key in seen:
                continue
            seen.add(key)

            plans.append(build_plan(
                name=plan_name,
                network_type=network_type,
                download_speed=download_speed,
                upload_speed=upload_speed,
                price=original_price,
                promo_price=promo_price,
                promo_period='6 months',
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
    for plan in plans:
        promo = f" (promo: ${plan['promo_price']})" if plan['promo_price'] else ""
        print(f"  - {plan['plan_name']} [{plan['network_type']}]: ${plan['price']}/mth{promo}")