"""
Update all scraped output files from all_plans.csv (attached/canonical data).
"""
import csv
import json
import os
from datetime import datetime

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output')
CSV_PATH = os.path.join(OUTPUT_DIR, 'all_plans.csv')

PROVIDER_IDS = {'telstra': 1, 'superloop': 4, 'occom': 5, 'aussie': 3}

# Map source_url → per-page file base name (without _plans suffix)
TELSTRA_URL_MAP = {
    'https://www.telstra.com.au/internet/nbn': 'telstra_plans',
    'https://www.telstra.com.au/internet/5g-home-internet': 'telstra_5g_home_plans',
    'https://www.telstra.com.au/internet/plans': 'telstra_plans_plans',
    'https://www.telstra.com.au/small-business/internet': 'telstra_small_business_plans',
    'https://www.telstra.com.au/internet/starlink': 'telstra_starlink_plans',
}

SUPERLOOP_URL_MAP = {
    'https://www.superloop.com/internet/nbn/': 'superloop_nbn_plans',
    'https://www.superloop.com/internet/fibre/': 'superloop_fibre_plans',
    'https://www.superloop.com/internet/fixed-wireless/': 'superloop_fixed_wireless_plans',
    'https://www.superloop.com/flip-to-fibre/': 'superloop_flip_to_fibre_plans',
}

OCCOM_URL_MAP = {
    'https://occom.com.au/nbn-plans/': 'occom_nbn_plans',
    'https://occom.com.au/opticomm-plans/': 'occom_opticomm_plans',
    'https://occom.com.au/nbn-fttp-upgrade/': 'occom_nbn_fttp_plans',
    'https://occom.com.au/supa-network-plans/': 'occom_supa_plans',
    'https://occom.com.au/redtrain-plans/': 'occom_redtrain_plans',
    'https://occom.com.au/community-fibre-plans/': 'occom_community_fibre_plans',
}

CSV_HEADER = 'provider,network_type,plan_name,download_speed,upload_speed,price,promo_price,promo_period,contract,typical_evening_dl,typical_evening_ul,source_url'


def parse_float(val):
    if val is None or val == '':
        return None
    return float(val)

def parse_int(val):
    if val is None or val == '':
        return None
    return int(float(val))

def read_csv_data(path):
    plans = []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            plan = {
                'provider': row['provider'],
                'network_type': row['network_type'],
                'plan_name': row['plan_name'],
                'download_speed': int(float(row['download_speed'])),
                'upload_speed': int(float(row['upload_speed'])),
                'price': parse_float(row['price']),
                'promo_price': parse_float(row.get('promo_price', '')),
                'promo_period': row.get('promo_period', '') or None,
                'contract': row.get('contract', ''),
                'typical_evening_dl': parse_int(row.get('typical_evening_dl', '')),
                'typical_evening_ul': parse_int(row.get('typical_evening_ul', '')),
                'source_url': row.get('source_url', ''),
            }
            plans.append(plan)
    return plans


def plan_to_csv_row(plan):
    """Convert a plan dict to a CSV row string."""
    fields = [
        plan['provider'],
        plan['network_type'],
        plan['plan_name'],
        str(plan['download_speed']),
        str(plan['upload_speed']),
        str(plan['price']),
        str(plan['promo_price']) if plan['promo_price'] is not None else '',
        plan['promo_period'] if plan['promo_period'] else '',
        plan['contract'],
        str(plan['typical_evening_dl']) if plan['typical_evening_dl'] is not None else '',
        str(plan['typical_evening_ul']) if plan['typical_evening_ul'] is not None else '',
        plan['source_url'],
    ]
    return ','.join(fields)


def write_csv(path, plans):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(CSV_HEADER + '\n')
        for plan in plans:
            f.write(plan_to_csv_row(plan) + '\n')
    print(f"  CSV: {os.path.relpath(path, OUTPUT_DIR)} ({len(plans)} plans)")


def plan_to_all_json(plan):
    """Format for all_plans.json (wrapper format with speed + provider)."""
    return {
        'provider_id': PROVIDER_IDS.get(plan['provider'], 0),
        'plan_name': plan['plan_name'],
        'network_type': plan['network_type'],
        'speed': plan['download_speed'],
        'download_speed': plan['download_speed'],
        'upload_speed': plan['upload_speed'],
        'price': plan['price'],
        'promo_price': plan['promo_price'],
        'promo_period': plan['promo_period'],
        'contract': plan['contract'],
        'source_url': plan['source_url'],
        'provider': plan['provider'],
    }


def plan_to_telstra_page_json(plan):
    """Format for telstra per-page JSON (has speed, no typical_evening)."""
    return {
        'provider_id': PROVIDER_IDS['telstra'],
        'plan_name': plan['plan_name'],
        'network_type': plan['network_type'],
        'speed': plan['download_speed'],
        'download_speed': plan['download_speed'],
        'upload_speed': plan['upload_speed'],
        'price': plan['price'],
        'promo_price': plan['promo_price'],
        'promo_period': plan['promo_period'],
        'contract': plan['contract'],
        'source_url': plan['source_url'],
    }


def plan_to_telstra_all_json(plan):
    """Format for telstra_all_plans.json (has typical_evening, no speed)."""
    return {
        'provider_id': PROVIDER_IDS['telstra'],
        'plan_name': plan['plan_name'],
        'network_type': plan['network_type'],
        'download_speed': plan['download_speed'],
        'upload_speed': plan['upload_speed'],
        'typical_evening_dl': plan['typical_evening_dl'] if plan['typical_evening_dl'] is not None else plan['download_speed'],
        'typical_evening_ul': plan['typical_evening_ul'] if plan['typical_evening_ul'] is not None else plan['upload_speed'],
        'price': plan['price'],
        'promo_price': plan['promo_price'],
        'promo_period': plan['promo_period'],
        'contract': plan['contract'],
        'source_url': plan['source_url'],
    }


def plan_to_superloop_json(plan):
    """Format for superloop JSON files (has typical_evening, no speed)."""
    return {
        'provider_id': PROVIDER_IDS['superloop'],
        'plan_name': plan['plan_name'],
        'network_type': plan['network_type'],
        'download_speed': plan['download_speed'],
        'upload_speed': plan['upload_speed'],
        'typical_evening_dl': plan['typical_evening_dl'] if plan['typical_evening_dl'] is not None else 0,
        'typical_evening_ul': plan['typical_evening_ul'] if plan['typical_evening_ul'] is not None else 0,
        'price': plan['price'],
        'promo_price': plan['promo_price'],
        'promo_period': plan['promo_period'],
        'contract': plan['contract'],
        'source_url': plan['source_url'],
    }


def plan_to_occom_json(plan):
    """Format for occom JSON files (has speed, no typical_evening)."""
    return {
        'provider_id': PROVIDER_IDS['occom'],
        'plan_name': plan['plan_name'],
        'network_type': plan['network_type'],
        'speed': plan['download_speed'],
        'download_speed': plan['download_speed'],
        'upload_speed': plan['upload_speed'],
        'price': plan['price'],
        'promo_price': plan['promo_price'],
        'promo_period': plan['promo_period'],
        'contract': plan['contract'],
        'source_url': plan['source_url'],
    }


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    count = len(data) if isinstance(data, list) else data.get('total_plans', '?')
    print(f"  JSON: {os.path.relpath(path, OUTPUT_DIR)} ({count} plans)")


def write_provider_files(provider_dir, all_file_base, url_map, all_plans, json_formatter):
    """Write per-page CSV/JSON and all_plans CSV/JSON for a provider."""
    csv_dir = os.path.join(provider_dir, 'csv')
    json_dir = os.path.join(provider_dir, 'json')

    # Group plans by source_url
    by_url = {}
    for plan in all_plans:
        url = plan['source_url']
        by_url.setdefault(url, []).append(plan)

    # Write per-page files
    written_page_files = set()
    for url, file_base in url_map.items():
        page_plans = by_url.get(url, [])
        write_csv(os.path.join(csv_dir, file_base + '.csv'), page_plans)
        write_json(os.path.join(json_dir, file_base + '.json'),
                   [json_formatter(p) for p in page_plans])
        written_page_files.add(file_base)

    # Write all_plans
    write_csv(os.path.join(csv_dir, all_file_base + '_all_plans.csv'), all_plans)

    return all_plans


def main():
    print("Reading CSV data...")
    all_plans = read_csv_data(CSV_PATH)
    print(f"Total plans in CSV: {len(all_plans)}")

    # Split by provider
    by_provider = {}
    for plan in all_plans:
        by_provider.setdefault(plan['provider'], []).append(plan)

    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    # === 1. Write all_plans.csv ===
    print("\n--- all_plans.csv ---")
    write_csv(os.path.join(OUTPUT_DIR, 'all_plans.csv'), all_plans)

    # === 2. Write all_plans.json ===
    print("\n--- all_plans.json ---")
    all_json = {
        'scraped_at': timestamp,
        'total_plans': len(all_plans),
        'plans': [plan_to_all_json(p) for p in all_plans],
    }
    write_json(os.path.join(OUTPUT_DIR, 'all_plans.json'), all_json)

    # === 3. Telstra ===
    print("\n--- Telstra ---")
    telstra_plans = by_provider.get('telstra', [])
    telstra_dir = os.path.join(OUTPUT_DIR, 'scrape_isp_telstra')

    write_provider_files(telstra_dir, 'telstra', TELSTRA_URL_MAP,
                         telstra_plans, plan_to_telstra_page_json)

    # telstra_all_plans.json uses different format (with typical_evening)
    write_json(os.path.join(telstra_dir, 'json', 'telstra_all_plans.json'),
               [plan_to_telstra_all_json(p) for p in telstra_plans])

    # === 4. Superloop ===
    print("\n--- Superloop ---")
    superloop_plans = by_provider.get('superloop', [])
    superloop_dir = os.path.join(OUTPUT_DIR, 'scrape_isp_superloop')

    write_provider_files(superloop_dir, 'superloop', SUPERLOOP_URL_MAP,
                         superloop_plans, plan_to_superloop_json)

    # superloop_all_plans.json
    write_json(os.path.join(superloop_dir, 'json', 'superloop_all_plans.json'),
               [plan_to_superloop_json(p) for p in superloop_plans])

    # superloop_plans = same as superloop_nbn (main page)
    nbn_plans = [p for p in superloop_plans if p['source_url'] == 'https://www.superloop.com/internet/nbn/']
    write_csv(os.path.join(superloop_dir, 'csv', 'superloop_plans.csv'), nbn_plans)
    write_json(os.path.join(superloop_dir, 'json', 'superloop_plans.json'),
               [plan_to_superloop_json(p) for p in nbn_plans])

    # === 5. Occom ===
    print("\n--- Occom ---")
    occom_plans = by_provider.get('occom', [])
    occom_dir = os.path.join(OUTPUT_DIR, 'scrape_isp_occom')

    write_provider_files(occom_dir, 'occom', OCCOM_URL_MAP,
                         occom_plans, plan_to_occom_json)

    # occom_all_plans.json
    write_json(os.path.join(occom_dir, 'json', 'occom_all_plans.json'),
               [plan_to_occom_json(p) for p in occom_plans])

    # === 6. Aussie (empty) ===
    print("\n--- Aussie ---")
    aussie_dir = os.path.join(OUTPUT_DIR, 'scrape_isp_aussie')
    aussie_plans = by_provider.get('aussie', [])
    write_csv(os.path.join(aussie_dir, 'csv', 'aussie_plans.csv'), aussie_plans)
    write_json(os.path.join(aussie_dir, 'json', 'aussie_plans.json'), [])

    print(f"\nDone! All output files updated.")


if __name__ == '__main__':
    main()
