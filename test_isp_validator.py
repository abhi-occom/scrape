import unittest

from isp.validator import ISPValidator


class SpeedCeilingTests(unittest.TestCase):
    """Network-specific speed ceiling check in ISPValidator.validate_plan()."""

    def setUp(self):
        self.validator = ISPValidator()

    def _plan(self, **overrides):
        base = {
            'plan_name': 'Test Plan',
            'price': 79.0,
            'download_speed': 50,
            'network_type': 'NBN FTTN',
        }
        base.update(overrides)
        return base

    def test_speed_within_ceiling_no_warning(self):
        result = self.validator.validate_plan(self._plan(network_type='NBN FTTN', download_speed=90))
        self.assertTrue(result.is_valid)
        self.assertFalse(any('ceiling' in w for w in result.warnings))

    def test_fttn_plan_above_ceiling_warns(self):
        result = self.validator.validate_plan(self._plan(network_type='NBN FTTN', download_speed=1000))
        self.assertTrue(any('FTTN' in w and 'ceiling' in w for w in result.warnings))

    def test_fixed_wireless_above_ceiling_warns(self):
        result = self.validator.validate_plan(
            self._plan(network_type='NBN Fixed Wireless', download_speed=500)
        )
        self.assertTrue(any('Fixed Wireless' in w and 'ceiling' in w for w in result.warnings))

    def test_fttp_plan_allows_high_speed(self):
        # FTTP ceiling is 2000 — a 1000 Mbps FTTP plan is legitimate and must not warn.
        result = self.validator.validate_plan(self._plan(network_type='NBN FTTP', download_speed=1000))
        self.assertFalse(any('ceiling' in w for w in result.warnings))

    def test_unknown_technology_is_not_checked(self):
        # Bare "NBN" has no derivable access_technology, so there's no ceiling to apply.
        result = self.validator.validate_plan(self._plan(network_type='NBN', download_speed=5000))
        self.assertFalse(any('ceiling' in w for w in result.warnings))


class PriceOutlierTests(unittest.TestCase):
    """Batch-level price-per-Mbps outlier detection."""

    def test_flags_plan_far_above_group_median(self):
        plans = [
            {'plan_name': 'A', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 80},
            {'plan_name': 'B', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 85},
            {'plan_name': 'C', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 90},
            # Same speed, wildly higher price -> outlier vs. the ~$0.85/Mbps median.
            {'plan_name': 'D', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 400},
        ]
        warnings = ISPValidator.flag_price_outliers(plans)
        flagged_names = {p['plan_name'] for p in plans if id(p) in warnings}
        self.assertEqual({'D'}, flagged_names)

    def test_flags_plan_far_below_group_median(self):
        plans = [
            {'plan_name': 'A', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 80},
            {'plan_name': 'B', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 85},
            {'plan_name': 'C', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 90},
            {'plan_name': 'D', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 5},
        ]
        warnings = ISPValidator.flag_price_outliers(plans)
        flagged_names = {p['plan_name'] for p in plans if id(p) in warnings}
        self.assertEqual({'D'}, flagged_names)

    def test_no_flags_for_consistent_group(self):
        plans = [
            {'plan_name': 'A', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 80},
            {'plan_name': 'B', 'network_type': 'NBN FTTP', 'download_speed': 250, 'price': 95},
            {'plan_name': 'C', 'network_type': 'NBN FTTP', 'download_speed': 1000, 'price': 130},
        ]
        self.assertEqual({}, ISPValidator.flag_price_outliers(plans))

    def test_skips_groups_below_min_size(self):
        # Only 2 FTTN plans — too small a sample for a meaningful median.
        plans = [
            {'plan_name': 'A', 'network_type': 'NBN FTTN', 'download_speed': 50, 'price': 60},
            {'plan_name': 'B', 'network_type': 'NBN FTTN', 'download_speed': 50, 'price': 600},
        ]
        self.assertEqual({}, ISPValidator.flag_price_outliers(plans))

    def test_different_technologies_compared_separately(self):
        # An FTTP plan at $130 for 1000 Mbps is normal; an FTTN plan at the
        # same price for 50 Mbps is not — they must not be pooled together.
        plans = [
            {'plan_name': 'A', 'network_type': 'NBN FTTP', 'download_speed': 1000, 'price': 130},
            {'plan_name': 'B', 'network_type': 'NBN FTTP', 'download_speed': 500, 'price': 100},
            {'plan_name': 'C', 'network_type': 'NBN FTTP', 'download_speed': 250, 'price': 90},
            {'plan_name': 'D', 'network_type': 'NBN FTTN', 'download_speed': 50, 'price': 60},
            {'plan_name': 'E', 'network_type': 'NBN FTTN', 'download_speed': 50, 'price': 65},
            {'plan_name': 'F', 'network_type': 'NBN FTTN', 'download_speed': 50, 'price': 600},
        ]
        warnings = ISPValidator.flag_price_outliers(plans)
        flagged_names = {p['plan_name'] for p in plans if id(p) in warnings}
        self.assertEqual({'F'}, flagged_names)

    def test_ignores_plans_missing_price_or_speed(self):
        plans = [
            {'plan_name': 'A', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 80},
            {'plan_name': 'B', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 85},
            {'plan_name': 'C', 'network_type': 'NBN FTTP', 'download_speed': 0, 'price': 90},
            {'plan_name': 'D', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': None},
        ]
        # Should not raise (division by zero / None arithmetic) and should
        # simply exclude C and D from the group used to compute the median.
        warnings = ISPValidator.flag_price_outliers(plans)
        self.assertEqual({}, warnings)


class ComputeConfidenceTests(unittest.TestCase):
    def test_no_warnings_is_strong(self):
        self.assertEqual('Strong', ISPValidator.compute_confidence([]))

    def test_any_warning_is_needs_review(self):
        self.assertEqual('Needs Review', ISPValidator.compute_confidence(['some warning']))
        self.assertEqual('Needs Review', ISPValidator.compute_confidence(['w1', 'w2']))


class ValidateBatchIntegrationTests(unittest.TestCase):
    def test_outlier_warning_surfaces_through_validate_batch(self):
        plans = [
            {'plan_name': 'A', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 80},
            {'plan_name': 'B', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 85},
            {'plan_name': 'C', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 90},
            {'plan_name': 'D', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 400},
        ]
        valid, invalid, results = ISPValidator().validate_batch(plans)
        # Outliers are warnings, not errors — the plan stays valid and present.
        self.assertEqual(4, len(valid))
        self.assertEqual(0, len(invalid))
        outlier_result = next(r for r in results if r.plan['plan_name'] == 'D')
        self.assertTrue(any('median' in w for w in outlier_result.warnings))

    def test_clean_plan_gets_strong_confidence(self):
        plans = [
            {'plan_name': 'A', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 80},
            {'plan_name': 'B', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 85},
            {'plan_name': 'C', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 90},
        ]
        ISPValidator().validate_batch(plans)
        self.assertTrue(all(p['confidence'] == 'Strong' for p in plans))

    def test_per_plan_warning_gets_needs_review_confidence(self):
        # Unknown network type triggers a per-plan warning in validate_plan()
        # itself — confidence must reflect that even without an outlier.
        plans = [{'plan_name': 'A', 'network_type': 'garbage', 'download_speed': 50, 'price': 80}]
        ISPValidator().validate_batch(plans)
        self.assertEqual('Needs Review', plans[0]['confidence'])

    def test_outlier_only_plan_gets_needs_review_confidence(self):
        # D has no per-plan issues of its own — only the batch-level outlier
        # check flags it. Confidence must still downgrade to Needs Review,
        # proving it's computed AFTER the outlier warning is merged in.
        plans = [
            {'plan_name': 'A', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 80},
            {'plan_name': 'B', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 85},
            {'plan_name': 'C', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 90},
            {'plan_name': 'D', 'network_type': 'NBN FTTP', 'download_speed': 100, 'price': 400},
        ]
        ISPValidator().validate_batch(plans)
        by_name = {p['plan_name']: p['confidence'] for p in plans}
        self.assertEqual({'A': 'Strong', 'B': 'Strong', 'C': 'Strong', 'D': 'Needs Review'}, by_name)


if __name__ == '__main__':
    unittest.main()
