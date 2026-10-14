"""Pricing rules.

Discounts are keyed by canonical tier name (see `tiers.CANONICAL_TIERS`).
Callers are expected to hand us an already-normalized tier; `apply_discount`
normalizes defensively because a wrong discount is worse than a crash.
"""

from .tiers import normalize

DISCOUNTS = {
    "STANDARD": 0.00,
    "GOLD": 0.05,
    "PLATINUM": 0.12,
}


def apply_discount(subtotal, tier):
    """Return the discounted subtotal for `subtotal` at `tier`."""
    rate = DISCOUNTS[normalize(tier)]
    return round(subtotal * (1 - rate), 2)


def rate_for(tier):
    """Expose the raw rate so the API layer can show customers their benefit."""
    return DISCOUNTS[normalize(tier)]