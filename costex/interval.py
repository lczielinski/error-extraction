"""Intervals over MPFR, rounded outward.

Every operation computes its lower endpoint rounded down and its upper one
rounded up.  That leaves an exact result alone, which the exactness rules in
analysis.py turn on, and keeps the arithmetic monotone under inclusion, which
extraction's optimality turns on.

An interval is bounded or TOP, "no bound could be derived".  To arithmetic,
one unbounded on either side is TOP, and any operation involving TOP returns
TOP, with two exceptions: TOP meet K is K, and 0 * TOP is 0, since TOP is
still a real.  The second is load bearing: an exactly computed radicand that
can be zero has d1 = 0 over sqrt(x~) + sqrt(x), which straddles zero.
"""

from __future__ import annotations

import gmpy2
from gmpy2 import mpfr

DEFAULT_PRECISION = 200

DOWN = gmpy2.context(round=gmpy2.RoundDown)
UP = gmpy2.context(round=gmpy2.RoundUp)


def set_precision(bits: int) -> None:
    for ctx in (gmpy2.get_context(), DOWN, UP):
        ctx.precision = bits


set_precision(DEFAULT_PRECISION)

INF = mpfr("inf")
NINF = -INF


def _add_lo(a, b):
    return DOWN.add(a, b)


def _add_hi(a, b):
    return UP.add(a, b)


def _mul(a, b):
    return DOWN.mul(a, b), UP.mul(a, b)


def _recip(x):
    return DOWN.div(1, x), UP.div(1, x)


def _sqrt(x):
    return DOWN.sqrt(x), UP.sqrt(x)


def _fmt(x) -> str:
    if x == INF:
        return "inf"
    if x == NINF:
        return "-inf"
    return f"{float(x):.6g}"


class Iv:
    """A closed interval [lo, hi], empty when lo > hi."""

    __slots__ = ("lo", "hi")

    def __init__(self, lo, hi):
        self.lo = mpfr(lo)
        self.hi = mpfr(hi)

    @property
    def is_empty(self) -> bool:
        return self.lo > self.hi

    def __repr__(self) -> str:
        if self.is_empty:
            return "[]"
        return f"[{_fmt(self.lo)}, {_fmt(self.hi)}]"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Iv):
            return NotImplemented
        if self.is_empty or other.is_empty:
            return self.is_empty and other.is_empty
        return self.lo == other.lo and self.hi == other.hi

    def __hash__(self) -> int:
        if self.is_empty:
            return hash("empty")
        return hash((float(self.lo), float(self.hi)))

    @property
    def is_top(self) -> bool:
        return self.lo == NINF or self.hi == INF

    @property
    def contains_zero(self) -> bool:
        return self.lo <= 0 <= self.hi

    @property
    def mag(self):
        return max(abs(self.lo), abs(self.hi))

    @property
    def mig(self):
        if self.contains_zero:
            return mpfr(0)
        return min(abs(self.lo), abs(self.hi))

    def issubset(self, other: "Iv") -> bool:
        if self.is_empty:
            return True
        if other.is_empty:
            return False
        return other.lo <= self.lo and self.hi <= other.hi

    def hull(self, other: "Iv") -> "Iv":
        if self.is_empty:
            return other
        if other.is_empty:
            return self
        return Iv(min(self.lo, other.lo), max(self.hi, other.hi))

    def intersect(self, other: "Iv") -> "Iv":
        if self.is_empty or other.is_empty:
            return EMPTY
        return Iv(max(self.lo, other.lo), min(self.hi, other.hi))

    def __neg__(self) -> "Iv":
        if self.is_empty:
            return EMPTY
        return Iv(-self.hi, -self.lo)

    def __add__(self, other: "Iv") -> "Iv":
        if self.is_empty or other.is_empty:
            return EMPTY
        if self.is_top or other.is_top:
            return TOP
        return Iv(_add_lo(self.lo, other.lo), _add_hi(self.hi, other.hi))

    def __sub__(self, other: "Iv") -> "Iv":
        return self + (-other)

    def __mul__(self, other: "Iv") -> "Iv":
        if self.is_empty or other.is_empty:
            return EMPTY
        if self.is_top or other.is_top:
            return ZERO if ZERO in (self, other) else TOP
        corners =(_mul(self.lo, other.lo), _mul(self.lo, other.hi),
                   _mul(self.hi, other.lo), _mul(self.hi, other.hi))
        return Iv(min(lo for lo, _ in corners), max(hi for _, hi in corners))

    def recip(self) -> "Iv":
        if self.is_empty:
            return EMPTY
        if self.is_top or self.contains_zero:
            return TOP
        return Iv(_recip(self.hi)[0], _recip(self.lo)[1])

    def __truediv__(self, other: "Iv") -> "Iv":
        return self * other.recip()

    def sqrt(self) -> "Iv":
        if self.is_empty:
            return EMPTY
        if self.is_top:
            return TOP
        if self.hi < 0:
            return EMPTY
        lo = self.lo if self.lo > 0 else mpfr(0)
        return Iv(_sqrt(lo)[0], _sqrt(self.hi)[1])


TOP = Iv(NINF, INF)
EMPTY = Iv(INF, NINF)
ZERO = Iv(0, 0)
ONE = Iv(1, 1)
