"""Epsinet provider scraper.

Scrapes fibre broadband month-to-month plans from https://epsinet.com.au/.
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


PROVIDER_ID = config.PROVIDERS.get('epsinet', {}).get('id', 22)
PROVIDER_NAME = 'Epsinet'
URL = 'https://epsinet.com.au/'

PLAN_NAMES = ('Casual', 'Everyday', 'Family', 'Power User')


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
    # Epsinet may fail certificate validation in Python's cert store on Windows.
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    response = requests.get(URL, timeout=30, verify=False)
    response.raise_for_status()
    return response.text


def _plan_header(line: str) -> Optional[Tuple[str, float]]:
    for name in PLAN_NAMES:
        if re.match(rf'^{re.escape(name)}\b', line, re.IGNORECASE):
            price = _parse_price(line)
            if price is not None:
                return name, price
    return None


def _extract_plans_from_lines(lines: List[str]) -> List[Dict[str, Any]]:
    plans: List[Dict[str, Any]] = []
    i = 0
    while i < len(lines):
        header = _plan_header(lines[i])
        if not header:
            i += 1
            continue

        name, price = header
        block = lines[i:i + 12]
        download_speed = 0
        upload_speed = 0
        for line in block[1:]:
            download_speed, upload_speed = _parse_speed(line)
            if download_speed:
                break

        if not download_speed:
            log_warning(f'Epsinet: missing speed data for {name}', provider='epsinet')
            i += 1
            continue

        plans.append({
            'provider_id': PROVIDER_ID,
            'provider': PROVIDER_NAME,
            'network_type': 'Fibre',
            'plan_name': f'Epsinet {name}',
            'download_speed': download_speed,
            'upload_speed': upload_speed,
            'price': price,
            'promo_price': None,
            'promo_period': None,
            'contract': 'Month to month, no lock-in',
            'typical_evening_dl': download_speed,
            'typical_evening_ul': upload_speed,
            'source_url': URL,
        })
        i += 1
    return plans


def scrape_epsinet_plans() -> List[Dict[str, Any]]:
    log_info('Starting Epsinet scraper', provider='epsinet')
    plans: List[Dict[str, Any]] = []

    try:
        soup = BeautifulSoup(_fetch_html(), 'html.parser')
        pricing_section = soup.select_one('#fibrearea')
        if not pricing_section:
            log_error('Epsinet: #fibrearea section not found', provider='epsinet')
            return []

        lines = [
            _normalise_text(line)
            for line in pricing_section.get_text('\n', strip=True).splitlines()
            if _normalise_text(line)
        ]
        plans = _extract_plans_from_lines(lines)

    except Exception as exc:
        log_error(f'Epsinet scraper failed: {exc}', provider='epsinet')

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
        log_warning('Epsinet scraper returned no plans', provider='epsinet')
    log_success(f'Epsinet scraper complete: {len(unique_plans)} plans', provider='epsinet')
    return unique_plans


if __name__ == '__main__':
    for item in scrape_epsinet_plans():
        print(item)
