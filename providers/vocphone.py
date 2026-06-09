"""VOCPhone provider scraper.

Scrapes VOCPhone broadband plans from:
- https://vocphone.com/nbn-plans
- https://vocphone.com/pricing/internet-pricing
"""

import os
import re
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from playwright.sync_api import sync_playwright
from utils.logger import log_error, log_info, log_success
from utils.stealth import create_stealth_browser, create_stealth_page


PROVIDER_ID = config.PROVIDERS.get('vocphone', {}).get('id', 25)
PROVIDER_NAME = 'VOCPhone'

PLAN_PAGES = [
    {
        'url': 'https://vocphone.com/nbn-plans',
        'network_type': 'NBN',
        'valid_names': ['NBN Home', 'NBN Business'],
    },
    {
        'url': 'https://vocphone.com/pricing/internet-pricing',
        'network_type': 'SUPA Fibre',
        'valid_names': ['Fiber 50', 'Fiber 500', 'Fiber 750', 'Fiber 1000'],
    },
]


def _parse_money(value: str) -> Optional[float]:
    match = re.search(r'\$([0-9]+(?:\.[0-9]+)?)', value.replace(',', ''))
    return float(match.group(1)) if match else None


def _extract_cards(text: str) -> List[str]:
    """Split page text into likely plan card text blocks."""
    chunks = []
    pattern = re.compile(
        r'((?:HOME|BUSINESS|BUSINESS\s+·\s+GIGABIT|FIBER\s+·\s+[A-Z ]+)\s+'
        r'(?:NBN\s+(?:Home|Business)|Fiber\s+\d+).*?Get this plan\s+→)',
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(text):
        chunks.append(match.group(1))
    return chunks


def _normalise_name(raw_name: str) -> str:
    return re.sub(r'\s+', ' ', raw_name).strip()


def _parse_plan_from_chunk(chunk: str, page_cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        name_match = re.search(r'\b(NBN\s+(?:Home|Business)|Fiber\s+\d+)\b', chunk, re.IGNORECASE)
        if not name_match:
            return None
        plan_name = _normalise_name(name_match.group(1))

        if plan_name not in page_cfg['valid_names']:
            return None

        speed_match = re.search(r'(\d+)\s*/\s*(\d+)\s*(?:SYMMETRIC\s+)?MBPS', chunk, re.IGNORECASE)
        if not speed_match:
            return None
        download_speed = int(speed_match.group(1))
        upload_speed = int(speed_match.group(2))

        money_values = [_parse_money(m.group(0)) for m in re.finditer(r'\$[0-9]+(?:\.[0-9]+)?', chunk)]
        money_values = [value for value in money_values if value is not None]
        if not money_values:
            return None

        regular_price = money_values[0]
        promo_price = money_values[1] if len(money_values) > 1 and money_values[1] < regular_price else None
        price = regular_price

        promo_period = None
        if promo_price is not None:
            promo_period = '3 months' if page_cfg['network_type'] == 'SUPA Fibre' else 'Sale price'

        typical_match = re.search(
            r'Typical evening:\s*(\d+)\s*/\s*(\d+)\s*Mbps',
            chunk,
            re.IGNORECASE,
        )
        typical_evening_dl = int(typical_match.group(1)) if typical_match else download_speed
        typical_evening_ul = int(typical_match.group(2)) if typical_match else upload_speed

        return {
            'provider_id': PROVIDER_ID,
            'provider': PROVIDER_NAME,
            'network_type': page_cfg['network_type'],
            'plan_name': f'{PROVIDER_NAME} {plan_name} {download_speed}/{upload_speed}',
            'download_speed': download_speed,
            'upload_speed': upload_speed,
            'price': price,
            'promo_price': promo_price,
            'promo_period': promo_period,
            'contract': 'No Contract',
            'typical_evening_dl': typical_evening_dl,
            'typical_evening_ul': typical_evening_ul,
            'source_url': page_cfg['url'],
        }
    except Exception as exc:
        log_error(f'VOCPhone card parse failed: {exc}', provider='vocphone')
        return None


def scrape_vocphone_plans() -> List[Dict[str, Any]]:
    """Scrape VOCPhone NBN and SUPA fibre internet plans."""
    log_info('Starting VOCPhone scraper', provider='vocphone')
    plans: List[Dict[str, Any]] = []
    seen = set()

    try:
        with sync_playwright() as p:
            browser = create_stealth_browser(p)
            page = create_stealth_page(browser)

            for page_cfg in PLAN_PAGES:
                page.goto(page_cfg['url'], wait_until='domcontentloaded', timeout=45000)
                page.wait_for_timeout(5000)
                text = page.inner_text('body')
                chunks = _extract_cards(text)
                log_info(
                    f"VOCPhone found {len(chunks)} candidate cards on {page_cfg['url']}",
                    provider='vocphone',
                )

                for chunk in chunks:
                    plan = _parse_plan_from_chunk(chunk, page_cfg)
                    if not plan:
                        continue
                    key = (plan['network_type'], plan['plan_name'], plan['download_speed'])
                    if key in seen:
                        continue
                    seen.add(key)
                    plans.append(plan)

            browser.close()

    except Exception as exc:
        log_error(f'VOCPhone scraper failed: {exc}', provider='vocphone')

    plans.sort(key=lambda p: (p['network_type'], p['download_speed'], p['price']))
    log_success(f'VOCPhone scraper complete: {len(plans)} plans', provider='vocphone')
    return plans


if __name__ == '__main__':
    for item in scrape_vocphone_plans():
        print(item)
