"""Show scraper output for all working providers and save to JSON + CSV."""
import sys
import json
import csv
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')

CSV_COLUMNS = [
    'provider', 'network_type', 'plan_name', 'download_speed', 'upload_speed',
    'price', 'promo_price', 'promo_period', 'contract',
    'typical_evening_dl', 'typical_evening_ul', 'source_url'
]


def get_isp_dir(isp_name, fmt):
    """Get output dir: output/scrape_isp_<isp>/<json|csv>/"""
    d = os.path.join(BASE_OUTPUT_DIR, f"scrape_isp_{isp_name}", fmt)
    os.makedirs(d, exist_ok=True)
    return d


def print_plans(provider_name, plans):
    print(f"\n{'='*90}")
    print(f"  {provider_name} — {len(plans)} plans scraped")
    print(f"{'='*90}")
    print(f"  {'Plan Name':<40} {'Network':<16} {'Speed':>12} {'Price':>10} {'Promo':>10}")
    print(f"  {'-'*40} {'-'*16} {'-'*12} {'-'*10} {'-'*10}")
    for p in plans:
        name = p['plan_name'][:40]
        net = p.get('network_type', '')[:16]
        speed = f"{p['download_speed']}/{p['upload_speed']} Mbps"
        price = f"${p['price']:.0f}/mth"
        promo = f"${p['promo_price']:.0f}/mth" if p.get('promo_price') else "-"
        print(f"  {name:<40} {net:<16} {speed:>12} {price:>10} {promo:>10}")

    print(f"\n  Total plans: {len(plans)}")
    if plans:
        prices = [p['price'] for p in plans]
        print(f"  Price range: ${min(prices):.0f} - ${max(prices):.0f}/mth")
        speeds = [p['download_speed'] for p in plans]
        print(f"  Speed range: {min(speeds)} - {max(speeds)} Mbps")


def save_provider_json(isp_name, filename, data):
    """Save JSON file into output/scrape_isp_<isp>/json/"""
    d = get_isp_dir(isp_name, 'json')
    filepath = os.path.join(d, f"{filename}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    count = len(data) if isinstance(data, list) else data.get('total_plans', '?')
    print(f"  JSON  {count:>3} plans -> {filepath}")
    return filepath


def save_provider_csv(isp_name, filename, plans, provider_label=None):
    """Save CSV file into output/scrape_isp_<isp>/csv/"""
    d = get_isp_dir(isp_name, 'csv')
    filepath = os.path.join(d, f"{filename}.csv")
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction='ignore')
        writer.writeheader()
        for plan in plans:
            row = dict(plan)
            row['provider'] = provider_label or isp_name
            for col in CSV_COLUMNS:
                row.setdefault(col, '')
            writer.writerow(row)
    print(f"  CSV   {len(plans):>3} plans -> {filepath}")
    return filepath


def save_isp_output(isp_name, plans_dict):
    """
    Save all plans for an ISP to its folder.
    plans_dict: either a flat list or a dict of {sub_key: [plans]}
    """
    if isinstance(plans_dict, list):
        # Simple provider (Telstra, Superloop) — single list
        save_provider_json(isp_name, f"{isp_name}_plans", plans_dict)
        save_provider_csv(isp_name, f"{isp_name}_plans", plans_dict, isp_name)
    elif isinstance(plans_dict, dict):
        # Multi-page provider (Occom) — dict of sub-pages
        all_plans = []
        for sub_key, plans in plans_dict.items():
            save_provider_json(isp_name, f"{isp_name}_{sub_key}_plans", plans)
            save_provider_csv(isp_name, f"{isp_name}_{sub_key}_plans", plans, isp_name)
            all_plans.extend(plans)

        # Save combined for this ISP
        save_provider_json(isp_name, f"{isp_name}_all_plans", all_plans)
        save_provider_csv(isp_name, f"{isp_name}_all_plans", all_plans, isp_name)


def save_combined(all_flat_plans):
    """Save combined all-providers file at output/ root level."""
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)

    # Combined JSON
    combined = {
        'scraped_at': timestamp,
        'total_plans': len(all_flat_plans),
        'plans': all_flat_plans
    }
    combined_json = os.path.join(BASE_OUTPUT_DIR, 'all_plans.json')
    with open(combined_json, 'w', encoding='utf-8') as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)
    print(f"  JSON  {len(all_flat_plans):>3} plans -> {combined_json}")

    # Combined CSV
    combined_csv = os.path.join(BASE_OUTPUT_DIR, 'all_plans.csv')
    with open(combined_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction='ignore')
        writer.writeheader()
        for plan in all_flat_plans:
            row = dict(plan)
            for col in CSV_COLUMNS:
                row.setdefault(col, '')
            writer.writerow(row)
    print(f"  CSV   {len(all_flat_plans):>3} plans -> {combined_csv}")


# ============================================================
#  SCRAPE ALL PROVIDERS
# ============================================================
all_flat_plans = []

# --- Telstra ---
from providers.telstra import scrape_telstra_plans
telstra_plans = scrape_telstra_plans()
print_plans("TELSTRA", telstra_plans)
for p in telstra_plans:
    p.setdefault('provider', 'telstra')
all_flat_plans.extend(telstra_plans)

# --- Superloop ---
from providers.superloop import scrape_superloop_plans
superloop_plans = scrape_superloop_plans()
print_plans("SUPERLOOP", superloop_plans)
for p in superloop_plans:
    p.setdefault('provider', 'superloop')
all_flat_plans.extend(superloop_plans)

# --- Occom (6 pages) ---
from providers.occom import scrape_occom_plans
occom_all = scrape_occom_plans()  # Returns dict: {page_key: [plans]}

for page_key, plans in occom_all.items():
    print_plans(f"OCCOM / {page_key.upper()}", plans)
    for p in plans:
        p.setdefault('provider', 'occom')
    all_flat_plans.extend(plans)

# ============================================================
#  SAVE OUTPUT
# ============================================================
print(f"\n{'='*90}")
print(f"  SAVING TO JSON + CSV")
print(f"{'='*90}")

save_isp_output('telstra', telstra_plans)
save_isp_output('superloop', superloop_plans)
save_isp_output('occom', occom_all)

print(f"\n  --- Combined ---")
save_combined(all_flat_plans)

print(f"\n  Grand total: {len(all_flat_plans)} unique plans saved")
