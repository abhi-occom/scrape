# scrape/providers/activ8me.py
"""Scrape internet plans from activ8me.net.au."""

import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from utils.logger import log_error, log_info, log_success
from utils.stealth import create_stealth_browser, create_stealth_page

PROVIDER_ID = 19
PROVIDER_NAME = "activ8me"
PLAN_URL = "https://www.activ8me.net.au/internet/nbn-fibre-fttp-hfc"


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _first_price(text: str) -> Optional[float]:
    match = re.search(r"\$([\d]+(?:\.\d+)?)", text or "")
    return float(match.group(1)) if match else None


def _parse_plan_speeds(text: str) -> Optional[Tuple[int, int]]:
    match = re.search(r"\bnbn\s*(?:®|Â®)?\s*(\d+)\s*/\s*(\d+)\b", text, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _parse_typical_speeds(text: str) -> Tuple[int, int]:
    section = re.search(
        r"Typical\s+Evening\s+Speed\s+(.+?)(?:Suited\s+for|Features|SELECT)",
        text,
        re.IGNORECASE,
    )
    if not section:
        return 0, 0

    speeds = [
        int(value)
        for value in re.findall(r"(\d+)\s*Mbps", section.group(1), re.IGNORECASE)
    ]
    if len(speeds) >= 2:
        return speeds[0], speeds[1]
    if len(speeds) == 1:
        return speeds[0], 0
    return 0, 0


def _parse_promo(text: str, current_price: float) -> Tuple[float, Optional[float], Optional[str]]:
    ongoing_match = re.search(
        r"then\s+\$([\d]+(?:\.\d+)?)\s*/?\s*mth\s+ongoing",
        text,
        re.IGNORECASE,
    )
    period_match = re.search(r"for\s+the\s+first\s+(\d+)\s+months?", text, re.IGNORECASE)

    if ongoing_match:
        regular_price = float(ongoing_match.group(1))
        promo_period = f"{period_match.group(1)} months" if period_match else None
        return regular_price, current_price, promo_period

    return current_price, None, None


def _extract_plan_from_item(item) -> Optional[Dict[str, Any]]:
    text = _clean_text(item.get_text(" ", strip=True))
    speeds = _parse_plan_speeds(text)
    if not speeds:
        return None

    current_price = _first_price(text)
    if current_price is None:
        return None

    download_speed, upload_speed = speeds
    typical_evening_dl, typical_evening_ul = _parse_typical_speeds(text)
    price, promo_price, promo_period = _parse_promo(text, current_price)

    headings = [_clean_text(tag.get_text(" ", strip=True)) for tag in item.find_all(["h3", "h4"])]
    plan_family = headings[0] if headings else f"NBN {download_speed}/{upload_speed}"
    allowance = next((heading for heading in headings if "GB" in heading or "Unlimited" in heading), "")
    plan_name = f"{plan_family} {allowance}".strip()

    return {
        "provider_id": PROVIDER_ID,
        "provider": PROVIDER_NAME,
        "network_type": "NBN",
        "plan_name": plan_name,
        "download_speed": download_speed,
        "upload_speed": upload_speed,
        "price": price,
        "promo_price": promo_price,
        "promo_period": promo_period,
        "contract": "Month-to-Month",
        "typical_evening_dl": typical_evening_dl,
        "typical_evening_ul": typical_evening_ul,
        "source_url": PLAN_URL,
    }


def scrape_activ8me_plans() -> List[Dict[str, Any]]:
    """Scrape activ8me NBN fibre plan cards into the standard output schema."""
    log_info("Starting activ8me scraper", provider=PROVIDER_NAME)
    plans: List[Dict[str, Any]] = []

    try:
        with sync_playwright() as p:
            browser = create_stealth_browser(p)
            page = create_stealth_page(browser)
            page.goto(PLAN_URL, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(8000)

            soup = BeautifulSoup(page.content(), "html.parser")
            seen = set()
            for item in soup.select('[data-slot="carousel-item"]'):
                plan = _extract_plan_from_item(item)
                if not plan:
                    continue

                key = (
                    plan["plan_name"].lower(),
                    plan["download_speed"],
                    plan["upload_speed"],
                    plan["price"],
                    plan.get("promo_price"),
                )
                if key in seen:
                    continue
                seen.add(key)
                plans.append(plan)

            browser.close()
    except Exception as exc:
        log_error(f"activ8me scraper failed: {exc}", provider=PROVIDER_NAME)

    log_success(f"activ8me scraper complete: {len(plans)} plans", provider=PROVIDER_NAME)
    return plans


if __name__ == "__main__":
    plans = scrape_activ8me_plans()
    print(f"Scraped {len(plans)} plans")
    for plan in plans:
        print(
            f"  {plan['plan_name']}: "
            f"{plan['download_speed']}/{plan['upload_speed']} Mbps, "
            f"${plan['price']}/mth"
        )
