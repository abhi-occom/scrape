"""New Aus Fiber provider scraper.

Scrapes static fibre broadband plans from https://newausfiber.com.au/.
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


PROVIDER_ID = config.PROVIDERS.get('newausfiber', {}).get('id', 24)
PROVIDER_NAME = 'New Aus Fiber'
URL = 'https://newausfiber.com.au/'
PLAN_NAMES = ('Casual', 'Everyday', 'Family', 'Extreme')


def _normalise_text(text: str) -> str:
    text = text.replace('\xa0', ' ')
    text = re.sub(r'[\ue000-\uf8ff]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _fetch_html() -> str:
    # This site can fail certificate validation in Python's cert store on Windows.
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    response = requests.get(URL, timeout=30, verify=False)
    response.raise_for_status()
    return response.text


def _parse_plan_header(line: str) -> Optional[Tuple[str, float]]:
    match = re.match(
        r'^(Casual|Everyday|Family|Extreme)\s*[-–]\s*\$\s*([0-9]+(?:\.[0-9]+)?)',
        line,
        re.IGNORECASE,
    )
    if not match:
        return None
    plan_name = next(name for name in PLAN_NAMES if name.lower() == match.group(1).lower())
    return plan_name, float(match.group(2))


def _parse_speed(line: str) -> Tuple[int, int]:
    speed_match = re.search(
        r'(\d+)\s*Mbps(?:\s*/\s*(\d+)\s*Mbps)?',
        line,
        re.IGNORECASE,
    )
    if not speed_match:
        return 0, 0

    download_speed = int(speed_match.group(1))
    upload_speed = int(speed_match.group(2)) if speed_match.group(2) else download_speed
    return download_speed, upload_speed


def _page_lines(html: str) -> List[str]:
    soup = BeautifulSoup(html, 'html.parser')
    lines = [
        _normalise_text(line)
        for line in soup.get_text('\n', strip=True).splitlines()
    ]
    return [line for line in lines if line]


def _extract_plans(lines: List[str]) -> List[Dict[str, Any]]:
    plans: List[Dict[str, Any]] = []
    index = 0
    while index < len(lines):
        header = _parse_plan_header(lines[index])
        if not header:
            index += 1
            continue

        plan_name, price = header
        block = lines[index:index + 12]
        download_speed = 0
        upload_speed = 0
        for line in block[1:]:
            download_speed, upload_speed = _parse_speed(line)
            if download_speed:
                break

        if not download_speed:
            log_warning(f'New Aus Fiber: missing speed data for {plan_name}', provider='newausfiber')
            index += 1
            continue

        plans.append({
            'provider_id': PROVIDER_ID,
            'provider': PROVIDER_NAME,
            'network_type': 'Fibre',
            'plan_name': f'{PROVIDER_NAME} {plan_name}',
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
        index += 1
    return plans


def scrape_newausfiber_plans() -> List[Dict[str, Any]]:
    log_info('Starting New Aus Fiber scraper', provider='newausfiber')
    plans: List[Dict[str, Any]] = []

    try:
        plans = _extract_plans(_page_lines(_fetch_html()))
    except Exception as exc:
        log_error(f'New Aus Fiber scraper failed: {exc}', provider='newausfiber')

    seen = set()
    unique_plans: List[Dict[str, Any]] = []
    for plan in plans:
        key = (plan['plan_name'], plan['download_speed'], plan['upload_speed'], plan['price'])
        if key in seen:
            continue
        seen.add(key)
        unique_plans.append(plan)

    unique_plans.sort(key=lambda plan: plan['download_speed'])
    if not unique_plans:
        log_warning('New Aus Fiber scraper returned no plans', provider='newausfiber')
    log_success(f'New Aus Fiber scraper complete: {len(unique_plans)} plans', provider='newausfiber')
    return unique_plans


if __name__ == '__main__':
    for item in scrape_newausfiber_plans():
        print(item)
