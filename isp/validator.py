"""
ISP Crawler – Data Validator
-----------------------------
Validates and normalises plans scraped by the dynamic scraper engine.

Validation rules:
  - plan_name must be a non-empty string (max 200 chars).
  - price must be a positive number between $1 and $500.
  - download_speed must be a positive integer between 1 and 10 000.
  - download_speed must not exceed the realistic ceiling for the plan's
    access technology (e.g. an FTTN plan claiming 1000 Mbps is flagged).
  - network_type should be one of the known types (warn if unknown).
  - price-per-Mbps must not be a wild outlier vs. other plans on the same
    access technology (batch-level check, see flag_price_outliers()).

Each plan validated via validate_batch() also gets a `confidence` field —
'Strong' if it passed every check clean, 'Needs Review' if any check raised
a warning. See compute_confidence().

Also builds an "expected vs actual" comparison log for test scenarios.
"""

import re
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import log_info, log_warning
from utils.network_classifier import (
    classify_access_technology,
    is_broadband_network_type,
    SPEED_CEILING_MBPS,
)


@dataclass
class ValidationResult:
    """Result of validating a single plan."""
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    plan: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComparisonEntry:
    """Expected vs Actual comparison entry for test scenarios."""
    url: str
    scenario: str              # 'static_menu' | 'dynamic_address'
    expected_plans: int
    actual_plans: int
    missing_plans: List[str] = field(default_factory=list)
    incorrect_prices: List[Dict] = field(default_factory=list)
    incorrect_speeds: List[Dict] = field(default_factory=list)
    match_rate: float = 0.0
    timestamp: str = ''


class ISPValidator:
    """Validate scraped plan data."""

    def validate_plan(self, plan: Dict[str, Any]) -> ValidationResult:
        """Validate a single plan dict."""
        result = ValidationResult(plan=plan)

        # ── plan_name ────────────────────────────────────────
        name = plan.get('plan_name', '')
        if not name or not isinstance(name, str) or not name.strip():
            result.is_valid = False
            result.errors.append('plan_name is missing or empty')
        elif len(name) > 200:
            result.warnings.append(f'plan_name is very long ({len(name)} chars), truncated')
            plan['plan_name'] = name[:200]

        # ── price ────────────────────────────────────────────
        price = plan.get('price')
        if price is None:
            result.is_valid = False
            result.errors.append('price is missing')
        else:
            try:
                price = float(price)
                if price <= 0:
                    result.is_valid = False
                    result.errors.append(f'price must be positive (got {price})')
                elif price > 500:
                    result.warnings.append(f'price seems unusually high: ${price}')
                plan['price'] = price
            except (ValueError, TypeError):
                result.is_valid = False
                result.errors.append(f'price is not a valid number: {price}')

        # ── promo_price ──────────────────────────────────────
        promo = plan.get('promo_price')
        if promo is not None:
            try:
                promo = float(promo)
                if promo <= 0:
                    plan['promo_price'] = None
                    result.warnings.append('promo_price <= 0, cleared')
                elif price and promo >= price:
                    plan['promo_price'] = None
                    result.warnings.append('promo_price >= regular price, cleared')
                else:
                    plan['promo_price'] = promo
            except (ValueError, TypeError):
                plan['promo_price'] = None

        # ── download_speed ───────────────────────────────────
        speed = plan.get('download_speed')
        if speed is None or speed == 0:
            # Try extracting from plan name
            name_match = re.search(r'(\d+)\s*[Mm]bps', plan.get('plan_name', ''))
            if name_match:
                plan['download_speed'] = int(name_match.group(1))
                plan['speed_label'] = plan['download_speed']
            else:
                result.warnings.append('download_speed is 0 or missing')
        else:
            try:
                speed = int(speed)
                if speed < 0:
                    result.is_valid = False
                    result.errors.append(f'download_speed cannot be negative: {speed}')
                elif speed > 10000:
                    result.warnings.append(f'download_speed seems unusually high: {speed}')
                plan['download_speed'] = speed
                plan['speed_label'] = speed
            except (ValueError, TypeError):
                result.warnings.append(f'download_speed is not a valid integer: {speed}')

        # ── network-specific speed ceiling ────────────────────
        tech = classify_access_technology(plan.get('network_type'))
        ceiling = SPEED_CEILING_MBPS.get(tech)
        if ceiling and plan.get('download_speed', 0) > ceiling:
            result.warnings.append(
                f'{tech} plan advertises {plan["download_speed"]} Mbps, above the '
                f'expected ceiling of {ceiling} Mbps for this technology — verify'
            )

        # ── network_type ─────────────────────────────────────
        net = plan.get('network_type', '')
        if net:
            if not is_broadband_network_type(net):
                result.warnings.append(f'Unknown network type: "{net}"')
        else:
            result.warnings.append('network_type is empty')

        return result

    @staticmethod
    def flag_price_outliers(
        plans: List[Dict[str, Any]], factor: float = 3.0, min_group_size: int = 3,
    ) -> Dict[int, str]:
        """
        Batch-level check: group plans by access technology, compute each
        group's median price-per-Mbps, and flag any plan whose price/Mbps is
        more than `factor`x away from its group's median in either direction.

        Catches scraping errors that produce a physically-plausible-looking
        but wrong price/speed pair (e.g. a misparsed digit) that the flat
        $1-$500 / 1-10,000 Mbps bounds in validate_plan() wouldn't catch on
        their own, because it compares plans against their peers rather than
        fixed limits. Skipped for groups smaller than `min_group_size` since
        a median of 1-2 plans isn't a meaningful baseline.

        Returns {id(plan): warning_message} — callers key off object identity
        since plans don't carry a stable unique id at this layer.
        """
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for plan in plans:
            speed = plan.get('download_speed') or 0
            price = plan.get('price') or 0
            if speed <= 0 or price <= 0:
                continue
            tech = classify_access_technology(plan.get('network_type'))
            groups.setdefault(tech, []).append(plan)

        warnings: Dict[int, str] = {}
        for tech, group in groups.items():
            if len(group) < min_group_size:
                continue
            ratios = sorted(p['price'] / p['download_speed'] for p in group)
            mid = len(ratios) // 2
            median = ratios[mid] if len(ratios) % 2 else (ratios[mid - 1] + ratios[mid]) / 2
            if median <= 0:
                continue
            for plan in group:
                ratio = plan['price'] / plan['download_speed']
                if ratio > median * factor or ratio < median / factor:
                    warnings[id(plan)] = (
                        f'Price/Mbps (${ratio:.2f}) for this {tech} plan is more than '
                        f'{factor:.0f}x off the {tech} group median (${median:.2f}) — verify'
                    )
        return warnings

    @staticmethod
    def compute_confidence(warnings: List[str]) -> str:
        """
        'Strong' if a plan passed every check clean; 'Needs Review' if any
        check raised a warning (unknown network type, speed/price bounds,
        network-specific speed ceiling, price-per-Mbps outlier, ...).

        Deliberately takes the final warnings list rather than being called
        from inside validate_plan(): the price-outlier warning is only known
        at the batch level (flag_price_outliers() needs every plan in the
        run to compute a group median), so confidence must be computed after
        that warning has already been merged in — see validate_batch().
        """
        return 'Strong' if not warnings else 'Needs Review'

    def validate_batch(
        self, plans: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[ValidationResult]]:
        """
        Validate a list of plans.

        Returns:
            (valid_plans, invalid_plans, all_results)
        """
        valid = []
        invalid = []
        results = []
        outlier_warnings = self.flag_price_outliers(plans)

        for plan in plans:
            vr = self.validate_plan(plan)
            outlier_msg = outlier_warnings.get(id(plan))
            if outlier_msg:
                vr.warnings.append(outlier_msg)
            plan['confidence'] = self.compute_confidence(vr.warnings)
            results.append(vr)
            if vr.is_valid:
                valid.append(plan)
            else:
                invalid.append({**plan, '_validation_errors': vr.errors})

            if vr.warnings:
                for w in vr.warnings:
                    log_warning(
                        f"Validation warning for '{plan.get('plan_name', '?')}': {w}",
                        provider="isp-crawler",
                    )

        log_info(
            f"Validation complete: {len(valid)} valid, {len(invalid)} invalid out of {len(plans)}",
            provider="isp-crawler",
        )
        return valid, invalid, results


class ComparisonLogger:
    """
    Build expected-vs-actual comparison logs for test scenarios.

    Usage:
        logger = ComparisonLogger()
        logger.add_scenario(
            url="https://telstra.com.au/internet/plans",
            scenario="static_menu",
            expected_plans=17,
            expected_data=[
                {"plan_name": "Basic NBN", "price": 85, "download_speed": 25},
                ...
            ],
            actual_plans=actual_scraped_plans,
        )
        report = logger.generate_report()
    """

    def __init__(self):
        self.entries: List[ComparisonEntry] = []

    def add_scenario(
        self,
        url: str,
        scenario: str,
        expected_plans: int,
        expected_data: Optional[List[Dict]] = None,
        actual_plans: Optional[List[Dict]] = None,
    ) -> ComparisonEntry:
        """Compare expected vs actual and log gaps."""
        entry = ComparisonEntry(
            url=url,
            scenario=scenario,
            expected_plans=expected_plans,
            actual_plans=len(actual_plans) if actual_plans else 0,
            timestamp=datetime.now().isoformat(),
        )

        if expected_data and actual_plans:
            actual_names = {p.get('plan_name', '').lower().strip() for p in actual_plans}
            actual_by_name = {
                p.get('plan_name', '').lower().strip(): p
                for p in actual_plans
            }

            for exp in expected_data:
                exp_name = exp.get('plan_name', '').lower().strip()

                if exp_name not in actual_names:
                    entry.missing_plans.append(exp.get('plan_name', '?'))
                    continue

                actual = actual_by_name[exp_name]

                # Check price
                exp_price = exp.get('price')
                act_price = actual.get('price')
                if exp_price and act_price and abs(float(exp_price) - float(act_price)) > 1.0:
                    entry.incorrect_prices.append({
                        'plan': exp.get('plan_name'),
                        'expected': exp_price,
                        'actual': act_price,
                    })

                # Check speed
                exp_speed = exp.get('download_speed')
                act_speed = actual.get('download_speed')
                if exp_speed and act_speed and int(exp_speed) != int(act_speed):
                    entry.incorrect_speeds.append({
                        'plan': exp.get('plan_name'),
                        'expected': exp_speed,
                        'actual': act_speed,
                    })

            # Match rate
            total_checks = len(expected_data)
            gaps = len(entry.missing_plans) + len(entry.incorrect_prices) + len(entry.incorrect_speeds)
            entry.match_rate = max(0, (total_checks - gaps) / total_checks * 100) if total_checks else 0

        self.entries.append(entry)
        return entry

    def generate_report(self) -> Dict[str, Any]:
        """Produce a summary report of all comparison entries."""
        return {
            'generated_at': datetime.now().isoformat(),
            'total_scenarios': len(self.entries),
            'scenarios': [asdict(e) for e in self.entries],
            'overall_match_rate': (
                sum(e.match_rate for e in self.entries) / len(self.entries)
                if self.entries else 0
            ),
        }
