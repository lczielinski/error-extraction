"""Extraction (Section 3): F_k(c) = Min(X_k(c)), with each cost kept beside a program having it."""

import time
from itertools import product

from .analysis import FAIL, err, precedes


def insert(front, entry, leq):
    if not any(leq(e, entry[0]) for e, _ in front):
        front[:] = [f for f in front if not leq(entry[0], f[0])] + [entry]


def program(node, programs):
    match node.op:
        case "Var":
            return ("Var", node.payload)
        case "Num" | "Lit":
            return ("Num", node.payload)
        case "Ctx":
            return programs[0]
        case "If":
            return ("If", (">", *node.payload), *programs)
        case op:
            return (op, *programs)


def assumes(node, box):
    """The guards (x, k, x > k) that a node's terms rely on, or None while a child's are unknown."""
    if any(child not in box for child in node.children):
        return None
    guards = [box[child] for child in node.children]
    match node.op:
        case "Ctx":
            return guards[0] | {node.payload}
        case "If":
            x, k = node.payload
            return (guards[0] - {(x, k, True)}) | (guards[1] - {(x, k, False)})
        case _:
            return frozenset().union(*guards)


def boxes(g):
    """Each class's box V_c, as the guards that all its nodes rely on."""
    box = {}
    while True:
        new = {}
        for c, nodes in g.nodes.items():
            guards = [s for s in (assumes(n, box) for n in nodes) if s is not None]
            if guards:
                new[c] = frozenset.intersection(*guards)
        if new == box:
            return box
        box = new


def extract(g, time_limit=None, cost=err, leq=precedes):
    """F_k for the largest k reached, k, and whether the time limit stopped it before
    F_{k+1} = F_k, for a local cost function and the partial order leq on its values.

    Only nodes whose children's boxes contain their class's box take part, and a node is
    evaluated again only when a child's frontier changed in the last round."""
    deadline = time_limit and time.monotonic() + time_limit
    box = boxes(g)
    num = {c: any(n.op == "Num" for n in nodes) for c, nodes in g.nodes.items()}
    nodes = [(c, n) for c, ns in g.nodes.items() for n in ns
             if assumes(n, box) is not None and assumes(n, box) <= box[c]]
    members, readers = {c: [] for c in g.nodes}, {c: set() for c in g.nodes}
    for i, (c, n) in enumerate(nodes):
        members[c].append(i)
        for child in n.children:
            readers[child].add(i)

    def share(c, node):
        """The costs node contributes to X_{k+1}(c), from its children's F_k."""
        Xs = [g.interval[child] for child in node.children]
        consts = [num[child] for child in node.children]
        out = []
        for i, entries in enumerate(product(*(F[child] for child in node.children))):
            if i % 1024 == 0 and deadline and time.monotonic() > deadline:
                return None
            e = cost(node.op, g.interval[c], Xs, [e for e, _ in entries], consts)
            if e is not FAIL:
                insert(out, (e, program(node, [p for _, p in entries])), leq)
        return out

    F, shares, todo, k = {c: [] for c in g.nodes}, {}, range(len(nodes)), 0
    while todo:
        for i in todo:
            shares[i] = share(*nodes[i])
            if shares[i] is None:
                return F, k, True
        changed = {}
        for c in {nodes[i][0] for i in todo}:
            front = list(F[c])
            for i in members[c]:
                for entry in shares.get(i, ()):
                    insert(front, entry, leq)
            if {e for e, _ in front} != {e for e, _ in F[c]}:
                changed[c] = front
        F.update(changed)
        k += 1
        todo = sorted({i for c in changed for i in readers[c]})
    return F, k, False


def best(front, I, bound):
    return min(front, key=lambda entry: bound(entry[0], I))
