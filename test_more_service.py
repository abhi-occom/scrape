import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper_service import scrape_provider, save_output

# Scrape More provider
result = scrape_provider('more')

print(f"Success: {result['success']}")
print(f"Total plans: {result['total_plans']}")
print(f"Error: {result.get('error', 'None')}")

if result['success']:
    # Save output
    files = save_output('more', result['plans'])
    print(f"Saved files: {files}")
    
    # Print plans
    for plan in result['plans']:
        promo_info = f" (promo: ${plan.get('promo_price')}/{plan.get('promo_period')})" if plan.get('promo_price') else ""
        print(f"  {plan['plan_name']}: {plan['download_speed']}/{plan['upload_speed']} Mbps - ${plan['price']}/mth{promo_info}")