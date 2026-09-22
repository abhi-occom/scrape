import unittest

from utils.network_classifier import (
    canonicalize_network_type,
    classify_access_technology,
    classify_upstream_network,
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


class ClassifyAccessTechnologyTests(unittest.TestCase):
    def test_explicit_technology_tokens(self):
        self.assertEqual("FTTP", classify_access_technology("NBN FTTP"))
        self.assertEqual("FTTB", classify_access_technology("NBN FTTB"))
        self.assertEqual("FTTN", classify_access_technology("NBN FTTN"))
        self.assertEqual("FTTC", classify_access_technology("NBN FTTC"))
        self.assertEqual("HFC", classify_access_technology("NBN HFC"))
        self.assertEqual("Fixed Wireless", classify_access_technology("NBN Fixed Wireless"))
        self.assertEqual("Satellite", classify_access_technology("NBN Satellite"))
        self.assertEqual("Satellite", classify_access_technology("Starlink"))

    def test_mobile_home_wireless_is_its_own_technology_not_fixed_wireless(self):
        self.assertEqual("4G", classify_access_technology("4G Home Wireless"))
        self.assertEqual("5G", classify_access_technology("5G Home Broadband"))

    def test_generic_fibre_maps_to_fttp(self):
        self.assertEqual("FTTP", classify_access_technology("Fibre"))

    def test_private_fibre_operators_default_to_fttp_without_explicit_tech(self):
        # Redtrain/Opticomm/Supa/etc are FTTP-only overbuild networks, so a
        # bare "Redtrain" plan is still known to be FTTP even though the
        # string never says so — this is the exact case the split was built for.
        self.assertEqual("FTTP", classify_access_technology("Redtrain"))
        self.assertEqual("FTTP", classify_access_technology("Opticomm"))
        self.assertEqual("FTTP", classify_access_technology("SUPA Networks"))
        self.assertEqual("FTTP", classify_access_technology("Lynham Networks"))
        self.assertEqual("FTTP", classify_access_technology("ASN Telecom"))
        self.assertEqual("FTTP", classify_access_technology("Vision Networks"))
        self.assertEqual("FTTP", classify_access_technology("Community Fibre"))

    def test_technology_unknown_when_not_derivable(self):
        self.assertEqual("Unknown", classify_access_technology("NBN"))
        self.assertEqual("Unknown", classify_access_technology("Business NBN"))
        self.assertEqual("Unknown", classify_access_technology("Business Mobile"))
        self.assertEqual("Unknown", classify_access_technology("asdkjhasd garbage"))

    def test_empty_input_returns_empty_string(self):
        self.assertEqual("", classify_access_technology(""))
        self.assertEqual("", classify_access_technology(None))


class ClassifyUpstreamNetworkTests(unittest.TestCase):
    def test_private_operators(self):
        self.assertEqual("Opticomm", classify_upstream_network("Opticomm"))
        self.assertEqual("Redtrain", classify_upstream_network("Redtrain"))
        self.assertEqual("Redtrain", classify_upstream_network("Red Train"))
        self.assertEqual("Supa", classify_upstream_network("SUPA Networks"))
        self.assertEqual("Lynham Networks", classify_upstream_network("Lynham Networks"))
        self.assertEqual("ASN Telecom", classify_upstream_network("ASN Telecom"))
        self.assertEqual("Vision Networks", classify_upstream_network("Vision Networks"))
        self.assertEqual("Community Fibre", classify_upstream_network("Community Fibre"))

    def test_nbn_operator_regardless_of_technology_suffix(self):
        self.assertEqual("NBN", classify_upstream_network("NBN"))
        self.assertEqual("NBN", classify_upstream_network("NBN FTTP"))
        self.assertEqual("NBN", classify_upstream_network("NBN FTTP Upgrade"))
        self.assertEqual("NBN", classify_upstream_network("Business NBN"))
        self.assertEqual("NBN", classify_upstream_network("NBN Fixed Wireless"))

    def test_operator_unknown_when_not_derivable(self):
        # Mobile-network-delivered plans and generic fibre don't name an
        # upstream operator in the raw string, so this must not guess "NBN".
        self.assertEqual("Unknown", classify_upstream_network("4G Home Wireless"))
        self.assertEqual("Unknown", classify_upstream_network("5G Home Broadband"))
        self.assertEqual("Unknown", classify_upstream_network("Fibre"))
        self.assertEqual("Unknown", classify_upstream_network("Business Mobile"))
        self.assertEqual("Unknown", classify_upstream_network("asdkjhasd garbage"))

    def test_empty_input_returns_empty_string(self):
        self.assertEqual("", classify_upstream_network(""))
        self.assertEqual("", classify_upstream_network(None))

    def test_redtrain_ftttp_compound_case(self):
        # The motivating example from the plan: a RedTrain plan delivered
        # over FTTP must report both facts independently, not collapse to one.
        raw = "Redtrain FTTP 100/20"
        self.assertEqual("Redtrain", classify_upstream_network(raw))
        self.assertEqual("FTTP", classify_access_technology(raw))


class NormalisePlansTests(unittest.TestCase):
    def test_flat_list_of_plans(self):
        plans = [
            {"plan_name": "A", "network_type": "nbn"},
            {"plan_name": "B", "network_type": "SUPA Fibre"},
        ]
        result = normalise_plans(plans)
        self.assertEqual("NBN", result[0]["network_type"])
        self.assertEqual("Supa", result[1]["network_type"])

    def test_adds_access_technology_and_upstream_network_fields(self):
        # canonicalize_network_type() collapses "Redtrain ..." down to the
        # bare operator name "Redtrain" (see test_private_network_aliases_collapse),
        # which is exactly why the split fields matter: they preserve the
        # FTTP technology information that network_type alone loses.
        plans = [{"plan_name": "A", "network_type": "Redtrain FTTP 100/20"}]
        result = normalise_plans(plans)
        self.assertEqual("Redtrain", result[0]["network_type"])
        self.assertEqual("Redtrain", result[0]["upstream_network"])
        self.assertEqual("FTTP", result[0]["access_technology"])

    def test_preserves_both_fields_for_compound_nbn_string(self):
        plans = [{"plan_name": "B", "network_type": "NBN FTTP"}]
        result = normalise_plans(plans)
        self.assertEqual("NBN FTTP", result[0]["network_type"])
        self.assertEqual("NBN", result[0]["upstream_network"])
        self.assertEqual("FTTP", result[0]["access_technology"])

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
