"""Test script for Leaptel scraper."""

from providers.leaptel import scrape_leaptel_plans
from utils.logger import log_info, log_success
import json


def main():
    """Run the Leaptel scraper and display results."""
    log_info("Starting Leaptel scraper test...", provider="leaptel")
    
    plans = scrape_leaptel_plans()
    
    log_success(f"Scraping completed. Found {len(plans)} plans.", provider="leaptel")
    
    # Pretty print the results
    print("\n" + "="*80)
    print("LEAPTEL PLANS")
    print("="*80 + "\n")
    
    for i, plan in enumerate(plans, 1):
        print(f"\n{i}. {plan['plan_name']} ({plan['network_type']})")
        print(f"   Download: {plan['download_speed']}Mbps | Upload: {plan['upload_speed']}Mbps")
        print(f"   Price: ${plan['price']}/month", end="")
        if plan.get('promo_price'):
            print(f" (Promo: ${plan['promo_price']}/month for {plan['promo_period']})", end="")
        print()
        if plan.get('typical_evening_speed'):
            print(f"   Typical Evening Speed: {plan['typical_evening_speed']}")
        if plan.get('total_saving'):
            print(f"   Total Saving: ${plan['total_saving']}")
    
    # Save to JSON
    output_file = "output/leaptel_plans.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(plans, f, indent=2, ensure_ascii=False)
    
    print(f"\n\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
