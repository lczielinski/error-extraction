"""Frontier extraction: the minimal (S, D) pairs of each class, with witnesses.

The paper's F_k, round by round: X_0(c) is empty, F_k(c) = Min(X_k(c)), and
X_{k+1}(c) holds cost_s(x_1..x_m) for each e-node s(c_1..c_m) of c and each
x_i in F_k(c_i).  F_k(c) is then the frontier of c's terms of height at most
k, and once F_{N+1} = F_N, the frontier of all of them.

A node's share of X_{k+1} depends only on its children's F_k, so a round
re-evaluates just the nodes whose children changed in the last one.  A
context is not part of a program, so it adds no height: within a round, it
reads its subject's F_{k+1}.  A cap abandons the round it interrupts, so a
truncated frontier is still exactly F_k for the last k finished.
"""

from __future__ import annotations

import time
from collections import deque
from fractions import Fraction
from itertools import product

from . import analysis as A
from .egg import OP_NAME, is_exact

DEFAULT_MAX_STEPS = 200_000


class Frontier:
    def __init__(self, entries, steps, height, truncated):
        self.entries = entries      # class id -> [(Pair, witness)]: F_height
        self.steps = steps          # node evaluations
        self.height = height        # the k of F_k
        self.truncated = truncated  # stopped short of F_{k+1} = F_k, so optimal
                                    # only among terms of height at most k

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
    consts = [_holds_const(g, g.locate(a)) for a in e[1:]]
    return A.transfer(e[0], kids, ivs, Ic, consts)


def _holds_const(g, cls) -> bool:
    return any(n.op == "Num" for n in g.nodes[cls])


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


def _arity(g, node):
    """What a node's share of X reads: the classes it crosses, and those it
    must be re-evaluated after."""
    op = OP_NAME[node.op]
    if op == "ifprop":
        # the first child is a Prop class, which has no frontier: the guard is
        # chosen from the classes it compares, and only the two arms are crossed
        kids = node.children[1:]
        reads = {c for n in g.props.get(node.children[0], ()) if n.op == "Gt"
                 for c in n.children}
        return op, kids, set(kids) | reads
    if op == "ctx":
        kids = node.children[1:]            # the Prop is analysis-only
        return op, kids, set(kids)
    return op, node.children, set(node.children)


def _share(g, F, cls, node, op, kids, past_deadline):
    """node's minimal share of X_{k+1}(cls), from F = F_k; None past the deadline."""
    guard = None
    if op == "ifprop":
        guard = _guard_witness(g, F, node.children[0])
        if guard is None:
            return []
    Ic = g.interval[cls]
    ivs = [g.interval[c] for c in kids]
    consts = [_holds_const(g, c) for c in kids]
    out = []
    # the deadline is checked inside the product too: a step cap counts nodes
    # and so does not bound one node's work
    for i, combo in enumerate(product(*(F[c] for c in kids))):
        if not i & 1023 and past_deadline():
            return None
        pair = A.transfer(op, [e[0] for e in combo], ivs, Ic, consts)
        if pair is A.FAIL:
            continue
        wits = tuple(e[1] for e in combo)
        if op == "ctx":
            witness = wits[0]           # a context is not part of a program
        elif guard is not None:
            witness = (op, guard) + wits
        else:
            witness = (op,) + wits
        _insert(out, pair, witness)
    return out


def extract(g, max_steps: int = DEFAULT_MAX_STEPS, time_limit: float = None) -> Frontier:
    deadline = None if time_limit is None else time.monotonic() + time_limit

    def past_deadline() -> bool:
        return deadline is not None and time.monotonic() > deadline

    # X_1: the leaves, which no later round changes
    leaves = {}
    inner, readers, ctx_readers = [], {}, {}
    for cls, nodes in g.nodes.items():
        for node in nodes:
            if not node.children:
                pair = _leaf_pair(node, g.interval[cls])
                if pair is not A.FAIL:
                    _insert(leaves.setdefault(cls, []), pair, _leaf_witness(node, g.lits))
                continue
            op, kids, reads = _arity(g, node)
            for c in reads:
                (ctx_readers if op == "ctx" else readers).setdefault(c, []).append(len(inner))
            inner.append((cls, node, op, kids))
    members = {}
    for i, (cls, *_) in enumerate(inner):
        members.setdefault(cls, []).append(i)

    F = {cls: [] for cls in g.nodes}         # F_0
    shares = {}                              # node -> its share of X, from the F it last read

    def rebuild(cls, nxt) -> bool:
        """Min of X(cls) into nxt from the current shares; True if its costs moved."""
        acc = []
        for part in [leaves.get(cls, ())] + [shares.get(i, ()) for i in members.get(cls, ())]:
            for pair, witness in part:
                _insert(acc, pair, witness)
        if {pair for pair, _ in acc} == {pair for pair, _ in nxt[cls]}:
            return False
        # a cost already found keeps the witness it was first found with
        old = dict(F[cls])
        nxt[cls] = [(pair, old.get(pair, witness)) for pair, witness in acc]
        return True

    stale, touched = [], set(leaves)         # round 1 reads F_0, where every inner node is empty
    steps, height = 0, 0
    while True:
        for i in stale:
            if steps >= max_steps or past_deadline():
                return Frontier(F, steps, height, True)
            steps += 1
            cls, node, op, kids = inner[i]
            share = _share(g, F, cls, node, op, kids, past_deadline)
            if share is None:
                return Frontier(F, steps, height, True)
            shares[i] = share

        nxt = dict(F)
        queue = deque(cls for cls in touched if rebuild(cls, nxt))
        dirty = set(touched)
        # contexts read F_{k+1}, so they close over it before the round ends
        while queue:
            for i in ctx_readers.get(queue.popleft(), ()):
                if steps >= max_steps or past_deadline():
                    return Frontier(F, steps, height, True)
                steps += 1
                cls, node, op, kids = inner[i]
                share = _share(g, nxt, cls, node, op, kids, past_deadline)
                if share is None:
                    return Frontier(F, steps, height, True)
                shares[i] = share
                dirty.add(cls)
                if rebuild(cls, nxt):
                    queue.append(cls)

        changed = {cls for cls in dirty
                   if {pair for pair, _ in nxt[cls]} != {pair for pair, _ in F[cls]}}
        F, height = nxt, height + 1
        if not changed:
            return Frontier(F, steps, height, False)
        stale = sorted({i for c in changed for i in readers.get(c, ())})
        touched = {inner[i][0] for i in stale}
