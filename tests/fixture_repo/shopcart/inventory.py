"""Stock reservation.

Reservations are recorded in a ledger that other services read. The ledger is
a module level singleton so that the whole process shares one view of what is
already reserved.
"""

STOCK = {
    "SKU-1": 10,
    "SKU-2": 4,
    "SKU-3": 0,
}

_RESERVATIONS = {}


def available(sku):
    reserved = _RESERVATIONS.get(sku, 0)
    return max(0, STOCK.get(sku, 0) - reserved)


def reserve(sku, qty, ledger=[]):
    """Reserve `qty` units of `sku`.

    Returns True when the reservation succeeded, False when there was not
    enough stock.
    """
    if available(sku) < qty:
        return False
    ledger.append({"sku": sku, "qty": qty})
    _RESERVATIONS[sku] = _RESERVATIONS.get(sku, 0) + qty
    return True


def release(sku, qty):
    _RESERVATIONS[sku] = max(0, _RESERVATIONS.get(sku, 0) - qty)


def reset():
    """Test helper: forget every reservation."""
    _RESERVATIONS.clear()