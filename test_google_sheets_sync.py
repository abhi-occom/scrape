import unittest

from google_sheets_sync import (
    SpeedTier,
    build_price_matrix,
    classify_plan_tier,
    plan_is_eligible,
    plan_speed,
)


SPEED_TIERS = [
    SpeedTier("12M", 12),
    SpeedTier("25M", 25),
    SpeedTier("50M", 50),
    SpeedTier("100/20M", 100, 20),
    SpeedTier("100/40M", 100, 40),
    SpeedTier("250M", 250),
    SpeedTier("500/50M", 500, 50),
    SpeedTier("750M", 750),
    SpeedTier("1000/100M", 1000, 100),
    SpeedTier("2000/100M", 2000, 100),
    SpeedTier("2000/200M", 2000, 200),
]


def nbn_plan(download, upload, **overrides):
    plan = {
        "provider": "Telstra",
        "network_type": "NBN",
        "plan_name": "Test NBN plan",
        "download_speed": download,
        "upload_speed": upload,
        "price": 99,
        "promo_price": None,
    }
    plan.update(overrides)
    return plan


class NearbySpeedTierTests(unittest.TestCase):
    def assert_tier(self, download, upload, expected):
        tier = classify_plan_tier(nbn_plan(download, upload), SPEED_TIERS)
        self.assertEqual(expected, tier.label if tier else None)

    def test_download_rounds_up_to_nearest_sheet_tier(self):
        for download in (65, 85, 97, 99, 100):
            with self.subTest(download=download):
                self.assert_tier(download, 20, "100/20M")

        for download, upload in ((820, 85), (850, 82), (885, 91), (1000, 100)):
            with self.subTest(download=download, upload=upload):
                self.assert_tier(download, upload, "1000/100M")

        for download in (400, 485, 500):
            with self.subTest(download=download):
                self.assert_tier(download, 50, "500/50M")

    def test_exact_lower_tier_does_not_round_up(self):
        self.assert_tier(50, 20, "50M")
        self.assert_tier(750, 50, "750M")

    def test_upload_rounds_up_within_download_bucket(self):
        for download, upload in ((65, 10), (85, 17), (97, 19), (100, 20)):
            with self.subTest(download=download, upload=upload):
                self.assert_tier(download, upload, "100/20M")

        for download, upload in ((97, 36), (100, 40)):
            with self.subTest(download=download, upload=upload):
                self.assert_tier(download, upload, "100/40M")

        self.assert_tier(2000, 100, "2000/100M")
        self.assert_tier(2000, 200, "2000/200M")

    def test_upload_above_available_tier_is_excluded(self):
        self.assert_tier(1000, 400, None)
        self.assert_tier(2000, 500, None)
        self.assert_tier(100, 41, None)

    def test_missing_upload_cannot_fill_explicit_upload_row(self):
        self.assert_tier(100, None, None)
        self.assert_tier(1000, None, None)

    def test_plan_name_is_only_used_for_missing_numeric_values(self):
        plan = nbn_plan(None, None, plan_name="Example NBN 100/40")
        self.assertEqual((100.0, 40.0), plan_speed(plan))
        self.assertEqual("100/40M", classify_plan_tier(plan, SPEED_TIERS).label)

        numeric_wins = nbn_plan(97, 19, plan_name="Example NBN 100/40")
        self.assertEqual((97.0, 19.0), plan_speed(numeric_wins))
        self.assertEqual("100/20M", classify_plan_tier(numeric_wins, SPEED_TIERS).label)

    def test_only_nbn_plans_are_eligible(self):
        self.assertTrue(plan_is_eligible(nbn_plan(100, 20)))
        self.assertFalse(plan_is_eligible(nbn_plan(100, 20, network_type="Opticomm", plan_name="Opticomm 100/20")))
        self.assertFalse(plan_is_eligible(nbn_plan(100, 20, network_type="5G", plan_name="5G Home Internet")))
        self.assertFalse(plan_is_eligible(nbn_plan(100, 20, network_type="Fixed Wireless", plan_name="Fixed Wireless")))

    def test_lowest_promo_first_price_wins_per_bucket(self):
        plans = [
            nbn_plan(85, 17, price=90, promo_price=70),
            nbn_plan(97, 19, price=80, promo_price=None),
            nbn_plan(100, 20, price=95, promo_price=75),
        ]
        prices, _ = build_price_matrix(plans, SPEED_TIERS)
        self.assertEqual(70, prices[("TELSTRA", "100/20M")])


if __name__ == "__main__":
    unittest.main()
