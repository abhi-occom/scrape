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


def _parse_price(raw):
    m = re.search(r'\$([0-9]+(?:\.[0-9]+)?)', raw.replace(',', ''))
    return float(m.group(1)) if m else None


def _parse_speeds(text):
    # Handle various formats like "25Mbps", "42.5Mbps", "85 Mbps"
    dl = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*Mbps\s*Download', text, re.IGNORECASE)
    ul = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*Mbps\s*Upload', text, re.IGNORECASE)
    download = int(float(dl.group(1))) if dl else 0
    upload = int(float(ul.group(1))) if ul else 0
    return download, upload


def _parse_promo_info(text):
    # Check for promo pattern: "$XX/mth for XX months, then $XX/mth"
    promo_match = re.search(r'\$([0-9]+(?:\.[0-9]+)?)\s*/mth\s*for\s*([0-9]+)\s*months?', text, re.IGNORECASE)
    if promo_match:
        promo_price = float(promo_match.group(1))
        promo_period = promo_match.group(2) + ' months'
        then_match = re.search(r'then\s*\$([0-9]+(?:\.[0-9]+)?)\s*/mth', text, re.IGNORECASE)
        regular_price = float(then_match.group(1)) if then_match else None
        return promo_price, promo_period, regular_price
    
    # Check for RRP price (regular price before any promo)
    rrp_match = re.search(r'RRP\s*\$([0-9]+(?:\.[0-9]+)?)', text, re.IGNORECASE)
    if rrp_match:
        rrp_price = float(rrp_match.group(1))
        # Look for displayed price (could be promo)
        price_match = re.search(r'\$([0-9]+(?:\.[0-9]+)?)\s*/mth', text, re.IGNORECASE)
        if price_match:
            display_price = float(price_match.group(1))
            if display_price < rrp_price:
                # Display price is promo
                return display_price, 'Promo', rrp_price
            else:
                return None, None, display_price
        return None, None, rrp_price
    
    # Simple price without promo
    price_match = re.search(r'\$([0-9]+(?:\.[0-9]+)?)\s*/mth', text, re.IGNORECASE)
    if price_match:
        return None, None, float(price_match.group(1))
    
    return None, None, None


def _extract_plan(card):
    try:
        text = card.inner_text()
        valid_names = ['Value', 'Value Plus', 'Fast Max', 'Ultrafast']
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
        
        return {
            'provider_id': PROVIDER_ID,
            'provider': 'more',
            'plan_name': 'More ' + plan_name,
            'network_type': 'NBN',
            'download_speed': download_speed,
            'upload_speed': upload_speed,
            'price': regular_price,
            'promo_price': promo_price,
            'promo_period': promo_period,
            'contract': 'No Lock-in',
            'source_url': URL
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
            page.goto(URL, timeout=40000, wait_until='domcontentloaded')
            page.wait_for_timeout(8000)
            container = page.query_selector('#products-list')
            if not container:
                container = page.query_selector('#speeds')
            if not container:
                log_error('Could not find products container', provider='more')
                browser.close()
                return []
            cards = container.query_selector_all('.owl-item')
            log_info(f'Found {len(cards)} owl-item elements', provider='more')
            seen = set()
            for card in cards:
                plan = _extract_plan(card)
                if plan is None:
                    continue
                key = plan['plan_name']
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