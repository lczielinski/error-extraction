"""Extraction on the e-graph read back from egglog. Each class's frontier F_k(c) is a
list of (cost, program) entries whose costs are Min(X_k(c)).

A cost that is FAIL is left out of every frontier."""

import time
from itertools import product

from .analysis import FAIL, err, precedes


def insert(front, entry, leq):
    """Add (cost, program) to a frontier unless a cost there is <= its cost, and drop the costs it
    is below. A cost keeps the first program found for it."""
    if not any(leq(e, entry[0]) for e, _ in front):
        front[:] = [f for f in front if not leq(entry[0], f[0])] + [entry]


def program(node, programs):
    """The program of a node, from its children's."""
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
    """The input box for a node."""
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
    """A class's input box: the intersection of its nodes' boxes."""
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


def participants(g):
    """The nodes whose input box is the same as the class's."""
    box = boxes(g)
    nodes = [(c, n) for c, ns in g.nodes.items() for n in ns
             if (guards := assumes(n, box)) is not None and guards <= box[c]]
    members, readers = {c: [] for c in g.nodes}, {c: set() for c in g.nodes}
    for i, (c, n) in enumerate(nodes):
        members[c].append(i)
        for child in n.children:
            readers[child].add(i)
    return nodes, members, readers


def extract(g, time_limit=None, cost=err, leq=precedes):
    """F_k of every class for the largest k reached, k, and whether the time limit stopped it
    before F_{k+1} = F_k. Round k+1 evaluates again only the nodes with a child whose frontier
    changed in round k."""
    deadline = time_limit and time.monotonic() + time_limit
    nodes, members, readers = participants(g)

    def costs(c, node):
        """Min of what node adds to X_{k+1}(c), from its children's F_k, or None at the deadline."""
        Xs = [g.interval[child] for child in node.children]
        out = []
        for i, entries in enumerate(product(*(F[child] for child in node.children))):
            if i % 1024 == 0 and deadline and time.monotonic() > deadline:
                return None
            e = cost(node.op, g.interval[c], Xs, [e for e, _ in entries])
            if e is not FAIL:
                insert(out, (e, program(node, [p for _, p in entries])), leq)
        return out

    F = {c: [] for c in g.nodes}  # F_0
    added, todo, k = {}, range(len(nodes)), 0
    while todo:
        for i in todo:
            added[i] = costs(*nodes[i])
            if added[i] is None:
                return F, k, True
        changed = {}
        for c in {nodes[i][0] for i in todo}:
            front = list(F[c])
            for i in members[c]:
                for entry in added[i]:
                    insert(front, entry, leq)
            if {e for e, _ in front} != {e for e, _ in F[c]}:
                changed[c] = front
        F.update(changed)
        k += 1
        todo = sorted({i for c in changed for i in readers[c]})
    return F, k, False


def best(front, bound):
    """The entry minimizing a monotone readout, such as a bound from analysis.BOUNDS."""
    return min(front, key=lambda entry: bound(entry[0]))
