"""
Origin Energy ISP plan scraper.
Scrapes NBN and Opticomm plans from /internet/plans/ page.
Uses tab navigation to access different network types.
Uses stealth browser to avoid detection.
"""

import re
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from utils.logger import log_info, log_error, log_success, log_warning
from utils.stealth import create_stealth_browser, create_stealth_page


ORIGIN_URL = 'https://www.originenergy.com.au/internet/plans/'

def scrape_origin_plans() -> Dict[str, List[Dict[str, Any]]]:
    """
    Main scraper function for Origin Energy plans.
    Scrapes both NBN and Opticomm plans by clicking through tabs.
    Returns dict of {network_type: [plans]}.
    """
    all_plans = {
        'nbn': [],
        'opticomm': []
    }
    
    with sync_playwright() as p:
        browser = create_stealth_browser(p)
        page = create_stealth_page(browser)
        
        try:
            log_info(f"Navigating to {ORIGIN_URL}", provider="origin")
            resp = page.goto(ORIGIN_URL, timeout=30000, wait_until='domcontentloaded')
            log_info(f"Status: {resp.status if resp else 'none'}", provider="origin")
            
            # Wait for page to fully load
            page.wait_for_timeout(10000)
            
            # Find all tabs
            tabs = page.query_selector_all('[role="tab"]')
            log_info(f"Found {len(tabs)} tabs", provider="origin")
            
            # Process each tab
            seen_plans = set()
            
            for i, tab in enumerate(tabs):
                try:
                    tab_text = tab.inner_text().strip()
                    log_info(f"Clicking tab: {tab_text}", provider="origin")
                    
                    # Determine network type from tab text
                    network_type = 'Opticomm' if 'opticomm' in tab_text.lower() else 'NBN'
                    network_key = 'opticomm' if 'opticomm' in tab_text.lower() else 'nbn'
                    
                    # Click the tab
                    tab.click()
                    page.wait_for_timeout(3000)
                    
                    # Find plan cards
                    cards = page.query_selector_all('div[class*="PlanCard"]')
                    log_info(f"Found {len(cards)} plan cards in {tab_text} tab", provider="origin")
                    
                    for j, card in enumerate(cards):
                        try:
                            plan = extract_plan_from_card(card, j, network_type)
                            if plan:
                                # Use plan name as deduplication key
                                plan_key = f"{plan['plan_name']}_{plan['price']}"
                                
                                if plan_key not in seen_plans:
                                    seen_plans.add(plan_key)
                                    all_plans[network_key].append(plan)
                                    log_success(f"Extracted plan: {plan['plan_name']}", provider="origin")
                        except Exception as e:
                            log_error(f"Error extracting plan {j} from tab {tab_text}: {e}", provider="origin")
                            continue
                    
                except Exception as e:
                    log_error(f"Error processing tab {i}: {e}", provider="origin")
                    continue
            
            total = sum(len(v) for v in all_plans.values())
            log_success(f"Total Origin plans extracted: {total} (NBN: {len(all_plans['nbn'])}, Opticomm: {len(all_plans['opticomm'])})", provider="origin")
            
        except Exception as e:
            log_error(f"Error scraping Origin plans: {e}", provider="origin")
        finally:
            browser.close()
    
    return all_plans

def extract_plan_from_card(card, index: int, network_type: str) -> Optional[Dict[str, Any]]:
    """
    Extract plan details from a single plan card.
    Based on investigation findings.
    
    Args:
        card: Playwright element handle
        index: Card index for logging
        network_type: 'NBN' or 'Opticomm'
    """
    try:
        full_text = card.inner_text()
        lines = full_text.split('\n')
        
        # Extract plan name
        # Look for line with network type and speed info (mbps or number/number pattern)
        plan_name = ''
        network_keywords = ['nbn', 'opticomm']
        
        for line in lines:
            line = line.strip()
            if line and any(kw in line.lower() for kw in network_keywords):
                # Check if it has mbps pattern or number/number pattern
                if 'mbps' in line.lower() or re.search(r'\d+/\d+', line):
                    plan_name = line
                    break
        
        if not plan_name:
            log_warning(f"No plan name found in card {index}", provider="origin")
            return None
        
        # Extract all prices from text
        all_prices = re.findall(r'\$(\d+\.?\d*)', full_text)
        all_prices = [float(p) for p in all_prices if float(p) > 0]
        
        # Determine regular and promo prices
        regular_price = 0
        promo_price = None
        promo_period = ''
        
        if len(all_prices) >= 2:
            # If multiple prices, first is usually promo, second is regular
            promo_price = all_prices[0]
            regular_price = all_prices[1]
            
            # Look for promo period
            period_match = re.search(r'(\d+)\s*months?', full_text, re.IGNORECASE)
            if period_match:
                promo_period = f"{period_match.group(1)} months"
        elif len(all_prices) == 1:
            regular_price = all_prices[0]
        
        if regular_price <= 0:
            log_warning(f"No valid price found in card {index}", provider="origin")
            return None
        
        # Extract download speed
        download_speed = 0
        match = re.search(r'(\d+)\s*mbps\s*download', full_text, re.IGNORECASE)
        if match:
            download_speed = int(match.group(1))
        
        # Extract upload speed
        upload_speed = 0
        match = re.search(r'(\d+\.?\d*)\s*mbps\s*upload', full_text, re.IGNORECASE)
        if match:
            upload_speed = int(float(match.group(1)))
        
        # Extract typical evening speed
        typical_evening_dl = 0
        typical_evening_ul = 0
        match = re.search(r'typical\s+evening\s+speed[:\s]+(\d+)/(\d+)', full_text, re.IGNORECASE)
        if match:
            typical_evening_dl = int(match.group(1))
            typical_evening_ul = int(match.group(2))
        
        # Check for unlimited data
        data_allowance = 'Unlimited'
        data_match = re.search(r'(\d+)\s*GB', full_text, re.IGNORECASE)
        if data_match:
            data_allowance = f"{data_match.group(1)} GB"
        
        # Contract type
        contract = 'No Contract'
        if 'contract' in full_text.lower():
            contract_match = re.search(r'(\d+)\s*month\s*contract', full_text, re.IGNORECASE)
            if contract_match:
                contract = f"{contract_match.group(1)} month contract"
        
        return {
            'provider_id': config.PROVIDERS['origin']['id'],
            'plan_name': plan_name,
            'network_type': network_type,
            'download_speed': download_speed,
            'upload_speed': upload_speed,
            'typical_evening_dl': typical_evening_dl,
            'typical_evening_ul': typical_evening_ul,
            'data_allowance': data_allowance,
            'price': regular_price,
            'promo_price': promo_price,
            'promo_period': promo_period,
            'contract': contract,
            'source_url': ORIGIN_URL,
        }
        
    except Exception as e:
        log_error(f"Error parsing card {index}: {e}", provider="origin")
        return None

def scrape_via_playwright() -> List[Dict[str, Any]]:
    """
    Legacy interface for backward compatibility.
    Flattens all plans into a single list.
    """
    results = scrape_origin_plans()
    flat = []
    for plans in results.values():
        flat.extend(plans)
    return flat


if __name__ == "__main__":
    """
    Test the scraper independently.
    """
    all_plans = scrape_origin_plans()
    
    print(f"\n{'='*60}")
    print(f"Origin Energy Plans Extracted")
    print(f"{'='*60}\n")
    
    for network_key, plans in all_plans.items():
        print(f"\n{'─'*60}")
        print(f"{network_key.upper()} Plans: {len(plans)}")
        print(f"{'─'*60}\n")
        
        for i, plan in enumerate(plans, 1):
            print(f"Plan {i}: {plan['plan_name']}")
            print(f"  Network: {plan['network_type']}")
            print(f"  Speed: {plan['download_speed']}/{plan['upload_speed']} Mbps")
            if plan['typical_evening_dl']:
                print(f"  Typical Evening: {plan['typical_evening_dl']}/{plan['typical_evening_ul']} Mbps")
            print(f"  Data: {plan['data_allowance']}")
            print(f"  Price: ${plan['price']}/month")
            if plan['promo_price']:
                print(f"  Promo Price: ${plan['promo_price']}/month ({plan['promo_period']})")
            print(f"  Contract: {plan['contract']}")
            print("-" * 60)
    
    total = sum(len(v) for v in all_plans.values())
    print(f"\n{'='*60}")
    print(f"Total Plans: {total}")
    print(f"{'='*60}")