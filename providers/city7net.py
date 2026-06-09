"""City7Net provider scraper.

Scrapes static fibre internet plans from https://city7net.com.au/.
"""

import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import requests
import urllib3
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from utils.logger import log_error, log_info, log_success, log_warning


PROVIDER_ID = config.PROVIDERS.get('city7net', {}).get('id', 21)
PROVIDER_NAME = 'City7Net'
URL = 'https://city7net.com.au/'


def _normalise_text(text: str) -> str:
    text = text.replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def _parse_price(text: str) -> Optional[float]:
    match = re.search(r'\$\s*([0-9]+(?:\.[0-9]+)?)', text.replace(',', ''))
    return float(match.group(1)) if match else None


def _parse_speed(text: str) -> Tuple[int, int]:
    match = re.search(r'(\d+)\s*Mbps\s*/\s*(\d+)\s*Mbps', text, re.IGNORECASE)
    if not match:
        return 0, 0
    return int(match.group(1)), int(match.group(2))


def _fetch_html() -> str:
    # City7Net can fail certificate validation in Python's cert store on Windows.
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    response = requests.get(URL, timeout=30, verify=False)
    response.raise_for_status()
    return response.text


def _extract_plan(column) -> Optional[Dict[str, Any]]:
    lines = [
        _normalise_text(line)
        for line in column.get_text('\n', strip=True).splitlines()
        if _normalise_text(line)
    ]
    if not lines:
        return None

    plan_name = lines[0]
    price = None
    download_speed = 0
    upload_speed = 0

    for line in lines[1:]:
        if price is None:
            price = _parse_price(line)
        if not download_speed:
            download_speed, upload_speed = _parse_speed(line)

    if price is None or not download_speed:
        log_warning(f'City7Net: missing required data for {plan_name}', provider='city7net')
        return None

    return {
        'provider_id': PROVIDER_ID,
        'provider': PROVIDER_NAME,
        'network_type': 'Fibre',
        'plan_name': f'City7Net {plan_name}',
        'download_speed': download_speed,
        'upload_speed': upload_speed,
        'price': price,
        'promo_price': None,
        'promo_period': None,
        'contract': 'Month to month, no lock-in',
        'typical_evening_dl': download_speed,
        'typical_evening_ul': upload_speed,
        'source_url': URL,
    }


def scrape_city7net_plans() -> List[Dict[str, Any]]:
    log_info('Starting City7Net scraper', provider='city7net')
    plans: List[Dict[str, Any]] = []

    try:
        soup = BeautifulSoup(_fetch_html(), 'html.parser')
        pricing_section = soup.select_one('#pricingarea')
        if not pricing_section:
            log_error('City7Net: pricing section not found', provider='city7net')
            return []

        columns = pricing_section.select('.et_pb_row_2 .et_pb_column_1_4')
        if not columns:
            columns = pricing_section.select('.et_pb_column_1_4')

        for column in columns:
            plan = _extract_plan(column)
            if plan:
                plans.append(plan)

    except Exception as exc:
        log_error(f'City7Net scraper failed: {exc}', provider='city7net')

    seen = set()
    unique_plans = []
    for plan in plans:
        key = (plan['plan_name'], plan['download_speed'], plan['upload_speed'], plan['price'])
        if key in seen:
            continue
        seen.add(key)
        unique_plans.append(plan)

    unique_plans.sort(key=lambda plan: plan['download_speed'])
    if not unique_plans:
        log_warning('City7Net scraper returned no plans', provider='city7net')
    log_success(f'City7Net scraper complete: {len(unique_plans)} plans', provider='city7net')
    return unique_plans


if __name__ == '__main__':
    for item in scrape_city7net_plans():
        print(item)
