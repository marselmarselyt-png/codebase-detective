"""shopcart - a tiny order pipeline used as a Codebase Detective test fixture.

Deliberately contains cross-file bugs. See ../BUGS.md.
"""

from .models import Customer, LineItem, Order  # noqa: F401
from .service import place_order  # noqa: F401

__all__ = ["Customer", "LineItem", "Order", "place_order"]