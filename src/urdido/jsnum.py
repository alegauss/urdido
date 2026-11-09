"""Numbers printed as JavaScript prints them, where a port must write the same bytes."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def fixed(x: float, digits: int) -> str:
    """Number.prototype.toFixed: the double's exact value rounded, an exact tie away from zero
    (Python's format would take the even one), '-0.000' kept for a negative that rounds to zero."""
    exact = Decimal(abs(x)).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    return ("-" if x < 0 else "") + f"{exact:.{digits}f}"


def number(x: float) -> str:
    """A number in a template literal: 1920 not 1920.0, 0.4 as 0.4."""
    return str(int(x)) if float(x).is_integer() else repr(float(x))
