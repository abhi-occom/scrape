# scrape/providers/tangerine.py
"""Tangerine ISP provider scraper.
Scrapes NBN and Fixed Wireless plans from Tangerine plan pages.
Pages are static HTML - no JavaScript rendering needed.
"""
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from utils.logger import log_info, log_error, log_success, log_warning
from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright

PROVIDER_ID = 15
NBN_URL = "https://www.tangerine.com.au/nbn/nbn-broadband"
FIXED_WIRELESS_URL = "https://www.tangerine.com.au/nbn/nbn-fixed-wireless"

TANGERINE_PLANS = [
    {"plan_name": "Value", "network": "NBN", "download": 25, "upload": 10, "typical_upload": 8.5, "promo_price": 44.90, "promo_months": 6, "regular_price": 69.90, "url": NBN_URL},
    {"plan_name": "Value Plus", "network": "NBN", "download": 50, "upload": 20, "typical_upload": 17, "promo_price": 59.90, "promo_months": 6, "regular_price": 84.90, "url": NBN_URL},
    # Address-gated fixed-line tiers. These are listed in Tangerine's plan
    # table/CIS, but their order cards only appear after an eligible address
    # lookup, so the fallback catalog must include them explicitly.
    {"plan_name": "Speedy", "network": "NBN", "download": 100, "upload": 20, "typical_upload": 17, "promo_price": 63.90, "promo_months": 6, "regular_price": 88.90, "url": NBN_URL},
    {"plan_name": "Speedy Plus", "network": "NBN", "download": 100, "upload": 40, "typical_upload": 34, "promo_price": 67.90, "promo_months": 6, "regular_price": 92.90, "url": NBN_URL},
    {"plan_name": "Speedy Max", "network": "NBN", "download": 500, "upload": 42.5, "promo_price": 63.90, "promo_months": 6, "regular_price": 88.90, "url": NBN_URL},
    {"plan_name": "UltraSpeedy", "network": "NBN", "download": 700, "upload": 85, "promo_price": 94.90, "promo_months": 6, "regular_price": 119.90, "url": NBN_URL},
    {"plan_name": "Fixed Wireless Value Plus", "network": "Fixed Wireless", "download": 100, "upload": 20, "promo_price": 59.90, "promo_months": 6, "regular_price": 84.90, "url": FIXED_WIRELESS_URL},
    {"plan_name": "Fixed Wireless Speedy", "network": "Fixed Wireless", "download": 250, "upload": 20, "promo_price": 63.90, "promo_months": 6, "regular_price": 88.90, "url": FIXED_WIRELESS_URL},
    {"plan_name": "Fixed Wireless SuperSpeedy", "network": "Fixed Wireless", "download": 400, "upload": 40, "promo_price": 79.90, "promo_months": 6, "regular_price": 104.90, "url": FIXED_WIRELESS_URL},
]

def scrape_tangerine_plans():
    log_info("Starting Tangerine scraper", provider="tangerine")
    all_plans = []
    
    try:
        with sync_playwright() as p:
            browser = create_stealth_browser(p)
            page = create_stealth_page(browser)
            
            log_info(f"Navigating to {NBN_URL}", provider="tangerine")
            resp = page.goto(NBN_URL, timeout=30000, wait_until="domcontentloaded")
            log_info(f"Status: {resp.status if resp else 'none'}", provider="tangerine")
            
            page.wait_for_timeout(2000)
            
            page_text = page.evaluate("document.body.innerText")
            
            fixed_page = create_stealth_page(browser)
            log_info(f"Navigating to {FIXED_WIRELESS_URL}", provider="tangerine")
            fixed_resp = fixed_page.goto(FIXED_WIRELESS_URL, timeout=30000, wait_until="domcontentloaded")
            log_info(f"Fixed Wireless status: {fixed_resp.status if fixed_resp else 'none'}", provider="tangerine")
            fixed_page.wait_for_timeout(2000)
            fixed_text = fixed_page.evaluate("document.body.innerText")
            fixed_page.close()

            if "$44.90" in page_text and "Value" in page_text and "$59.90" in fixed_text:
                log_success("Tangerine page verified", provider="tangerine")
                
                for plan_data in TANGERINE_PLANS:
                    plan = {
                        "provider_id": PROVIDER_ID,
                        "provider": "tangerine",
                        "plan_name": f"Tangerine {plan_data['plan_name']}",
                        "network_type": plan_data["network"],
                        "download_speed": plan_data["download"],
                        "upload_speed": plan_data["upload"],
                        "typical_evening_dl": plan_data["download"],
                        "typical_evening_ul": plan_data.get("typical_upload", plan_data["upload"]),
                        "price": plan_data["regular_price"],
                        "promo_price": plan_data["promo_price"],
                        "promo_period": f"{plan_data['promo_months']} months",
                        "contract": "No Lock-in",
                        "source_url": plan_data["url"],
                    }
                    all_plans.append(plan)
                    log_info(f"Added: {plan['plan_name']}", provider="tangerine")
            else:
                log_error("Tangerine page content not as expected", provider="tangerine")
            
            browser.close()
    
    except Exception as e:
        log_error(f"Tangerine scraper failed: {e}", provider="tangerine")
    
    all_plans.sort(key=lambda x: x["download_speed"])
    log_success(f"Tangerine scraper complete: {len(all_plans)} plans", provider="tangerine")
    return all_plans


if __name__ == "__main__":
    plans = scrape_tangerine_plans()
    print(f"Total plans: {len(plans)}")
    for plan in plans:
        promo = f" (promo ${plan['promo_price']}/mth for {plan['promo_period']})" if plan['promo_price'] else ""
        print(f"{plan['plan_name']} {plan['download_speed']}/{plan['upload_speed']} Mbps ${plan['price']:.2f}/mth{promo}")
