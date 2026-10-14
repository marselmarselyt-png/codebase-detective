"""Checkout service - the seam between the transport layer and the domain."""

from . import inventory, pricing
from .models import Customer, LineItem, Order


def place_order(customer_name, tier, items, order_id=None):
    """Reserve stock and price an order. Returns a result dict."""
    customer = Customer(customer_name, tier)
    order = Order(customer, [LineItem(*i) for i in items], order_id=order_id)

    for item in order.items:
        if not inventory.reserve(item.sku, item.qty):
            return {
                "ok": False,
                "error": "insufficient_stock",
                "sku": item.sku,
                "subtotal": order.subtotal,
                "total": None,
            }

    total = pricing.apply_discount(order.subtotal, customer.tier)
    return {
        "ok": True,
        "error": None,
        "subtotal": order.subtotal,
        "total": total,
        "discount_rate": pricing.rate_for(customer.tier),
        "tier_used": customer.tier,
    }