import unittest

from shopcart.pricing import apply_discount, rate_for
from shopcart.tiers import normalize


class NormalizeTests(unittest.TestCase):
    def test_aliases_map_to_canonical_names(self):
        self.assertEqual(normalize("gold"), "GOLD")
        self.assertEqual(normalize("Premium"), "GOLD")
        self.assertEqual(normalize("enterprise"), "PLATINUM")

    def test_unknown_tier_falls_back_to_standard(self):
        self.assertEqual(normalize("diamond-ish"), "STANDARD")
        self.assertEqual(normalize(None), "STANDARD")


class PricingTests(unittest.TestCase):
    def test_standard_customer_pays_full_price(self):
        self.assertEqual(apply_discount(100.0, "standard"), 100.0)

    def test_gold_customer_gets_five_percent(self):
        self.assertEqual(apply_discount(100.0, "gold"), 95.0)

    def test_rate_for_matches_applied_discount(self):
        self.assertAlmostEqual(rate_for("gold"), 0.05)


if __name__ == "__main__":
    unittest.main()