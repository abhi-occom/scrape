"""IQNet provider scraper.

Scrapes IQNet plans across ASN, Lynham, SUPA, NBN Co and Vision network pages.
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


PROVIDER_ID = config.PROVIDERS.get('iqnet', {}).get('id', 23)
PROVIDER_NAME = 'IQNet'

PLAN_PAGES = [
    {
        'url': 'https://iqnet.com.au/asn/',
        'network_type': 'ASN Telecom',
        'labels': ('ASN Networks',),
    },
    {
        'url': 'https://iqnet.com.au/choose-iq-net-as-your-lynham-networks/',
        'network_type': 'Lynham Networks',
        'labels': ('Lynham Networks',),
    },
    {
        'url': 'https://iqnet.com.au/broadband/',
        'network_type': 'SUPA Networks',
        'labels': ('Fibre Broadband',),
    },
    {
        'url': 'https://iqnet.com.au/nbn-co/',
        'network_type': 'NBN',
        'labels': ('Broadband', 'Fibre-HFC'),
    },
    {
        'url': 'https://iqnet.com.au/vision',
        'network_type': 'Vision Networks',
        'labels': ('Vision Networks',),
    },
]


def _normalise_text(text: str) -> str:
    text = text.replace('\xa0', ' ')
    text = re.sub(r'[\ue000-\uf8ff]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _fetch_html(url: str) -> str:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    response = requests.get(url, timeout=30, verify=False)
    response.raise_for_status()
    return response.text


def _page_lines(html: str) -> List[str]:
    soup = BeautifulSoup(html, 'html.parser')
    lines = [
        _normalise_text(line)
        for line in soup.get_text('\n', strip=True).splitlines()
    ]
    return [line for line in lines if line]


def _parse_price(lines: List[str], index: int) -> Optional[float]:
    if lines[index] != '$':
        match = re.search(r'\$\s*([0-9]+(?:\.[0-9]+)?)', lines[index].replace(',', ''))
        return float(match.group(1)) if match else None

    if index + 1 >= len(lines):
        return None
    price_text = lines[index + 1].replace(',', '')
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', price_text):
        return None
    return float(price_text)


def _parse_speed(line: str) -> Optional[int]:
    match = re.search(r'(\d+)(?:\s*-\s*\d+)?\s*Mbps', line, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _extract_plan(lines: List[str], index: int, page_cfg: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], int]:
    if index + 3 >= len(lines):
        return None, index + 1

    network_label = lines[index]
    plan_tier = lines[index + 1]
    if lines[index + 2] != '$':
        return None, index + 1

    price = _parse_price(lines, index + 2)
    if price is None:
        return None, index + 1

    block_end = min(len(lines), index + 18)
    block = lines[index:block_end]
    download_speed = 0
    upload_speed = 0
    for pos, line in enumerate(block):
        if 'Download Speeds' in line:
            download_speed = _parse_speed(line) or 0
        elif 'Upload Speeds' in line:
            upload_speed = _parse_speed(line) or 0
        if download_speed and upload_speed:
            break

    if not download_speed:
        log_warning(f'IQNet: missing speed data for {network_label} {plan_tier}', provider='iqnet')
        return None, index + 1

    connection_fee = any('$45 Connection FEE' in line for line in block)
    contract = 'No lock-in, unlimited data'
    if connection_fee:
        contract += '; $45 connection fee'

    plan_name = f'{PROVIDER_NAME} {network_label} {plan_tier}'
    return {
        'provider_id': PROVIDER_ID,
        'provider': PROVIDER_NAME,
        'network_type': page_cfg['network_type'],
        'plan_name': plan_name,
        'download_speed': download_speed,
        'upload_speed': upload_speed,
        'price': price,
        'promo_price': None,
        'promo_period': None,
        'contract': contract,
        'typical_evening_dl': download_speed,
        'typical_evening_ul': upload_speed,
        'source_url': page_cfg['url'],
    }, block_end


def _extract_page_plans(page_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    lines = _page_lines(_fetch_html(page_cfg['url']))
    plans: List[Dict[str, Any]] = []
    labels = set(page_cfg['labels'])
    index = 0
    while index < len(lines):
        if lines[index] not in labels:
            index += 1
            continue
        plan, next_index = _extract_plan(lines, index, page_cfg)
        if plan:
            plans.append(plan)
        index += 1
    return plans


def scrape_iqnet_plans() -> List[Dict[str, Any]]:
    log_info('Starting IQNet scraper', provider='iqnet')
    all_plans: List[Dict[str, Any]] = []

    for page_cfg in PLAN_PAGES:
        try:
            plans = _extract_page_plans(page_cfg)
            log_info(
                f"{page_cfg['network_type']}: extracted {len(plans)} plans",
                provider='iqnet',
            )
            all_plans.extend(plans)
        except Exception as exc:
            log_error(f"IQNet scrape failed for {page_cfg['url']}: {exc}", provider='iqnet')

    seen = set()
    unique_plans: List[Dict[str, Any]] = []
    for plan in all_plans:
        key = (
            plan['network_type'],
            plan['plan_name'],
            plan['download_speed'],
            plan['upload_speed'],
            plan['price'],
        )
        if key in seen:
            continue
        seen.add(key)
        unique_plans.append(plan)

    unique_plans.sort(key=lambda p: (p['network_type'], p['download_speed'], p['upload_speed'], p['price']))
    if not unique_plans:
        log_warning('IQNet scraper returned no plans', provider='iqnet')
    log_success(f'IQNet scraper complete: {len(unique_plans)} plans', provider='iqnet')
    return unique_plans


if __name__ == '__main__':
    for item in scrape_iqnet_plans():
        print(item)
