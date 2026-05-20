"""
MATE ISP Provider Scraper
Scrapes all 7 NBN plans from MATE's individual plan sub-pages under:
  https://www.letsbemates.com.au/mate/<plan-slug>/

DOM structure confirmed via investigate_mate.py:
  - Plan card wrapper : div.card.h-100
  - Plan name         : h3.fw-bold.text-purple           (e.g. "Crikey")
  - Speed tier label  : h4.text-lowercase                (e.g. "nbn® 25/10")
  - Speed box         : div.speed-box                    ("25 Mbps\nDownload Speed\n10 Mbps\nUpload Speed")
  - Regular price     : span.text-decoration-line-through (strikethrough, e.g. "$76")
  - Promo price       : span.text-green                  (active price, e.g. "$51")
  - Promo footnote    : div.plan-type p.fs-12            ("*for the first 6 months, then reverts to $76/month")

All pages return HTTP 500 to plain HTTP clients but render correctly in Playwright.
Uses a single browser session across all 7 plan pages.
"""

import re
import sys
import os
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from utils.logger import log_info, log_error, log_success, log_warning
from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright

PROVIDER_ID = config.PROVIDERS.get('mate', {}).get('id', 16)
PROVIDER_NAME = 'mate'

# ---------------------------------------------------------------------------
# Plan definitions
# Each entry maps the plan slug to its nominal (advertised) speed tier.
# Actual typical speeds are scraped live from the speed-box on each page.
# ---------------------------------------------------------------------------
MATE_PLANS = {
    'crikey': {
        'url': 'https://www.letsbemates.com.au/mate/crikey-nbn-25-10/',
        'download_speed': 25,
        'upload_speed': 10,
        'network_type': 'NBN',
    },
    'ripper': {
        'url': 'https://www.letsbemates.com.au/mate/ripper-nbn-50-20/',
        'download_speed': 50,
        'upload_speed': 20,
        'network_type': 'NBN',
    },
    'no_worries_100': {
        'url': 'https://www.letsbemates.com.au/mate/no-worries-100-20/',
        'download_speed': 100,
        'upload_speed': 20,
        'network_type': 'NBN',
    },
    'you_beaut': {
        'url': 'https://www.letsbemates.com.au/mate/you-beaut-100-40/',
        'download_speed': 100,
        'upload_speed': 40,
        'network_type': 'NBN',
    },
    'no_worries_500': {
        'url': 'https://www.letsbemates.com.au/mate/no-worries-500-50/',
        'download_speed': 500,
        'upload_speed': 50,
        'network_type': 'NBN',
    },
    'fair_dinkum': {
        'url': 'https://www.letsbemates.com.au/mate/fair-dinkum-750-50/',
        'download_speed': 750,
        'upload_speed': 50,
        'network_type': 'NBN',
    },
    'flamin_fast': {
        'url': 'https://www.letsbemates.com.au/mate/flamin-fast-1000-100/',
        'download_speed': 1000,
        'upload_speed': 100,
        'network_type': 'NBN',
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_price(text: str) -> Optional[float]:
    """Extract a dollar amount from text like '$76' or '$51.00'."""
    m = re.search(r'\$(\d+(?:\.\d+)?)', text)
    return float(m.group(1)) if m else None


def _parse_speed(text: str) -> int:
    """Extract the first integer from a speed string like '25 Mbps' or '97 Mbps'."""
    m = re.search(r'(\d+)', text)
    return int(m.group(1)) if m else 0


def _parse_promo_period(text: str) -> Optional[str]:
    """
    Extract promo duration from footnote text.
    e.g. '*for the first 6 months, then reverts to $76/month' -> '6 months'
    """
    m = re.search(r'(\d+)\s*months?', text, re.IGNORECASE)
    return f"{m.group(1)} months" if m else None


# ---------------------------------------------------------------------------
# Page scraper
# ---------------------------------------------------------------------------

def _scrape_plan_page(
    browser,
    slug: str,
    plan_meta: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Navigate to a single MATE plan sub-page and extract all plan fields.

    Selector strategy (confirmed via investigate_mate.py):
      1. card wrapper  : div.card.h-100
      2. plan name     : h3 inside card-header
      3. speed tier    : h4 inside card-header
      4. speeds        : div.speed-box  (first two numeric lines = DL / UL Mbps)
      5. regular price : span.text-decoration-line-through
      6. promo price   : span.text-green
      7. promo period  : div.plan-type p.fs-12  (footnote)
    """
    url = plan_meta['url']
    page = None

    try:
        page = create_stealth_page(browser)

        # networkidle gives React/JS time to hydrate; retry with domcontentloaded
        # if the timeout fires (e.g. analytics scripts hang)
        try:
            page.goto(url, timeout=45000, wait_until='networkidle')
        except Exception:
            log_warning(f"networkidle timed out for {slug}, retrying with domcontentloaded",
                        provider=PROVIDER_NAME)
            page.goto(url, timeout=45000, wait_until='domcontentloaded')

        # Extra wait for keen-slider / React hydration
        page.wait_for_timeout(4000)

        # ── locate the primary plan card ─────────────────────────────────────
        # The plan card is always the first div.card.h-100 on the page
        card = page.query_selector('div.card.h-100')
        if not card:
            log_warning(f"No div.card.h-100 found on {slug} page, trying .singleplan-container",
                        provider=PROVIDER_NAME)
            card = page.query_selector('.singleplan-container')
        if not card:
            log_error(f"Cannot locate plan card on {slug} — skipping", provider=PROVIDER_NAME)
            return None

        # ── plan name (h3 inside card-header) ────────────────────────────────
        plan_name_el = card.query_selector('h3')
        plan_name_raw = plan_name_el.inner_text().strip() if plan_name_el else slug.replace('_', ' ').title()
        plan_name = f"MATE {plan_name_raw}"

        # ── speed tier label (h4 inside card-header) ─────────────────────────
        # e.g. "nbn® 25/10" — useful for the plan name suffix
        speed_tier_el = card.query_selector('h4')
        speed_tier = speed_tier_el.inner_text().strip() if speed_tier_el else ''
        # Clean up the registered trademark symbol for display
        speed_tier_clean = speed_tier.replace('nbn®', 'nbn').strip()

        # Append speed tier to plan name for uniqueness (e.g. "MATE Crikey nbn 25/10")
        if speed_tier_clean:
            plan_name = f"{plan_name} {speed_tier_clean}"

        # ── actual speeds from speed-box ─────────────────────────────────────
        # Structure: "25 Mbps\nDownload Speed\n10 Mbps\nUpload Speed\n..."
        speed_box = card.query_selector('.speed-box')
        download_speed = plan_meta['download_speed']   # fallback to nominal
        upload_speed   = plan_meta['upload_speed']

        if speed_box:
            speed_text = speed_box.inner_text()
            lines = [l.strip() for l in speed_text.split('\n') if l.strip()]
            # Lines order: "<DL> Mbps", "Download Speed", "<UL> Mbps", "Upload Speed", ...
            for i, line in enumerate(lines):
                if 'Download Speed' in line and i > 0:
                    download_speed = _parse_speed(lines[i - 1]) or download_speed
                if 'Upload Speed' in line and i > 0:
                    upload_speed = _parse_speed(lines[i - 1]) or upload_speed

        # ── prices ───────────────────────────────────────────────────────────
        # Regular price: span with strikethrough class (the "thereafter" rate)
        regular_price_el = card.query_selector('span.text-decoration-line-through')
        regular_price = _parse_price(regular_price_el.inner_text()) if regular_price_el else None

        # Promo price: span.text-green (the discounted active price)
        promo_price_el = card.query_selector('span.text-green')
        promo_price = _parse_price(promo_price_el.inner_text()) if promo_price_el else None

        # ── promo period ─────────────────────────────────────────────────────
        # Footnote: "*for the first 6 months, then reverts to $76/month"
        promo_period = None
        footnote_el = card.query_selector('.plan-type p.fs-12')
        if footnote_el:
            promo_period = _parse_promo_period(footnote_el.inner_text())
        else:
            # Fallback: scan all p.fs-12 elements on the page
            for p_el in page.query_selector_all('p.fs-12'):
                txt = p_el.inner_text()
                if 'months' in txt.lower() and 'reverts' in txt.lower():
                    promo_period = _parse_promo_period(txt)
                    break

        # ── price fallback: parse full card text ─────────────────────────────
        if regular_price is None or promo_price is None:
            log_warning(f"Span selectors missed prices on {slug}, falling back to text parse",
                        provider=PROVIDER_NAME)
            card_text = card.inner_text()
            prices_found = re.findall(r'\$(\d+(?:\.\d+)?)', card_text)
            numeric_prices = sorted(set(float(p) for p in prices_found if float(p) > 10), reverse=True)
            if len(numeric_prices) >= 2:
                regular_price = regular_price or numeric_prices[0]
                promo_price   = promo_price   or numeric_prices[1]
            elif len(numeric_prices) == 1:
                regular_price = regular_price or numeric_prices[0]

        # ── validate minimum data ─────────────────────────────────────────────
        if regular_price is None:
            log_error(f"Could not extract regular price for {slug} — skipping",
                      provider=PROVIDER_NAME)
            return None

        plan = {
            'provider_id':    PROVIDER_ID,
            'provider':       PROVIDER_NAME,
            'plan_name':      plan_name,
            'network_type':   plan_meta['network_type'],
            'download_speed': download_speed,
            'upload_speed':   upload_speed,
            'speed_label':    plan_meta['download_speed'],   # nominal tier
            'price':          regular_price,
            'promo_price':    promo_price,
            'promo_period':   promo_period,
            'contract':       'No Contract',
            'source_url':     url,
        }

        log_success(
            f"{plan_name}: ${regular_price}/mth"
            + (f" (promo ${promo_price} for {promo_period})" if promo_price else ""),
            provider=PROVIDER_NAME,
        )
        return plan

    except Exception as e:
        log_error(f"Error scraping {slug} ({url}): {str(e)}", provider=PROVIDER_NAME)
        return None

    finally:
        if page:
            page.close()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def scrape_mate_plans() -> List[Dict[str, Any]]:
    """
    Scrape all MATE NBN plans in a single browser session.

    Returns a flat list of plan dicts, one per plan page, sorted by
    nominal download speed (ascending).
    """
    log_info("Starting MATE scraper (7 NBN plan pages)", provider=PROVIDER_NAME)
    all_plans: List[Dict[str, Any]] = []

    try:
        with sync_playwright() as p:
            browser = create_stealth_browser(p)

            for slug, plan_meta in MATE_PLANS.items():
                log_info(f"Scraping plan: {slug} — {plan_meta['url']}", provider=PROVIDER_NAME)
                plan = _scrape_plan_page(browser, slug, plan_meta)
                if plan:
                    all_plans.append(plan)
                else:
                    log_warning(f"No data returned for plan slug: {slug}", provider=PROVIDER_NAME)

            browser.close()

    except Exception as e:
        log_error(f"MATE scraper failed: {str(e)}", provider=PROVIDER_NAME)

    # Sort by nominal speed tier ascending (25 -> 50 -> 100 -> 500 -> 750 -> 1000)
    all_plans.sort(key=lambda x: x.get('speed_label', 0))

    log_success(
        f"MATE scraper complete: {len(all_plans)}/{len(MATE_PLANS)} plans extracted",
        provider=PROVIDER_NAME,
    )
    return all_plans


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    plans = scrape_mate_plans()
    print(f"\nTotal plans found: {len(plans)}")
    print(f"{'Plan':<35} {'DL':>6} {'UL':>6} {'Regular':>9} {'Promo':>7} {'Period'}")
    print('-' * 80)
    for plan in plans:
        promo_str  = f"${plan['promo_price']:.0f}" if plan['promo_price'] else '  -  '
        period_str = plan['promo_period'] or ''
        print(
            f"{plan['plan_name']:<35} "
            f"{plan['download_speed']:>5}M "
            f"{plan['upload_speed']:>5}M "
            f"${plan['price']:>7.2f} "
            f"{promo_str:>7} "
            f"{period_str}"
        )
