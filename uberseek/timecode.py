"""Time as exact rational seconds.

Positions inside a stream are integer presentation timestamps (pts) in the stream's own time base.
Positions a caller asks for are rational seconds. Floats are never used for time.
"""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction

Seconds = Fraction


def seconds(value: str | int | float | Decimal | Fraction) -> Seconds:
    """Parse seconds: 12, "12.5", "1:02:03.5", "7/2" or a Fraction."""
    if isinstance(value, Fraction):
        return value
    if isinstance(value, float):
        value = repr(value)
    if isinstance(value, str) and ":" in value:
        total = Fraction(0)
        for part in value.split(":"):
            total = total * 60 + Fraction(part)
        return total
    return Fraction(value)


def clock(t: Seconds) -> str:
    """Format as M:SS.mmm (H:MM:SS.mmm past an hour), rounded down to the millisecond."""
    ms = int(t * 1000)
    sign, ms = ("-" if ms < 0 else ""), abs(ms)
    h, rest = divmod(ms, 3_600_000)
    m, rest = divmod(rest, 60_000)
    s, ms = divmod(rest, 1000)
    head = f"{h}:{m:02d}" if h else f"{m}"
    return f"{sign}{head}:{s:02d}.{ms:03d}"
