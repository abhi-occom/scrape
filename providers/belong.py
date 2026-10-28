"""Belong provider scraper.

Scrapes Belong's nbn internet, mobile SIM and data SIM plans:
  - https://www.belong.com.au/go/internet
  - https://www.belong.com.au/go/mobile
  - https://www.belong.com.au/go/data-plans
"""

import os
import re
import sys
from typing import Any, Dict, List, Optional

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from utils.logger import log_error, log_info, log_success, log_warning
from utils.stealth import create_stealth_browser, create_stealth_page


PROVIDER_ID = config.PROVIDERS.get('belong', {}).get('id', 28)
PROVIDER_NAME = 'Belong'

INTERNET_URL = 'https://www.belong.com.au/go/internet'
MOBILE_URL = 'https://www.belong.com.au/go/mobile'
DATA_URL = 'https://www.belong.com.au/go/data-plans'

_RE_TIER = re.compile(r'^nbn\W{0,3}\s*(\d{2,4})$', re.IGNORECASE)
_RE_MONTHLY = re.compile(r'^\$\s*(\d+(?:\.\d+)?)\s*/\s*month$', re.IGNORECASE)
_RE_PROMO = re.compile(
    r'for\s+(\d+)\s+months?,?\s+then\s+\$\s*(\d+(?:\.\d+)?)\s*/\s*month',
    re.IGNORECASE,
)
_RE_EVENING_DL = re.compile(r'^(\d+)\s*Mbps\s+download$', re.IGNORECASE)
_RE_EVENING_UL = re.compile(r'^(\d+)\s*Mbps\s+upload$', re.IGNORECASE)
_RE_GIGABYTES = re.compile(r'^\d+\s+gigabytes$', re.IGNORECASE)
_RE_MTH_PRICE = re.compile(r'^\$\s*(\d+(?:\.\d+)?)\s*/\s*mth$', re.IGNORECASE)
_RE_SPEED_CAP = re.compile(r'capped at\s+(\d+)\s*Mbps', re.IGNORECASE)


def _lines(text: str) -> List[str]:
    text = (text or '').replace('\xa0', ' ')
    return [re.sub(r'\s+', ' ', line).strip() for line in text.splitlines() if line.strip()]


def parse_internet_plans(text: str, url: str = INTERNET_URL) -> List[Dict[str, Any]]:
    """Parse nbn plan cards. Each card is anchored on its 'nbn®NN' tier line."""
    lines = _lines(text)
    tiers = [i for i, line in enumerate(lines) if _RE_TIER.match(line)]
    plans: List[Dict[str, Any]] = []
    seen = set()

    for n, idx in enumerate(tiers):
        speed = int(_RE_TIER.match(lines[idx]).group(1))
        end = tiers[n + 1] if n + 1 < len(tiers) else len(lines)
        block = lines[idx + 1:end]

        # The "<Name> plan" label sits just before the tier line. The "$X/month
        # off" banner lines around it are discounts, never prices.
        label = ''
        for line in reversed(lines[max(0, idx - 4):idx]):
            if re.search(r'\bplan$', line, re.IGNORECASE) and not line.startswith('$'):
                label = line
                break

        price: Optional[float] = None
        promo_price: Optional[float] = None
        promo_period: Optional[str] = None
        for pos, line in enumerate(block[:8]):
            monthly = _RE_MONTHLY.match(line)
            if monthly and price is None:
                price = float(monthly.group(1))
                promo = _RE_PROMO.search(' '.join(block[pos + 1:pos + 3]))
                if promo:
                    promo_price = price
                    promo_period = f'{promo.group(1)} months'
                    price = float(promo.group(2))
                break
        if price is None:
            log_warning(f'Belong: no price found for nbn {speed}', provider='belong')
            continue

        evening_dl = evening_ul = 0
        for line in block:
            dl = _RE_EVENING_DL.match(line)
            ul = _RE_EVENING_UL.match(line)
            if dl and not evening_dl:
                evening_dl = int(dl.group(1))
            if ul and not evening_ul:
                evening_ul = int(ul.group(1))

        name = f'{label} - nbn {speed}' if label else f'nbn {speed}'
        key = (name, price)
        if key in seen:
            continue
        seen.add(key)
        plans.append({
            'provider_id': PROVIDER_ID,
            'provider': PROVIDER_NAME,
            'network_type': 'NBN',
            'plan_name': name,
            'download_speed': speed,
            'upload_speed': evening_ul,
            'price': price,
            'promo_price': promo_price,
            'promo_period': promo_period,
            'contract': 'No lock-in',
            'typical_evening_dl': evening_dl or speed,
            'typical_evening_ul': evening_ul,
            'source_url': url,
        })
    return plans


def parse_sim_plans(text: str, network_type: str, url: str) -> List[Dict[str, Any]]:
    """Parse mobile / data SIM cards. Each card has '<name>', 'N gigabytes', '$X/mth'."""
    lines = _lines(text)
    plans: List[Dict[str, Any]] = []
    seen = set()

    anchors = [i for i, line in enumerate(lines) if _RE_GIGABYTES.match(line) and i > 0]
    for n, idx in enumerate(anchors):
        name = lines[idx - 1]
        end = anchors[n + 1] - 1 if n + 1 < len(anchors) else len(lines)
        block = lines[idx + 1:end]

        price = None
        for line in block[:6]:
            m = _RE_MTH_PRICE.match(line)
            if m:
                price = float(m.group(1))
                break
        if price is None:
            log_warning(f'Belong: no price found for {name}', provider='belong')
            continue

        cap = _RE_SPEED_CAP.search(' '.join(block))
        speed = int(cap.group(1)) if cap else 0

        key = (name, price)
        if key in seen:
            continue
        seen.add(key)
        plans.append({
            'provider_id': PROVIDER_ID,
            'provider': PROVIDER_NAME,
            'network_type': network_type,
            'plan_name': name,
            'download_speed': speed,
            'upload_speed': 0,
            'price': price,
            'promo_price': None,
            'promo_period': None,
            'contract': 'No lock-in',
            'typical_evening_dl': speed,
            'typical_evening_ul': 0,
            'source_url': url,
        })
    return plans


def _page_text(browser, url: str, marker: str) -> str:
    """Load a page and return its text once the plan cards have rendered."""
    page = create_stealth_page(browser)
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=45000)
        try:
            page.wait_for_function(
                'm => document.body && document.body.innerText.includes(m)',
                arg=marker,
                timeout=20000,
            )
        except Exception:
            log_warning(f'Belong: "{marker}" not seen on {url}', provider='belong')
        page.wait_for_timeout(1500)
        return page.inner_text('body')
    finally:
        try:
            page.close()
        except Exception:
            pass


def scrape_belong_plans() -> List[Dict[str, Any]]:
    log_info('Starting Belong scraper', provider='belong')
    plans: List[Dict[str, Any]] = []

    try:
        with sync_playwright() as pw:
            browser = create_stealth_browser(pw)
            try:
                jobs = (
                    (INTERNET_URL, 'Typical evening speeds',
                     lambda t, u: parse_internet_plans(t, u)),
                    (MOBILE_URL, 'gigabytes',
                     lambda t, u: parse_sim_plans(t, 'Mobile', u)),
                    (DATA_URL, 'gigabytes',
                     lambda t, u: parse_sim_plans(t, 'Mobile Broadband', u)),
                )
                for url, marker, parse in jobs:
                    try:
                        found = parse(_page_text(browser, url, marker), url)
                        log_info(f'Belong: {len(found)} plans from {url}', provider='belong')
                        plans.extend(found)
                    except Exception as exc:
                        log_error(f'Belong: failed on {url}: {exc}', provider='belong')
            finally:
                browser.close()
    except Exception as exc:
        log_error(f'Belong scraper failed: {exc}', provider='belong')

    if not plans:
        log_warning('Belong scraper returned no plans', provider='belong')
    log_success(f'Belong scraper complete: {len(plans)} plans', provider='belong')
    return plans


if __name__ == '__main__':
    for item in scrape_belong_plans():
        print(item)
