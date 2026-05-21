"""Leaptel ISP provider scraper."""
import re
from typing import List, Dict, Any
from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page
from utils.logger import log_info, log_success, log_error, log_warning
import config

LEAPTEL_PAGES = {
    'nbn': {
        'url': 'https://leaptel.com.au/plans/?provider=nbn',
        'network_type': 'NBN'
    },
    'opticomm': {
        'url': 'https://leaptel.com.au/plans/?provider=opt',
        'network_type': 'Opticomm'
    },
    'redtrain': {
        'url': 'https://leaptel.com.au/plans/?provider=red',
        'network_type': 'Redtrain'
    },
    'fixed_wireless': {
        'url': 'https://leaptel.com.au/fixed-wireless/',
        'network_type': 'Fixed Wireless'
    },
}


def extract_number(text: str) -> int:
    """Extract first number from text."""
    match = re.search(r'\d+', str(text))
    return int(match.group()) if match else 0


def extract_price(text: str) -> float:
    """Extract price from text like '$49.95 / month'."""
    match = re.search(r'\$(\d+\.?\d*)', str(text))
    return float(match.group(1)) if match else 0.0


def extract_speed_range(text: str) -> tuple:
    """Extract speed range from text like '75-100Mbps' or '25Mbps'."""
    text = str(text).replace('Mbps', '').strip()
    if '-' in text:
        parts = text.split('-')
        try:
            return (int(parts[0].strip()), int(parts[1].strip()))
        except:
            return (0, 0)
    else:
        try:
            val = int(text)
            return (val, val)
        except:
            return (0, 0)


def extract_plan_from_card(card, network_type: str, source_url: str) -> Dict[str, Any]:
    """Extract plan data from a plan card element."""
    try:
        card_text = card.inner_text()

        # Extract plan name from header
        plan_name = ''
        headers = card.query_selector_all('h3, h4, h2')
        if headers:
            plan_name = headers[0].inner_text().strip()

        if not plan_name:
            return None

        # Extract speeds from text
        # Structure: Plan name, then Mbps, then DOWNLOAD, then Mbps, then UPLOAD
        download_speed = 0
        upload_speed = 0

        lines = card_text.split('\n')
        for i, line in enumerate(lines):
            # Find download speed (line with Mbps that comes before DOWNLOAD)
            if i + 1 < len(lines) and 'DOWNLOAD' in lines[i + 1]:
                match = re.search(r'(\d+)-?(\d*)\s*Mbps', line)
                if match:
                    val1 = int(match.group(1))
                    val2 = int(match.group(2)) if match.group(2) else val1
                    download_speed = max(val1, val2)

            # Find upload speed (line with Mbps that comes before UPLOAD)
            if i + 1 < len(lines) and 'UPLOAD' in lines[i + 1]:
                match = re.search(r'(\d+)-?(\d*)\s*Mbps', line)
                if match:
                    val1 = int(match.group(1))
                    val2 = int(match.group(2)) if match.group(2) else val1
                    upload_speed = max(val1, val2)

        # Extract price
        price = 0.0
        price_match = re.search(r'\$(\d+\.?\d*)\s*/\s*month', card_text)
        if price_match:
            price = float(price_match.group(1))

        # Extract promo price and period
        promo_price = None
        promo_period = None
        promo_match = re.search(r'\$(\d+\.?\d*)\s*discount\s*for\s*(\d+\s*(?:months?|years?))', card_text)
        if promo_match:
            discount_amount = float(promo_match.group(1))
            period_text = promo_match.group(2)
            promo_price = price - discount_amount if price > discount_amount else price
            promo_period = period_text.strip()

        # Skip invalid plans
        if not plan_name or price <= 0:
            return None

        plan = {
            'provider_id': config.PROVIDERS.get('leaptel', {}).get('id', 8),
            'plan_name': plan_name,
            'network_type': network_type,
            'download_speed': download_speed,
            'upload_speed': upload_speed,
            'price': price,
            'promo_price': promo_price,
            'promo_period': promo_period,
            'contract': 'No Contract',
            'source_url': source_url
        }

        return plan
    except Exception as e:
        log_error(f'Error extracting plan from card: {str(e)}', provider='leaptel')
        return None



def scrape_page(browser, url: str, network_type: str) -> List[Dict[str, Any]]:
    """Scrape a single Leaptel page and extract plans."""
    plans = []
    page = None

    try:
        page = create_stealth_page(browser)
        page.goto(url, timeout=40000, wait_until='domcontentloaded')
        page.wait_for_timeout(6000)

        # Find plan cards
        cards = page.query_selector_all('[class*="card"]')
        log_info(f'Found {len(cards)} card elements on {network_type} page', provider='leaptel')

        for card in cards:
            try:
                plan = extract_plan_from_card(card, network_type, url)
                if plan:
                    plans.append(plan)
            except Exception as e:
                log_warning(f'Error processing card on {network_type}: {str(e)}', provider='leaptel')
                continue

        # Deduplicate plans by name+price+speeds
        seen = set()
        unique_plans = []
        for plan in plans:
            key = f"{plan['plan_name']}_{plan['price']}_{plan['download_speed']}_{plan['upload_speed']}"
            if key not in seen:
                seen.add(key)
                unique_plans.append(plan)

        log_success(f'Extracted {len(unique_plans)} unique plans from {network_type} page', provider='leaptel')
        return unique_plans

    except Exception as e:
        log_error(f'Error scraping {network_type} page: {str(e)}', provider='leaptel')
        return plans
    finally:
        if page:
            page.close()


def scrape_leaptel_plans() -> List[Dict[str, Any]]:
    """Main scraper function - returns flat list of all Leaptel plans."""
    all_plans = []

    try:
        with sync_playwright() as p:
            browser = create_stealth_browser(p)

            for page_key, page_config in LEAPTEL_PAGES.items():
                try:
                    log_info(f'Scraping {page_key} plans', provider='leaptel')
                    plans = scrape_page(browser, page_config['url'], page_config['network_type'])
                    all_plans.extend(plans)
                except Exception as e:
                    log_error(f'Failed to scrape {page_key}: {str(e)}', provider='leaptel')
                    continue

            browser.close()

        log_success(f'Scraping complete. Total plans: {len(all_plans)}', provider='leaptel')
        return all_plans

    except Exception as e:
        log_error(f'Fatal error in scrape_leaptel_plans: {str(e)}', provider='leaptel')
        return all_plans
