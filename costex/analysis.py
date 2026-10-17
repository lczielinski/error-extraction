"""The error analysis of Section 4: err(t) = (S, D) with x~/x in S and x~ - x in D, or FAIL."""

from collections import namedtuple

import gmpy2

from .interval import INF, ONE, TOP, UP, ZERO, Iv

Pair = namedtuple("Pair", "S D")
FAIL = None
EXACT = Pair(ONE, ZERO)
FORMATS = {"binary64": (53, -1022), "binary32": (24, -126)}


def set_format(name):
    global U, ETA, TINY, OMEGA
    p, emin = FORMATS[name]
    U, ETA, TINY = gmpy2.exp2(-p), gmpy2.exp2(emin - p), gmpy2.exp2(emin)
    OMEGA = (2 - 2 * U) * gmpy2.exp2(1 - emin)


set_format("binary64")


def precedes(e1, e2):
    return e1.S <= e2.S and e1.D <= e2.D


def computed(I, e):
    """X~: where the computed value lies, for a real value in I."""
    return I + e.D if 0 in I else (I + e.D) & (I * e.S)


def reduce(I, S, D):
    if 0 in I:
        return Pair(S, D)
    return Pair(S & (ONE + D / I), D & (I * (S - ONE)))


def ufp(r):
    return gmpy2.exp2(gmpy2.frexp(r)[0] - 1)


def gamma_a(Ih):
    if Ih.mag == 0:
        return ZERO
    g = max(U * ufp(Ih.mag), ETA)
    return Iv(-g, g)


def gamma_r(Ih):
    # u ufp(r)/|r| is u at each power of two and falls across a binade, so its sup on Ih
    # is u unless Ih lies inside one binade; there, like eta/|r|, it peaks at Ih.mig.
    m = Ih.mig
    if m == 0:
        g = 1
    else:
        g = UP.div(U * ufp(m), m) if ufp(m) == ufp(Ih.mag) else U
        g = min(1, max(g, UP.div(ETA, m)))
    return ONE + Iv(-g, g)


def rounded(I, S, D, exact):
    """The pair of an operation from its pre-rounding pair: FAIL if it may overflow."""
    e = reduce(I, S, D)
    Ih = computed(I, e)
    if Ih.mag > OMEGA:
        return FAIL
    if exact(Ih):
        return e
    return reduce(I, e.S * gamma_r(Ih), e.D + gamma_a(Ih))


def never(Ih):
    return False


def power_of_two(X, e, const):
    """k if the operand computes the constant +-2^k exactly: its class holds a constant and
    its pair is EXACT. Asking the class rather than the term keeps err local."""
    if const and e == EXACT:
        k, m = gmpy2.frexp(X.lo)
        if abs(m) == 0.5:
            return k - 1
    return None


def scales_exactly(k, Ih):
    return k >= 0 or Ih.mig >= TINY


def sterbenz(Xt, Yt):
    a, b = (Xt, -Yt) if Xt.lo > 0 else (-Xt, Yt)
    return a.lo > 0 and b.lo > 0 and b.hi <= 2 * a.lo and a.hi <= 2 * b.lo


def mix(lam, S1, S2):
    L = Iv(lam, lam)
    return L * S1 + (ONE - L) * S2


def add(I, X, Y, e1, e2):
    if 0 in X or 0 in Y:
        S = TOP
    else:
        lam = (X / I) & (ONE - Y / I) & (ONE / (ONE + Y / X))
        S = mix(lam.lo, e1.S, e2.S) | mix(lam.hi, e1.S, e2.S)
    Xt, Yt = computed(X, e1), computed(Y, e2)
    return rounded(I, S, e1.D + e2.D, lambda Ih: sterbenz(Xt, Yt))


def mul(I, X, Y, e1, e2, c1, c2):
    ks = [k for k in (power_of_two(X, e1, c1), power_of_two(Y, e2, c2)) if k is not None]
    S, D = e1.S * e2.S, X * e2.D + Y * e1.D + e1.D * e2.D
    return rounded(I, S, D, lambda Ih: any(scales_exactly(k, Ih) for k in ks))


def div(I, X, Y, e1, e2, c2):
    Yt = computed(Y, e2)
    if 0 in Yt:
        return FAIL
    k = power_of_two(Y, e2, c2)
    S, D = e1.S / e2.S, (e1.D - X * (e2.S - ONE)) / Yt
    return rounded(I, S, D, lambda Ih: k is not None and scales_exactly(-k, Ih))


def sqrt(I, X, e1):
    Xt = computed(X, e1)
    if Xt.lo < 0:
        return FAIL
    return rounded(I, e1.S.sqrt(), e1.D / (Xt.sqrt() + X.sqrt()), never)


def err(op, I, Xs, es, consts):
    """err_s of an e-node, from its class interval I and its children's intervals and costs."""
    if FAIL in es:
        return FAIL
    match op:
        case "Var" | "Num":
            return EXACT
        case "Lit":
            return rounded(I, ONE, ZERO, never)
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


def abs_bound(e, I):
    return e.D.mag


def rel_bound(e, I):
    return INF if 0 in I else max(UP.sub(1, e.S.lo), UP.sub(e.S.hi, 1))


BOUNDS = {"abs": abs_bound, "rel": rel_bound}
