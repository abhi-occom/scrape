# scrape/providers/more.py
"""More ISP provider scraper.
Scrapes https://more.com.au/personal/nbn-plans
The page is JavaScript-rendered with plan data in .owl-item elements.
"""
import re, sys, os
from typing import Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from utils.logger import log_info, log_error, log_success, log_warning
from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright, ElementHandle

PROVIDER_ID = 14
URL = 'https://more.com.au/personal/nbn-plans'

PLAN_PAGES = [
    {
        'url': 'https://more.com.au/personal/nbn-plans',
        'network_type': 'NBN',
        'valid_names': ['Value', 'Value Plus', 'Fast Max', 'Ultrafast'],
        'prefix': 'More ',
    },
    {
        'url': 'https://more.com.au/personal/nbn-fixed-wireless',
        'network_type': 'Fixed Wireless',
        'valid_names': ['Fixed Wireless Value Plus', 'Fixed Wireless Fast', 'Fixed Wireless Superfast'],
        'prefix': 'More ',
    },
    {
        'url': 'https://more.com.au/personal/mobile-plans',
        'network_type': 'Mobile',
        'valid_names': ['14GB', '30GB', '50GB', '75GB', '100GB', '160GB'],
        'prefix': 'More Mobile ',
    },
    {
        'url': 'https://more.com.au/business/business-nbn-plans',
        'network_type': 'Business NBN',
        'valid_names': ['Business Fast Max', 'Business Superfast', 'Business Ultrafast', 'Business Ultrafast Plus'],
        'prefix': 'More ',
    },
    {
        'url': 'https://more.com.au/business/business-nbn-fixed-wireless',
        'network_type': 'Business Fixed Wireless',
        'valid_names': ['Fixed Wireless Value Plus', 'Fixed Wireless Fast', 'Fixed Wireless Superfast'],
        'prefix': 'More Business ',
    },
    {
        'url': 'https://more.com.au/business/business-mobile-plans',
        'network_type': 'Business Mobile',
        'valid_names': ['14GB', '30GB', '50GB', '75GB', '100GB', '160GB'],
        'prefix': 'More Business Mobile ',
    },
]


def _clean_money(value):
    return float(re.sub(r'\s+', '', value))


def _parse_price(raw):
    m = re.search(r'\$\s*([0-9]+(?:\s*\.\s*[0-9]+)?)', raw.replace(',', ''))
    return _clean_money(m.group(1)) if m else None


def _parse_speeds(text):
    # Handle various formats like "25Mbps", "42.5Mbps", "85 Mbps"
    dl = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*Mbps\s*Download', text, re.IGNORECASE)
    ul = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*Mbps\s*Upload', text, re.IGNORECASE)
    if not dl:
        dl = re.search(
            r'Download\s+speeds\s+are\s+capped\s+at\s+([0-9]+(?:\.[0-9]+)?)\s*Mbps',
            text,
            re.IGNORECASE,
        )
    download = float(dl.group(1)) if dl else 0
    upload = float(ul.group(1)) if ul else 0
    download = int(download) if download.is_integer() else download
    upload = int(upload) if upload.is_integer() else upload
    return download, upload


def _parse_promo_info(text):
    # Check for promo pattern: "$XX/mth for XX months, then $XX/mth"
    money = r'\$\s*([0-9]+(?:\s*\.\s*[0-9]+)?)'
    monthly = rf'{money}\s*(?:/|per)?\s*mth'
    promo_match = re.search(
        rf'{monthly}\s*for\s*([0-9]+)\s*months?',
        text,
        re.IGNORECASE,
    )
    if promo_match:
        promo_price = _clean_money(promo_match.group(1))
        promo_period = promo_match.group(2) + ' months'
        then_match = re.search(rf'then\s*{monthly}', text, re.IGNORECASE)
        regular_price = _clean_money(then_match.group(1)) if then_match else None
        return promo_price, promo_period, regular_price

    # Check for RRP price (regular price before any promo)
    rrp_match = re.search(rf'RRP\s*{money}', text, re.IGNORECASE)
    if rrp_match:
        rrp_price = _clean_money(rrp_match.group(1))
        # Look for displayed price (could be promo)
        price_matches = list(re.finditer(monthly, text, re.IGNORECASE))
        price_match = price_matches[0] if price_matches else None
        if price_match:
            display_price = _clean_money(price_match.group(1))
            if display_price < rrp_price:
                # Display price is promo
                period_match = re.search(r'for\s*([0-9]+)\s*months?', text, re.IGNORECASE)
                promo_period = period_match.group(1) + ' months' if period_match else 'Promo'
                then_match = re.search(rf'then\s*{monthly}', text, re.IGNORECASE)
                regular_price = _clean_money(then_match.group(1)) if then_match else rrp_price
                return display_price, promo_period, regular_price
            else:
                return None, None, display_price
        return None, None, rrp_price

    # Simple price without promo
    price_match = re.search(monthly, text, re.IGNORECASE)
    if price_match:
        return None, None, _clean_money(price_match.group(1))

    price = _parse_price(text)
    if price is not None:
        return None, None, price

    return None, None, None


def _extract_plan(card, page_cfg):
    try:
        text = card.inner_text()
        valid_names = page_cfg['valid_names']
        if not any(name in text for name in valid_names):
            return None
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        plan_name = lines[0] if lines else ''
        if plan_name not in valid_names:
            return None
        
        # Parse pricing - handles both promo and regular pricing
        promo_price, promo_period, regular_price = _parse_promo_info(text)
        
        # Parse speeds
        download_speed, upload_speed = _parse_speeds(text)
        
        if not plan_name or not regular_price:
            log_warning(f'More: missing required data for {plan_name}', provider='more')
            return None
        
        network_type = page_cfg['network_type']
        if network_type in ('Mobile', 'Business Mobile'):
            network_type = '4G Mobile' if '4G NETWORK ACCESS' in text else '5G Mobile'

        return {
            'provider_id': PROVIDER_ID,
            'provider': 'More',
            'plan_name': page_cfg['prefix'] + plan_name,
            'network_type': network_type,
            'download_speed': download_speed,
            'upload_speed': upload_speed,
            'price': regular_price,
            'promo_price': promo_price,
            'promo_period': promo_period,
            'contract': 'No Lock-in',
            'typical_evening_dl': download_speed,
            'typical_evening_ul': upload_speed,
            'source_url': page_cfg['url']
        }
    except Exception as e:
        log_error(f'More: error extracting card - {e}', provider='more')
        return None


def scrape_more_plans():
    log_info('Starting More scraper', provider='more')
    all_plans = []
    try:
        with sync_playwright() as p:
            browser = create_stealth_browser(p)
            page = create_stealth_page(browser)
            seen = set()
            for page_cfg in PLAN_PAGES:
                page.goto(page_cfg['url'], timeout=40000, wait_until='domcontentloaded')
                page.wait_for_timeout(7000)
                container = page.query_selector('#products-list')
                if not container:
                    container = page.query_selector('#speeds')
                if not container:
                    log_error(f"Could not find products container: {page_cfg['url']}", provider='more')
                    continue
                cards = container.query_selector_all('.owl-item')
                log_info(
                    f"Found {len(cards)} owl-item elements on {page_cfg['url']}",
                    provider='more',
                )
                for card in cards:
                    plan = _extract_plan(card, page_cfg)
                    if plan is None:
                        continue
                    key = (plan['plan_name'], plan['network_type'], plan['source_url'])
                    if key in seen:
                        continue
                    seen.add(key)
                    all_plans.append(plan)
            browser.close()
    except Exception as e:
        log_error(f'More scraper failed: {e}', provider='more')
    all_plans.sort(key=lambda x: x['download_speed'])
    log_success(f'More scraper complete: {len(all_plans)} plans', provider='more')
    return all_plans


if __name__ == '__main__':
    plans = scrape_more_plans()
    print(f'Total plans: {len(plans)}')
    for plan in plans:
        promo = f" (promo ${plan['promo_price']}/mth for {plan['promo_period']})" if plan['promo_price'] else ""
        print(f"{plan['plan_name']} {plan['download_speed']}/{plan['upload_speed']} Mbps ${plan['price']:.2f}/mth{promo}")
