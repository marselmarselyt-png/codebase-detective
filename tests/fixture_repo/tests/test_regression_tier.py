"""Regression test for the cross-file tier bug.

The pricing unit tests pass on their own because they construct a tier string
directly. The bug only appears on the HTTP path, where the tier travels as a
JSON field through `api` -> `service` -> `models.Customer` -> `pricing`.
"""

import unittest

from shopcart.api import handle_checkout_request


def checkout_body(tier="gold"):
    return {
        "orderId": "A-1001",
        "customer": {"name": "Rina", "tier": tier},
        "items": [{"sku": "SKU-1", "qty": 2, "unitPrice": 25.00}],
    }


class CheckoutTierTests(unittest.TestCase):
    def test_documented_payload_field_is_honoured(self):
        result = handle_checkout_request(checkout_body("gold"))

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["subtotal"], 50.0)
        self.assertEqual(result["tier_used"], "GOLD")
        self.assertEqual(result["total"], 47.5, "gold customers must receive the 5% discount")

    def test_alternative_spellings_survive_the_transport_layer(self):
        for spelling in ("premium", "PLATINUM", "enterprise"):
            with self.subTest(spelling=spelling):
                result = handle_checkout_request(checkout_body(spelling))
                self.assertNotEqual(
                    result["tier_used"], "STANDARD", f"{spelling!r} was silently downgraded"
                )

    def test_standard_customer_is_unaffected(self):
        result = handle_checkout_request(checkout_body("standard"))
        self.assertEqual(result["tier_used"], "STANDARD")
        self.assertEqual(result["total"], 50.0)


if __name__ == "__main__":
    unittest.main()