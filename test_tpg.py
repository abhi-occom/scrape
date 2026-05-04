"""Test TPG scraper and save output."""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from providers.tpg import scrape_tpg_plans
from scraper_service import save_output

print("Starting TPG scraper...")
plans = scrape_tpg_plans()

print("\n=== Results ===")
total = 0
for page_key, page_plans in plans.items():
    count = len(page_plans)
    total += count
    print(f"\n{page_key}: {count} plans")
    for p in page_plans:
        promo = f" (promo ${p['promo_price']} for {p['promo_period']})" if p.get('promo_price') else ""
        print(f"  {p['plan_name']}: {p['download_speed']}/{p['upload_speed']}Mbps ${p['price']}/mth{promo}")

print(f"\nTotal: {total} plans")

# Save output
print("\nSaving output files...")
files = save_output('tpg', plans)
print(f"JSON files: {files['json']}")
print(f"CSV files: {files['csv']}")

# Also update all_plans.csv and all_plans.json
from scraper_service import save_provider_json, save_provider_csv, BASE_OUTPUT_DIR
import csv

# Flatten all plans for combined output
all_tpg = []
for page_plans in plans.values():
    all_tpg.extend(page_plans)

# Read existing all_plans.csv, remove old tpg entries, add new ones
all_csv_path = os.path.join(BASE_OUTPUT_DIR, 'all_plans.csv')
existing_plans = []
if os.path.exists(all_csv_path):
    with open(all_csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('provider', '').lower() != 'tpg':
                existing_plans.append(row)

# Add TPG plans in CSV format
CSV_COLUMNS = [
    'provider', 'network_type', 'plan_name', 'download_speed', 'upload_speed',
    'price', 'promo_price', 'promo_period', 'contract',
    'typical_evening_dl', 'typical_evening_ul', 'source_url'
]

for p in all_tpg:
    row = {
        'provider': 'tpg',
        'network_type': p.get('network_type', ''),
        'plan_name': p.get('plan_name', ''),
        'download_speed': p.get('download_speed', ''),
        'upload_speed': p.get('upload_speed', ''),
        'price': p.get('price', ''),
        'promo_price': p.get('promo_price', '') if p.get('promo_price') is not None else '',
        'promo_period': p.get('promo_period', '') or '',
        'contract': p.get('contract', 'No Lock-in'),
        'typical_evening_dl': p.get('typical_evening_dl', ''),
        'typical_evening_ul': p.get('typical_evening_ul', ''),
        'source_url': p.get('source_url', ''),
    }
    existing_plans.append(row)

with open(all_csv_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction='ignore')
    writer.writeheader()
    for row in existing_plans:
        writer.writerow(row)

print(f"\nUpdated {all_csv_path} with {len(all_tpg)} TPG plans (total rows: {len(existing_plans)})")

# Update all_plans.json
all_json_path = os.path.join(BASE_OUTPUT_DIR, 'all_plans.json')
from datetime import datetime
all_json_plans = []

# Read existing non-TPG plans
if os.path.exists(all_json_path):
    with open(all_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        for p in data.get('plans', []):
            if p.get('provider', '').lower() != 'tpg':
                all_json_plans.append(p)

# Add TPG plans
for p in all_tpg:
    all_json_plans.append({
        **p,
        'speed': p['download_speed'],
        'provider': 'tpg',
    })

all_json = {
    'scraped_at': datetime.now().strftime('%Y-%m-%d_%H-%M-%S'),
    'total_plans': len(all_json_plans),
    'plans': all_json_plans,
}

with open(all_json_path, 'w', encoding='utf-8') as f:
    json.dump(all_json, f, indent=2, ensure_ascii=False)

print(f"Updated {all_json_path} (total plans: {len(all_json_plans)})")
print("\nDone!")
