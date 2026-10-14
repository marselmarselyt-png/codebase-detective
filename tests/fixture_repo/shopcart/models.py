"""Domain objects.

`Customer` and `LineItem` are plain data holders. They deliberately do no
validation beyond normalising the tier - the API layer is responsible for
rejecting malformed requests.
"""

from . import tiers


class LineItem:
    def __init__(self, sku, qty, unit_price):
        self.sku = sku
        self.qty = qty
        self.unit_price = unit_price

    @property
    def line_total(self):
        return round(self.qty * self.unit_price, 2)


class Customer:
    def __init__(self, name, tier=None):
        self.name = name
        self.tier = tiers.normalize(tier)


class Order:
    def __init__(self, customer, items, order_id=None):
        self.id = order_id
        self.customer = customer
        self.items = list(items)

    @property
    def subtotal(self):
        return round(sum(i.line_total for i in self.items), 2)