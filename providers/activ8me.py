
# scrape/providers/activ8me.py
"""Scrape internet plans from activ8me.net.au"""

import os
import sys
from typing import List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright
from utils.validator import validate_plans

# Provider configuration
PROVIDER_ID = 11
PROVIDER_NAME = "activ8me"
BASE_URL = "https://www.activ8me.net.au"
PLAN_URL = "https://www.activ8me.net.au/internet/nbn-fibre-fttp-hfc"

# Standardized output schema
STANDARDIZED_FIELDS = {
    "name": str,
    "speed_down": int,
    "speed_up": int,
    "regular_price": float,
    "promo_price_val": float,
    "promo_period": str,
    "network_type": str
}

def scrape_activ8me_plans() -> List[Dict[str, Any]]:
    """
    Scrape internet plans from activ8me.net.au
    
    Returns:
        List of plan dictionaries with standardized frontend-compatible fields
    """
    plans = []
    
    # Create stealth browser and navigate to plans page
    try:
        with sync_playwright() as p:
            browser = create_stealth_browser(p)
            page = create_stealth_page(browser)
            
            # Navigate to the plans page
            page.goto(PLAN_URL, timeout=30000, wait_until='domcontentloaded')
            
            # Wait for content to load
            page.wait_for_timeout(8000)
            
            # Check if we can find plan cards
            # First try the main plan card selectors
            plan_cards = page.query_selector_all('.plan-card') or page.query_selector_all('.plan-item')
            
            # If no plan cards found, check for alternative containers
            if not plan_cards:
                # Look for divs with "plan" in class name
                plan_cards = page.query_selector_all('div[class*="plan"]') or page.query_selector_all('div[class*="internet"]')
            
            # If still no cards found, indicate the issue
            if not plan_cards:
                print("⚠️ No plan cards found on the page. The page appears to contain general information about NBN Fibre, not actual plan listings.")
                print("The page has only 'Special Offer!' ribbons without actual plan details like names, speeds, or prices.")
                return []
            
            print(f"Found {len(plan_cards)} potential plan card elements")
            
            # Extract data from each plan card
            for i, card in enumerate(plan_cards):
                plan_data = {}
                
                # Extract plan name - check for h3 elements with plan-name or similar
                name_element = card.query_selector('h3.plan-name') or card.query_selector('h3') or card.query_selector('h2')
                plan_name = name_element.text_content() if name_element else ""
                
                # Extract speed details
                speed_element = card.query_selector('span.speed') or card.query_selector('span') or card.query_selector('div span')
                speed_text = speed_element.text_content() if speed_element else ""
                
                # Parse speed from text (e.g., "25 Mbps" -> 25)
                speed_parts = speed_text.split()
                speed_mbps = None
                if len(speed_parts) > 0 and speed_parts[-1].endswith('Mbps'):
                    try:
                        speed_mbps = int(speed_parts[-2])
                    except ValueError:
                        pass
                
                # Extract price details
                price_element = card.query_selector('span.price') or card.query_selector('span') or card.query_selector('div span')
                price_text = price_element.text_content() if price_element else ""
                
                # Only parse price if it's a valid price string
                price_val = None
                if price_text and price_text.strip():
                    # Check if it contains a dollar sign and digits
                    if price_text.strip().startswith('$'):
                        price_text = price_text.strip()[1:]
                    price_text = price_text.strip()
                    # Try to convert to float - skip if it's not a valid number
                    try:
                        price_val = float(price_text)
                    except ValueError:
                        price_val = None
                
                # Extract promo details
                promo_element = card.query_selector('span.promo') or card.query_selector('span') or card.query_selector('div span')
                promo_text = promo_element.text_content() if promo_element else ""
                promo_price_val = None
                promo_period = None
                
                # Only parse promo if it's a valid promo string
                if promo_text and promo_text.strip():
                    # Check if it contains "Promo" and digits
                    if promo_text.strip().startswith('Promo'):
                        promo_text = promo_text.strip()[6:]
                    promo_text = promo_text.strip()
                    # Try to convert to float - skip if it's not a valid number
                    try:
                        promo_price_val = float(promo_text)
                    except ValueError:
                        promo_price_val = None
                
                # Extract network type
                network_type = "NBN"  # Default for this URL
                
                # Build standardized plan dictionary
                plan_data = {
                    "name": plan_name.strip(),
                    "speed_down": speed_mbps,
                    "speed_up": 0,  # No upload speed specified in this page
                    "regular_price": price_val,
                    "promo_price_val": promo_price_val,
                    "promo_period": promo_period,
                    "network_type": network_type
                }
                
                # Validate and clean data
                validated_plan = validate_plans([plan_data])[0]
                if validated_plan:
                    plans.append(validated_plan)
            
            browser.close()
            
    except Exception as e:
        print(f"❌ Error during scraping: {str(e)}")
        # Log error to file if needed
        with open("output/logs.txt", "a") as f:
            f.write(f"Error scraping activ8me: {str(e)}\n")
    
    return plans

# Entry point for direct execution
if __name__ == "__main__":
    print("🔍 Starting activ8me plan scraper...")
    plans = scrape_activ8me_plans()
    print(f"✅ Scraped {len(plans)} plans")
    for plan in plans:
        print(f"  {plan['name']}: {plan['speed_down']} Mbps down, ${plan['regular_price']} regular price")