"""The error analysis of Section 4: err(t) = (S, D) with x~/x in S and x~ - x in D, or FAIL."""

from collections import namedtuple

import gmpy2

from .interval import ONE, TOP, UP, ZERO, Iv

Pair = namedtuple("Pair", "S D")
FAIL = None
EXACT = Pair(ONE, ZERO)
FORMATS = {"binary64": (53, -1022), "binary32": (24, -126)}


def set_format(name):
    global U, ETA, TINY, OMEGA, FLOATS
    p, emin = FORMATS[name]
    FLOATS = gmpy2.ieee(64 if name == "binary64" else 32)
    U, ETA, TINY = gmpy2.exp2(-p), gmpy2.exp2(emin - p), gmpy2.exp2(emin)
    OMEGA = (2 - 2 * U) * gmpy2.exp2(1 - emin)


set_format("binary64")


def precedes(e1, e2):
    return e1.S <= e2.S and e1.D <= e2.D


def computed(I, e):
    """X~, where the computed value lies."""
    return I + e.D if 0 in I else (I + e.D) & (I * e.S)


def reduce(I, S, D):
    return Pair(S & (ONE + D / I), D if 0 in I else D & (I * (S - ONE)))


def ufp(r):
    return gmpy2.exp2(gmpy2.frexp(r)[0] - 1)


def ufp_below(M):
    """The largest ufp(r) of a non-float r with |r| <= M."""
    return ufp(M) / 2 if ufp(M) == M else ufp(M)


def gamma_a(Ih, eta):
    return max(U * ufp_below(Ih.mag), eta) if Ih.mag else 0


def gamma_r(Ih, eta):
    m = Ih.mig
    if m == 0:
        return 1 if eta else U
    g = UP.div(U * ufp(m), m) if ufp(m) == ufp_below(Ih.mag) else U
    return min(1, max(g, UP.div(eta, m)))


def rounded(I, S, D, J=TOP, exact=False, scale=None, sum=False):
    """The pair after rounding, from the pair before it and J = f(X~, Y~). scale is k when the
    operation multiplies by 2^k; a sum has no eta."""
    e = reduce(I, S, D)
    Ih = computed(I, e) & J
    if Ih.mag > OMEGA:
        return FAIL
    if exact or Ih.lo == Ih.hi == FLOATS.plus(Ih.lo) or scale is not None and (scale >= 0 or Ih.mig >= TINY):
        return e
    eta = 0 if sum else ETA
    g, h = gamma_r(Ih, eta), gamma_a(Ih, eta)
    return reduce(I, e.S * (ONE + Iv(-g, g)), e.D + Iv(-h, h))


def power_of_two(X, e, const):
    """k if the operand's class is the constant 2^k or -2^k and its pair is EXACT."""
    if const and e == EXACT:
        k, m = gmpy2.frexp(X.lo)
        if abs(m) == 0.5:
            return k - 1


def sterbenz(Xt, Yt):
    a, b = (Xt, -Yt) if Xt.lo > 0 else (-Xt, Yt)
    return a.lo > 0 and b.lo > 0 and b.hi <= 2 * a.lo and a.hi <= 2 * b.lo


def mix(lam, S1, S2):
    L = Iv(lam, lam)
    return L * S1 + (ONE - L) * S2


def add(I, X, Y, e1, e2):
    S = TOP
    if 0 not in X and 0 not in Y:
        lam = (X / I) & (ONE - Y / I) & (ONE / (ONE + Y / X))
        S = mix(lam.lo, e1.S, e2.S) | mix(lam.hi, e1.S, e2.S)
    Xt, Yt = computed(X, e1), computed(Y, e2)
    return rounded(I, S, e1.D + e2.D, Xt + Yt, exact=sterbenz(Xt, Yt), sum=True)


def mul(I, X, Y, e1, e2, c1, c2):
    ks = [k for k in (power_of_two(X, e1, c1), power_of_two(Y, e2, c2)) if k is not None]
    D = X * e2.D + Y * e1.D + e1.D * e2.D
    return rounded(I, e1.S * e2.S, D, computed(X, e1) * computed(Y, e2), scale=max(ks, default=None))


def div(I, X, Y, e1, e2, c2):
    Yt = computed(Y, e2)
    if 0 in Yt:
        return FAIL
    k = power_of_two(Y, e2, c2)
    D = (e1.D - X * (e2.S - ONE)) / Yt
    return rounded(I, e1.S / e2.S, D, computed(X, e1) / Yt, scale=None if k is None else -k)


def sqrt(I, X, e1):
    Xt = computed(X, e1)
    if Xt.lo < 0:
        return FAIL
    return rounded(I, e1.S.sqrt(), e1.D / (Xt.sqrt() + X.sqrt()), Xt.sqrt())


def err(op, I, Xs, es, consts):
    """err_s of a node, from its class's interval I, its children's intervals Xs and costs es,
    and whether each child's class holds a constant."""
    if FAIL in es:
        return FAIL
    match op:
        case "Var" | "Num":
            return EXACT
        case "Lit":
            return rounded(I, ONE, ZERO)
        case "Neg":
            return reduce(I, es[0].S, -es[0].D)
        case "Ctx":
            return reduce(I, *es[0])
        case "If":
            return reduce(I, es[0].S | es[1].S, es[0].D | es[1].D)
        case "Add":
            return add(I, *Xs, *es)
        case "Mul":
            return mul(I, *Xs, *es, *consts)
        case "Div":
            return div(I, *Xs, *es, consts[1])
        case "Sqrt":
            return sqrt(I, *Xs, *es)


def abs_bound(e):
    return e.D.mag


def rel_bound(e):
    return (e.S - ONE).mag


BOUNDS = {"abs": abs_bound, "rel": rel_bound}
