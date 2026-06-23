"""Aussie Broadband provider scraper.

The live Aussie Broadband checkout is protected by Cloudflare Turnstile in
automated browser sessions. Aussie publishes plan-card content for NBN and
Opticomm pages, so this module keeps those public values as a maintained
fallback.
"""

from typing import Any, Dict, List, Sequence, Tuple

import config
from utils.logger import log_info, log_success


PROVIDER_ID = config.PROVIDERS.get('aussie', {}).get('id', 3)
PROVIDER_NAME = 'Aussie Broadband'
NBN_SOURCE_URL = 'https://www.aussiebroadband.com.au/internet/nbn-plans/'
OPTICOMM_SOURCE_URL = 'https://www.aussiebroadband.com.au/internet/opticomm-plans/'


PlanSeed = Dict[str, Any]


NBN_PLANS: Sequence[PlanSeed] = [
    {
        'name': 'Basic',
        'speed': (12, 1),
        'price': 73.0,
        'promo_price': None,
        'promo_period': None,
        'typical': (12, 1),
    },
    {
        'name': 'Basic Plus',
        'speed': (25, 10),
        'price': 79.0,
        'promo_price': 55.30,
        'promo_period': 'first month; $58.10/month for months 2-3',
        'typical': (23, 9),
    },
    {
        'name': 'Value',
        'speed': (50, 20),
        'price': 93.0,
        'promo_price': 65.10,
        'promo_period': 'first month; $66.50/month for months 2-3',
        'typical': (47, 18),
    },
    {
        'name': 'Fast',
        'speed': (100, 20),
        'price': 95.0,
        'promo_price': 80.0,
        'promo_period': 'first month; $84/month for months 2-6',
        'typical': (94, 18),
    },
    {
        'name': 'Fast Fibre',
        'speed': (500, 50),
        'price': 95.0,
        'promo_price': 80.0,
        'promo_period': 'first month; $84/month for months 2-6',
        'typical': (500, 44),
    },
    {
        'name': 'Ultrafast Fibre',
        'speed': (1000, 100),
        'price': 129.0,
        'promo_price': 109.0,
        'promo_period': 'first 6 months',
        'typical': (875, 92),
    },
    {
        'name': 'Hyperfast',
        'speed': (2000, 200),
        'price': 189.0,
        'promo_price': 169.0,
        'promo_period': 'first 6 months',
        'typical': (1810, 178),
    },
]


OPTICOMM_PLANS: Sequence[PlanSeed] = [
    {
        'name': 'Basic',
        'speed': (12, 1),
        'price': 73.0,
        'promo_price': None,
        'promo_period': None,
        'typical': (12, 1),
    },
    {
        'name': 'Basic Plus',
        'speed': (25, 10),
        'price': 79.0,
        'promo_price': 55.30,
        'promo_period': 'first month; $58.10/month for months 2-3',
        'typical': (23, 9),
    },
    {
        'name': 'Value',
        'speed': (50, 20),
        'price': 93.0,
        'promo_price': 65.10,
        'promo_period': 'first month; $66.50/month for months 2-3',
        'typical': (47, 18),
    },
    {
        'name': 'Fast',
        'speed': (100, 20),
        'price': 95.0,
        'promo_price': 80.0,
        'promo_period': 'first month; $84/month for months 2-6',
        'typical': (94, 18),
    },
    {
        'name': 'SuperFast',
        'speed': (250, 25),
        'price': 119.0,
        'promo_price': 104.0,
        'promo_period': 'first 6 months',
        'typical': (250, 22),
    },
    {
        'name': 'Ultrafast',
        'speed': (1000, 50),
        'price': 129.0,
        'promo_price': 109.0,
        'promo_period': 'first 6 months',
        'typical': (875, 42),
    },
]


NETWORK_CATALOGUES: Sequence[Tuple[str, str, Sequence[PlanSeed]]] = (
    ('NBN', NBN_SOURCE_URL, NBN_PLANS),
    ('Opticomm', OPTICOMM_SOURCE_URL, OPTICOMM_PLANS),
)


def _plan_row(network_type: str, source_url: str, plan: PlanSeed) -> Dict[str, Any]:
    download_speed, upload_speed = plan['speed']
    typical_evening_dl, typical_evening_ul = plan['typical']
    return {
        'provider_id': PROVIDER_ID,
        'provider': PROVIDER_NAME,
        'network_type': network_type,
        'plan_name': f"{PROVIDER_NAME} {network_type} {plan['name']} {download_speed}/{upload_speed}",
        'download_speed': download_speed,
        'upload_speed': upload_speed,
        'price': plan['price'],
        'promo_price': plan['promo_price'],
        'promo_period': plan['promo_period'],
        'contract': 'No lock-in contract',
        'typical_evening_dl': typical_evening_dl,
        'typical_evening_ul': typical_evening_ul,
        'source_url': source_url,
    }


def scrape_aussie_plans() -> List[Dict[str, Any]]:
    """Return maintained Aussie Broadband NBN and Opticomm rows."""
    log_info('Starting Aussie Broadband scraper', provider='aussie')
    plans = [
        _plan_row(network_type, source_url, plan)
        for network_type, source_url, catalogue in NETWORK_CATALOGUES
        for plan in catalogue
    ]
    log_success(f'Aussie Broadband scraper complete: {len(plans)} plans', provider='aussie')
    return plans


def scrape_via_playwright() -> List[Dict[str, Any]]:
    """Compatibility entrypoint used by older service code."""
    return scrape_aussie_plans()


if __name__ == '__main__':
    for item in scrape_aussie_plans():
        print(item)
