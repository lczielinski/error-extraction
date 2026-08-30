"""Intervals over MPFR, rounded outward.

Every operation returns (down, up), widened by an ulp exactly when it was
inexact: round to nearest can move an endpoint inward, which would drop a
value the interval must hold.  An exact result is left alone, since the
exactness rules in analysis.py turn on it.
"""

from __future__ import annotations

import gmpy2
from gmpy2 import mpfr

DEFAULT_PRECISION = 200


def set_precision(bits: int) -> None:
    gmpy2.get_context().precision = bits


set_precision(DEFAULT_PRECISION)

INF = mpfr("inf")
NINF = -INF


def _out(r):
    if not gmpy2.get_context().inexact or not gmpy2.is_finite(r):
        return r, r
    return gmpy2.next_below(r), gmpy2.next_above(r)


def _widen(f, *args):
    ctx = gmpy2.get_context()
    ctx.clear_flags()
    return _out(f(*args))


def _add(a, b):
    return _widen(lambda x, y: x + y, a, b)


def _add_lo(a, b):
    if a == NINF or b == NINF:
        return NINF
    return _add(a, b)[0]


def _add_hi(a, b):
    if a == INF or b == INF:
        return INF
    return _add(a, b)[1]


def _mul(a, b):
    # 0 * inf = 0
    if a == 0 or b == 0:
        return mpfr(0), mpfr(0)
    return _widen(lambda x, y: x * y, a, b)


def _recip(x):
    # 1/inf = 0
    if x == INF or x == NINF:
        return mpfr(0), mpfr(0)
    return _widen(lambda t: 1 / t, x)


def _sqrt(x):
    return _widen(gmpy2.sqrt, x)


def _signed_sqrt(t):
    if t < 0:
        lo, hi = _widen(gmpy2.sqrt, -t)
        return -hi, -lo
    return _widen(gmpy2.sqrt, t)


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
        return Iv(_add_lo(self.lo, other.lo), _add_hi(self.hi, other.hi))

    def __sub__(self, other: "Iv") -> "Iv":
        return self + (-other)

    def __mul__(self, other: "Iv") -> "Iv":
        if self.is_empty or other.is_empty:
            return EMPTY
        corners = (_mul(self.lo, other.lo), _mul(self.lo, other.hi),
                   _mul(self.hi, other.lo), _mul(self.hi, other.hi))
        return Iv(min(lo for lo, _ in corners), max(hi for _, hi in corners))

    def recip(self) -> "Iv":
        if self.is_empty:
            return EMPTY
        if self.contains_zero:
            return TOP
        return Iv(_recip(self.hi)[0], _recip(self.lo)[1])

    def __truediv__(self, other: "Iv") -> "Iv":
        return self * other.recip()

    def sqrt(self) -> "Iv":
        if self.is_empty or self.hi < 0:
            return EMPTY
        lo = self.lo if self.lo > 0 else mpfr(0)
        return Iv(_sqrt(lo)[0], _sqrt(self.hi)[1])

    def signed_sqrt(self) -> "Iv":
        if self.is_empty:
            return EMPTY
        return Iv(_signed_sqrt(self.lo)[0], _signed_sqrt(self.hi)[1])


TOP = Iv(NINF, INF)
EMPTY = Iv(INF, NINF)
ZERO = Iv(0, 0)
ONE = Iv(1, 1)
