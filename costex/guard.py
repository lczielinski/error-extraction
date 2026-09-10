"""Guarded rewrites: carry the precondition in the program, not in the box.

A subtraction with a high condition number cancels, and cancellation forces its
operands to share a sign -- which is the conjugate rule's premise, since
same-signed operands give |a+c| = |a|+|c| > 0.  The condition that makes the
node ill-conditioned is the one that licenses its fix.

The conjugate cannot just be unioned in: it is undefined where a+c = 0, and
rules.egg grants "the divisor of a Div e-node is nonzero on B" for free, so an
undefined member would poison every rule reading the class.  So we build
(IfProp guard then else), total and equal to both arms, and give each arm a
renamed copy of the subterm whose leaf boxes carry what the guard certifies.
Nonzero(a+c) is then derivable in the `then` copy alone, and the IfProp's
interval, the hull of the arms, pulls the class off zero so rho revives.

Two saturations: guards.egg reduces its own guards in the caller's pass, so the
first already carries the candidates and their guards, and the second builds the
nodes -- whose contexts need leaf boxes only the driver can set.
"""

from __future__ import annotations

import subprocess
import time
from fractions import Fraction

from . import analysis as A
from . import egg, extract

KAPPA_MIN = 10.0     # the atomic condition number worth guarding
MAX_NODES = 2        # guarded nodes per program
ITERS_BONUS = 2      # a newly fired gate needs another opt round to propagate
TIMEOUT = 60.0       # seconds per egglog run
TIME_LIMIT = 60.0    # seconds per extraction
BUDGET = 120.0       # seconds for the whole guarded pass


def _leaf(g, cls, op):
    for n in g.nodes.get(cls, ()):
        if n.op == op:
            return n.payload
    return None


def _signed_var(g, cls):
    """(name, sign) when cls is a variable or a negated one, else None.

    One Neg and no deeper: rules.egg already collapses (Neg (Neg a)).
    """
    v = _leaf(g, cls, "Var")
    if v is not None:
        return v, 1
    for n in g.nodes.get(cls, ()):
        if n.op == "Neg":
            v = _leaf(g, n.children[0], "Var")
            if v is not None:
                return v, -1
    return None


def terms(g) -> dict:
    """Some program per class, by structure.

    Any member will do -- they are equal on B -- so this is a bottom-up
    fixpoint: leaves first, then any node whose children all already have a
    term.  Doing it per class in one pass matters; recursing per query instead
    retries every e-node on failure and is exponential on a class-rich graph.
    """
    leaf = {"Var": lambda p: ("var", p),
            "Num": lambda p: ("num", Fraction(p)),
            "Lit": lambda p: g.lits[p]}
    out = {}
    for cls, nodes in g.nodes.items():
        for n in nodes:
            if n.op in leaf:
                out[cls] = leaf[n.op](n.payload)
                break
    changed = True
    while changed:
        changed = False
        for cls in sorted(g.nodes):
            if cls in out:
                continue
            for n in g.nodes[cls]:
                if n.op not in egg.OP_NAME or n.op == "IfProp":
                    continue
                if all(k in out for k in n.children):
                    out[cls] = ((egg.OP_NAME[n.op],)
                                + tuple(out[k] for k in n.children))
                    changed = True
                    break
    return out


def candidates(g) -> list:
    """(target, a, c) for each Sub whose operands cancel.

    Only where one operand is a square root: the conjugate rewrites a - c to
    (a*a - c*c)/(a + c), which helps only if the numerator collapses
    symbolically, and that needs a squared root to cancel against something.
    Otherwise it trades a cancelling subtraction for a cancelling subtraction of
    squares and leaves a dead member in every subtraction class.
    """
    out, seen, known = [], set(), terms(g)
    for cls in sorted(g.nodes):                 # sorted: the dump order is not stable
        Ic = g.interval[cls]
        if Ic.lo == Ic.hi:
            # constant on B, so there is no cancellation to separate: if the
            # constant is zero no relative bound exists however we rewrite, and
            # otherwise the subtraction is already well conditioned.  kappa
            # cannot see this, since it reads INF off any Ic holding zero.
            continue
        for n in g.nodes[cls]:
            if n.op != "Sub":
                continue
            a, c = n.children
            if A.kappa(g.interval[a], -g.interval[c], Ic) <= KAPPA_MIN:
                continue
            if not any(m.op == "Sqrt" for k in (a, c) for m in g.nodes.get(k, ())):
                continue
            target, wa, wc = (known.get(k) for k in (cls, a, c))
            if None in (target, wa, wc) or (wa, wc) in seen:
                continue
            seen.add((wa, wc))
            out.append((cls, target, wa, wc))
    # the root class first: its interval is the one the readouts use, so a guard
    # anywhere else can tighten a class nothing ends up reading
    out.sort(key=lambda r: r[0] != g.root)
    return [r[1:] for r in out]


def _pair(gt):
    """A guard and its complement: not (x > y) is y >= x."""
    return gt, ("ge", gt[2], gt[1])


def guard_for(g, box: dict, a, c):
    """An emittable guard for SameSign(a,c), with its complement, or None.

    A member comparing a variable against a constant is what we are after: the
    program decides it exactly, since a variable holds a representable value and
    k is representable, and guards.egg's refinement rules read it as a bound on
    v inside each context, which the ordinary ana pass then propagates.  A negated variable counts -- the
    sign folds into the threshold -- so this does not depend on whether the
    normalising rewrites happened to fire before the dump.
    """
    try:
        cls = g.locate_prop(("samesign", a, c))
    except RuntimeError:
        return None
    for n in g.props.get(cls, ()):
        if n.op != "Gt":
            continue
        for flip, (x, y) in enumerate((n.children, n.children[::-1])):
            got, k = _signed_var(g, x), _leaf(g, y, "Num")
            if got is None or k is None or got[0] not in box:
                continue
            # the node reads Gt(x, y).  flip says which side holds the variable
            # and sign folds a Neg into the threshold: s*v > k is v > k when
            # s = 1, and v < -k when s = -1
            (v, sign), t = got, (k if got[1] > 0 else -k)
            lo, hi = box[v]
            if not lo < t < hi:
                continue               # the box already decides this guard
            num = ("num", Fraction(t))
            if (sign > 0) != bool(flip):
                return _pair(("gt", ("var", v), num))
            return _pair(("gt", num, ("var", v)))
    return None


class Guarded:
    def __init__(self, graph, front, plans):
        self.graph = graph
        self.front = front
        self.plans = plans

    @property
    def guards(self) -> list:
        return [p[1] for p in self.plans]


def run(core, base, iters: int = egg.DEFAULT_ITERS, out_path: str = None):
    """Guard what cancels, or None when there is nothing worth guarding.

    `base` is the caller's already-saturated e-graph, so a program with no
    ill-conditioned subtraction costs nothing beyond the candidate scan.
    """
    deadline = time.monotonic() + BUDGET

    def left() -> float:
        return deadline - time.monotonic()

    def build(**kw):
        if left() <= 0:
            return None
        try:
            return egg.build(core.body, core.box, timeout=min(TIMEOUT, left()), **kw)
        except (egg.BadBox, RuntimeError, subprocess.TimeoutExpired):
            return None

    cands = candidates(base)[:MAX_NODES]
    if not cands:
        return None

    plans = []
    for target, a, c in cands:
        got = guard_for(base, core.box, a, c)
        if got is not None:
            plans.append((target,) + got)
    if not plans:
        return None

    final = build(iters=iters + ITERS_BONUS, plans=plans, out_path=out_path)
    if final is None:
        return None
    front = extract.extract(final, time_limit=max(1.0, min(TIME_LIMIT, left())))
    return Guarded(final, front, plans)
