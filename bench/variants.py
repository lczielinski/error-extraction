"""The alternatives to frontier extraction that Section 6 compares it with."""

import heapq
import time

from costex import analysis as A
from costex.analysis import FAIL, ONE, TOP, ZERO, err, never, power_of_two, sterbenz
from costex.extract import assumes, boxes, extract, program


def analyze(g, p):
    """err of the program p as a term of g, with g's class intervals."""
    index = {(n.op, n.payload, n.children): c for c, ns in g.nodes.items() for n in ns}
    num = {c: any(n.op == "Num" for n in ns) for c, ns in g.nodes.items()}

    def walk(p):
        if p[0] == "Num" and ("Num", p[1], ()) not in index:
            c = index[("Lit", p[1], ())]
            return c, err("Lit", g.interval[c], [], [], [])
        if p[0] in ("Var", "Num"):
            c, kids = index[(p[0], p[1], ())], []
        else:
            kids = [walk(q) for q in p[1:]]
            c = index[(p[0], None, tuple(k for k, _ in kids))]
        Xs = [g.interval[k] for k, _ in kids]
        return c, err(p[0], g.interval[c], Xs, [e for _, e in kids], [num[k] for k, _ in kids])

    return walk(p)[1]


def smallest(g, n, time_limit=None):
    """The n smallest programs of the root class, counting operations and leaves, found in
    rounds like extraction's."""
    deadline = time_limit and time.monotonic() + time_limit
    box = boxes(g)
    nodes = [(c, m) for c, ms in g.nodes.items() for m in ms
             if assumes(m, box) is not None and assumes(m, box) <= box[c]]
    members, readers = {c: [] for c in g.nodes}, {c: set() for c in g.nodes}
    for i, (c, m) in enumerate(nodes):
        members[c].append(i)
        for child in m.children:
            readers[child].add(i)
    best, shares, todo = {c: [] for c in g.nodes}, {}, range(len(nodes))
    while todo and not (deadline and time.monotonic() > deadline):
        for i in todo:
            shares[i] = sums(nodes[i][1], [best[x] for x in nodes[i][1].children], n)
        changed = {}
        for c in {nodes[i][0] for i in todo}:
            found = heapq.nsmallest(n, (e for i in members[c] for e in shares.get(i, ())))
            if found != best[c]:
                changed[c] = found
        best.update(changed)
        todo = sorted({i for c in changed for i in readers[c]})
    return [p for _, p in best[g.root]]


def sums(m, lists, n):
    """The n smallest terms with root m, from its children's sorted (size, program) lists."""
    if not lists:
        return [(1, program(m, []))]
    if len(lists) == 1:
        return [(1 + s, program(m, [p])) for s, p in lists[0][:n]]
    a, b = lists
    if not a or not b:
        return []
    out, seen, heap = [], {(0, 0)}, [(a[0][0] + b[0][0], 0, 0)]
    while heap and len(out) < n:
        s, i, j = heapq.heappop(heap)
        out.append((1 + s, program(m, [a[i][1], b[j][1]])))
        for i2, j2 in ((i + 1, j), (i, j + 1)):
            if i2 < len(a) and j2 < len(b) and (i2, j2) not in seen:
                seen.add((i2, j2))
                heapq.heappush(heap, (a[i2][0] + b[j2][0], i2, j2))
    return out


def greedy(metric):
    """The order that keeps a single cost per class: the one with the smallest bound."""
    bound = (lambda e: e.D.mag) if metric == "abs" else (lambda e: (e.S - ONE).mag)
    return lambda e1, e2: bound(e1) <= bound(e2)


def abs_only(op, I, Xs, Ds, consts):
    """x~ - x in D, tracked alone: no S, no reduction."""
    if any(D is FAIL for D in Ds):
        return FAIL

    def rounded(D, exact):
        Ih = I + D
        if Ih.mag > A.OMEGA:
            return FAIL
        return D if exact(Ih) else D + A.gamma_a(Ih)

    def scale(i):
        return power_of_two(Xs[i], A.Pair(ONE, Ds[i]), consts[i])

    match op:
        case "Var" | "Num":
            return ZERO
        case "Lit":
            return rounded(ZERO, never)
        case "Neg":
            return -Ds[0]
        case "Add":
            Xt, Yt = Xs[0] + Ds[0], Xs[1] + Ds[1]
            return rounded(Ds[0] + Ds[1], lambda Ih: sterbenz(Xt, Yt))
        case "Mul":
            ks = [k for k in (scale(0), scale(1)) if k is not None]
            D = Xs[0] * Ds[1] + Xs[1] * Ds[0] + Ds[0] * Ds[1]
            return rounded(D, lambda Ih: any(A.scales_exactly(k, Ih) for k in ks))
        case "Div":
            Yt = Xs[1] + Ds[1]
            if 0 in Yt:
                return FAIL
            k = scale(1)
            return rounded((Ds[0] - I * Ds[1]) / Yt, lambda Ih: k is not None and A.scales_exactly(-k, Ih))
        case "Sqrt":
            Xt = Xs[0] + Ds[0]
            if Xt.lo < 0:
                return FAIL
            return rounded(Ds[0] / (Xt.sqrt() + Xs[0].sqrt()), never)


def rel_only(op, I, Xs, Ss, consts):
    """x~/x in S, tracked alone: no D, no reduction, and nothing where a value can be 0."""
    if any(S is FAIL for S in Ss):
        return FAIL

    def rounded(S, exact):
        Ih = TOP if 0 in I else I * S
        if Ih.mag > A.OMEGA:
            return FAIL
        return S if exact(Ih) else S * A.gamma_r(Ih)

    def scale(i):
        return power_of_two(Xs[i], A.Pair(Ss[i], ZERO), consts[i])

    def computed(i):
        return TOP if 0 in Xs[i] else Xs[i] * Ss[i]

    match op:
        case "Var" | "Num":
            return ONE
        case "Lit":
            return rounded(ONE, never)
        case "Neg":
            return Ss[0]
        case "Add":
            S = TOP
            if 0 not in Xs[0] and 0 not in Xs[1]:
                X, Y = Xs
                lam = (X / I) & (ONE - Y / I) & (ONE / (ONE + Y / X))
                S = A.mix(lam.lo, *Ss) | A.mix(lam.hi, *Ss)
            Xt, Yt = computed(0), computed(1)
            return rounded(S, lambda Ih: sterbenz(Xt, Yt))
        case "Mul":
            ks = [k for k in (scale(0), scale(1)) if k is not None]
            return rounded(Ss[0] * Ss[1], lambda Ih: any(A.scales_exactly(k, Ih) for k in ks))
        case "Div":
            if 0 in computed(1):
                return FAIL
            k = scale(1)
            return rounded(Ss[0] / Ss[1], lambda Ih: k is not None and A.scales_exactly(-k, Ih))
        case "Sqrt":
            if computed(0).lo < 0:
                return FAIL
            return rounded(Ss[0].sqrt(), never)


def single(g, metric, time_limit=None):
    """The program extracted by tracking one metric alone."""
    cost, bound = (abs_only, lambda D: D.mag) if metric == "abs" else (rel_only, lambda S: (S - ONE).mag)
    F, _, _ = extract(g, time_limit, cost=cost, leq=lambda a, b: a <= b)
    return min(F[g.root], key=lambda entry: bound(entry[0]))[1] if F[g.root] else None
