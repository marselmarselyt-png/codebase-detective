"""Customer tier vocabulary.

Single source of truth for the canonical tier names used by the pricing
engine. Everything else in the system is expected to pass tiers through
`normalize` before comparing them against `DISCOUNTS`.
"""

CANONICAL_TIERS = ("STANDARD", "GOLD", "PLATINUM")

TIER_ALIASES = {
    "standard": "STANDARD",
    "basic": "STANDARD",
    "free": "STANDARD",
    "gold": "GOLD",
    "premium": "GOLD",
    "platinum": "PLATINUM",
    "enterprise": "PLATINUM",
}


def normalize(raw):
    """Map any accepted spelling to a canonical tier name.

    Unknown or missing values fall back to STANDARD: the shop never refuses
    to sell because of a typo in the tier field.
    """
    if raw is None:
        return "STANDARD"
    return TIER_ALIASES.get(str(raw).strip().lower(), "STANDARD")