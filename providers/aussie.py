"""
Aussie Broadband ISP plan scraper.
Uses API-first approach, falls back to Playwright if needed.
"""

import requests
from typing import List, Dict, Any
from playwright.sync_api import sync_playwright
import config
from utils.logger import log_info, log_error, log_success
from utils.stealth import create_stealth_browser, create_stealth_page


# Aussie Broadband API endpoint (example - update with actual API if available)
AUSSIE_API_URL = "https://www.aussiebroadband.com.au/api/plans"
AUSSIE_WEBSITE_URL = "https://www.aussiebroadband.com.au/broadband/nbn/"


def scrape_aussie_plans() -> List[Dict[str, Any]]:
    """
    Scrape Aussie Broadband ISP plans.
    First attempts API, falls back to Playwright scraping.
    
    Returns:
        List of plan dictionaries
    """
    log_info("Starting Aussie Broadband scraper", provider="aussie")
    
    # Try API first
    try:
        plans = scrape_via_api()
        if plans:
            log_success(f"Successfully scraped {len(plans)} plans via API", provider="aussie")
            return plans
    except Exception as e:
        log_info("API scraping failed, falling back to Playwright", provider="aussie", 
                data={'error': str(e)})
    
    # Fallback to Playwright
    try:
        plans = scrape_via_playwright()
        if plans:
            log_success(f"Successfully scraped {len(plans)} plans via Playwright", provider="aussie")
            return plans
    except Exception as e:
        log_error(f"Playwright scraping failed: {str(e)}", provider="aussie")
    
    log_error("All scraping methods failed for Aussie Broadband", provider="aussie")
    return []


def scrape_via_api() -> List[Dict[str, Any]]:
    """
    Scrape Aussie Broadband plans using their API.
    
    Returns:
        List of plan dictionaries
    """
    plans = []
    
    try:
        response = requests.get(AUSSIE_API_URL, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Parse API response (adjust based on actual API structure)
        if isinstance(data, dict) and 'plans' in data:
            for plan_data in data['plans']:
                plan = parse_aussie_api_plan(plan_data)
                if plan:
                    plans.append(plan)
        
    except requests.exceptions.RequestException as e:
        log_error(f"API request failed: {str(e)}", provider="aussie")
    except Exception as e:
        log_error(f"API parsing failed: {str(e)}", provider="aussie")
    
    return plans


def parse_aussie_api_plan(plan_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse an Aussie Broadband API plan response into standardized format.
    
    Args:
        plan_data: Raw plan data from API
    
    Returns:
        Standardized plan dictionary
    """
    try:
        return {
            'provider_id': config.PROVIDERS['aussie']['id'],
            'plan_name': plan_data.get('name', ''),
            'network_type': plan_data.get('networkType', 'NBN'),
            'speed': int(plan_data.get('speed', 0)),
            'download_speed': int(plan_data.get('downloadSpeed', plan_data.get('speed', 0))),
            'upload_speed': int(plan_data.get('uploadSpeed', 0)),
            'price': float(plan_data.get('monthlyPrice', 0)),
            'promo_price': float(plan_data.get('promoPrice', 0)) if plan_data.get('promoPrice') else None,
            'promo_period': plan_data.get('promoPeriod', ''),
            'contract': plan_data.get('contractTerm', 'No Contract'),
            'source_url': AUSSIE_WEBSITE_URL
        }
    except Exception as e:
        log_error(f"Failed to parse Aussie Broadband API plan: {str(e)}", provider="aussie")
        return None


def scrape_via_playwright() -> List[Dict[str, Any]]:
    """
    Scrape Aussie Broadband plans using Playwright (for dynamic websites).
    
    Returns:
        List of plan dictionaries
    """
    plans = []
    
    with sync_playwright() as p:
        browser = create_stealth_browser(p)
        page = create_stealth_page(browser)
        
        try:
            # Navigate to Aussie Broadband NBN plans page
            page.goto(AUSSIE_WEBSITE_URL, timeout=config.PLAYWRIGHT_TIMEOUT, wait_until="domcontentloaded")
            
            # Wait for page to load
            page.wait_for_timeout(config.PLAYWRIGHT_WAIT_TIME)
            
            # Wait for plan cards to appear
            page.wait_for_selector('.plan-card, .nbn-plan, [data-plan]', 
                                 timeout=10000, state='visible')
            
            # Find all plan cards
            plan_cards = page.query_selector_all('.plan-card, .nbn-plan, [data-plan]')
            
            for card in plan_cards:
                try:
                    plan = extract_plan_from_card(page, card)
                    if plan:
                        plans.append(plan)
                except Exception as e:
                    log_error(f"Failed to extract plan from card: {str(e)}", provider="aussie")
            
        except Exception as e:
            log_error(f"Playwright scraping error: {str(e)}", provider="aussie")
        finally:
            browser.close()
    
    return plans


def extract_plan_from_card(page, card) -> Dict[str, Any]:
    """
    Extract plan data from a single plan card element.
    
    Args:
        page: Playwright page object
        card: Playwright element handle for plan card
    
    Returns:
        Standardized plan dictionary
    """
    try:
        # Extract plan name
        plan_name_elem = card.query_selector('.plan-name, h3, .plan-title, .title')
        plan_name = plan_name_elem.inner_text().strip() if plan_name_elem else ''
        
        # Extract speed
        speed_elem = card.query_selector('.plan-speed, .speed, .typical-speed')
        speed_text = speed_elem.inner_text().strip() if speed_elem else '0'
        speed = extract_speed_from_text(speed_text)
        
        # Extract price
        price_elem = card.query_selector('.plan-price, .price, .monthly-cost')
        price_text = price_elem.inner_text().strip() if price_elem else '0'
        price = extract_price_from_text(price_text)
        
        # Extract network type
        network_elem = card.query_selector('.network-type, .technology, .connection-type')
        network_type = network_elem.inner_text().strip() if network_elem else 'NBN'
        
        # Extract upload speed
        upload_elem = card.query_selector('.upload-speed, .typical-upload')
        upload_text = upload_elem.inner_text().strip() if upload_elem else '0'
        upload_speed = extract_speed_from_text(upload_text)
        
        # Extract contract term
        contract_elem = card.query_selector('.contract-term, .no-lock')
        contract = contract_elem.inner_text().strip() if contract_elem else 'No Contract'
        
        # Check for promo
        promo_elem = card.query_selector('.promo, .special, .offer')
        promo_price = None
        promo_period = None
        if promo_elem:
            promo_text = promo_elem.inner_text().strip()
            promo_price = extract_price_from_text(promo_text)
            # Try to extract promo period
            import re
            period_match = re.search(r'(\d+)\s*(months?|mths?)', promo_text, re.IGNORECASE)
            if period_match:
                promo_period = f"{period_match.group(1)} months"
        
        return {
            'provider_id': config.PROVIDERS['aussie']['id'],
            'plan_name': plan_name,
            'network_type': network_type,
            'speed': speed,
            'download_speed': speed,
            'upload_speed': upload_speed,
            'price': price,
            'promo_price': promo_price,
            'promo_period': promo_period,
            'contract': contract,
            'source_url': AUSSIE_WEBSITE_URL
        }
        
    except Exception as e:
        log_error(f"Error extracting plan from card: {str(e)}", provider="aussie")
        return None


def extract_speed_from_text(text: str) -> int:
    """
    Extract speed value from text.
    
    Args:
        text: Text containing speed information
    
    Returns:
        Speed as integer
    """
    import re
    match = re.search(r'(\d+)', text)
    return int(match.group(1)) if match else 0


def extract_price_from_text(text: str) -> float:
    """
    Extract price value from text.
    
    Args:
        text: Text containing price information
    
    Returns:
        Price as float
    """
    import re
    # Remove currency symbols and extract number
    match = re.search(r'\$?([\d.]+)', text)
    return float(match.group(1)) if match else 0.0
