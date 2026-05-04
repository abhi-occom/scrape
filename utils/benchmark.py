"""
Competitive Price Benchmarking Engine for Occom.
Compares Occom plans against competitors by speed tier, calculates value scores,
and identifies pricing advantages/gaps.
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from config import PROVIDERS, OUTPUT_DIR


# Speed tier definitions for grouping plans across providers
SPEED_TIERS = {
    'basic':     {'label': 'Basic',     'min': 0,    'max': 15},
    'standard':  {'label': 'Standard',  'min': 16,   'max': 30},
    'boost':     {'label': 'Boost',     'min': 31,   'max': 60},
    'fast':      {'label': 'Fast',      'min': 61,   'max': 150},
    'superfast': {'label': 'Superfast', 'min': 151,  'max': 300},
    'ultrafast': {'label': 'Ultrafast', 'min': 301,  'max': 600},
    'hyper':     {'label': 'Hyper',     'min': 601,  'max': 1000},
    'mega':      {'label': 'Mega',      'min': 1001, 'max': 99999},
}

OCCOM_PROVIDER_ID = PROVIDERS.get('occom', {}).get('id', 5)


def classify_speed_tier(speed_mbps: int) -> str:
    """Classify a download speed into a named tier."""
    for tier_key, tier in SPEED_TIERS.items():
        if tier['min'] <= speed_mbps <= tier['max']:
            return tier_key
    return 'unknown'


def get_effective_price(plan: Dict[str, Any]) -> float:
    """Get the effective price a customer pays (promo if available, else regular)."""
    promo = plan.get('promo_price')
    regular = plan.get('price', 0)
    if promo and promo > 0:
        return float(promo)
    return float(regular)


def get_regular_price(plan: Dict[str, Any]) -> float:
    """Get the regular (non-promo) price."""
    return float(plan.get('price', 0))


def calc_value_score(speed_mbps: int, price: float) -> float:
    """Calculate Mbps-per-dollar value score."""
    if price <= 0:
        return 0.0
    return round(speed_mbps / price, 2)


def calc_annual_cost(plan: Dict[str, Any]) -> float:
    """
    Calculate the total cost for the first 12 months,
    accounting for promo periods.
    """
    regular = get_regular_price(plan)
    promo = plan.get('promo_price')
    promo_period_str = plan.get('promo_period') or ''

    promo_months = 0
    if promo and promo > 0 and promo_period_str:
        import re
        match = re.search(r'(\d+)', promo_period_str)
        if match:
            promo_months = min(int(match.group(1)), 12)

    if promo_months > 0 and promo and promo > 0:
        return round(promo * promo_months + regular * (12 - promo_months), 2)
    return round(regular * 12, 2)


def load_all_plans(file_path: str = None) -> List[Dict[str, Any]]:
    """Load plans from the all_plans.json output file."""
    if file_path is None:
        file_path = os.path.join(OUTPUT_DIR, 'all_plans.json')

    if not os.path.exists(file_path):
        return []

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Handle both formats: list of plans or { plans: [...] }
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get('plans', [])
    return []


def group_plans_by_tier(plans: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[Dict]]]:
    """
    Group plans by speed tier, then by provider.
    Returns: { tier_key: { provider_name: [plans] } }
    """
    grouped = {}
    for plan in plans:
        speed = plan.get('download_speed') or plan.get('speed') or 0
        provider = plan.get('provider', '').lower()
        tier = classify_speed_tier(speed)

        if tier not in grouped:
            grouped[tier] = {}
        if provider not in grouped[tier]:
            grouped[tier][provider] = []
        grouped[tier][provider].append(plan)

    return grouped


def find_cheapest_plan(plans: List[Dict[str, Any]], use_promo: bool = True) -> Optional[Dict[str, Any]]:
    """Find the cheapest plan from a list."""
    if not plans:
        return None
    price_fn = get_effective_price if use_promo else get_regular_price
    return min(plans, key=lambda p: price_fn(p))


def run_benchmark(plans: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Run the full competitive benchmark analysis.

    Returns a structured report dict with:
    - tier_comparisons: per-tier price comparison across all providers
    - occom_advantages: tiers where Occom is cheapest
    - occom_gaps: tiers where Occom is NOT cheapest
    - value_rankings: Mbps/$ rankings per tier
    - summary: high-level stats
    """
    if plans is None:
        plans = load_all_plans()

    if not plans:
        return {'error': 'No plan data available', 'generated_at': datetime.now().isoformat()}

    grouped = group_plans_by_tier(plans)

    tier_comparisons = []
    occom_advantages = []
    occom_gaps = []
    value_rankings = []

    for tier_key in SPEED_TIERS:
        tier_info = SPEED_TIERS[tier_key]
        providers_in_tier = grouped.get(tier_key, {})

        if not providers_in_tier:
            continue

        # Build per-provider best plan in this tier
        provider_best = {}
        for prov, prov_plans in providers_in_tier.items():
            best = find_cheapest_plan(prov_plans, use_promo=True)
            if best:
                eff_price = get_effective_price(best)
                reg_price = get_regular_price(best)
                speed = best.get('download_speed') or best.get('speed') or 0
                provider_best[prov] = {
                    'provider': prov,
                    'plan_name': best.get('plan_name', ''),
                    'speed': speed,
                    'effective_price': eff_price,
                    'regular_price': reg_price,
                    'promo_price': best.get('promo_price'),
                    'promo_period': best.get('promo_period'),
                    'annual_cost': calc_annual_cost(best),
                    'value_score': calc_value_score(speed, eff_price),
                    'network_type': best.get('network_type', ''),
                    'contract': best.get('contract', ''),
                }

        if not provider_best:
            continue

        # Find overall cheapest
        cheapest_prov = min(provider_best.values(), key=lambda x: x['effective_price'])
        most_expensive_prov = max(provider_best.values(), key=lambda x: x['effective_price'])
        best_value_prov = max(provider_best.values(), key=lambda x: x['value_score'])

        tier_entry = {
            'tier': tier_key,
            'tier_label': tier_info['label'],
            'speed_range': f"{tier_info['min']}-{tier_info['max']} Mbps",
            'providers': provider_best,
            'cheapest': cheapest_prov['provider'],
            'cheapest_price': cheapest_prov['effective_price'],
            'most_expensive': most_expensive_prov['provider'],
            'most_expensive_price': most_expensive_prov['effective_price'],
            'best_value': best_value_prov['provider'],
            'best_value_score': best_value_prov['value_score'],
        }
        tier_comparisons.append(tier_entry)

        # Occom advantage / gap analysis
        occom_entry = provider_best.get('occom')
        if occom_entry:
            occom_price = occom_entry['effective_price']
            is_cheapest = cheapest_prov['provider'] == 'occom'

            comparison = {
                'tier': tier_key,
                'tier_label': tier_info['label'],
                'occom_price': occom_price,
                'occom_plan': occom_entry['plan_name'],
                'occom_speed': occom_entry['speed'],
                'occom_value_score': occom_entry['value_score'],
                'cheapest_competitor': cheapest_prov['provider'] if not is_cheapest else None,
                'cheapest_competitor_price': cheapest_prov['effective_price'] if not is_cheapest else None,
            }

            if is_cheapest:
                # Find second cheapest for savings calculation
                others = [v for k, v in provider_best.items() if k != 'occom']
                if others:
                    second = min(others, key=lambda x: x['effective_price'])
                    comparison['savings_vs_next'] = round(second['effective_price'] - occom_price, 2)
                    comparison['savings_pct'] = round(
                        (second['effective_price'] - occom_price) / second['effective_price'] * 100, 1
                    )
                    comparison['next_cheapest'] = second['provider']
                occom_advantages.append(comparison)
            else:
                comparison['gap_amount'] = round(occom_price - cheapest_prov['effective_price'], 2)
                comparison['gap_pct'] = round(
                    (occom_price - cheapest_prov['effective_price']) / cheapest_prov['effective_price'] * 100, 1
                )
                occom_gaps.append(comparison)

        # Value rankings for this tier
        ranked = sorted(provider_best.values(), key=lambda x: x['value_score'], reverse=True)
        value_rankings.append({
            'tier': tier_key,
            'tier_label': tier_info['label'],
            'rankings': [
                {
                    'rank': i + 1,
                    'provider': r['provider'],
                    'value_score': r['value_score'],
                    'speed': r['speed'],
                    'price': r['effective_price'],
                }
                for i, r in enumerate(ranked)
            ]
        })

    # Summary
    total_tiers_present = len(tier_comparisons)
    tiers_occom_cheapest = len(occom_advantages)
    tiers_occom_gap = len(occom_gaps)

    all_providers_seen = set()
    for tc in tier_comparisons:
        all_providers_seen.update(tc['providers'].keys())

    summary = {
        'total_plans_analyzed': len(plans),
        'total_providers': len(all_providers_seen),
        'providers': sorted(all_providers_seen),
        'total_speed_tiers': total_tiers_present,
        'occom_cheapest_tiers': tiers_occom_cheapest,
        'occom_gap_tiers': tiers_occom_gap,
        'occom_win_rate': round(
            tiers_occom_cheapest / total_tiers_present * 100, 1
        ) if total_tiers_present > 0 else 0,
    }

    report = {
        'generated_at': datetime.now().isoformat(),
        'summary': summary,
        'tier_comparisons': tier_comparisons,
        'occom_advantages': occom_advantages,
        'occom_gaps': occom_gaps,
        'value_rankings': value_rankings,
    }

    return report


def save_benchmark_report(report: Dict[str, Any], file_path: str = None) -> str:
    """Save the benchmark report to a JSON file."""
    if file_path is None:
        file_path = os.path.join(OUTPUT_DIR, 'benchmark_report.json')

    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return file_path


def save_benchmark_csv(report: Dict[str, Any], file_path: str = None) -> str:
    """Export tier comparisons as a CSV for the marketing team."""
    import csv

    if file_path is None:
        file_path = os.path.join(OUTPUT_DIR, 'benchmark_report.csv')

    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    rows = []
    for tc in report.get('tier_comparisons', []):
        for prov, info in tc['providers'].items():
            rows.append({
                'tier': tc['tier_label'],
                'speed_range': tc['speed_range'],
                'provider': prov,
                'plan_name': info['plan_name'],
                'speed_mbps': info['speed'],
                'effective_price': info['effective_price'],
                'regular_price': info['regular_price'],
                'promo_price': info.get('promo_price') or '',
                'promo_period': info.get('promo_period') or '',
                'annual_cost': info['annual_cost'],
                'value_score': info['value_score'],
                'is_cheapest': 'Yes' if tc['cheapest'] == prov else '',
                'is_best_value': 'Yes' if tc['best_value'] == prov else '',
            })

    fieldnames = [
        'tier', 'speed_range', 'provider', 'plan_name', 'speed_mbps',
        'effective_price', 'regular_price', 'promo_price', 'promo_period',
        'annual_cost', 'value_score', 'is_cheapest', 'is_best_value'
    ]

    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return file_path
