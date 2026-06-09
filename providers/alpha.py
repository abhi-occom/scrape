"""Alpha Dot Net provider scraper.

Scrapes residential Alpha home internet plans from home.alpha.net.au.
The submitted www.alpha.net.au URL is a holding page that links users to
home.alpha.net.au for residential plans.
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


PROVIDER_ID = config.PROVIDERS.get('alpha', {}).get('id', 20)
PROVIDER_NAME = 'Alpha'

PLAN_PAGES = [
    ('Supanetworks', 'https://home.alpha.net.au/plans/plan-supanetworks.html'),
    ('Lynham Networks', 'https://home.alpha.net.au/plans/plan-lynham-networks.html'),
    ('Opticomm', 'https://home.alpha.net.au/plans/plan-opticomm.html'),
    ('NBN', 'https://home.alpha.net.au/plans/plan-nbn.html'),
]


def _normalise_text(text: str) -> str:
    text = text.replace('\xa0', ' ')
    text = text.replace('\u200d', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def _parse_speed(speed_text: str) -> Tuple[int, int]:
    match = re.search(
        r'(\d+)\s*mbps\s*/\s*(\d+)\s*mbps',
        speed_text,
        re.IGNORECASE,
    )
    if not match:
        return 0, 0
    return int(match.group(1)), int(match.group(2))


def _parse_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    return float(value.replace(',', ''))


def _fetch_html(url: str) -> str:
    # Alpha's certificate chain can fail in Python's cert store on Windows.
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    response = requests.get(url, timeout=30, verify=False)
    response.raise_for_status()
    return response.text


def _extract_plans_from_html(network_type: str, url: str, html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text('\n')
    text = re.sub(r'\n\s*\n+', '\n', text)

    blocks = re.findall(
        r'Information About Pricing\s+([\s\S]*?)\s+Other Information',
        text,
        re.IGNORECASE,
    )

    plans: List[Dict[str, Any]] = []
    for block in blocks:
        plan_match = re.search(
            r'([A-Za-z ]+\s+\d+\s*mbps\s*/\s*\d+\s*mbps)\s+Plans',
            block,
            re.IGNORECASE,
        )
        price_match = re.search(
            r'Monthly Charge\s*\$\s*([0-9.]+)',
            block,
            re.IGNORECASE,
        )

        if not plan_match or not price_match:
            continue

        raw_name = _normalise_text(plan_match.group(1))
        download_speed, upload_speed = _parse_speed(raw_name)
        price = _parse_float(price_match.group(1))
        if not download_speed or price is None:
            continue

        setup_match = re.search(r'Set Up Fee\s*\$\s*([0-9.]+)', block, re.IGNORECASE)
        setup_fee = _parse_float(setup_match.group(1)) if setup_match else None
        setup_note = f"; ${setup_fee:.2f} setup fee" if setup_fee and setup_fee > 0 else ''

        plans.append({
            'provider_id': PROVIDER_ID,
            'provider': PROVIDER_NAME,
            'network_type': network_type,
            'plan_name': f'Alpha {raw_name}',
            'download_speed': download_speed,
            'upload_speed': upload_speed,
            'price': price,
            'promo_price': None,
            'promo_period': None,
            'contract': f'Month to month, no cancellation fees{setup_note}',
            'typical_evening_dl': download_speed,
            'typical_evening_ul': upload_speed,
            'source_url': url,
        })

    return plans


def scrape_alpha_plans() -> List[Dict[str, Any]]:
    log_info('Starting Alpha scraper', provider='alpha')
    all_plans: List[Dict[str, Any]] = []

    for network_type, url in PLAN_PAGES:
        try:
            html = _fetch_html(url)
            plans = _extract_plans_from_html(network_type, url, html)
            log_info(f'{network_type}: extracted {len(plans)} plans', provider='alpha')
            all_plans.extend(plans)
        except Exception as exc:
            log_error(f'Alpha scrape failed for {url}: {exc}', provider='alpha')

    seen = set()
    unique_plans = []
    for plan in all_plans:
        key = (
            plan['network_type'],
            plan['download_speed'],
            plan['upload_speed'],
            plan['price'],
        )
        if key in seen:
            continue
        seen.add(key)
        unique_plans.append(plan)

    unique_plans.sort(key=lambda p: (p['network_type'], p['download_speed'], p['upload_speed']))
    if not unique_plans:
        log_warning('Alpha scraper returned no plans', provider='alpha')
    log_success(f'Alpha scraper complete: {len(unique_plans)} plans', provider='alpha')
    return unique_plans


if __name__ == '__main__':
    for plan in scrape_alpha_plans():
        print(
            f"{plan['network_type']}: {plan['plan_name']} "
            f"{plan['download_speed']}/{plan['upload_speed']} Mbps "
            f"${plan['price']:.2f}/month"
        )
