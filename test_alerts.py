import unittest

from utils.alerts import detect_new_plans, detect_removed_plans, reconcile_renames


def _new_alert(provider, plan_name, speed, price=80):
    return {
        'type': 'new_plan', 'severity': 'medium', 'provider': provider,
        'plan_name': plan_name, 'speed': speed, 'price': price,
        'message': f'New plan: {provider} {plan_name} @ ${price}/mo',
    }


def _removed_alert(provider, plan_name, speed, price=80):
    return {
        'type': 'removed_plan', 'severity': 'low', 'provider': provider,
        'plan_name': plan_name, 'speed': speed, 'price': price,
        'message': f'Removed: {provider} {plan_name} (was ${price}/mo)',
    }


class ReconcileRenamesTests(unittest.TestCase):
    def test_similar_name_same_provider_and_speed_is_a_rename(self):
        new_alerts = [_new_alert('tangerine', 'Value Plus', 50)]
        removed_alerts = [_removed_alert('tangerine', 'Value', 50)]

        renamed, unmatched_new, unmatched_removed = reconcile_renames(new_alerts, removed_alerts)

        self.assertEqual(1, len(renamed))
        self.assertEqual('plan_renamed', renamed[0]['type'])
        self.assertEqual('Value', renamed[0]['old_name'])
        self.assertEqual('Value Plus', renamed[0]['new_name'])
        self.assertEqual('tangerine', renamed[0]['provider'])
        self.assertEqual([], unmatched_new)
        self.assertEqual([], unmatched_removed)

    def test_dissimilar_names_stay_as_separate_new_and_removed(self):
        new_alerts = [_new_alert('dodo', 'Everyday NBN25', 25)]
        removed_alerts = [_removed_alert('dodo', 'Superfast NBN100', 25)]

        renamed, unmatched_new, unmatched_removed = reconcile_renames(new_alerts, removed_alerts)

        self.assertEqual([], renamed)
        self.assertEqual(1, len(unmatched_new))
        self.assertEqual(1, len(unmatched_removed))

    def test_different_provider_never_matched_even_if_name_identical(self):
        new_alerts = [_new_alert('tpg', 'Value', 50)]
        removed_alerts = [_removed_alert('tangerine', 'Value', 50)]

        renamed, unmatched_new, unmatched_removed = reconcile_renames(new_alerts, removed_alerts)

        self.assertEqual([], renamed)
        self.assertEqual(1, len(unmatched_new))
        self.assertEqual(1, len(unmatched_removed))

    def test_different_speed_never_matched_even_if_name_identical(self):
        # A same-named plan at a different speed tier is a genuinely
        # different plan, not a rename of the old one.
        new_alerts = [_new_alert('tangerine', 'Value', 100)]
        removed_alerts = [_removed_alert('tangerine', 'Value', 50)]

        renamed, unmatched_new, unmatched_removed = reconcile_renames(new_alerts, removed_alerts)

        self.assertEqual([], renamed)
        self.assertEqual(1, len(unmatched_new))
        self.assertEqual(1, len(unmatched_removed))

    def test_each_new_plan_used_at_most_once(self):
        # Two removed plans both loosely resemble the one new plan — only
        # the best-scoring pair should be reconciled; the other stays removed.
        new_alerts = [_new_alert('tangerine', 'Value Plus', 50)]
        removed_alerts = [
            _removed_alert('tangerine', 'Value', 50),
            _removed_alert('tangerine', 'Val', 50),
        ]

        renamed, unmatched_new, unmatched_removed = reconcile_renames(new_alerts, removed_alerts)

        self.assertEqual(1, len(renamed))
        self.assertEqual([], unmatched_new)
        self.assertEqual(1, len(unmatched_removed))

    def test_price_carried_through_on_rename(self):
        new_alerts = [_new_alert('tangerine', 'Value Plus', 50, price=64.9)]
        removed_alerts = [_removed_alert('tangerine', 'Value', 50, price=59.9)]

        renamed, _, _ = reconcile_renames(new_alerts, removed_alerts)

        self.assertEqual(59.9, renamed[0]['old_price'])
        self.assertEqual(64.9, renamed[0]['new_price'])

    def test_empty_inputs_return_empty_outputs(self):
        renamed, unmatched_new, unmatched_removed = reconcile_renames([], [])
        self.assertEqual([], renamed)
        self.assertEqual([], unmatched_new)
        self.assertEqual([], unmatched_removed)

    def test_custom_threshold_is_respected(self):
        # "Value" vs "Value Plus" scores ~0.67 — with a very high threshold
        # it should NOT be treated as a rename, even though the default
        # threshold (0.6) does catch it (see test above).
        new_alerts = [_new_alert('tangerine', 'Value Plus', 50)]
        removed_alerts = [_removed_alert('tangerine', 'Value', 50)]

        renamed, unmatched_new, unmatched_removed = reconcile_renames(
            new_alerts, removed_alerts, threshold=0.99
        )
        self.assertEqual([], renamed)
        self.assertEqual(1, len(unmatched_new))
        self.assertEqual(1, len(unmatched_removed))

    def test_realistic_rename_patterns_are_caught_at_default_threshold(self):
        # Calibration guard: these are the kinds of renames providers
        # actually make (suffix added/removed, spacing/slash normalised).
        # If SequenceMatcher's ratio for any of these ever drops below the
        # default threshold, this test catches the regression.
        cases = [
            ('Speedy', 'Speedy Plus'),
            ('NBN50', 'NBN 50'),
            ('Everyday NBN25/10', 'Everyday NBN25'),
            ('Ultra Fast Fibre', 'Ultrafast Fibre'),
            ('Basic', 'Basic Plus'),
        ]
        for old_name, new_name in cases:
            with self.subTest(old_name=old_name, new_name=new_name):
                renamed, _, _ = reconcile_renames(
                    [_new_alert('provider', new_name, 50)],
                    [_removed_alert('provider', old_name, 50)],
                )
                self.assertEqual(1, len(renamed), f'{old_name!r} -> {new_name!r} was not caught as a rename')


class RenameReconciliationIntegrationTests(unittest.TestCase):
    """detect_new_plans() + detect_removed_plans() + reconcile_renames() together."""

    def test_provider_rename_produces_single_rename_alert_not_add_and_remove(self):
        previous_plans = [
            {'provider': 'tangerine', 'plan_name': 'Value', 'download_speed': 50, 'price': 59.9},
        ]
        current_plans = [
            {'provider': 'tangerine', 'plan_name': 'Value Plus', 'download_speed': 50, 'price': 64.9},
        ]

        new_alerts = detect_new_plans(current_plans, previous_plans)
        removed_alerts = detect_removed_plans(current_plans, previous_plans)
        self.assertEqual(1, len(new_alerts))
        self.assertEqual(1, len(removed_alerts))

        renamed, unmatched_new, unmatched_removed = reconcile_renames(new_alerts, removed_alerts)
        self.assertEqual(1, len(renamed))
        self.assertEqual([], unmatched_new)
        self.assertEqual([], unmatched_removed)

    def test_genuine_new_and_removed_plans_are_unaffected(self):
        previous_plans = [
            {'provider': 'dodo', 'plan_name': 'Superfast NBN100', 'download_speed': 100, 'price': 90},
        ]
        current_plans = [
            {'provider': 'dodo', 'plan_name': 'Everyday NBN25', 'download_speed': 25, 'price': 60},
        ]

        new_alerts = detect_new_plans(current_plans, previous_plans)
        removed_alerts = detect_removed_plans(current_plans, previous_plans)

        renamed, unmatched_new, unmatched_removed = reconcile_renames(new_alerts, removed_alerts)
        self.assertEqual([], renamed)
        self.assertEqual(1, len(unmatched_new))
        self.assertEqual(1, len(unmatched_removed))


if __name__ == '__main__':
    unittest.main()
