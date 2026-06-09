import unittest

from providers.tangerine import TANGERINE_PLANS


class TangerineCatalogTests(unittest.TestCase):
    def test_address_gated_fixed_line_100_tiers_are_present(self):
        plans_by_tier = {
            (plan["network"], plan["download"], plan["upload"]): plan
            for plan in TANGERINE_PLANS
        }

        speedy = plans_by_tier.get(("NBN", 100, 20))
        speedy_plus = plans_by_tier.get(("NBN", 100, 40))

        self.assertIsNotNone(speedy)
        self.assertEqual(speedy["plan_name"], "Speedy")
        self.assertEqual(speedy["regular_price"], 88.90)
        self.assertEqual(speedy["promo_price"], 63.90)
        self.assertEqual(speedy["typical_upload"], 17)

        self.assertIsNotNone(speedy_plus)
        self.assertEqual(speedy_plus["plan_name"], "Speedy Plus")
        self.assertEqual(speedy_plus["regular_price"], 92.90)
        self.assertEqual(speedy_plus["promo_price"], 67.90)
        self.assertEqual(speedy_plus["typical_upload"], 34)

    def test_fixed_wireless_100_tier_is_not_used_as_fixed_line_speedy(self):
        fixed_wireless = [
            plan for plan in TANGERINE_PLANS
            if plan["network"] == "Fixed Wireless"
            and plan["download"] == 100
            and plan["upload"] == 20
        ]

        self.assertEqual(len(fixed_wireless), 1)
        self.assertEqual(fixed_wireless[0]["regular_price"], 84.90)


if __name__ == "__main__":
    unittest.main()
