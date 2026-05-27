# -*- coding: ascii -*-
"""iiNet ISP plan scraper -- multi-page.

Scrapes 4 iiNet product pages:

  - /broadband/nbn/plans/fibre  -> 8 .card elements across 3 network types:
        NBN FTTP plans (NBN25, NBN50, NBN500, NBN Superfast, NBN Ultrafast)
        5G Home Broadband plans (5G Plus, 5G Premium)
        4G Home Wireless plan (Home Wireless Broadband)

  - /broadband/nbn/plans/wireless -> Angular address-lookup app (1 visible plan:
        NBN Fixed Wireless NBN25 -- scraped from page body text)

  - /internet-products/fibre/ftth  -> FTTH plans (.card elements, same format as fibre)

  - /nbn/fibre-upgrade -> Informational only, no plans -> skipped.

Card structure on fibre page (.card elements):
  h3[0]   -> plan name          e.g. "NBN500", "5G Plus", "Home Wireless Broadband"
  h3[1]   -> download speed     e.g. "500Mbps"
  h3[2]   -> upload speed       e.g. "42Mbps"
  spans[3] -> promo price whole  e.g. "$64"
  spans[5] -> promo price cents  e.g. ".99\\n/mth"  (split cents from period text)
  full text "then $XX.XX/mth"  -> regular (ongoing) price

Network type classification by plan name prefix / card promo text:
  - "NBN" prefix        -> NBN FTTP
  - "5G" prefix         -> 5G Home Broadband
  - "Home Wireless"     -> 4G Home Wireless
  - "Wireless" page     -> NBN Fixed Wireless

Returns Dict[str, List[Dict]] keyed by page name.
"""

import re
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright, Page
import config
from utils.logger import log_info, log_error, log_success
from utils.stealth import create_stealth_browser, create_stealth_page

BASE = 'https://www.iinet.net.au/internet-product'

IINET_PAGES = {
    'fibre': {
        'url': f'{BASE}/broadband/nbn/plans/fibre',
        'method': 'fibre_cards',
    },
    'wireless': {
        'url': f'{BASE}/broadband/nbn/plans/wireless',
        'method': 'wireless_text',
    },
    'ftth': {
        'url': 'https://www.iinet.net.au/internet-products/fibre/ftth/',
        'method': 'fibre_cards',
    },
    'fibre_upgrade': {
        'url': f'{BASE}/nbn/fibre-upgrade',
        'method': 'info_only',
    },
}

PROVIDER_ID = config.PROVIDERS.get('iinet', {}).get('id', 9)


# ==================================================================
#  ENTRY POINTS
# ==================================================================

def scrape_iinet_plans() -> Dict[str, List[Dict[str, Any]]]:
    """
    Scrape all iiNet pages.
    Returns dict of {page_key: [plans]}.
    """
    all_results: Dict[str, List[Dict[str, Any]]] = {}

    with sync_playwright() as p:
        browser = create_stealth_browser(p)

        for page_key, page_cfg in IINET_PAGES.items():
            if page_cfg['method'] == 'info_only':
                all_results[page_key] = []
                log_info(f'Skipping {page_key} (informational only)', provider='iinet')
                continue

            pw_page = create_stealth_page(browser)
            try:
                url = page_cfg['url']
                log_info(f'Scraping {page_key}: {url}', provider='iinet')
                resp = pw_page.goto(url, timeout=35000, wait_until='domcontentloaded')
                log_info(f'Status: {resp.status if resp else "none"}', provider='iinet')
                pw_page.wait_for_timeout(7000)

                method = page_cfg['method']
                if method == 'fibre_cards':
                    plans = extract_fibre_cards(pw_page, url)
                elif method == 'wireless_text':
                    plans = extract_wireless_plan(pw_page, url)
                else:
                    plans = []

                plans = deduplicate_plans(plans)
                all_results[page_key] = plans
                log_success(f'{page_key}: {len(plans)} plans', provider='iinet')

            except Exception as e:
                log_error(f'Error scraping {page_key}: {e}', provider='iinet')
                all_results[page_key] = []
            finally:
                pw_page.close()

        browser.close()

    total = sum(len(v) for v in all_results.values())
    log_success(f'Total iiNet plans: {total}', provider='iinet')
    return all_results


def scrape_via_playwright() -> List[Dict[str, Any]]:
    """Legacy single-list interface (backward-compatible). Flattens all pages."""
    results = scrape_iinet_plans()
    flat: List[Dict[str, Any]] = []
    for plans in results.values():
        flat.extend(plans)
    return flat


# ==================================================================
#  FIBRE PAGE -- 8 .card elements
# ==================================================================

def extract_fibre_cards(page: Page, source_url: str) -> List[Dict[str, Any]]:
    """
    Extract all plan cards from the /broadband/nbn/plans/fibre page.
    Each .card contains NBN FTTP, 5G Home Broadband, or 4G Home Wireless plans.

    Card DOM layout (confirmed via probe):
      h3[0]     -> plan name             e.g. "NBN500", "5G Plus", "Home Wireless\\nBroadband"
      h3[1]     -> typical DL speed      e.g. "500Mbps"
      h3[2]     -> typical UL speed      e.g. "42Mbps"
      span[0]   -> data cap text         e.g. "Liimitless Data"  (skip)
      span[1-2] -> tooltip icons         (skip)
      span[3]   -> promo price whole     e.g. "$64"
      span[4]   -> "$" prefix            (skip)
      span[5]   -> promo price cents+period  e.g. ".99\\n/mth"
      full text  "then $XX.XX/mth"      -> regular ongoing price
    """
    plans: List[Dict[str, Any]] = []
    cards = page.query_selector_all('.card')
    log_info(f'Found {len(cards)} .card elements on fibre page', provider='iinet')

    for card in cards:
        try:
            plan = _parse_fibre_card(card, source_url)
            if plan:
                plans.append(plan)
        except Exception as e:
            log_error(f'Error parsing fibre card: {e}', provider='iinet')

    return plans


def _parse_fibre_card(card, source_url: str) -> Optional[Dict[str, Any]]:
    """Parse a single .card element from the fibre page."""
    full_text = card.inner_text().strip()
    if not full_text:
        return None

    # ?? Plan name ?????????????????????????????????????????????????
    h3_els = card.query_selector_all('h3')
    h3_texts = [el.inner_text().strip() for el in h3_els]
    if not h3_texts:
        return None

    plan_name = ' '.join(h3_texts[0].split())  # collapse newlines and extra spaces
    if not plan_name:
        return None

    # ?? Network type classification ???????????????????????????????
    name_upper = plan_name.upper()
    if name_upper.startswith('5G'):
        network_type = '5G Home Broadband'
    elif 'WIRELESS' in name_upper or 'HOME WIRELESS' in name_upper:
        network_type = '4G Home Wireless'
    else:
        # NBN prefix (NBN25, NBN50, NBN500, NBN Superfast, NBN Ultrafast)
        network_type = 'NBN'

    # ?? Typical evening speeds (h3[1] = DL, h3[2] = UL) ?????????
    typical_dl = _parse_mbps(h3_texts[1]) if len(h3_texts) > 1 else 0
    typical_ul = _parse_mbps(h3_texts[2]) if len(h3_texts) > 2 else 0

    # ?? Nominal (max) speeds from body text ???????????????????????
    # 5G/wireless cards: "Max speeds of 50Mbps/20Mbps"
    # NBN cards: no explicit nominal -> use typical as nominal
    max_dl, max_ul = typical_dl, typical_ul
    max_match = re.search(r'Max speeds of (\d+)Mbps/(\d+)Mbps', full_text, re.IGNORECASE)
    if max_match:
        max_dl = int(max_match.group(1))
        max_ul = int(max_match.group(2))

    # ?? Promo price ???????????????????????????????????????????????
    # spans[3] = "$XX" (whole dollars), spans[5] = ".YY\n/mth" or ".YY/mth"
    spans = card.query_selector_all('span')
    span_texts = [s.inner_text().strip() for s in spans]

    promo_price = _extract_promo_price(span_texts)

    # ?? Regular (ongoing) price ???????????????????????????????????
    # Appears as "then $XX.XX/mth" in the full text.
    # Some 5G/wireless cards have no "then" and only a single price.
    regular_price = _parse_regular_price(full_text)

    # If no "then" price found, the promo price IS the only price.
    if regular_price <= 0 and promo_price is not None and promo_price > 0:
        regular_price = promo_price
        promo_price = None

    if regular_price <= 0:
        return None

    # ?? Promo period ??????????????????????????????????????????????
    promo_period = ''
    if promo_price is not None:
        period_match = re.search(r'(?:first|for)\s+(\d+)\s+months?', full_text, re.IGNORECASE)
        if period_match:
            promo_period = f"{period_match.group(1)} months"

    return build_plan(
        name=plan_name,
        network_type=network_type,
        download_speed=max_dl,
        upload_speed=max_ul,
        typical_evening_dl=typical_dl,
        typical_evening_ul=typical_ul,
        price=regular_price,
        promo_price=promo_price,
        promo_period=promo_period,
        source_url=source_url,
    )


def _extract_promo_price(span_texts: List[str]) -> Optional[float]:
    """
    Extract promo price from the span list.
    Observed pattern:
      span[3] = "$64"          -> whole dollar amount
      span[5] = ".99\\n/mth"  -> cents + period suffix
    Combine them into "$64.99".
    """
    # Find the span that starts with '$' and contains only a dollar amount
    dollar_idx = -1
    for i, txt in enumerate(span_texts):
        if txt.startswith('$') and re.match(r'^\$\d+$', txt):
            dollar_idx = i
            break

    if dollar_idx < 0:
        return None

    whole = span_texts[dollar_idx].lstrip('$')

    # Cents are in the next non-empty span after the "$" prefix span
    # Layout: [dollar_idx] "$XX"  [dollar_idx+1] "$"  [dollar_idx+2] ".YY\n/mth"
    cents = '00'
    for j in range(dollar_idx + 1, min(dollar_idx + 4, len(span_texts))):
        txt = span_texts[j].split('\n')[0].strip()
        m = re.match(r'^\.(\d{2})', txt)
        if m:
            cents = m.group(1)
            break

    try:
        return float(f'{whole}.{cents}')
    except ValueError:
        return None


# ==================================================================
#  WIRELESS PAGE -- single plan from body text
# ==================================================================

def extract_wireless_plan(page: Page, source_url: str) -> List[Dict[str, Any]]:
    """
    Extract the single NBN Fixed Wireless plan displayed on the wireless page.

    The Angular app shows one address-independent plan by default (NBN25).
    Page body text layout (observed):
      "Select a plan\\nNBN25\\n$ 76 .99 /mth\\n...\\n20Mbps\\nDownload\\n3.8Mbps\\nUpload\\n
       Typical Evening Speed*\\n$79.99/mth from ...\\nLiimitless Data"

    Fields extracted via regex from the plan section text:
      - Plan name:      first word-group after "Select a plan"
      - Current price:  "$ NN .NN /mth"  (split by spaces)
      - Future price:   "$NN.NN/mth from" (price rising date)
      - Download speed: digits before "Mbps\\nDownload"
      - Upload speed:   digits before "Mbps\\nUpload"
    """
    plans: List[Dict[str, Any]] = []

    body_text = page.evaluate('() => document.body.innerText')

    # Isolate the plan section between "Select a plan" and "Do you need a modem?"
    start_marker = 'Select a plan'
    end_marker = 'Do you need a modem?'
    start_idx = body_text.find(start_marker)
    end_idx = body_text.find(end_marker)

    if start_idx < 0:
        log_error('Wireless page: "Select a plan" marker not found', provider='iinet')
        return plans

    section = body_text[start_idx: end_idx if end_idx > start_idx else start_idx + 600]
    log_info(f'Wireless plan section: {repr(section[:300])}', provider='iinet')

    # Plan name -- first token after "Select a plan\n"
    name_match = re.search(r'Select a plan\s*\n\s*(.+)', section)
    plan_name = name_match.group(1).strip() if name_match else 'NBN Fixed Wireless'

    # Current price -- "$ 76 .99 /mth" (spaces between parts on this page)
    price_match = re.search(r'\$\s*(\d+)\s+\.(\d{2})\s*/mth', section)
    if price_match:
        current_price = float(f'{price_match.group(1)}.{price_match.group(2)}')
    else:
        # Fallback: "$XX.XX/mth"
        fb = re.search(r'\$([\d]+\.[\d]{2})\s*/mth', section)
        current_price = float(fb.group(1)) if fb else 0.0

    if current_price <= 0:
        log_error('Wireless page: could not parse price', provider='iinet')
        return plans

    # Future price (announced increase) -- "$XX.XX/mth from DD/MM/YYYY"
    future_match = re.search(r'\$([\d]+\.[\d]{2})/mth\s+from\s+\d', section)
    future_price = float(future_match.group(1)) if future_match else None

    # Typical evening download speed -- "NN.N Mbps\nDownload"
    dl_match = re.search(r'([\d.]+)\s*Mbps\s*\nDownload', section, re.IGNORECASE)
    typical_dl = float(dl_match.group(1)) if dl_match else 0.0

    # Typical evening upload speed -- "NN.N Mbps\nUpload"
    ul_match = re.search(r'([\d.]+)\s*Mbps\s*\nUpload', section, re.IGNORECASE)
    typical_ul = float(ul_match.group(1)) if ul_match else 0.0

    plan = build_plan(
        name=plan_name,
        network_type='NBN Fixed Wireless',
        download_speed=int(typical_dl),
        upload_speed=int(typical_ul),
        typical_evening_dl=typical_dl,
        typical_evening_ul=typical_ul,
        price=current_price,
        promo_price=None,
        promo_period='',
        source_url=source_url,
    )
    plans.append(plan)
    return plans


# ==================================================================
#  HELPERS
# ==================================================================

def _parse_mbps(text: str) -> float:
    """Parse a speed value like '500Mbps' or '3.8Mbps' -> float."""
    m = re.search(r'([\d.]+)\s*Mbps', text, re.IGNORECASE)
    return float(m.group(1)) if m else 0.0


def _parse_regular_price(text: str) -> float:
    """
    Parse the regular (ongoing) price from the full card text.
    Matches: "then $94.99/mth" or "then$94.99/mth".
    """
    m = re.search(r'then\s*\$\s*([\d]+\.[\d]{2})/mth', text, re.IGNORECASE)
    return float(m.group(1)) if m else 0.0


def build_plan(name: str, network_type: str, download_speed, upload_speed,
               typical_evening_dl, typical_evening_ul, price: float,
               promo_price: Optional[float], promo_period: str,
               source_url: str) -> Dict[str, Any]:
    """Build a standardised plan dict matching the project schema."""
    return {
        'provider_id': PROVIDER_ID,
        'provider': 'iinet',
        'plan_name': name,
        'network_type': network_type,
        'download_speed': int(download_speed),
        'upload_speed': int(upload_speed),
        'typical_evening_dl': float(typical_evening_dl),
        'typical_evening_ul': float(typical_evening_ul),
        'price': price,
        'promo_price': promo_price,
        'promo_period': promo_period,
        'contract': 'No Lock-in',
        'source_url': source_url,
    }


def deduplicate_plans(plans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate plans by (plan_name, price). Keep highest download speed."""
    best: Dict[str, Dict[str, Any]] = {}
    for plan in plans:
        key = f"{plan.get('plan_name')}_{plan.get('price')}"
        if key not in best or plan.get('download_speed', 0) > best[key].get('download_speed', 0):
            best[key] = plan
    return list(best.values())
