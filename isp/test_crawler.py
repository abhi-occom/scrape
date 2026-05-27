"""
ISP Crawler – Test Suite
-------------------------
Tests the mini crawler end-to-end against known ISP websites.

Test matrix:
  - Static plans (menu-based, always visible)
  - Dynamic plans (JS-rendered, needs wait)
  - Opticomm / RedTrain / Supa-specific pages
  - Edge cases (blocked sites, timeouts, empty pages)

Usage:
    python -m isp.test_crawler              # run all tests
    python -m isp.test_crawler --quick      # quick smoke test (Telstra only)
    python -m isp.test_crawler --provider telstra
"""

import sys
import os
import json
import time
from datetime import datetime
from typing import Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from isp.main_crawler import ISPCrawler, CrawlResult, OUTPUT_DIR


# ══════════════════════════════════════════════════════════════════
#  TEST SCENARIOS
# ══════════════════════════════════════════════════════════════════

TEST_SCENARIOS: Dict[str, Dict[str, Any]] = {
    'telstra': {
        'url': 'https://www.telstra.com.au/internet',
        'name': 'Telstra',
        'type': 'dynamic',           # JS-rendered cards
        'networks': ['nbn', 'opticomm'],
        'depth': 2,
        'expected': {
            'min_plan_pages': 1,
            'min_plans': 3,
            'expected_networks': ['NBN'],
            'sample_plans': [
                # Known Telstra plans for comparison
                {'plan_name_contains': 'Basic', 'min_price': 50, 'max_price': 120},
                {'plan_name_contains': 'Premium', 'min_price': 80, 'max_price': 200},
            ],
        },
    },

    'superloop': {
        'url': 'https://www.superloop.com/consumer/internet',
        'name': 'Superloop',
        'type': 'dynamic',
        'networks': ['nbn', 'opticomm'],
        'depth': 2,
        'expected': {
            'min_plan_pages': 1,
            'min_plans': 2,
            'expected_networks': ['NBN'],
            'sample_plans': [],
        },
    },

    'swoop': {
        'url': 'https://www.swoop.com.au',
        'name': 'Swoop',
        'type': 'dynamic',
        'networks': ['nbn', 'opticomm'],
        'depth': 2,
        'expected': {
            'min_plan_pages': 1,
            'min_plans': 2,
            'expected_networks': ['NBN', 'Opticomm'],
            'sample_plans': [],
        },
    },

    'occom': {
        'url': 'https://www.occom.com.au',
        'name': 'Occom',
        'type': 'dynamic',
        'networks': ['nbn', 'opticomm', 'redtrain', 'supa'],
        'depth': 2,
        'expected': {
            'min_plan_pages': 1,
            'min_plans': 2,
            'expected_networks': ['NBN'],
            'sample_plans': [],
        },
    },

    'exetel': {
        'url': 'https://www.exetel.com.au',
        'name': 'Exetel',
        'type': 'dynamic',
        'networks': ['nbn', 'opticomm'],
        'depth': 2,
        'expected': {
            'min_plan_pages': 1,
            'min_plans': 2,
            'expected_networks': ['NBN'],
            'sample_plans': [],
        },
    },

    'leaptel': {
        'url': 'https://www.leaptel.com.au',
        'name': 'Leaptel',
        'type': 'static',
        'networks': ['nbn', 'opticomm', 'redtrain', 'supa'],
        'depth': 2,
        'expected': {
            'min_plan_pages': 1,
            'min_plans': 2,
            'expected_networks': ['NBN'],
            'sample_plans': [],
        },
    },
}


# ══════════════════════════════════════════════════════════════════
#  TEST RUNNER
# ══════════════════════════════════════════════════════════════════

class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.details: List[str] = []

    def check(self, condition: bool, pass_msg: str, fail_msg: str):
        if condition:
            self.passed += 1
            self.details.append(f"  PASS  {pass_msg}")
        else:
            self.failed += 1
            self.details.append(f"  FAIL  {fail_msg}")

    def warn(self, msg: str):
        self.warnings += 1
        self.details.append(f"  WARN  {msg}")

    @property
    def success(self) -> bool:
        return self.failed == 0

    def summary(self) -> str:
        status = "PASSED" if self.success else "FAILED"
        return (
            f"[{status}] {self.name}: "
            f"{self.passed} passed, {self.failed} failed, {self.warnings} warnings"
        )


def run_test(scenario_name: str, scenario: Dict) -> TestResult:
    """Run a single test scenario."""
    tr = TestResult(scenario_name)
    expected = scenario['expected']

    print(f"\n{'─'*60}")
    print(f"  Testing: {scenario['name']} ({scenario['url']})")
    print(f"  Type: {scenario['type']}")
    print(f"  Networks: {scenario['networks']}")
    print(f"{'─'*60}")

    start = time.time()

    try:
        crawler = ISPCrawler(
            base_url=scenario['url'],
            network_types=scenario['networks'],
            max_depth=scenario['depth'],
            provider_name=scenario['name'],
        )
        result: CrawlResult = crawler.run()

        duration = time.time() - start

        # ── Basic assertions ─────────────────────────────────
        tr.check(
            result.urls_visited > 0,
            f"Visited {result.urls_visited} URLs",
            "No URLs were visited",
        )

        tr.check(
            result.plan_pages_found >= expected['min_plan_pages'],
            f"Found {result.plan_pages_found} plan pages (min: {expected['min_plan_pages']})",
            f"Only {result.plan_pages_found} plan pages (expected >= {expected['min_plan_pages']})",
        )

        tr.check(
            result.valid_plans >= expected['min_plans'],
            f"Scraped {result.valid_plans} valid plans (min: {expected['min_plans']})",
            f"Only {result.valid_plans} valid plans (expected >= {expected['min_plans']})",
        )

        tr.check(
            result.duration_seconds < 120,
            f"Completed in {result.duration_seconds:.1f}s (< 120s limit)",
            f"Took {result.duration_seconds:.1f}s (too slow, > 120s)",
        )

        # ── Network type checks ──────────────────────────────
        for net in expected['expected_networks']:
            found = net.upper() in [n.upper() for n in result.network_types_found]
            if found:
                tr.check(True, f"Found expected network: {net}", "")
            else:
                tr.warn(f"Expected network '{net}' not found in results: {result.network_types_found}")

        # ── Sample plan checks ───────────────────────────────
        for sample in expected.get('sample_plans', []):
            matching = [
                p for p in result.plans
                if sample['plan_name_contains'].lower() in p.get('plan_name', '').lower()
            ]
            if matching:
                plan = matching[0]
                price = plan.get('price', 0)
                price_ok = sample['min_price'] <= price <= sample['max_price']
                tr.check(
                    price_ok,
                    f"Plan '{plan['plan_name']}' price ${price} in range "
                    f"${sample['min_price']}-${sample['max_price']}",
                    f"Plan '{plan['plan_name']}' price ${price} OUT OF range "
                    f"${sample['min_price']}-${sample['max_price']}",
                )
            else:
                tr.warn(f"No plan matching '{sample['plan_name_contains']}' found")

        # ── Data quality checks ──────────────────────────────
        if result.plans:
            plans_with_speed = [p for p in result.plans if p.get('download_speed', 0) > 0]
            speed_ratio = len(plans_with_speed) / len(result.plans)
            tr.check(
                speed_ratio >= 0.5,
                f"{len(plans_with_speed)}/{len(result.plans)} plans have speed data ({speed_ratio:.0%})",
                f"Only {speed_ratio:.0%} of plans have speed data",
            )

            plans_with_name = [p for p in result.plans if p.get('plan_name', '').strip()]
            name_ratio = len(plans_with_name) / len(result.plans)
            tr.check(
                name_ratio >= 0.8,
                f"{len(plans_with_name)}/{len(result.plans)} plans have names ({name_ratio:.0%})",
                f"Only {name_ratio:.0%} of plans have names",
            )

        # ── Error check ──────────────────────────────────────
        if result.errors:
            tr.warn(f"{len(result.errors)} errors: {result.errors[:3]}")

        # ── Print plan summary ───────────────────────────────
        if result.plans:
            print(f"\n  Plans found ({len(result.plans)}):")
            for p in result.plans[:10]:
                promo = f" (promo ${p['promo_price']})" if p.get('promo_price') else ""
                print(f"    - {p['plan_name']:<35s} ${p.get('price', '?'):>8}/mth{promo}  "
                      f"{p.get('download_speed', '?')}/{p.get('upload_speed', '?')} Mbps  "
                      f"[{p.get('network_type', '?')}]")
            if len(result.plans) > 10:
                print(f"    ... and {len(result.plans) - 10} more")

    except Exception as e:
        tr.check(False, "", f"Test crashed: {str(e)}")

    # Print test result
    print(f"\n  {tr.summary()}")
    for detail in tr.details:
        print(f"    {detail}")

    return tr


def run_all_tests(
    provider: str = None,
    quick: bool = False,
) -> Dict[str, Any]:
    """
    Run test scenarios and produce a report.

    Args:
        provider:  Run only this provider's test (e.g. 'telstra').
        quick:     Run only Telstra for a quick smoke test.
    """
    print(f"\n{'='*60}")
    print(f"  ISP CRAWLER TEST SUITE")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    scenarios = TEST_SCENARIOS
    if provider:
        if provider.lower() in scenarios:
            scenarios = {provider.lower(): scenarios[provider.lower()]}
        else:
            print(f"\n  Unknown provider: {provider}")
            print(f"  Available: {', '.join(scenarios.keys())}")
            return {}
    elif quick:
        scenarios = {'telstra': scenarios['telstra']}

    results: Dict[str, TestResult] = {}
    total_start = time.time()

    for name, scenario in scenarios.items():
        results[name] = run_test(name, scenario)

    total_duration = time.time() - total_start

    # ── Summary report ────────────────────────────────────────
    passed = sum(1 for r in results.values() if r.success)
    failed = sum(1 for r in results.values() if not r.success)
    total_checks = sum(r.passed + r.failed for r in results.values())
    passed_checks = sum(r.passed for r in results.values())

    print(f"\n{'='*60}")
    print(f"  TEST SUITE SUMMARY")
    print(f"{'='*60}")
    print(f"  Providers tested:  {len(results)}")
    print(f"  Passed:            {passed}")
    print(f"  Failed:            {failed}")
    print(f"  Total checks:      {passed_checks}/{total_checks}")
    print(f"  Total time:        {total_duration:.1f}s")
    print(f"{'='*60}")

    for name, tr in results.items():
        status = "PASS" if tr.success else "FAIL"
        print(f"  [{status}] {name}: {tr.passed} passed, {tr.failed} failed")

    # Save test report
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    report = {
        'timestamp': datetime.now().isoformat(),
        'duration_seconds': round(total_duration, 2),
        'total_providers': len(results),
        'passed': passed,
        'failed': failed,
        'total_checks': total_checks,
        'passed_checks': passed_checks,
        'results': {
            name: {
                'success': tr.success,
                'passed': tr.passed,
                'failed': tr.failed,
                'warnings': tr.warnings,
                'details': tr.details,
            }
            for name, tr in results.items()
        },
    }

    report_path = os.path.join(OUTPUT_DIR, 'test_report.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved to: {report_path}")

    return report


# ── CLI entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='ISP Crawler Test Suite')
    parser.add_argument('--provider', default=None, help='Test specific provider (e.g. telstra)')
    parser.add_argument('--quick', action='store_true', help='Quick smoke test (Telstra only)')

    args = parser.parse_args()
    run_all_tests(provider=args.provider, quick=args.quick)
