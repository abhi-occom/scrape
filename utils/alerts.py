"""
Automated alert system for competitive price monitoring.
Detects price changes, new/removed plans, and Occom pricing gaps.
Stores alert history and generates actionable notifications.
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from config import OUTPUT_DIR
from utils.logger import log_info, log_warning, log_success


ALERTS_FILE = os.path.join(OUTPUT_DIR, 'alerts.json')
SNAPSHOT_FILE = os.path.join(OUTPUT_DIR, 'plans_snapshot.json')


def load_previous_snapshot() -> List[Dict[str, Any]]:
    """Load the previously saved plans snapshot for comparison."""
    if not os.path.exists(SNAPSHOT_FILE):
        return []
    try:
        with open(SNAPSHOT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data.get('plans', [])
        return data
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_snapshot(plans: List[Dict[str, Any]]):
    """Save current plans as a snapshot for future diff."""
    os.makedirs(os.path.dirname(SNAPSHOT_FILE), exist_ok=True)
    with open(SNAPSHOT_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            'saved_at': datetime.now().isoformat(),
            'total_plans': len(plans),
            'plans': plans,
        }, f, indent=2, ensure_ascii=False)


def _plan_key(plan: Dict[str, Any]) -> str:
    """Create a unique key for a plan."""
    provider = plan.get('provider', str(plan.get('provider_id', '')))
    name = plan.get('plan_name', '')
    speed = plan.get('download_speed') or plan.get('speed') or 0
    return f"{provider}|{name}|{speed}"


def detect_price_changes(
    current_plans: List[Dict[str, Any]],
    previous_plans: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Detect plans where the price has changed since last snapshot."""
    prev_map = {_plan_key(p): p for p in previous_plans}
    alerts = []

    for plan in current_plans:
        key = _plan_key(plan)
        prev = prev_map.get(key)
        if not prev:
            continue

        old_price = prev.get('price', 0)
        new_price = plan.get('price', 0)
        old_promo = prev.get('promo_price') or 0
        new_promo = plan.get('promo_price') or 0

        if old_price != new_price:
            diff = new_price - old_price
            alerts.append({
                'type': 'price_change',
                'severity': 'high' if abs(diff) >= 10 else 'medium',
                'provider': plan.get('provider', ''),
                'plan_name': plan.get('plan_name', ''),
                'speed': plan.get('download_speed') or plan.get('speed') or 0,
                'old_price': old_price,
                'new_price': new_price,
                'difference': round(diff, 2),
                'direction': 'increase' if diff > 0 else 'decrease',
                'message': f"{plan.get('provider', '').title()} changed {plan.get('plan_name', '')} "
                           f"from ${old_price:.0f} to ${new_price:.0f}/mo "
                           f"({'↑' if diff > 0 else '↓'} ${abs(diff):.0f})"
            })

        if old_promo != new_promo and (old_promo or new_promo):
            alerts.append({
                'type': 'promo_change',
                'severity': 'medium',
                'provider': plan.get('provider', ''),
                'plan_name': plan.get('plan_name', ''),
                'old_promo': old_promo,
                'new_promo': new_promo,
                'message': f"{plan.get('provider', '').title()} promo on {plan.get('plan_name', '')} "
                           f"changed from ${old_promo:.0f} to ${new_promo:.0f}/mo"
            })

    return alerts


def detect_new_plans(
    current_plans: List[Dict[str, Any]],
    previous_plans: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Detect plans that are new (not in previous snapshot)."""
    prev_keys = {_plan_key(p) for p in previous_plans}
    alerts = []

    for plan in current_plans:
        if _plan_key(plan) not in prev_keys:
            alerts.append({
                'type': 'new_plan',
                'severity': 'medium',
                'provider': plan.get('provider', ''),
                'plan_name': plan.get('plan_name', ''),
                'speed': plan.get('download_speed') or plan.get('speed') or 0,
                'price': plan.get('price', 0),
                'message': f"New plan: {plan.get('provider', '').title()} "
                           f"{plan.get('plan_name', '')} @ ${plan.get('price', 0):.0f}/mo"
            })

    return alerts


def detect_removed_plans(
    current_plans: List[Dict[str, Any]],
    previous_plans: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Detect plans that were removed (in previous but not current)."""
    curr_keys = {_plan_key(p) for p in current_plans}
    alerts = []

    for plan in previous_plans:
        if _plan_key(plan) not in curr_keys:
            alerts.append({
                'type': 'removed_plan',
                'severity': 'low',
                'provider': plan.get('provider', ''),
                'plan_name': plan.get('plan_name', ''),
                'speed': plan.get('download_speed') or plan.get('speed') or 0,
                'price': plan.get('price', 0),
                'message': f"Removed: {plan.get('provider', '').title()} "
                           f"{plan.get('plan_name', '')} (was ${plan.get('price', 0):.0f}/mo)"
            })

    return alerts


def detect_occom_undercut(benchmark_report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate alerts when a competitor is cheaper than Occom in a tier.
    Uses the benchmark report's gap analysis.
    """
    alerts = []
    for gap in benchmark_report.get('occom_gaps', []):
        alerts.append({
            'type': 'occom_undercut',
            'severity': 'high',
            'tier': gap['tier_label'],
            'occom_price': gap['occom_price'],
            'competitor': gap.get('cheapest_competitor', ''),
            'competitor_price': gap.get('cheapest_competitor_price', 0),
            'gap_amount': gap.get('gap_amount', 0),
            'gap_pct': gap.get('gap_pct', 0),
            'message': f"⚠ {gap['tier_label']} tier: {gap.get('cheapest_competitor', '').title()} "
                       f"is ${gap.get('gap_amount', 0):.0f}/mo cheaper than Occom "
                       f"(${gap.get('cheapest_competitor_price', 0):.0f} vs ${gap['occom_price']:.0f})"
        })
    return alerts


def run_alerts(
    current_plans: List[Dict[str, Any]],
    benchmark_report: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Run all alert checks and return a consolidated alert report.
    Also saves alert history and updates the snapshot.
    """
    log_info("Running alert checks")

    previous_plans = load_previous_snapshot()
    all_alerts = []

    # Diff-based alerts (only if we have a previous snapshot)
    if previous_plans:
        all_alerts.extend(detect_price_changes(current_plans, previous_plans))
        all_alerts.extend(detect_new_plans(current_plans, previous_plans))
        all_alerts.extend(detect_removed_plans(current_plans, previous_plans))
    else:
        log_info("No previous snapshot found — skipping diff alerts (first run)")

    # Benchmark-based alerts
    if benchmark_report:
        all_alerts.extend(detect_occom_undercut(benchmark_report))

    # Add timestamps
    now = datetime.now().isoformat()
    for alert in all_alerts:
        alert['timestamp'] = now

    # Save snapshot for next run
    save_snapshot(current_plans)

    # Save alerts
    alert_report = {
        'generated_at': now,
        'total_alerts': len(all_alerts),
        'high': len([a for a in all_alerts if a.get('severity') == 'high']),
        'medium': len([a for a in all_alerts if a.get('severity') == 'medium']),
        'low': len([a for a in all_alerts if a.get('severity') == 'low']),
        'alerts': all_alerts,
    }

    _save_alerts(alert_report)

    if all_alerts:
        log_warning(f"Generated {len(all_alerts)} alerts "
                    f"({alert_report['high']} high, {alert_report['medium']} medium, {alert_report['low']} low)")
    else:
        log_success("No new alerts")

    return alert_report


def _save_alerts(alert_report: Dict[str, Any]):
    """Append alerts to the alerts history file."""
    os.makedirs(os.path.dirname(ALERTS_FILE), exist_ok=True)

    history = []
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            history = []

    history.append(alert_report)

    # Keep last 100 alert runs
    if len(history) > 100:
        history = history[-100:]

    with open(ALERTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
