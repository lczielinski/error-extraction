"""The (S, D) domain and its transfer functions.

A pair (S, D) for a program z~ of class c means: z~ is defined at every v in B,
    z~ - z  in D    everywhere on B,   and   z~/z  in S   wherever z != 0.
BOTTOM (None) means the program may be undefined somewhere on B.
"""

from __future__ import annotations

import gmpy2
from gmpy2 import mpfr

from .interval import EMPTY, INF, ONE, TOP, ZERO, Iv

BOTTOM = None

NONNEG = Iv(0, INF)

u = mpfr(2) ** -53   # unit roundoff of the target format
U = Iv(1 - u, 1 + u)
UE = Iv(-u, u)


mantissa = 53        # of the target format, not of the bound arithmetic


def set_target(mantissa_bits: int) -> None:
    """53 for binary64, 24 for binary32."""
    global u, U, UE, mantissa
    mantissa = mantissa_bits
    u = mpfr(2) ** -mantissa_bits
    U = Iv(1 - u, 1 + u)
    UE = Iv(-u, u)


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


# -- reduced product ----------------------------------------------------


def enc(S: Iv, D: Iv, Ic: Iv) -> Iv:
    """enc_c(S,D): an enclosure of the computed value itself."""
    return (Ic + D).intersect(TOP if Ic.contains_zero else Ic * S)


def rho(S: Iv, D: Iv, Ic: Iv) -> tuple:
    """Refine each component by the other.  Needs alpha defined on all of B."""
    if Ic.contains_zero:
        return S, D
    return S.intersect(ONE + D / Ic), D.intersect(Ic * (S - ONE))


def _round(Sh: Iv, Dh: Iv, Ic: Iv) -> Pair:
    """Reduce the pre-rounding pair, then account for the operation's own rounding."""
    Sh, Dh = rho(Sh, Dh, Ic)
    Ih = enc(Sh, Dh, Ic)
    S, D = rho(Sh * U, Dh + UE * Ih, Ic)
    return Pair(S, D)


# -- transfer functions -------------------------------------------------


def constant(exact: bool, Ic: Iv) -> Pair:
    if exact:
        return EXACT
    return Pair(*rho(U, UE * Ic, Ic))


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
        # alpha^ is the convex combination lambda*alpha_1 + (1-lambda)*alpha_2,
        # affine in lambda, so its extremes sit at the ends of Lambda
        lam = Iv(0, 1).intersect(I1 / Ic)
        if not lam.is_empty:
            Sh = _combine(lam.lo, p1.S, p2.S).hull(_combine(lam.hi, p1.S, p2.S))
    return _round(Sh, Dh, Ic)


def _combine(t, S1: Iv, S2: Iv) -> Iv:
    ti = Iv(t, t)
    return ti * S1 + (ONE - ti) * S2


def sub(p1: Pair, p2: Pair, I1: Iv, I2: Iv, Ic: Iv) -> Pair:
    """x - y is x + (-y), with the right operand's pair and interval negated."""
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


def transfer(node, pairs: list, ivs: list, Ic: Iv) -> Pair:
    """Apply op_f for one e-node, given its children's pairs and intervals."""
    op = node.op
    if op in ("Var", "Num"):
        return EXACT
    if op == "Lit":
        return constant(False, Ic)
    if op == "Neg":
        return neg(pairs[0], Ic)
    if op == "Sqrt":
        return sqrt(pairs[0], ivs[0], Ic)
    f = {"Add": add, "Sub": sub, "Mul": mul, "Div": div}[op]
    return f(pairs[0], pairs[1], ivs[0], ivs[1], Ic)


# -- readouts -----------------------------------------------------------


def mu_d(p: Pair, Ic: Iv):
    """Bounds |ln(z~/z)|."""
    if Ic.contains_zero or p.S.lo <= 0:
        return INF
    return max(-gmpy2.log(p.S.lo), gmpy2.log(p.S.hi))


def mu_rel(p: Pair, Ic: Iv):
    """Bounds |z~ - z|/|z|."""
    if Ic.contains_zero:
        return INF
    return max(1 - p.S.lo, p.S.hi - 1)


def mu_abs(p: Pair, Ic: Iv):
    """Bounds |z~ - z|."""
    return max(-p.D.lo, p.D.hi)


METRICS = {"d": mu_d, "rel": mu_rel, "abs": mu_abs}
