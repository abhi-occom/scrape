import unittest

from utils.network_classifier import (
    canonicalize_network_type,
    is_broadband_network_type,
    normalise_plans,
)


class CanonicalizeNetworkTypeTests(unittest.TestCase):
    def test_empty_input_returns_empty_string(self):
        self.assertEqual("", canonicalize_network_type(""))
        self.assertEqual("", canonicalize_network_type(None))
        self.assertEqual("", canonicalize_network_type("   "))

    def test_compound_nbn_strings_are_not_mangled(self):
        # Regression guard: a naive keyword scan checks 'nbn' before 'fttp'
        # and would collapse these down to plain "NBN", losing real information.
        self.assertEqual("NBN FTTP", canonicalize_network_type("NBN FTTP"))
        self.assertEqual("NBN FTTP Upgrade", canonicalize_network_type("NBN FTTP Upgrade"))
        self.assertEqual("NBN Fixed Wireless", canonicalize_network_type("NBN Fixed Wireless"))

    def test_exact_known_tokens_get_nicely_cased(self):
        self.assertEqual("NBN", canonicalize_network_type("nbn"))
        self.assertEqual("Fibre", canonicalize_network_type("fibre"))
        self.assertEqual("FTTP", canonicalize_network_type("fttp"))
        self.assertEqual("5G", canonicalize_network_type("5g"))
        self.assertEqual("Business NBN", canonicalize_network_type("Business NBN"))
        self.assertEqual("ASN Telecom", canonicalize_network_type("ASN Telecom"))
        self.assertEqual("Lynham Networks", canonicalize_network_type("Lynham Networks"))

    def test_private_network_aliases_collapse(self):
        self.assertEqual("Opticomm", canonicalize_network_type("Opticomm"))
        self.assertEqual("Redtrain", canonicalize_network_type("Redtrain"))
        self.assertEqual("Supa", canonicalize_network_type("SUPA Networks"))
        self.assertEqual("Supa", canonicalize_network_type("SUPA Fibre"))
        self.assertEqual("Supa", canonicalize_network_type("Supanetworks"))

    def test_mobile_and_home_wireless_variants(self):
        self.assertEqual("4G Home Wireless", canonicalize_network_type("4G Home Wireless"))
        self.assertEqual("5G Home Broadband", canonicalize_network_type("5G Home Broadband"))

    def test_business_mobile_is_not_classified_as_broadband(self):
        self.assertEqual("Unknown", canonicalize_network_type("Business Mobile"))

    def test_unrecognized_garbage_never_defaults_to_nbn(self):
        self.assertEqual("Unknown", canonicalize_network_type("asdkjhasd garbage"))


class IsBroadbandNetworkTypeTests(unittest.TestCase):
    def test_recognized_broadband_types_are_true(self):
        for value in (
            "NBN", "NBN FTTP", "NBN FTTP Upgrade", "Opticomm", "Redtrain",
            "SUPA Networks", "SUPA Fibre", "Supanetworks", "5G Home Broadband",
            "4G Home Wireless", "NBN Fixed Wireless", "Business NBN",
            "ASN Telecom", "Lynham Networks", "Vision Networks",
            "Community Fibre",
        ):
            with self.subTest(value=value):
                self.assertTrue(is_broadband_network_type(value))

    def test_non_broadband_values_are_false(self):
        for value in ("Business Mobile", "asdkjhasd garbage", "", None):
            with self.subTest(value=value):
                self.assertFalse(is_broadband_network_type(value))


class NormalisePlansTests(unittest.TestCase):
    def test_flat_list_of_plans(self):
        plans = [
            {"plan_name": "A", "network_type": "nbn"},
            {"plan_name": "B", "network_type": "SUPA Fibre"},
        ]
        result = normalise_plans(plans)
        self.assertEqual("NBN", result[0]["network_type"])
        self.assertEqual("Supa", result[1]["network_type"])

    def test_dict_of_lists_keyed_by_page(self):
        plans = {
            "page1": [{"plan_name": "A", "network_type": "nbn"}],
            "page2": [{"plan_name": "B", "network_type": "Opticomm"}],
        }
        result = normalise_plans(plans)
        self.assertEqual("NBN", result["page1"][0]["network_type"])
        self.assertEqual("Opticomm", result["page2"][0]["network_type"])

    def test_does_not_mutate_input_plans(self):
        original = {"plan_name": "A", "network_type": "nbn"}
        plans = [original]
        normalise_plans(plans)
        self.assertEqual("nbn", original["network_type"])

    def test_skips_non_dict_items_without_raising(self):
        plans = [{"plan_name": "A", "network_type": "nbn"}, "not-a-plan", None]
        result = normalise_plans(plans)
        self.assertEqual("NBN", result[0]["network_type"])
        self.assertEqual("not-a-plan", result[1])
        self.assertIsNone(result[2])


if __name__ == "__main__":
    unittest.main()
