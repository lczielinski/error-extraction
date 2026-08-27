"""The (S, D) domain and its transfer functions.

(S, D) for a program z~ of class c: z~ is defined everywhere on B,
z~ - z in D on B, and z~/z in S wherever z != 0.  BOTTOM: may be undefined.
"""

from __future__ import annotations

import gmpy2
from gmpy2 import mpfr

from .interval import INF, ONE, TOP, ZERO, Iv

BOTTOM = None

NONNEG = Iv(0, INF)

mantissa = 53              # of the target format, not of the bound arithmetic
u = mpfr(2) ** -53
eta = mpfr(2) ** -1075

EMIN = {53: -1022, 24: -126}


def set_target(mantissa_bits: int) -> None:
    """53 for binary64, 24 for binary32."""
    global u, eta, mantissa
    mantissa = mantissa_bits
    u = mpfr(2) ** -mantissa_bits
    eta = mpfr(2) ** (EMIN[mantissa_bits] - mantissa_bits)


def ufp(x):
    """2^floor(log2|x|)."""
    x = abs(x)
    if x == 0:
        return mpfr(0)
    if not gmpy2.is_finite(x):
        return INF
    return mpfr(2) ** (gmpy2.frexp(x)[0] - 1)


def gamma(I: Iv) -> Iv:
    """fl(t) - t for every t in I."""
    m = I.mag
    if m == 0:
        return ZERO
    g = max(u * ufp(m), eta)
    return Iv(-g, g)


def urel(I: Iv) -> Iv:
    """fl(t)/t for every nonzero t in I."""
    q = I.mig
    r = mpfr(1) if q == 0 else min(mpfr(1), max(u, eta / q))
    return Iv(1 - r, 1 + r)


class Pair:
    __slots__ = ("S", "D")

    def __init__(self, S: Iv, D: Iv):
        self.S = S
        self.D = D

    def precedes(self, other: "Pair") -> bool:
        return self.S.issubset(other.S) and self.D.issubset(other.D)

    def is_top(self) -> bool:
        return self.S == TOP and self.D == TOP

    def __eq__(self, other):
        return isinstance(other, Pair) and self.S == other.S and self.D == other.D

    def __hash__(self):
        return hash((self.S, self.D))

    def __repr__(self):
        return f"(S={self.S}, D={self.D})"


EXACT = Pair(ONE, ZERO)
TOP_PAIR = Pair(TOP, TOP)


def enc(S: Iv, D: Iv, Ic: Iv) -> Iv:
    """An enclosure of the computed value itself."""
    return (Ic + D).intersect(TOP if Ic.contains_zero else Ic * S)


def rho(S: Iv, D: Iv, Ic: Iv) -> tuple:
    """Refine each component by the other."""
    if Ic.contains_zero:
        return S, D
    return S.intersect(ONE + D / Ic), D.intersect(Ic * (S - ONE))


def _round(Sh: Iv, Dh: Iv, Ic: Iv) -> Pair:
    """Reduce the pre-rounding pair, then add this operation's rounding."""
    Sh, Dh = rho(Sh, Dh, Ic)
    Ih = enc(Sh, Dh, Ic)
    S, D = rho(Sh * urel(Ih), Dh + gamma(Ih), Ic)
    return Pair(S, D)


def constant(exact: bool, Ic: Iv) -> Pair:
    if exact:
        return EXACT
    return Pair(*rho(urel(Ic), gamma(Ic), Ic))


def neg(p: Pair, Ic: Iv) -> Pair:
    if p is BOTTOM:
        return BOTTOM
    if p.is_top():
        return TOP_PAIR
    return Pair(*rho(p.S, -p.D, Ic))


def mul(p1: Pair, p2: Pair, I1: Iv, I2: Iv, Ic: Iv) -> Pair:
    if p1 is BOTTOM or p2 is BOTTOM:
        return BOTTOM
    if p1.is_top() or p2.is_top():
        return TOP_PAIR
    It1, It2 = enc(p1.S, p1.D, I1), enc(p2.S, p2.D, I2)
    Sh = p1.S * p2.S
    Dh = (It2 * p1.D + I1 * p2.D).intersect(I2 * p1.D + It1 * p2.D)
    return _round(Sh, Dh, Ic)


def add(p1: Pair, p2: Pair, I1: Iv, I2: Iv, Ic: Iv) -> Pair:
    if p1 is BOTTOM or p2 is BOTTOM:
        return BOTTOM
    if p1.is_top() or p2.is_top():
        return TOP_PAIR
    Dh = p1.D + p2.D
    same_sign = (I1.lo > 0 and I2.lo > 0) or (I1.hi < 0 and I2.hi < 0)
    Sh = TOP
    if same_sign:
        # affine in lambda, so the extremes sit at the ends of Lambda
        lam = Iv(0, 1).intersect(I1 / Ic)
        if not lam.is_empty:
            Sh = _combine(lam.lo, p1.S, p2.S).hull(_combine(lam.hi, p1.S, p2.S))
    return _round(Sh, Dh, Ic)


def _combine(t, S1: Iv, S2: Iv) -> Iv:
    ti = Iv(t, t)
    return ti * S1 + (ONE - ti) * S2


def sub(p1: Pair, p2: Pair, I1: Iv, I2: Iv, Ic: Iv) -> Pair:
    if p2 is BOTTOM:
        return BOTTOM
    return add(p1, Pair(p2.S, -p2.D), I1, -I2, Ic)


def div(p1: Pair, p2: Pair, I1: Iv, I2: Iv, Ic: Iv) -> Pair:
    if p1 is BOTTOM or p2 is BOTTOM:
        return BOTTOM
    It2 = enc(p2.S, p2.D, I2)
    if p2.S.contains_zero and It2.contains_zero:
        return BOTTOM          # the divisor may round to zero
    Sh = TOP if p2.S.contains_zero else p1.S / p2.S
    if It2.contains_zero:
        Dh = TOP
    else:
        Dh = (p1.D - I1 * (p2.S - ONE)).intersect(p1.D - Ic * p2.D) / It2
    return _round(Sh, Dh, Ic)


def sqrt(p1: Pair, I1: Iv, Ic: Iv) -> Pair:
    if p1 is BOTTOM:
        return BOTTOM
    It1 = enc(p1.S, p1.D, I1)
    It1p = It1.intersect(NONNEG)
    if not (It1p == It1 or (p1.S.lo >= 0 and I1.lo > 0)):
        return BOTTOM          # the radicand may round negative
    Sh = p1.S.sqrt()
    Dh = (p1.D / (It1p.sqrt() + I1.sqrt())).intersect(p1.D.signed_sqrt())
    return _round(Sh, Dh, Ic)


_BINARY = {"add": add, "sub": sub, "mul": mul, "div": div}


def transfer(op: str, pairs: list, ivs: list, Ic: Iv) -> Pair:
    if op == "neg":
        return neg(pairs[0], Ic)
    if op == "sqrt":
        return sqrt(pairs[0], ivs[0], Ic)
    return _BINARY[op](pairs[0], pairs[1], ivs[0], ivs[1], Ic)


def mu_rel(p: Pair, Ic: Iv):
    """Bounds |z~ - z|/|z|."""
    if Ic.contains_zero:
        return INF
    return max(1 - p.S.lo, p.S.hi - 1)


def mu_abs(p: Pair, Ic: Iv):
    """Bounds |z~ - z|."""
    return max(-p.D.lo, p.D.hi)


METRICS = {"abs": mu_abs, "rel": mu_rel}
