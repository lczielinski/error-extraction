"""Frontier extraction: the minimal (S, D) pairs of each class, with witnesses."""

from __future__ import annotations

import time
from collections import deque
from fractions import Fraction
from itertools import product

from . import analysis as A
from .egg import OP_NAME, is_exact

DEFAULT_MAX_STEPS = 200_000


class Frontier:
    def __init__(self, entries, steps, truncated):
        self.entries = entries      # class id -> [(Pair, witness)]
        self.steps = steps
        self.truncated = truncated  # hit a cap, so not provably optimal

    def best(self, cls: str, Ic, metric: str):
        mu = A.METRICS[metric]
        out = None
        for pair, witness in self.entries.get(cls, ()):
            value = mu(pair, Ic)
            if out is None or value < out[0]:
                out = (value, pair, witness)
        return out


def analyze_program(g, e):
    """A(z~) for one straight-line program, over the e-graph's class intervals."""
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


def _guard_witness(g, F, prop_cls):
    """The guard to emit for a Prop class: a leaf compared with zero, or None.

    A split's predicate class always holds (Gt w 0) or (Gt 0 w) with w a leaf,
    since that is what licensed the split.  It is also the only member a float
    program decides the way the real one does: a variable holds a representable
    value and zero is exact, whereas any rounded operand could flip the test
    near zero and run an arm whose assumption is false.
    """
    for node in g.props.get(prop_cls, ()):
        if node.op != "Gt":
            continue
        wits = []
        for child in node.children:
            hit = next((w for pair, w in F.get(child, ()) if pair == A.EXACT), None)
            if hit is None or hit[0] not in ("var", "num"):
                break
            wits.append(hit)
        else:
            return ("gt",) + tuple(wits)
    return None


def _insert(entries, pair, witness):
    """Keep the list a minimal antichain.  True if it changed."""
    for q, _ in entries:
        if q.precedes(pair):
            return False
    entries[:] = [(q, w) for q, w in entries if not pair.precedes(q)] + [(pair, witness)]
    return True


def extract(g, max_steps: int = DEFAULT_MAX_STEPS, time_limit: float = None) -> Frontier:
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
                witness = _leaf_witness(node, g.lits)
                if pair is not A.BOTTOM and _insert(F[cls], pair, witness):
                    enqueue(cls)

    def past_deadline() -> bool:
        return deadline is not None and time.monotonic() > deadline

    steps, truncated = 0, False
    while queue:
        if steps >= max_steps or past_deadline():
            truncated = True
            break
        cls, node = queue.popleft()
        queued.discard((cls, node.key()))
        steps += 1
        Ic = g.interval[cls]
        changed = False
        op = OP_NAME[node.op]
        guard = None
        if op == "ifprop":
            # the first child is a Prop class, which has no frontier: the guard
            # is chosen once, and only the two arms are crossed
            guard = _guard_witness(g, F, node.children[0])
            if guard is None:
                continue
            kids = node.children[1:]
        elif op == "ctx":
            kids = node.children[1:]        # the Prop is analysis-only
        else:
            kids = node.children
        ivs = [g.interval[c] for c in kids]
        # the deadline is checked inside the product too: a step cap counts
        # popped nodes and so does not bound one node's work
        for i, combo in enumerate(product(*(F[c] for c in kids))):
            if not i & 1023 and past_deadline():
                truncated = True
                break
            pair = A.transfer(op, [e[0] for e in combo], ivs, Ic)
            if pair is A.BOTTOM:
                continue
            wits = tuple(e[1] for e in combo)
            if op == "ctx":
                witness = wits[0]           # a context is not part of a program
            elif guard is not None:
                witness = (op, guard) + wits
            else:
                witness = (op,) + wits
            changed |= _insert(F[cls], pair, witness)
        if changed:
            enqueue(cls)
        if truncated:
            break

    return Frontier(F, steps, truncated)
