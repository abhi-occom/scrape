# scrape/providers/kogan.py
"""
kogan.py  —  Scrape Kogan Internet plan cards from:
  https://www.koganinternet.com.au/plans/

DOM structure (confirmed via live investigation 2026-05):
  Selector : .planItem                    → one element per plan (7 total)
  h2._3xhK5                              → plan name  (e.g. "Bronze", "4G Internet")
  .H5xru                                 → duration label ("90-Day Plan", "12mth discount!")
  ._3A3Q_                                → full/original monthly price  ($XX.XX)
  ._3DwQq                                → promo/discounted monthly price ($XX.XX)
  .rRNco  (rich-text <p>)                → total cost note
  section._2x6hy h3                      → speed badge  ("20Mbps", "nbn® 25")
  section._2x6hy p                       → evening speed detail ("↓ XX Mbps & ↑ XX Mbps")
  section._3r4CW ul li                   → feature bullet points

Card layout per plan (confirmed from investigation 2026-05-14):
  4G Internet  : 90-Day,  $54.90 / $49.90,  total $149.70,  badge 20Mbps,    evening ↓17/↑1.9,   4G
  Bronze       : 12-mth,  $70.90 / $58.90,  total  $58.90,  badge nbn® 25,   evening ↓25/↑8,     NBN
  Silver       : 12-mth,  $80.90 / $70.90,  total  $70.90,  badge nbn® 50,   evening ↓50/↑17,    NBN
  Gold         : 12-mth,  $85.90 / $71.90,  total  $71.90,  badge nbn® 100,  evening ↓99/↑17,    NBN
  Gold Plus    : 12-mth,  $85.90 / $71.90,  total  $71.90,  badge nbn® 500,  evening ↓500/↑42,   NBN
  Platinum     : 12-mth,  $94.90 / $84.90,  total  $84.90,  badge nbn® 750,  evening ↓740/↑42,   NBN
  Diamond      : 12-mth, $108.90 / $94.90,  total  $94.90,  badge nbn® 1000, evening ↓850/↑85,   NBN
"""

import sys
import os
import re
import json
import csv
from typing import List, Dict, Any, Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright, ElementHandle
from utils.logger import log_info, log_error, log_success, log_warning

# ── Constants ────────────────────────────────────────────────────────────────
URL: str        = 'https://www.koganinternet.com.au/plans/'
PROVIDER_ID: int = 13
PROVIDER: str   = 'kogan'

# CSS selectors confirmed by live DOM investigation
_SEL_CARD          = '.planItem'           # each plan card
_SEL_NAME          = 'h2'                  # plan name inside card
_SEL_DURATION      = '.H5xru'             # "90-Day Plan" / "12mth discount!"
_SEL_PRICE_FULL    = '._3A3Q_'            # original / rack-rate price
_SEL_PRICE_PROMO   = '._3DwQq'            # promotional / discounted price
_SEL_TOTAL_NOTE    = '.rRNco'             # "Total once-off cost $149.70."
_SEL_SPEED_BADGE   = 'section._2x6hy h3'  # "20Mbps" / "nbn® 25"
_SEL_SPEED_DETAIL  = 'section._2x6hy p'   # evening speed string
_SEL_FEATURES      = 'section._3r4CW ul li'  # bullet feature items

# ── Helpers ──────────────────────────────────────────────────────────────────

def _text(el: Optional[ElementHandle]) -> str:
    """Return stripped inner-text of element, or empty string if None."""
    if el is None:
        return ''
    try:
        return (el.inner_text() or '').strip()
    except Exception:
        return ''


def _texts(els: List[ElementHandle]) -> List[str]:
    """Return list of stripped inner-texts, skipping blanks."""
    return [t for t in (_text(e) for e in els) if t]


def _parse_price(raw: str) -> Optional[float]:
    """Extract first $XX.XX amount from a string."""
    m = re.search(r'\$(\d+(?:\.\d+)?)', raw)
    return round(float(m.group(1)), 2) if m else None


def _parse_speed_mbps(text: str) -> Optional[int]:
    """
    Return the *download* speed in Mbps as an integer.

    Handles:
      '20Mbps'           -> 20
      'nbn® 25'          -> 25
      'nbn® 500'         -> 500
      'nbn® 750'         -> 750  (Platinum badge says 750)
      'nbn® 1000'        -> 1000
      '↓ 740 Mbps & ...' -> 740  (evening speed detail)
    """
    # Look for explicit Mbps number first (badge like "20Mbps" or detail)
    m = re.search(r'(\d+)\s*[Mm]bps', text)
    if m:
        return int(m.group(1))
    # Fall back to trailing integer in nbn® tier names
    m = re.search(r'nbn[®\s]*[^\d]*(\d+)', text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _parse_duration(label: str, card_text: str) -> str:
    """
    Normalise the plan duration string.

    The .H5xru element contains labels like:
      '90-Day Plan'   -> '90-Day'
      '30-Day Plan'   -> '30-Day'
      '12mth discount!'  -> '12-month'
    """
    low = label.lower()
    if '90' in low:
        return '90-Day'
    if '30' in low:
        return '30-Day'
    if '12' in low or '12mth' in low:
        return '12-month'
    # Fallback: scan card text
    if '90-day' in card_text.lower():
        return '90-Day'
    if '30-day' in card_text.lower():
        return '30-Day'
    if '12' in card_text and ('mth' in card_text.lower() or 'month' in card_text.lower()):
        return '12-month'
    return 'Month-to-Month'


def _parse_total_cost(note: str) -> Optional[float]:
    """Extract total cost from strings like 'Total min. cost $58.90.'

    Handles multi-line notes such as::

        $70.90/month thereafter.
        Total min. cost $58.90.

    The capture group uses ``(d+(.d{1,2})?)`` to avoid greedily
    matching a trailing sentence period (e.g. ``$149.70.``).
    """
    m = re.search(
        r'(?:Total\s+(?:once-off|min\.?)\s+cost|Total\s+cost)\s*\$?(\d+(?:\.\d{1,2})?)',
        note, re.IGNORECASE
    )
    if m:
        try:
            return round(float(m.group(1)), 2)
        except ValueError:
            pass
    # Fallback: any price in the note
    return _parse_price(note)


def _infer_network_type(name: str, speed_badge: str) -> str:
    """Determine network type from plan name / speed badge."""
    combined = (name + ' ' + speed_badge).lower()
    if '4g' in combined:
        return '4G'
    if 'nbn' in combined:
        return 'NBN'
    return 'NBN'


# ── Per-card extractor ───────────────────────────────────────────────────────

def _extract_card(card: ElementHandle, index: int) -> Optional[Dict[str, Any]]:
    """
    Parse one .planItem card into a structured plan dict.

    Field mapping (all confirmed from live DOM probe):
      name          <- h2 inside card
      plan_duration <- .H5xru label
      price_monthly <- ._3DwQq  (promo/discounted price; shown prominently)
      price_full    <- ._3A3Q_  (original rack-rate price)
      total_cost    <- .rRNco text
      speed         <- section._2x6hy h3  (speed badge), then p (evening detail)
      speed_down    <- parsed integer download Mbps
      speed_up      <- parsed integer upload Mbps from evening detail
      speed_evening <- raw evening speed string
      features      <- section._3r4CW ul li bullets
      network_type  <- inferred from name / speed badge
      contract      <- always 'No Contract' (Kogan has no lock-in)
    """
    try:
        card_text = _text(card)

        # ── Plan name ───────────────────────────────────────────────────────
        name = _text(card.query_selector(_SEL_NAME)) or ''
        if not name:
            log_warning(f'Card {index}: no name found, skipping', provider=PROVIDER)
            return None

        # ── Duration label ──────────────────────────────────────────────────
        duration_label = _text(card.query_selector(_SEL_DURATION))
        plan_duration  = _parse_duration(duration_label, card_text)

        # ── Prices ──────────────────────────────────────────────────────────
        # ._3A3Q_ = full/rack-rate price (the crossed-out one for promo cards)
        # ._3DwQq = discounted/promo price (the big highlighted price)
        price_full_raw  = _text(card.query_selector(_SEL_PRICE_FULL))
        price_promo_raw = _text(card.query_selector(_SEL_PRICE_PROMO))

        price_full  = _parse_price(price_full_raw)  or 0.0
        price_promo = _parse_price(price_promo_raw) or 0.0

                # Standardised pricing (matches frontend schema):
        #   price       = regular/ongoing monthly price (the "thereafter" rate)
        #   promo_price = discounted monthly price during promo period (or None)
        has_promo = price_promo > 0 and price_full > 0 and price_full != price_promo
        regular_price = price_full if price_full > 0 else price_promo
        promo_price_val: Optional[float] = price_promo if has_promo else None

                # ── Promo period ────────────────────────────────────────────────────
        promo_period = '12 months' if has_promo else ''

        # ── Total cost note ─────────────────────────────────────────────────
        total_note = _text(card.query_selector(_SEL_TOTAL_NOTE))
        total_cost = _parse_total_cost(total_note) or 0.0

        # ── Speed badge + evening detail ────────────────────────────────────
        speed_badge   = _text(card.query_selector(_SEL_SPEED_BADGE))   # "20Mbps" / "nbn® 25"
        speed_details = _texts(card.query_selector_all(_SEL_SPEED_DETAIL))  # list of <p> texts

        # Evening speed is usually the <p> that contains 'Mbps' or up/down arrows
        evening_raw = ''
        for detail in speed_details:
            if 'Mbps' in detail or 'mbps' in detail or any(c in detail for c in ['\u2193', '\u2191', 'down', 'up']):
                evening_raw = detail
                break

        # Parse download / upload from evening detail string like:
        #   "\u2193 17 Mbps & \u2191 1.9 Mbps"
        speed_down: Optional[int] = None
        speed_up: Optional[float] = None

        # First try the speed badge (most reliable for the plan tier)
        badge_down = _parse_speed_mbps(speed_badge)
        if badge_down:
            speed_down = badge_down

        # Parse up/down from evening detail string
        ev_match = re.search(
            r'(?:[\u2193↓]|down)[\s\xa0]*(\d+(?:\.\d+)?)\s*[Mm]bps[^\d]*'
            r'(?:[\u2191↑]|up)[\s\xa0]*(\d+(?:\.\d+)?)\s*[Mm]bps',
            evening_raw, re.IGNORECASE
        )
        if ev_match:
            speed_down = speed_down or int(float(ev_match.group(1)))
            speed_up   = float(ev_match.group(2))

        # Fallback: parse any Mbps from the badge text if still missing
        if not speed_down:
            speed_down = _parse_speed_mbps(card_text) or 0

                                # Parse typical evening download from evening detail
        # (may differ from badge — e.g. Gold badge=100 but evening=99)
        typical_evening_dl: Optional[int] = None
        typical_evening_ul: Optional[float] = None
        if ev_match:
            typical_evening_dl = int(float(ev_match.group(1)))
            typical_evening_ul = float(ev_match.group(2))

        # Human-readable speed string
        speed_str = f'{speed_down} Mbps' if speed_down else ''

        # ── Features ────────────────────────────────────────────────────────
        feature_els = card.query_selector_all(_SEL_FEATURES)
        features    = [t for t in _texts(feature_els) if len(t) > 2]

        # ── Network type / contract ─────────────────────────────────────────
        network_type = _infer_network_type(name, speed_badge)
        contract     = 'No Contract'

                        # ── Build plan name (e.g. "Kogan Bronze") ────────────────────────
        plan_name = f"Kogan {name}"

        # ── Assemble plan dict (standardised field names) ────────────────────
        plan: Dict[str, Any] = {
            'provider_id':        PROVIDER_ID,
            'provider':           PROVIDER,
            'plan_name':          plan_name,
            'network_type':       network_type,
            'download_speed':     speed_down or 0,
            'upload_speed':       speed_up,
            'typical_evening_dl': typical_evening_dl,
            'typical_evening_ul': typical_evening_ul,
            'price':              regular_price,
            'promo_price':        promo_price_val,
            'promo_period':       promo_period,
            'contract':           contract,
            'source_url':         URL,
            # ── Kogan-specific extras ────────────────────────────────────
            'speed_badge':        speed_badge,
            'speed_evening':      evening_raw,
            'plan_duration':      plan_duration,
            'total_cost':         total_cost,
            'total_note':         total_note,
            'features':           features,
        }

                # ── Validation ──────────────────────────────────────────────────────
        if not plan['plan_name'] or not plan['download_speed'] or plan['price'] <= 0:
            log_warning(
                f'Card {index} incomplete — name={plan["plan_name"]!r} '
                f'speed={plan["download_speed"]} price={plan["price"]}',
                provider=PROVIDER,
            )
            return None

        return plan

    except Exception as exc:
        log_error(f'Card {index} extraction failed: {exc}', provider=PROVIDER)
        return None


# ── Output helpers ───────────────────────────────────────────────────────────

def _output_dir(subdir: str) -> str:
    """Resolve output directory relative to this file, ensure it exists."""
    base = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'output', 'scrape_isp_kogan', subdir,
    )
    os.makedirs(base, exist_ok=True)
    return base


def save_plans_to_json(
    plans: List[Dict[str, Any]],
    output_dir: Optional[str] = None,
    timestamped: bool = True,
) -> Optional[str]:
    """
    Persist plans to JSON.

    Writes two files:
      kogan_plans.json              — current snapshot (always overwritten)
      kogan_plans_YYYYMMDD_HHMMSS.json  — timestamped archive

    Returns path of the timestamped file, or None on failure.
    """
    dir_path = output_dir or _output_dir('json')
    os.makedirs(dir_path, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    payload = {
        'scraped_at':  timestamp,
        'provider':    PROVIDER,
        'provider_id': PROVIDER_ID,
        'source_url':  URL,
        'total_plans': len(plans),
        'plans':       plans,
    }

    # Timestamped archive
    ts_path = os.path.join(dir_path, f'kogan_plans_{timestamp}.json')
    # Current snapshot
    cur_path = os.path.join(dir_path, 'kogan_plans.json')

    try:
        for path in (ts_path, cur_path):
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        log_success(f'JSON saved -> {ts_path}', provider=PROVIDER)
        return ts_path
    except Exception as exc:
        log_error(f'JSON save failed: {exc}', provider=PROVIDER)
        return None


def save_plans_to_csv(
    plans: List[Dict[str, Any]],
    output_dir: Optional[str] = None,
) -> Optional[str]:
    """
    Persist plans to CSV.

    Writes two files:
      kogan_plans.csv             — current snapshot
      kogan_all_plans.csv         — alias for compatibility

    Returns path of kogan_plans.csv, or None on failure.
    """
    if not plans:
        return None

    dir_path = output_dir or _output_dir('csv')
    os.makedirs(dir_path, exist_ok=True)

    # Flatten features list to a semicolon-separated string for CSV
    rows = []
    for p in plans:
        row = dict(p)
        row['features'] = '; '.join(p.get('features', []))
        rows.append(row)

    fieldnames = list(rows[0].keys()) if rows else []
    cur_path = os.path.join(dir_path, 'kogan_plans.csv')
    all_path = os.path.join(dir_path, 'kogan_all_plans.csv')

    try:
        for path in (cur_path, all_path):
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        log_success(f'CSV saved -> {cur_path}', provider=PROVIDER)
        return cur_path
    except Exception as exc:
        log_error(f'CSV save failed: {exc}', provider=PROVIDER)
        return None


# ── Main scraper ─────────────────────────────────────────────────────────────

def scrape_kogan_plans() -> List[Dict[str, Any]]:
    """
    Navigate to Kogan's plans page, scrape all .planItem cards, and
    return a list of structured plan dicts sorted by download speed.

    Returns:
        List[Dict]  — one dict per plan, empty list on complete failure.
    """
    log_info('Starting Kogan scraper', provider=PROVIDER)
    all_plans: List[Dict[str, Any]] = []

    try:
        with sync_playwright() as p:
            browser = create_stealth_browser(p)
            page    = create_stealth_page(browser)

            log_info(f'Navigating to {URL}', provider=PROVIDER)
            page.goto(URL, timeout=40000, wait_until='domcontentloaded')
            page.wait_for_timeout(8000)   # allow React/SPA JS to render

            log_info(f'Page title: {page.title()!r}', provider=PROVIDER)

            # ── Locate all plan cards ────────────────────────────────────────
            plan_cards = page.query_selector_all(_SEL_CARD)

            if not plan_cards:
                log_warning(
                    f'No cards found with selector {_SEL_CARD!r}. '
                    'The page may have changed or blocked the scraper.',
                    provider=PROVIDER,
                )
                browser.close()
                return []

            log_info(f'Found {len(plan_cards)} plan cards', provider=PROVIDER)

                        # ── Extract each card ────────────────────────────────────────────
            for i, card in enumerate(plan_cards):
                plan = _extract_card(card, index=i)
                if plan is not None:
                    all_plans.append(plan)
                    promo_str = f'  promo ${plan["promo_price"]:.2f}' if plan['promo_price'] else ''
                    log_info(
                        f'  [{i}] {plan["plan_name"]:20s}  '
                        f'{plan["download_speed"]:>5} Mbps  '
                        f'${plan["price"]:.2f}/mth{promo_str}',
                        provider=PROVIDER,
                    )

            browser.close()

    except Exception as exc:
        log_error(f'Kogan scraper failed: {exc}', provider=PROVIDER)
        return []

    # ── Sort by download speed ascending ────────────────────────────────────
    all_plans.sort(key=lambda x: x.get('download_speed', 0))

    log_success(
        f'Kogan scraper complete: {len(all_plans)} plans extracted',
        provider=PROVIDER,
    )
    return all_plans


# ── Standalone execution ─────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys

    plans = scrape_kogan_plans()

    if not plans:
        print('\nNo plans scraped — check logs for details.')
        sys.exit(1)

    # Persist
    json_path = save_plans_to_json(plans)
    csv_path  = save_plans_to_csv(plans)

        # ── Pretty-print results ─────────────────────────────────────────────────
    SEP = '=' * 80
    print(f'\n{SEP}')
    print(f'  KOGAN INTERNET PLANS  —  {len(plans)} plans scraped')
    print(SEP)
    print(f'{"Plan Name":<22} {"Net":<5} {"DL":>6} {"UL":>5}  '
          f'{"Price":>8}  {"Promo":>8}  {"Period":<12} {"Contract"}')
    print('-' * 95)

    for p in plans:
        promo = f'${p["promo_price"]:.2f}' if p['promo_price'] else '-'
        ul = f'{p["upload_speed"]}' if p['upload_speed'] else '-'
        print(
            f'{p["plan_name"]:<22} '
            f'{p["network_type"]:<5} '
            f'{p["download_speed"]:>5}  '
            f'{ul:>5}  '
            f'${p["price"]:>7.2f}  '
            f'{promo:>8}  '
            f'{p["promo_period"] or "-":<12} '
            f'{p["contract"]}'
        )

    print(SEP)
    print(f'\nJSON: {json_path}')
    print(f'CSV:  {csv_path}')