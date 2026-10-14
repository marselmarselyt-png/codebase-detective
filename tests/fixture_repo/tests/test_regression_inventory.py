"""Regression test for reservation ledger isolation.

A reservation ledger must never be shared between two independent calls: an
order that fails halfway through must not leave stock reserved for the next
customer, and a caller-supplied ledger must not leak into later orders.
"""

import unittest

from shopcart import inventory


class ReservationLedgerTests(unittest.TestCase):
    def setUp(self):
        inventory.reset()

    def tearDown(self):
        inventory.reset()

    def test_repeated_reservations_do_not_share_one_ledger(self):
        first = []
        second = []
        inventory.reserve("SKU-1", 2, first)
        inventory.reserve("SKU-1", 3, second)

        self.assertEqual(len(first), 1, "the first ledger must contain only its own reservation")
        self.assertEqual(len(second), 1, "the second ledger must contain only its own reservation")
        self.assertEqual(inventory.available("SKU-1"), 5)

    def test_default_ledger_does_not_accumulate_across_calls(self):
        inventory.reserve("SKU-2", 1)
        inventory.reserve("SKU-2", 1)

        self.assertEqual(inventory.available("SKU-2"), 2,
                         "reservations must be reflected in stock availability")

    def test_reserve_rejects_more_than_available(self):
        self.assertTrue(inventory.reserve("SKU-3", 0))
        self.assertFalse(inventory.reserve("SKU-3", 1))


if __name__ == "__main__":
    unittest.main()