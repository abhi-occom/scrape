"""Airtel AU provider scraper.

Scrapes Airtel AU mobile and travel SIM plans from:
- https://airtel.au/mobile
- https://airtel.au/travel-sim
"""

import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from playwright.sync_api import sync_playwright
from utils.logger import log_error, log_info, log_success, log_warning
from utils.stealth import create_stealth_browser, create_stealth_page


PROVIDER_ID = config.PROVIDERS.get('airtel', {}).get('id', 19)
PROVIDER_NAME = 'Airtel'
MOBILE_URL = 'https://airtel.au/mobile'
TRAVEL_SIM_URL = 'https://airtel.au/travel-sim'

MOBILE_TABS = [
    ('5G Plans', '5G Mobile'),
    ('4G Plans', '4G Mobile'),
    ('Family Share', 'Family Share Mobile'),
    ('Roaming Plans', 'Roaming Mobile'),
    ('5G Broad Band', '5G Mobile Broadband'),
]

TRAVEL_TABS = [
    ('Global', 'Travel SIM Global'),
    ('Europe', 'Travel SIM Europe'),
    ('Asia', 'Travel SIM Asia'),
    ('Aisa Zone 2', 'Travel SIM Asia Zone 2'),
]


def _parse_price(text: str) -> Optional[float]:
    match = re.search(r'\$([0-9]+(?:\.[0-9]+)?)', text.replace(',', ''))
    return float(match.group(1)) if match else None


def _parse_period(text: str) -> Optional[str]:
    match = re.search(r'(\d+)\s*Days?', text, re.IGNORECASE)
    return f"{match.group(1)} Days" if match else None


def _parse_speeds(text: str) -> Tuple[int, int]:
    match = re.search(
        r'(?:Up/\s*Down|Upload\s*/\s*Download)\s+Speed\s+(\d+)\s*/\s*(\d+)',
        text,
        re.IGNORECASE,
    )
    if not match:
        return 0, 0
    return int(match.group(1)), int(match.group(2))


def _data_allowance_to_speed(data_allowance: str) -> int:
    match = re.search(r'(\d+)\s*GB', data_allowance, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _visible_lines(page) -> List[str]:
    return [line.strip() for line in page.inner_text('body').splitlines() if line.strip()]


def _section_lines(lines: List[str], tab_labels: List[str], selected_label: str) -> List[str]:
    """Return visible plan text after the tab labels and before SIM/add-on sections."""
    label_positions = [i for i, line in enumerate(lines) if line in tab_labels]
    if not label_positions:
        return lines

    start = max(label_positions) + 1
    if selected_label in ('5G Plans', 'Global'):
        # First visible item is also presented as the selected tab label.
        start = max(i for i, line in enumerate(lines) if line == selected_label)

    stop_phrases = (
        'Select your SIM option',
        'Stay connected worldwide',
        'Roaming countries:',
        'Add airtime for Calls and SMS',
        'Your Order Summary',
        'Frequently asked questions',
    )
    end = len(lines)
    for i in range(start, len(lines)):
        if any(lines[i].startswith(phrase) for phrase in stop_phrases):
            end = i
            break
    return lines[start:end]


def _parse_mobile_section(lines: List[str], network_type: str, source_url: str) -> List[Dict[str, Any]]:
    plans: List[Dict[str, Any]] = []
    i = 0
    while i < len(lines) - 3:
        name = lines[i]
        data_allowance = lines[i + 1]
        price_raw = lines[i + 2]
        period_raw = lines[i + 3]

        if not re.search(r'\d+\s*GB', data_allowance, re.IGNORECASE) or not price_raw.startswith('$'):
            i += 1
            continue

        price = _parse_price(price_raw)
        if price is None:
            i += 1
            continue

        detail = '\n'.join(lines[i:i + 9])
        upload_speed, download_speed = _parse_speeds(detail)

        plans.append({
            'provider_id': PROVIDER_ID,
            'provider': PROVIDER_NAME,
            'network_type': network_type,
            'plan_name': f'Airtel {name} {data_allowance}',
            'download_speed': download_speed,
            'upload_speed': upload_speed,
            'price': price,
            'promo_price': None,
            'promo_period': None,
            'contract': 'No Lock-in',
            'typical_evening_dl': download_speed,
            'typical_evening_ul': upload_speed,
            'source_url': source_url,
        })
        i += 4
    return plans


def _parse_travel_section(lines: List[str], network_type: str, source_url: str) -> List[Dict[str, Any]]:
    plans: List[Dict[str, Any]] = []
    i = 0
    while i < len(lines) - 3:
        name = lines[i]
        data_allowance = lines[i + 1]
        price_raw = lines[i + 2]
        period_raw = lines[i + 3]

        if not re.search(r'\d+\s*GB', data_allowance, re.IGNORECASE) or not price_raw.startswith('$'):
            i += 1
            continue

        price = _parse_price(price_raw)
        if price is None:
            i += 1
            continue

        download_speed = _data_allowance_to_speed(data_allowance)
        plans.append({
            'provider_id': PROVIDER_ID,
            'provider': PROVIDER_NAME,
            'network_type': network_type,
            'plan_name': f'Airtel {name} {data_allowance}',
            'download_speed': download_speed,
            'upload_speed': 0,
            'price': price,
            'promo_price': None,
            'promo_period': _parse_period(period_raw),
            'contract': 'Prepaid',
            'typical_evening_dl': download_speed,
            'typical_evening_ul': 0,
            'source_url': source_url,
        })
        i += 4
    return plans


def _click_tab(page, label: str) -> None:
    page.get_by_text(label, exact=True).click(timeout=5000)
    page.wait_for_timeout(1500)


def scrape_airtel_plans() -> List[Dict[str, Any]]:
    log_info('Starting Airtel scraper', provider='airtel')
    plans: List[Dict[str, Any]] = []

    try:
        with sync_playwright() as p:
            browser = create_stealth_browser(p)
            page = create_stealth_page(browser)

            page.goto(MOBILE_URL, timeout=45000, wait_until='domcontentloaded')
            page.wait_for_timeout(5000)
            mobile_labels = [label for label, _ in MOBILE_TABS]
            for label, network_type in MOBILE_TABS:
                try:
                    _click_tab(page, label)
                except Exception as exc:
                    log_warning(f'Airtel: could not select mobile tab {label}: {exc}', provider='airtel')
                    continue
                section = _section_lines(_visible_lines(page), mobile_labels, label)
                plans.extend(_parse_mobile_section(section, network_type, MOBILE_URL))

            page.goto(TRAVEL_SIM_URL, timeout=45000, wait_until='domcontentloaded')
            page.wait_for_timeout(5000)
            travel_labels = [label for label, _ in TRAVEL_TABS]
            for label, network_type in TRAVEL_TABS:
                try:
                    _click_tab(page, label)
                except Exception as exc:
                    log_warning(f'Airtel: could not select travel tab {label}: {exc}', provider='airtel')
                    continue
                section = _section_lines(_visible_lines(page), travel_labels, label)
                plans.extend(_parse_travel_section(section, network_type, TRAVEL_SIM_URL))

            browser.close()

    except Exception as exc:
        log_error(f'Airtel scraper failed: {exc}', provider='airtel')

    deduped = []
    seen = set()
    for plan in plans:
        key = (plan['network_type'], plan['plan_name'], plan['price'], plan['source_url'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(plan)

    deduped.sort(key=lambda plan: (plan['network_type'], plan['download_speed'], plan['price']))
    log_success(f'Airtel scraper complete: {len(deduped)} plans', provider='airtel')
    return deduped


if __name__ == '__main__':
    for item in scrape_airtel_plans():
        print(item)
