"""Interval arithmetic with 200-bit endpoints, rounded outward (Appendix B)."""

import gmpy2
from gmpy2 import mpfr

# Negation and doubling use the default context, so it gets the same precision to keep them exact
gmpy2.get_context().precision = 200
DOWN = gmpy2.context(precision=200, round=gmpy2.RoundDown)
UP = gmpy2.context(precision=200, round=gmpy2.RoundUp)
INF = mpfr("inf")


class Iv:
    """A closed interval. One with an infinite endpoint is TOP, and any operation involving TOP
    returns TOP, except TOP & K = K and [0, 0] * TOP = [0, 0]."""

    __slots__ = ("lo", "hi")

    def __init__(self, lo, hi):
        self.lo = lo
        self.hi = hi

    def __eq__(self, other):
        return self.lo == other.lo and self.hi == other.hi

    def __hash__(self):
        return hash((self.lo, self.hi))

    def __repr__(self):
        return f"[{float(self.lo):.6g}, {float(self.hi):.6g}]"

    def __contains__(self, x):
        return self.lo <= x <= self.hi

    def __le__(self, other):
        """Containment."""
        return other.lo <= self.lo and self.hi <= other.hi

    @property
    def top(self):
        return self.lo == -INF or self.hi == INF

    @property
    def mag(self):
        """The largest |x| in the interval."""
        return max(self.hi, -self.lo)

    @property
    def mig(self):
        """The smallest |x| in the interval."""
        return max(self.lo, -self.hi, 0)

    def __and__(self, other):
        """Intersection."""
        return Iv(max(self.lo, other.lo), min(self.hi, other.hi))

    def __or__(self, other):
        """Hull."""
        return Iv(min(self.lo, other.lo), max(self.hi, other.hi))

    def __neg__(self):
        return Iv(-self.hi, -self.lo)

    def __add__(self, other):
        if self.top or other.top:
            return TOP
        return Iv(DOWN.add(self.lo, other.lo), UP.add(self.hi, other.hi))

    def __sub__(self, other):
        return self + -other

    def __mul__(self, other):
        if self.top or other.top:
            return ZERO if ZERO in (self, other) else TOP
        a, b, c, d = self.lo, self.hi, other.lo, other.hi
        return Iv(min(DOWN.mul(a, c), DOWN.mul(a, d), DOWN.mul(b, c), DOWN.mul(b, d)),
                  max(UP.mul(a, c), UP.mul(a, d), UP.mul(b, c), UP.mul(b, d)))

    def __truediv__(self, other):
        """K/L = K * TOP when 0 is in L, so [0, 0]/L = [0, 0]."""
        if other.top or 0 in other:
            return self * TOP
        return self * Iv(DOWN.div(1, other.hi), UP.div(1, other.lo))

    def sqrt(self):
        """The image of the interval's nonnegative part."""
        if self.top:
            return TOP
        return Iv(DOWN.sqrt(max(self.lo, 0)), UP.sqrt(self.hi))


TOP = Iv(-INF, INF)
ZERO = Iv(mpfr(0), mpfr(0))
ONE = Iv(mpfr(1), mpfr(1))
