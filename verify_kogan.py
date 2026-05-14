"""Verify the freshly scraped Kogan JSON output."""
import json, sys, os

path = os.path.join(os.path.dirname(__file__), 'output', 'scrape_isp_kogan', 'json', 'kogan_plans.json')
with open(path, encoding='utf-8') as f:
    data = json.load(f)

print(f"scraped_at  : {data['scraped_at']}")
print(f"source_url  : {data['source_url']}")
print(f"total_plans : {data['total_plans']}")
print()

for p in data['plans']:
    print(f"[{p['index']}] {p['name']:<12}  {p['network_type']:<4}  {p['plan_duration']:<12}  {p['speed']:<10}")
    print(f"     promo=${p['price_monthly']:.2f}/mth  full=${p['price_full']:.2f}/mth  total=${p['total_cost']:.2f}")
    print(f"     speed_down={p['speed_down']} Mbps  speed_up={p['speed_up']} Mbps")
    print(f"     badge   : {p['speed_badge']!r}")
    print(f"     evening : {p['speed_evening']!r}")
    print(f"     features: {p['features']}")
    print(f"     total_note: {p['total_note']!r}")
    print()
