"""Transport layer.

Parses JSON request bodies into service calls. The public HTTP contract is
documented in `docs/api.md`: every customer object carries `tier`.
"""

from . import service

TIER_FIELD = "customerTier"


def handle_checkout_request(body):
    """Handle a POST /checkout body. Returns the service result dict."""
    customer = body.get("customer") or {}
    items = [
        (i.get("sku"), int(i.get("qty", 0)), float(i.get("unitPrice", 0)))
        for i in body.get("items", [])
    ]
    return service.place_order(
        customer_name=customer.get("name", "anonymous"),
        tier=customer.get(TIER_FIELD),
        items=items,
        order_id=body.get("orderId"),
    )


def describe_benefit(tier):
    """GET /benefits - tells the storefront what discount a tier receives."""
    from .pricing import rate_for

    return {"rate": rate_for(tier)}