"""
Occom ISP plan scraper.
Scrapes plans from multiple Occom network pages (NBN, Opticomm, Redtrain, etc.).
Plan data is extracted from .plan-card elements in an owl-carousel.
"""

import re
from typing import List, Dict, Any
from playwright.sync_api import sync_playwright
import config
from utils.logger import log_info, log_error, log_success
from utils.stealth import create_stealth_browser, create_stealth_page


# All Occom plan page URLs with their network type
OCCOM_PLAN_PAGES = {
    'nbn': {
        'url': 'https://occom.com.au/nbn-plans/',
        'network_type': 'NBN',
    },
    'opticomm': {
        'url': 'https://occom.com.au/opticomm-plans/',
        'network_type': 'Opticomm',
    },
    'nbn_fttp': {
        'url': 'https://occom.com.au/nbn-fttp-upgrade/',
        'network_type': 'NBN FTTP',
    },
    'supa': {
        'url': 'https://occom.com.au/supa-network-plans/',
        'network_type': 'Supa',
    },
    'redtrain': {
        'url': 'https://occom.com.au/redtrain-plans/',
        'network_type': 'Redtrain',
    },
    'community_fibre': {
        'url': 'https://occom.com.au/community-fibre-plans/',
        'network_type': 'Community Fibre',
    },
}


def scrape_occom_plans() -> Dict[str, List[Dict[str, Any]]]:
    """
    Scrape all Occom plan pages. Returns a dict keyed by network type.
    
    Returns:
        Dict mapping network key to list of plan dicts
    """
    log_info("Starting Occom multi-page scraper", provider="occom")
    
    all_plans = {}
    
    with sync_playwright() as p:
        browser = create_stealth_browser(p)
        
        for page_key, page_config in OCCOM_PLAN_PAGES.items():
            url = page_config['url']
            network_type = page_config['network_type']
            
            log_info(f"Scraping {network_type} plans from {url}", provider="occom")
            
            plans = scrape_page(browser, url, network_type)
            all_plans[page_key] = plans
            
            if plans:
                log_success(f"Scraped {len(plans)} {network_type} plans", provider="occom")
            else:
                log_error(f"No plans found for {network_type}", provider="occom")
        
        browser.close()
    
    total = sum(len(v) for v in all_plans.values())
    log_success(f"Total Occom plans scraped: {total} across {len(all_plans)} pages", provider="occom")
    
    return all_plans


def scrape_page(browser, url: str, network_type: str) -> List[Dict[str, Any]]:
    """
    Scrape plans from a single Occom page.
    
    Args:
        browser: Playwright browser instance
        url: Page URL
        network_type: Network label (NBN, Opticomm, etc.)
    
    Returns:
        List of plan dicts
    """
    plans = []
    page = None
    
    try:
        from utils.stealth import create_stealth_page
        page = create_stealth_page(browser)
        
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        
        # Wait for plan cards
        page.wait_for_selector('.plan-card', timeout=15000, state='attached')
        
        # Try newPlanDesign first, fall back to any .plan-card
        cards = page.query_selector_all('.plan-card.newPlanDesign')
        if not cards:
            cards = page.query_selector_all('.plan-card')
        
        log_info(f"Found {len(cards)} cards on {url}", provider="occom")
        
        seen = set()
        for card in cards:
            plan = extract_plan_from_card(card, network_type, url)
            if plan:
                key = f"{plan['plan_name']}_{plan['price']}"
                if key not in seen:
                    seen.add(key)
                    plans.append(plan)
    
    except Exception as e:
        log_error(f"Error scraping {url}: {str(e)}", provider="occom")
    finally:
        if page:
            page.close()
    
    return plans


def extract_plan_from_card(card, network_type: str, source_url: str) -> Dict[str, Any]:
    """
    Extract plan data from an Occom .plan-card element.
    
    Structure:
        .plans-name         -> plan name (e.g. "Hyper")
        .plan-speed         -> tier (e.g. "(nbn2000)")
        .amount-price       -> download/upload speeds (two elements)
        .prices-regulars    -> promo price
        strike              -> original price
        .speeds             -> promo details text
    """
    try:
        # Plan name
        name_elem = card.query_selector('.plans-name')
        plan_name = name_elem.inner_text().strip() if name_elem else ''
        
        # Tier (e.g. "(nbn2000)")
        tier_elem = card.query_selector('.plan-speed')
        tier_text = tier_elem.inner_text().strip() if tier_elem else ''
        
        # Download and upload speeds from .amount-price elements
        speed_elems = card.query_selector_all('.amount-price')
        download_speed = 0
        upload_speed = 0
        if len(speed_elems) >= 1:
            download_speed = extract_speed(speed_elems[0].inner_text())
        if len(speed_elems) >= 2:
            upload_speed = extract_speed(speed_elems[1].inner_text())
        
        # Promo price from .prices-regulars
        promo_elem = card.query_selector('.prices-regulars')
        promo_price = 0
        if promo_elem:
            promo_price = extract_price(promo_elem.inner_text())
        
        # Original price from strike element
        strike_elem = card.query_selector('.price strike')
        original_price = 0
        if strike_elem:
            original_price = extract_price(strike_elem.inner_text())
        
        # Promo details text
        promo_details_elem = card.query_selector('.speeds')
        promo_period = ''
        if promo_details_elem:
            promo_text = promo_details_elem.inner_text().strip()
            period_match = re.search(r'For (\d+) months', promo_text)
            if period_match:
                promo_period = f"{period_match.group(1)} months"
        
        # Use original price as the standard price, promo as discount
        price = original_price if original_price > 0 else promo_price
        
        # Combine name with tier
        full_name = f"{plan_name} {tier_text}".strip()
        
        if not plan_name or price <= 0:
            return None
        
        return {
            'provider_id': config.PROVIDERS.get('occom', {}).get('id', 5),
            'plan_name': full_name,
            'network_type': network_type,
            'speed': download_speed,
            'download_speed': download_speed,
            'upload_speed': upload_speed,
            'price': price,
            'promo_price': promo_price if promo_price != price else None,
            'promo_period': promo_period,
            'contract': 'No Contract',
            'source_url': source_url
        }
        
    except Exception as e:
        log_error(f"Error extracting plan from card: {str(e)}", provider="occom")
        return None


def extract_speed(text: str) -> int:
    """Extract numeric speed value from text like '2000 Mbps'."""
    match = re.search(r'(\d+)', text)
    return int(match.group(1)) if match else 0


def extract_price(text: str) -> float:
    """Extract price value from text like '$165/mth'."""
    match = re.search(r'\$?([\d.]+)', text)
    return float(match.group(1)) if match else 0.0
