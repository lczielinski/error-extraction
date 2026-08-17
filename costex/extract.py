"""Frontier extraction.

F(c) holds the minimal (S,D) pairs reachable by any program of c, each with a
witness program achieving it. 
"""

from __future__ import annotations

import time
from collections import deque
from fractions import Fraction
from itertools import product

from . import analysis as A
from .egg import OP_NAME, is_exact
from .interval import TOP

DEFAULT_MAX_STEPS = 200_000


class Frontier:
    def __init__(self, entries, steps, truncated):
        self.entries = entries      # class id -> [(Pair, witness)]
        self.steps = steps
        self.truncated = truncated  # hit a cap, so optimality is not guaranteed

    def best(self, cls: str, Ic, metric: str):
        """The minimizing entry for a readout, or None if the class has no program."""
        mu = A.METRICS[metric]
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
        return A.constant(is_exact(e), Ic)
    kids = [analyze_program(g, a) for a in e[1:]]
    ivs = [g.interval[g.locate(a)] for a in e[1:]]
    return A.transfer(e[0], kids, ivs, Ic)


def _leaf_witness(node, lits):
    if node.op == "Var":
        return ("var", node.payload)
    if node.op == "Num":
        return ("num", Fraction(node.payload))
    return lits[node.payload]


def _leaf_pair(node, Ic):
    """A Var reads exactly and a Num is representable; a Lit rounds."""
    return A.EXACT if node.op in ("Var", "Num") else A.constant(False, Ic)


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


def extract(g, max_steps: int = DEFAULT_MAX_STEPS, max_frontier: int = None,
            time_limit: float = None) -> Frontier:
    deadline = None if time_limit is None else time.monotonic() + time_limit
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
                pair = _leaf_pair(node, g.interval[cls])
                if pair is not A.BOTTOM and _insert(F[cls], pair, _leaf_witness(node, g.lits),
                                                   max_frontier):
                    enqueue(cls)

    steps, truncated = 0, False
    while queue:
        if steps >= max_steps or (deadline is not None and time.monotonic() > deadline):
            truncated = True
            break
        cls, node = queue.popleft()
        queued.discard((cls, node.key()))
        steps += 1
        Ic = g.interval[cls]
        ivs = [g.interval[c] for c in node.children]
        changed = False
        op = OP_NAME[node.op]
        for combo in product(*(F[c] for c in node.children)):
            pair = A.transfer(op, [e[0] for e in combo], ivs, Ic)
            if pair is A.BOTTOM:
                continue
            witness = (op,) + tuple(e[1] for e in combo)
            changed |= _insert(F[cls], pair, witness, max_frontier)
        if changed:
            enqueue(cls)

    return Frontier(F, steps, truncated or max_frontier is not None)
