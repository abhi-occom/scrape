# scrape/providers/tangerine.py
"""
Tangerine ISP provider scraper.

Scrapes https://www.tangerine.com.au/nbn/nbn-broadband and
https://www.tangerine.com.au/nbn/nbn-fixed-wireless.

DOM structure confirmed 2026-09-17 via a live-page probe. Tangerine only
renders 3 speed tiers per page before an address is entered — the remaining
tiers (e.g. Value Plus, Speedy, Speedy Plus) are address-gated and only
appear after an eligible address lookup, so they are not scraped here (there
is no generic address that reliably unlocks them).

Card root:   div.plan-bl.plan-speed
  Sub-selectors:
    button[data-product-type="speed"]
      data-product-name   → plan name, e.g. "Value", "Speedy Max", "Fixed Wireless Value Plus"
      data-product-price  → currently advertised (discounted) price, e.g. "42.90"
      data-cart-type       → "nbn-broadband" | "nbn-fixed-wireless"
    p.top_height          → "25Mbps Download /8.5Mbps Upload Typical Evening Speed (7-11pm)"
    p.plan_footer         → "For 6 months, then $72.90 ongoing*"
                             (Fixed Wireless wording differs slightly:
                             "$63.90 for first full 6 months, then $88.90 ongoing...")

Pricing logic:
  • data-product-price is the currently advertised price.
  • p.plan_footer's "then $X ongoing" value, when present, is the regular
    price once the promo period ends — in that case
    promo_price = data-product-price and price = the ongoing value.
    Otherwise there's no active promo and price = data-product-price.
"""
import re
import sys
import os
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from utils.logger import log_info, log_error, log_success, log_warning
from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright, ElementHandle

PROVIDER_ID: int = config.PROVIDERS.get('tangerine', {}).get('id', 15)
NBN_URL: str = 'https://www.tangerine.com.au/nbn/nbn-broadband'
FIXED_WIRELESS_URL: str = 'https://www.tangerine.com.au/nbn/nbn-fixed-wireless'


# ── helpers ──────────────────────────────────────────────────────────────────

_RE_SPEED = re.compile(
    r'(\d+(?:\.\d+)?)\s*Mbps\s*download.*?(\d+(?:\.\d+)?)\s*Mbps\s*upload',
    re.IGNORECASE | re.DOTALL,
)
_RE_ONGOING_PRICE = re.compile(r'then\s*\$(\d+(?:\.\d+)?)\s*ongoing', re.IGNORECASE)
_RE_PERIOD_MONTHS = re.compile(r'(\d+)\s*months?', re.IGNORECASE)


def _num(value: float):
    """Render whole-number floats as ints, matching other providers' convention."""
    return int(value) if float(value).is_integer() else value


def _extract_card(card: ElementHandle, network_type: str, source_url: str) -> Optional[Dict[str, Any]]:
    """Extract a single plan dict from a .plan-bl.plan-speed card."""
    try:
        button = card.query_selector('button[data-product-type="speed"]')
        if button is None:
            return None

        plan_name = (button.get_attribute('data-product-name') or '').strip()
        price_raw = button.get_attribute('data-product-price')
        if not plan_name or not price_raw:
            log_warning('Tangerine: card missing plan name or price, skipping', provider='tangerine')
            return None
        advertised_price = float(price_raw)

        # ── speed ────────────────────────────────────────────────────────────
        speed_el   = card.query_selector('.top_height')
        speed_text = speed_el.inner_text().strip() if speed_el else ''
        speed_match = _RE_SPEED.search(speed_text)
        if not speed_match:
            log_warning(
                f'Tangerine: could not parse speed for "{plan_name}" from "{speed_text}", skipping card',
                provider='tangerine',
            )
            return None
        download_speed = _num(float(speed_match.group(1)))
        upload_speed   = _num(float(speed_match.group(2)))

        # ── pricing (promo vs ongoing) ──────────────────────────────────────
        footer_el   = card.query_selector('.plan_footer')
        footer_text = footer_el.inner_text().strip() if footer_el else ''
        ongoing_match = _RE_ONGOING_PRICE.search(footer_text)
        period_match  = _RE_PERIOD_MONTHS.search(footer_text)

        if ongoing_match:
            regular_price = float(ongoing_match.group(1))
            promo_price   = advertised_price
            promo_period  = f'{period_match.group(1)} months' if period_match else None
        else:
            regular_price = advertised_price
            promo_price   = None
            promo_period  = None

        return {
            'provider_id':        PROVIDER_ID,
            'provider':           'tangerine',
            'plan_name':          f'Tangerine {plan_name}',
            'network_type':       network_type,
            'download_speed':     download_speed,
            'upload_speed':       upload_speed,
            'typical_evening_dl': download_speed,
            'typical_evening_ul': upload_speed,
            'price':              regular_price,
            'promo_price':        promo_price,
            'promo_period':       promo_period,
            'contract':           'No Lock-in',
            'source_url':         source_url,
        }

    except Exception as exc:
        log_error(f'Tangerine: error extracting card — {exc}', provider='tangerine')
        return None


def _scrape_page(page, url: str, network_type: str) -> List[Dict[str, Any]]:
    """Scrape all plan-speed cards from a single Tangerine page."""
    page.goto(url, timeout=40000, wait_until='domcontentloaded')
    page.wait_for_timeout(4000)

    cards = page.query_selector_all('.plan-bl.plan-speed')
    log_info(f'Found {len(cards)} plan-speed cards on {url}', provider='tangerine')

    plans = []
    for card in cards:
        plan = _extract_card(card, network_type, url)
        if plan:
            plans.append(plan)
    return plans


# ── main scraper ─────────────────────────────────────────────────────────────

def scrape_tangerine_plans() -> List[Dict[str, Any]]:
    """
    Scrape all currently-advertised Tangerine NBN and Fixed Wireless plans.

    Returns a flat list of standardised plan dicts sorted by download speed.
    """
    log_info('Starting Tangerine scraper', provider='tangerine')
    all_plans: List[Dict[str, Any]] = []

    try:
        with sync_playwright() as p:
            browser = create_stealth_browser(p)

            page = create_stealth_page(browser)
            all_plans.extend(_scrape_page(page, NBN_URL, 'NBN'))
            page.close()

            page = create_stealth_page(browser)
            all_plans.extend(_scrape_page(page, FIXED_WIRELESS_URL, 'Fixed Wireless'))
            page.close()

            browser.close()

    except Exception as exc:
        log_error(f'Tangerine scraper failed: {exc}', provider='tangerine')

    all_plans.sort(key=lambda x: x['download_speed'])

    log_success(
        f'Tangerine scraper complete: {len(all_plans)} plans '
        f'({sum(1 for p in all_plans if p["promo_price"])} with active promo)',
        provider='tangerine',
    )
    return all_plans


# ── standalone test ───────────────────────────────────────────────────────────

if __name__ == '__main__':
    plans = scrape_tangerine_plans()
    print(f'\nTotal plans: {len(plans)}\n')
    for plan in plans:
        promo = (
            f'  (promo ${plan["promo_price"]}/mth for {plan["promo_period"]})'
            if plan['promo_price'] else ''
        )
        print(
            f"  {plan['plan_name']:35}  "
            f"{plan['download_speed']:>4}/{plan['upload_speed']:<5} Mbps  "
            f"${plan['price']:.2f}/mth"
            f"{promo}"
        )
