"""The (S, D) domain and its transfer functions.

(S, D) for a program z~ of class c: z~ is defined everywhere on B,
z~ - z in D on B, and z~/z in S wherever z != 0.  BOTTOM: may be undefined,
which includes may overflow.  So a pair always bounds z~, and (TOP, TOP) --
which does not -- is never the result of an operation.

Every operation follows the paper's recursive definition: compute the
pre-rounding pair (S^, D^), then hand it to _finish, which reduces it, bounds
the pre-rounding value X^, and either returns it (an exact operation) or
rounds it.
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
tiny = mpfr(2) ** -1022
omega = (mpfr(2) - mpfr(2) ** -52) * mpfr(2) ** 1023

EMIN = {53: -1022, 24: -126}


def set_target(mantissa_bits: int) -> None:
    global u, eta, mantissa, tiny, omega
    mantissa = mantissa_bits
    emin = EMIN[mantissa_bits]
    u = mpfr(2) ** -mantissa_bits
    eta = mpfr(2) ** (emin - mantissa_bits)
    tiny = mpfr(2) ** emin
    omega = (mpfr(2) - mpfr(2) ** (1 - mantissa_bits)) * mpfr(2) ** (1 - emin)


def _div_up(a, b):
    """A bound on a deviation, so never rounded down."""
    ctx = gmpy2.get_context()
    ctx.clear_flags()
    q = a / b
    if not ctx.inexact or not gmpy2.is_finite(q):
        return q
    return gmpy2.next_above(q)


def ufp(x):
    x = abs(x)
    if x == 0:
        return mpfr(0)
    if not gmpy2.is_finite(x):
        return INF
    return mpfr(2) ** (gmpy2.frexp(x)[0] - 1)


def gamma(I: Iv) -> Iv:
    """Gamma_a: fl(r) - r for r in I, from |fl(r) - r| <= max(u ufp(r), eta).

    Zero rounds exactly, so I = {0} gets none.
    """
    m = I.mag
    if m == 0:
        return ZERO
    g = max(u * ufp(m), eta)     # exact: powers of two
    return Iv(-g, g)


def urel(I: Iv) -> Iv:
    """Gamma_r: fl(r)/r for nonzero r in I.

    The sup of max(u ufp(r), eta) / |r| over I.  u ufp(r)/|r| is u at a power
    of two and falls across each binade, so it is u unless I lies within one
    binade, where it peaks at the smallest magnitude m; eta/|r| peaks there too.
    """
    m = I.mig
    if m == 0:
        r = mpfr(1)
    else:
        q = _div_up(u * ufp(m), m) if ufp(I.mag) == ufp(m) else u
        r = min(mpfr(1), max(q, _div_up(eta, m)))
    return ONE + Iv(-r, r)       # the sum rounds outward


class Pair:
    __slots__ = ("S", "D")

    def __init__(self, S: Iv, D: Iv):
        self.S = S
        self.D = D

    def precedes(self, other: "Pair") -> bool:
        return self.S.issubset(other.S) and self.D.issubset(other.D)

    def __eq__(self, other):
        return isinstance(other, Pair) and self.S == other.S and self.D == other.D

    def __hash__(self):
        return hash((self.S, self.D))

    def __repr__(self):
        return f"(S={self.S}, D={self.D})"


EXACT = Pair(ONE, ZERO)


def enc(S: Iv, D: Iv, Ic: Iv) -> Iv:
    """X~: where the computed value lies, given its pair."""
    return (Ic + D).intersect(TOP if Ic.contains_zero else Ic * S)


def rho(S: Iv, D: Iv, Ic: Iv) -> tuple:
    """The reduction: each component refined by the other."""
    if Ic.contains_zero:
        return S, D
    return S.intersect(ONE + D / Ic), D.intersect(Ic * (S - ONE))


def _never(Ih: Iv) -> bool:
    return False


def _finish(Sh: Iv, Dh: Iv, Ic: Iv, exact=_never) -> Pair:
    """From the pre-rounding pair to the operation's pair.

    Reduce it, bound the pre-rounding value by X^, and give up if that may
    overflow, which gamma and urel also need it not to.  An exact operation
    returns the pair as it is; any other rounds it.
    """
    Sh, Dh = rho(Sh, Dh, Ic)
    Ih = enc(Sh, Dh, Ic)
    if Ih.mag > omega:
        return BOTTOM
    if exact(Ih):
        return Pair(Sh, Dh)
    return Pair(*rho(Sh * urel(Ih), Dh + gamma(Ih), Ic))


def pow2(p: Pair, I: Iv):
    """k when the operand is computed exactly and is the constant +-2^k."""
    if p != EXACT or I.lo != I.hi or I.lo == 0 or not gmpy2.is_finite(I.lo):
        return None
    e, m = gmpy2.frexp(abs(I.lo))       # (exponent, mantissa), m in [1/2, 1)
    return e - 1 if m == 0.5 else None


def scales_exactly(k, Ih: Iv) -> bool:
    """Scaling by 2^k is exact unless it shrinks a value below 2^emin."""
    return k >= 0 or Ih.mig >= tiny


def sterbenz(It1: Iv, It2: Iv) -> bool:
    """x~ + y~ is exact when -y~/x~ lies in [1/2, 2] (Sterbenz's lemma).

    Checked as b/2 <= a <= 2b on a = x~, b = -y~ with matching signs, which
    is exact where the interval quotient would round.
    """
    It2 = -It2
    if It1.lo > 0 and It2.lo > 0:
        a, b = It1, It2
    elif It1.hi < 0 and It2.hi < 0:
        a, b = -It1, -It2
    else:
        return False
    return 2 * a.lo >= b.hi and a.hi <= 2 * b.lo


def constant(exact: bool, Ic: Iv) -> Pair:
    return _finish(ONE, ZERO, Ic, lambda Ih: exact)


def neg(p: Pair, Ic: Iv) -> Pair:
    if p is BOTTOM:
        return BOTTOM
    return Pair(*rho(p.S, -p.D, Ic))


def _lam(I1: Iv, I2: Iv, Ic: Iv):
    """An enclosure of lambda = x/z, or None when there is none.

    lambda = x/z, 1 - lambda = y/z and lambda = 1/(1 + y/x), so each quotient
    encloses it.  The last also puts a same-signed sum's lambda in (0, 1).
    """
    if I1.contains_zero or I2.contains_zero:
        return None
    lam = (I1 / Ic).intersect(ONE - I2 / Ic).intersect((ONE + I2 / I1).recip())
    if lam.is_empty or lam.lo == -INF or lam.hi == INF:
        return None
    return lam


def kappa(I1: Iv, I2: Iv, Ic: Iv):
    """A bound on the atomic condition number of x + y.

    Pointwise (|x| + |y|) / |x + y| = |lambda| + |1 - lambda|, exactly 1 for a
    same-signed sum.  Taking each magnitude over the interval separately
    overestimates, but lambda in [0,1] still bounds both by 1, so a same-signed
    sum never exceeds 2 however wide its intervals: above that is cancellation.
    """
    lam = _lam(I1, I2, Ic)
    if lam is None:
        return INF
    return lam.mag + (ONE - lam).mag


def _combine(t, S1: Iv, S2: Iv) -> Iv:
    ti = Iv(t, t)
    return ti * S1 + (ONE - ti) * S2


def _ratio(p1: Pair, p2: Pair, I1: Iv, I2: Iv, Ic: Iv) -> Iv:
    """S^ of a sum: z~/z = lambda s1 + (1 - lambda) s2, linear in lambda."""
    lam = _lam(I1, I2, Ic)
    if lam is None:
        return TOP
    return _combine(lam.lo, p1.S, p2.S).hull(_combine(lam.hi, p1.S, p2.S))


def add(p1: Pair, p2: Pair, I1: Iv, I2: Iv, Ic: Iv) -> Pair:
    if p1 is BOTTOM or p2 is BOTTOM:
        return BOTTOM
    Sh = _ratio(p1, p2, I1, I2, Ic)
    Dh = p1.D + p2.D
    It1, It2 = enc(p1.S, p1.D, I1), enc(p2.S, p2.D, I2)
    return _finish(Sh, Dh, Ic, lambda Ih: sterbenz(It1, It2))


def sub(p1: Pair, p2: Pair, I1: Iv, I2: Iv, Ic: Iv) -> Pair:
    if p2 is BOTTOM:
        return BOTTOM
    return add(p1, Pair(p2.S, -p2.D), I1, -I2, Ic)


def mul(p1: Pair, p2: Pair, I1: Iv, I2: Iv, Ic: Iv) -> Pair:
    """x~ y~ - x y = x d2 + y d1 + d1 d2."""
    if p1 is BOTTOM or p2 is BOTTOM:
        return BOTTOM
    Sh = p1.S * p2.S
    Dh = I1 * p2.D + I2 * p1.D + p1.D * p2.D
    k1, k2 = pow2(p1, I1), pow2(p2, I2)
    return _finish(Sh, Dh, Ic, lambda Ih: any(k is not None and scales_exactly(k, Ih)
                                               for k in (k1, k2)))


def div(p1: Pair, p2: Pair, I1: Iv, I2: Iv, Ic: Iv) -> Pair:
    """x~/y~ - x/y = (d1 - x (s2 - 1)) / y~."""
    if p1 is BOTTOM or p2 is BOTTOM:
        return BOTTOM
    It2 = enc(p2.S, p2.D, I2)
    if It2.contains_zero:
        return BOTTOM          # the divisor may round to zero
    Sh = p1.S / p2.S
    Dh = (p1.D - I1 * (p2.S - ONE)) / It2
    k = pow2(p2, I2)
    return _finish(Sh, Dh, Ic, lambda Ih: k is not None and scales_exactly(-k, Ih))


def sqrt(p1: Pair, I1: Iv, Ic: Iv) -> Pair:
    """sqrt(x~) - sqrt(x) = d1 / (sqrt(x~) + sqrt(x))."""
    if p1 is BOTTOM:
        return BOTTOM
    It1 = enc(p1.S, p1.D, I1)
    if not It1.issubset(NONNEG):
        return BOTTOM          # the radicand may round negative
    Sh = p1.S.sqrt()
    Dh = p1.D / (It1.sqrt() + I1.sqrt())
    return _finish(Sh, Dh, Ic)


def ifprop(pt: Pair, pe: Pair, Ic: Iv) -> Pair:
    """A guarded node: the hull of its arms.

    Exactly one arm runs at each v and each arm's pair holds where its guard
    selects, so the hull holds on all of B.  A comparison is exact, so the guard
    adds no rounding; what makes the arms' assumptions legitimate is that the
    guard compares a variable with zero, which extract.py insists on.
    """
    if pt is BOTTOM or pe is BOTTOM:
        return BOTTOM
    return Pair(*rho(pt.S.hull(pe.S), pt.D.hull(pe.D), Ic))


def ctx(p: Pair, Ic: Iv) -> Pair:
    """A context does not change the program, only what is known about it.

    So the pair passes through -- but through rho with the context's own
    interval, which is tighter than the subject's and is where the whole point
    of a context lands.
    """
    if p is BOTTOM:
        return BOTTOM
    return Pair(*rho(p.S, p.D, Ic))


_BINARY = {"add": add, "sub": sub, "mul": mul, "div": div}


def transfer(op: str, pairs: list, ivs: list, Ic: Iv) -> Pair:
    if op == "neg":
        return neg(pairs[0], Ic)
    if op == "sqrt":
        return sqrt(pairs[0], ivs[0], Ic)
    if op == "ifprop":
        return ifprop(pairs[0], pairs[1], Ic)
    if op == "ctx":
        return ctx(pairs[0], Ic)
    return _BINARY[op](pairs[0], pairs[1], ivs[0], ivs[1], Ic)


def mu_rel(p: Pair, Ic: Iv):
    if Ic.contains_zero:
        return INF
    return max(1 - p.S.lo, p.S.hi - 1)


def mu_abs(p: Pair, Ic: Iv):
    return max(-p.D.lo, p.D.hi)


METRICS = {"abs": mu_abs, "rel": mu_rel}
