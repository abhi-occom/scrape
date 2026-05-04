"""
Optus ISP plan scraper.
Uses Firefox browser (Chromium blocked by Optus with HTTP2 error).
Extracts plans from data-testid attributes on the NBN plans page.
"""

import re
from typing import List, Dict, Any
from playwright.sync_api import sync_playwright
import config
from utils.logger import log_info, log_error, log_success

OPTUS_URL = "https://www.optus.com.au/internet/nbn"


def scrape_via_playwright() -> List[Dict[str, Any]]:
    """
    Scrape Optus NBN plans using Firefox.
    Chromium is blocked (ERR_HTTP2_PROTOCOL_ERROR), so Firefox is required.
    """
    plans = []

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
            viewport={"width": 1280, "height": 720},
            locale="en-AU",
        )
        page = context.new_page()

        try:
            log_info(f"Navigating to {OPTUS_URL}", provider="optus")
            resp = page.goto(OPTUS_URL, timeout=30000, wait_until="domcontentloaded")
            log_info(f"Status: {resp.status if resp else 'no response'}", provider="optus")

            page.wait_for_timeout(5000)  # Wait for JS rendering

            plans = extract_plans(page)
            log_success(f"Extracted {len(plans)} plans from Optus", provider="optus")

        except Exception as e:
            log_error(f"Scraping error: {e}", provider="optus")
        finally:
            browser.close()

    return plans


def extract_plans(page) -> List[Dict[str, Any]]:
    """
    Extract plans using data-testid selectors.
    Each plan card has data-testid="plan-<id>" containing:
      - data-testid="plan-speed" (h3) — download speed e.g. "25 Mbps"
      - data-testid="plan-speed-legal-disclaimer" — network type
      - data-testid="plan-price-wrapper" — price e.g. "$ 49 /month"
      - data-testid="plan-block-price" — full price block with promo info
    """
    plans = []

    # Find all plan cards by data-testid pattern: plan-<digits>_<digits>
    plan_cards = page.query_selector_all('[data-testid^="plan-"][data-testid*="_"]')
    log_info(f"Found {len(plan_cards)} plan cards", provider="optus")

    for card in plan_cards:
        try:
            plan = extract_single_plan(card)
            if plan and plan.get('price', 0) > 0:
                plans.append(plan)
        except Exception as e:
            log_error(f"Failed to extract plan card: {e}", provider="optus")

    return plans


def extract_single_plan(card) -> Dict[str, Any]:
    """Extract data from a single plan card element."""

    # ── Speed ────────────────────────────────────────────────
    speed_el = card.query_selector('[data-testid="plan-speed"]')
    speed_text = speed_el.inner_text().strip() if speed_el else ""
    download_speed = extract_number(speed_text)

    # ── Full card text ───────────────────────────────────────
    full_text = card.inner_text()

    # Check for "Most Popular" badge
    badge = ""
    if "Most Popular" in full_text:
        badge = "Most Popular "

    # ── Network type ─────────────────────────────────────────
    disclaimer_el = card.query_selector('[data-testid="plan-speed-legal-disclaimer"]')
    disclaimer_text = disclaimer_el.inner_text().strip() if disclaimer_el else ""
    # "Typical Download Speed: FTTN, FTTC, FTTB" → "FTTN, FTTC, FTTB"
    network_type = "NBN"
    if ":" in disclaimer_text:
        network_part = disclaimer_text.split(":")[-1].strip()
        if network_part.lower() != "all nbn connections":
            network_type = network_part
        else:
            network_type = "NBN (all connections)"

    # ── Price ────────────────────────────────────────────────
    price_wrapper = card.query_selector('[data-testid="plan-price-wrapper"]')
    price_text = price_wrapper.inner_text().strip() if price_wrapper else ""
    promo_price = extract_price(price_text)

    # ── Full price block (contains promo period + regular price) ──
    price_block = card.query_selector('[data-testid="plan-block-price"]')
    price_block_text = price_block.inner_text().strip() if price_block else ""

    # Extract promo period: "for 6 months" or "for 12 months"
    promo_period = ""
    period_match = re.search(r'for\s+(\d+)\s+months?', price_block_text)
    if period_match:
        promo_period = f"{period_match.group(1)} months"

    # Extract regular price from fine print: "then $YY/month"
    regular_price = promo_price  # default
    then_match = re.search(r'then\s+\$(\d+(?:\.\d+)?)', full_text)
    if then_match:
        regular_price = float(then_match.group(1))

    # If no promo was found, regular = promo
    if regular_price == promo_price:
        promo_price_val = None
        final_price = regular_price
    else:
        promo_price_val = promo_price
        final_price = regular_price

    # ── Upload speed (from Optus speed tiers) ────────────────
    upload_speed = estimate_upload_speed(download_speed)

    # ── Plan name construction ───────────────────────────────
    plan_name = f"{badge}Optus {get_tier_name(download_speed, network_type)} {download_speed}Mbps"

    return {
        'provider_id': config.PROVIDERS['optus']['id'],
        'plan_name': plan_name.strip(),
        'network_type': network_type,
        'download_speed': download_speed,
        'upload_speed': upload_speed,
        'price': final_price,
        'promo_price': promo_price_val,
        'promo_period': promo_period,
        'contract': 'No Lock-in',
        'typical_evening_dl': download_speed,
        'typical_evening_ul': upload_speed,
        'source_url': OPTUS_URL,
    }


def get_tier_name(speed: int, network: str) -> str:
    """Map speed to Optus tier name."""
    if speed <= 25:
        return "Basic"
    elif speed <= 50:
        return "Everyday"
    elif speed <= 100:
        return "Fast"
    elif speed <= 500:
        return "Superfast"
    else:
        return "Ultrafast"


def estimate_upload_speed(download: int) -> int:
    """Estimate upload speed from Optus speed tiers."""
    mapping = {25: 5, 50: 10, 100: 20, 250: 22, 500: 43, 820: 80}
    return mapping.get(download, download // 5)


def extract_number(text: str) -> int:
    """Extract first integer from text."""
    match = re.search(r'(\d+)', text)
    return int(match.group(1)) if match else 0


def extract_price(text: str) -> float:
    """Extract dollar amount from text like '$ 49 /month'."""
    match = re.search(r'\$\s*(\d+(?:\.\d+)?)', text)
    return float(match.group(1)) if match else 0.0
