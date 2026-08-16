"""Frontier extraction.

F(c) holds the minimal (S,D) pairs reachable by any program of c, each with a
witness program achieving it.  Because the order is partial there is no single
best pair, so a class keeps a whole antichain; any monotone readout mu is then
minimised over F(c) (theorem 3).
"""

from __future__ import annotations

from collections import deque
from fractions import Fraction
from itertools import product

from . import analysis as A
from .egg import representable
from .interval import TOP

DEFAULT_MAX_STEPS = 200_000

WITNESS_OP = {"Add": "add", "Sub": "sub", "Mul": "mul", "Div": "div",
              "Neg": "neg", "Sqrt": "sqrt"}


class Frontier:
    def __init__(self, entries, steps, truncated):
        self.entries = entries      # class id -> [(Pair, witness)]
        self.steps = steps
        self.truncated = truncated  # hit a cap, so optimality is not guaranteed

    def best(self, cls: str, Ic, metric):
        """The minimizing entry for a readout, or None if the class has no program."""
        mu = A.METRICS[metric] if isinstance(metric, str) else metric
        out = None
        for pair, witness in self.entries.get(cls, ()):
            value = mu(pair, Ic)
            if out is None or value < out[0]:
                out = (value, pair, witness)
        return out


def analyze_program(g, e):
    """A(z~) for one concrete program tree, using the e-graph's class intervals."""
    Ic = g.interval[g.locate(e)]
    if e[0] == "var":
        return A.EXACT
    if e[0] in ("num", "const"):
        return A.constant(e[0] == "num" and representable(e[1]), Ic)
    kids = [analyze_program(g, a) for a in e[1:]]
    ivs = [g.interval[g.locate(a)] for a in e[1:]]
    if e[0] == "neg":
        return A.neg(kids[0], Ic)
    if e[0] == "sqrt":
        return A.sqrt(kids[0], ivs[0], Ic)
    f = {"add": A.add, "sub": A.sub, "mul": A.mul, "div": A.div}[e[0]]
    return f(kids[0], kids[1], ivs[0], ivs[1], Ic)


def _leaf_witness(node, lits):
    if node.op == "Var":
        return ("var", node.payload)
    if node.op == "Num":
        return ("num", Fraction(node.payload))
    return lits[node.payload]


def _score(pair):
    return (float(A.mu_abs(pair, TOP)), float(pair.S.hi - pair.S.lo))


def _insert(entries, pair, witness, cap):
    """Keep the list a minimal antichain.  True if it changed."""
    for q, _ in entries:
        if q.precedes(pair):
            return False
    kept = [(q, w) for q, w in entries if not pair.precedes(q)]
    kept.append((pair, witness))
    if cap and len(kept) > cap:
        kept.sort(key=lambda e: _score(e[0]))
        del kept[cap:]
    entries[:] = kept
    return True


def extract(g, max_steps: int = DEFAULT_MAX_STEPS, max_frontier: int = None) -> Frontier:
    parents = {}
    for cls, nodes in g.nodes.items():
        for node in nodes:
            for child in set(node.children):
                parents.setdefault(child, []).append((cls, node))

    F = {cls: [] for cls in g.nodes}
    queue, queued = deque(), set()

    def enqueue(cls):
        for item in parents.get(cls, ()):
            key = (item[0], item[1].key())
            if key not in queued:
                queued.add(key)
                queue.append(item)

    for cls, nodes in g.nodes.items():
        for node in nodes:
            if not node.children:
                pair = A.transfer(node, [], [], g.interval[cls])
                if pair is not A.BOTTOM and _insert(F[cls], pair, _leaf_witness(node, g.lits),
                                                   max_frontier):
                    enqueue(cls)

    steps, truncated = 0, False
    while queue:
        if steps >= max_steps:
            truncated = True
            break
        cls, node = queue.popleft()
        queued.discard((cls, node.key()))
        steps += 1
        Ic = g.interval[cls]
        ivs = [g.interval[c] for c in node.children]
        changed = False
        for combo in product(*(F[c] for c in node.children)):
            pair = A.transfer(node, [e[0] for e in combo], ivs, Ic)
            if pair is A.BOTTOM:
                continue
            witness = (WITNESS_OP[node.op],) + tuple(e[1] for e in combo)
            changed |= _insert(F[cls], pair, witness, max_frontier)
        if changed:
            enqueue(cls)

    return Frontier(F, steps, truncated or max_frontier is not None)
