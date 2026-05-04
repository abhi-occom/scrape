"""
Shared scraper service module for dual-mode operation (CLI + Frontend).
This module provides core scraping functions used by both CLI and Flask API.
"""
import sys
import os
import json
import csv
from datetime import datetime
from typing import Dict, List, Optional, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import PROVIDERS
from utils.stealth import create_stealth_browser, create_stealth_page

BASE_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')

CSV_COLUMNS = [
    'provider', 'network_type', 'plan_name', 'download_speed', 'upload_speed',
    'price', 'promo_price', 'promo_period', 'contract',
    'typical_evening_dl', 'typical_evening_ul', 'source_url'
]


def get_isp_dir(isp_name: str, fmt: str) -> str:
    """Get output dir: output/scrape_isp_<isp>/<json|csv>/"""
    d = os.path.join(BASE_OUTPUT_DIR, f"scrape_isp_{isp_name}", fmt)
    os.makedirs(d, exist_ok=True)
    return d


def save_provider_json(isp_name: str, filename: str, data: Any) -> str:
    """Save JSON file into output/scrape_isp_<isp>/json/"""
    d = get_isp_dir(isp_name, 'json')
    filepath = os.path.join(d, f"{filename}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return filepath


def save_provider_csv(isp_name: str, filename: str, plans: List[Dict], provider_label: Optional[str] = None) -> str:
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
    return filepath


def scrape_provider(provider_name: str) -> Dict[str, Any]:
    """
    Scrape a single provider and return results.
    Returns: {
        'success': bool,
        'provider': str,
        'plans': List[Dict] or Dict[str, List] for multi-page,
        'total_plans': int,
        'error': Optional[str]
    }
    """
    result = {
        'success': False,
        'provider': provider_name,
        'plans': [],
        'total_plans': 0,
        'error': None
    }

    try:
        # Import provider module dynamically
        provider_module = __import__(f'providers.{provider_name}', fromlist=[''])
        
        # Call scrape function — prefer multi-page scrapers for dict output
        if hasattr(provider_module, 'scrape_telstra_plans'):
            plans = provider_module.scrape_telstra_plans()
        elif hasattr(provider_module, 'scrape_superloop_plans'):
            plans = provider_module.scrape_superloop_plans()
        elif hasattr(provider_module, 'scrape_occom_plans'):
            plans = provider_module.scrape_occom_plans()
        elif hasattr(provider_module, 'scrape_tpg_plans'):
            plans = provider_module.scrape_tpg_plans()
        elif hasattr(provider_module, 'scrape_via_playwright'):
            plans = provider_module.scrape_via_playwright()
        else:
            raise AttributeError(f"No scrape function found in {provider_name}")

        result['plans'] = plans
        result['total_plans'] = len(plans) if isinstance(plans, list) else sum(len(v) for v in plans.values())
        result['success'] = True

    except Exception as e:
        result['error'] = str(e)
        result['success'] = False

    return result


def save_output(provider_name: str, plans: Any) -> Dict[str, str]:
    """
    Save scraped output to JSON and CSV files.
    Returns dict with file paths.
    """
    files = {'json': [], 'csv': []}

    if isinstance(plans, list):
        # Simple provider (Telstra, Superloop)
        json_path = save_provider_json(provider_name, f"{provider_name}_plans", plans)
        csv_path = save_provider_csv(provider_name, f"{provider_name}_plans", plans, provider_name)
        files['json'].append(json_path)
        files['csv'].append(csv_path)

    elif isinstance(plans, dict):
        # Multi-page provider (Occom)
        all_plans = []
        for sub_key, sub_plans in plans.items():
            json_path = save_provider_json(provider_name, f"{provider_name}_{sub_key}_plans", sub_plans)
            csv_path = save_provider_csv(provider_name, f"{provider_name}_{sub_key}_plans", sub_plans, provider_name)
            files['json'].append(json_path)
            files['csv'].append(csv_path)
            all_plans.extend(sub_plans)

        # Save combined
        json_path = save_provider_json(provider_name, f"{provider_name}_all_plans", all_plans)
        csv_path = save_provider_csv(provider_name, f"{provider_name}_all_plans", all_plans, provider_name)
        files['json'].append(json_path)
        files['csv'].append(csv_path)

    return files


def get_saved_results(provider_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve saved results from output folder.
    If provider_name is None, return all providers' results.
    """
    results = {}

    if provider_name:
        # Get specific provider
        isp_dir = get_isp_dir(provider_name, 'json')
        if os.path.exists(isp_dir):
            for filename in os.listdir(isp_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(isp_dir, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        results[filename.replace('.json', '')] = data

    else:
        # Get all providers
        for provider in PROVIDERS.keys():
            isp_dir = get_isp_dir(provider, 'json')
            if os.path.exists(isp_dir):
                provider_results = {}
                for filename in os.listdir(isp_dir):
                    if filename.endswith('.json') and 'all_plans' in filename:
                        filepath = os.path.join(isp_dir, filename)
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            provider_results[filename.replace('.json', '')] = data
                if provider_results:
                    results[provider] = provider_results

    return results


def get_provider_list() -> List[Dict[str, Any]]:
    """Get list of all providers with their status."""
    providers = []
    for name, config in PROVIDERS.items():
        isp_dir = get_isp_dir(name, 'json')
        has_data = os.path.exists(isp_dir) and any(f.endswith('.json') for f in os.listdir(isp_dir))
        
        providers.append({
            'id': config['id'],
            'name': config['name'],
            'key': name,
            'enabled': config['enabled'],
            'has_saved_data': has_data
        })

    return providers


def download_json(provider_name: str, filename: str) -> Optional[str]:
    """Get full path to JSON file for download."""
    filepath = os.path.join(get_isp_dir(provider_name, 'json'), f"{filename}.json")
    return filepath if os.path.exists(filepath) else None


def download_csv(provider_name: str, filename: str) -> Optional[str]:
    """Get full path to CSV file for download."""
    filepath = os.path.join(get_isp_dir(provider_name, 'csv'), f"{filename}.csv")
    return filepath if os.path.exists(filepath) else None
