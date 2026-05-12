"""Test script for the iiNet scraper."""
import json
from providers.iinet import scrape_iinet_plans

results = scrape_iinet_plans()
print()
for page_key, plans in results.items():
    print(f'=== {page_key}: {len(plans)} plans ===')
    for p in plans:
        promo_str = ''
        if p['promo_price']:
            promo_str = f' (promo={p["promo_price"]}/{p["promo_period"]})'
        print(
            f'  {p["plan_name"]:26s} {p["network_type"]:22s} '
            f'DL={p["download_speed"]:4d} UL={p["upload_speed"]:3d} '
            f'price={p["price"]:.2f}{promo_str}'
        )
    print()

total = sum(len(v) for v in results.values())
print(f'Total plans: {total}')
print()
print('=== Full JSON of first fibre plan ===')
if results.get('fibre'):
    print(json.dumps(results['fibre'][0], indent=2))
