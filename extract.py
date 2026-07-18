# /// script
# requires-python = ">=3.10"
# dependencies = ["egglog"]
# ///
"""Cost-based extraction from an equivalence e-graph, where the cost of a term
is a sound upper bound on its worst-case relative rounding error over the
input box -- the idea of NumFuzz (Kellison & Hsu, PLDI 2024) applied as an
e-graph extraction objective.

Pipeline (one function per stage, in order in this file):

  1. saturate         egglog builds the e-graph of terms equal to the
                      reference over the box (rules.egglog, same as egrammars)
  2. read_egraph      pull the e-classes out of egglog
  3. analyze_intervals a sound enclosure [lo, hi] per e-class
  4. cost_table       sound relative- and absolute-error bounds per e-class
  5. build            emit the cheapest term
  6. split_search     if nothing is bounded over the whole box, try one
                      `(if (<= var t) ...)` split and extract each arm

Usage:
    uv run extract.py nmse_problem_3_3_1
    uv run extract.py all
    uv run extract.py cancel_sqrt_shift3 --rounds 6
"""

import argparse
import contextlib
import json
import math
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
RULES = (HERE / "rules.egglog").read_text()

U = 2.0 ** -53           # unit roundoff of IEEE double, round-to-nearest
ULP = 2.0 ** -52         # for printing bounds in "ulps", like FPTaylor
ETA = 2.0 ** -1075       # largest rounding error in the subnormal range
INF = math.inf
TOP = (-INF, INF)        # the unknown interval

CONSTRUCTORS = {"Num", "Var", "Add", "Sub", "Neg", "Sqrt", "Mul", "Div"}
SPELLING = {"Add": "+", "Sub": "-", "Mul": "*", "Div": "/",
            "Neg": "-", "Sqrt": "sqrt"}


def up(x: float) -> float:
    """Nudge a computed error bound up so that the handful of double roundings
    in computing the bound itself can never make it an under-estimate."""
    return x * (1.0 + 2.0 ** -45)


# ---------------------------------------------------------------------------
# 1. Saturate: run the rewrite rules to (approximate) fixpoint with egglog.
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def quiet_stderr():
    """Silence egglog's Rust-side logging; Python exceptions still raise."""
    sys.stderr.flush()
    saved, devnull = os.dup(2), os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 2)
        yield
    finally:
        os.dup2(saved, 2)
        os.close(devnull)
        os.close(saved)


def saturate(source: str, box: dict, rounds: int, budget=20.0, node_cap=20_000):
    """The e-graph after `rounds` rule applications (stopping early on the
    time budget or node cap -- that only shrinks the set of terms we can
    choose from, never its soundness). `box` seeds egglog's own interval
    analysis so that domain-conditional rules only fire where they are valid."""
    from egglog.bindings import EGraph

    seeds = "".join(f"(set (lo {v}) {lo}) (set (hi {v}) {hi})\n"
                    for v, (lo, hi) in box.items())
    program = (RULES + source + seeds
               + "\n(relation __start__ (Math))\n(__start__ start)")
    egraph = EGraph()
    start = time.monotonic()
    with quiet_stderr():
        egraph.run_program(*egraph.parse_program(program))
        for _ in range(rounds):
            sizes = egraph.run_program(*egraph.parse_program("(print-size)"))
            if (time.monotonic() - start > budget
                    or sum(n for _, n in sizes[0].sizes) > node_cap):
                break
            if not egraph.run_program(*egraph.parse_program("(run 1)"))[0].report.updated:
                break
    return egraph


# ---------------------------------------------------------------------------
# 2. Read the e-graph: every class of equal terms, as a set of "spellings".
#    A spelling is (op, child class ids); Var/Num spellings point at a leaf
#    class whose token (the variable name / integer literal) lives in `leaf`.
# ---------------------------------------------------------------------------

def read_egraph(egraph):
    nodes = json.loads(egraph.serialize([]).to_json())["nodes"]
    root, classes, leaf = None, {}, {}
    for node in nodes.values():
        op = node["op"].strip('"')
        kids = tuple(nodes[c]["eclass"] for c in node["children"])
        if op == "__start__":
            root = kids[0]
        elif op in CONSTRUCTORS:  # everything else is egglog analysis bookkeeping
            classes.setdefault(node["eclass"], set()).add((op, kids))
            if op in ("Var", "Num"):
                leaf[kids[0]] = nodes[node["children"][0]]["op"].strip('"')
    assert root is not None, "benchmark must define a `start` expression"
    return root, classes, leaf


# ---------------------------------------------------------------------------
# 3. Interval analysis: a sound enclosure of each class's (exact) value over
#    the box. Every spelling of a class denotes the same value, so we may
#    intersect the enclosures the spellings imply. Endpoints are rounded
#    outward (nextafter) so machine arithmetic can't shave the truth off.
# ---------------------------------------------------------------------------

def hull(values) -> tuple[float, float]:
    if any(map(math.isnan, values)):  # e.g. inf - inf: we know nothing
        return TOP
    return (math.nextafter(min(values), -INF), math.nextafter(max(values), INF))


def interval(spelling, itv, leaf, box):
    op, kids = spelling
    if op == "Num":
        n = int(leaf[kids[0]])
        return hull([n]) if abs(n) > 2 ** 53 else (float(n), float(n))
    if op == "Var":
        return box.get(leaf[kids[0]], TOP)
    (alo, ahi) = itv[kids[0]]
    if op == "Neg":
        return (-ahi, -alo)
    if op == "Sqrt":
        if ahi < 0:
            return TOP  # never a real number; cost will not reward this
        return (max(0.0, math.nextafter(math.sqrt(max(alo, 0.0)), -INF)),
                math.nextafter(math.sqrt(ahi), INF))
    (blo, bhi) = itv[kids[1]]
    if op == "Add":
        return hull([alo + blo, ahi + bhi])
    if op == "Sub":
        return hull([alo - bhi, ahi - blo])
    if op == "Mul":
        return hull([alo * blo, alo * bhi, ahi * blo, ahi * bhi])
    if op == "Div":
        if blo <= 0.0 <= bhi:  # divisor may be zero: quotient unbounded
            return TOP
        return hull([alo / blo, alo / bhi, ahi / blo, ahi / bhi])
    raise ValueError(op)


def analyze_intervals(classes, leaf, box):
    itv = {c: TOP for c in classes}
    changed = True
    while changed:  # rerun until no enclosure narrows any further
        changed = False
        for c, spellings in classes.items():
            lo, hi = itv[c]
            for s in spellings:
                slo, shi = interval(s, itv, leaf, box)
                lo, hi = max(lo, slo), min(hi, shi)
            if lo <= hi and (lo, hi) != itv[c]:
                itv[c], changed = (lo, hi), True
    return itv


# ---------------------------------------------------------------------------
# 4. Cost: two sound error bounds, composed per operator.
#
#    Relative, in NumFuzz's log metric:  rel[c] = R  means the chosen term
#    computes  exact * e^s  with |s| <= R everywhere in the box. One rounding
#    is  *(1+e), |e| <= u,  i.e. at most  E = -ln(1-u)  in the metric, and the
#    ops compose *additively*: mul/div add the child bounds, sqrt exactly
#    halves, same-signed +- takes the max (no cancellation possible). A
#    cancelling +- pays the condition number  err / min|a+-b|  from the
#    intervals -- infinite when the result's enclosure reaches zero, the case
#    NumFuzz's type system rules out (its numbers are strictly positive).
#
#    Absolute:  ab[c] = A  means  |computed - exact| <= A.  This is the metric
#    that stays finite when the result can be exactly zero: cancellation is
#    free (absolute errors of +- just add), while mul/div/sqrt need the
#    interval magnitudes. The two metrics also help each other: a cancelling
#    +- may bound |x^ - x| by either  max|x|(e^R - 1)  or  A,  whichever is
#    smaller, so a finite absolute bound can rescue a relative one.
#
#    Assumed idealizations: round-to-nearest doubles; overflow makes a bound
#    infinite; subnormal rounding is covered by the ETA term.
# ---------------------------------------------------------------------------

E = up(-math.log1p(-U))  # one rounding step, measured in the log metric


def mag(iv) -> float:
    """max |value| over an interval."""
    return max(abs(iv[0]), abs(iv[1]))


def pmul(x: float, y: float) -> float:
    """x*y for error terms, where 0 * inf should mean 0 (no error is no
    error, whatever the other factor)."""
    return 0.0 if x == 0.0 or y == 0.0 else x * y


def growth(r: float) -> float:
    """e^r - 1: back from the log metric to plain relative error."""
    return INF if r > 700.0 else math.expm1(r)


def rel_bound(spelling, cls, rel, ab, itv, leaf) -> float:
    op, kids = spelling
    if op == "Var":
        return 0.0  # inputs are doubles, taken as exact (as FPTaylor does)
    if op == "Num":
        n = int(leaf[kids[0]])
        return 0.0 if float(n) == n else E  # literals over 2^53 round once
    ra = rel[kids[0]]
    if op == "Neg":
        return ra  # sign flip is exact
    if op == "Sqrt":
        return up(ra / 2 + E)  # sqrt(x e^s) = sqrt(x) e^(s/2), then one rounding
    rb = rel[kids[1]]
    if op in ("Mul", "Div"):
        return up(ra + rb + E)

    # Add/Sub; treat a - b as a + (-b) so one analysis covers both
    a, b = itv[kids[0]], itv[kids[1]]
    if op == "Sub":
        b = (-b[1], -b[0])
    best = INF
    if (a[0] >= 0 and b[0] >= 0) or (a[1] <= 0 and b[1] <= 0):
        best = max(ra, rb) + E  # same signs: no cancellation
    # condition-number path: |computed child - exact child| is bounded by the
    # better of its relative and absolute tracks
    err = (min(pmul(mag(a), growth(ra)), ab[kids[0]])
           + min(pmul(mag(b), growth(rb)), ab[kids[1]]))
    zlo, zhi = itv[cls]
    zmin = zlo if zlo > 0 else -zhi if zhi < 0 else 0.0  # min |exact result|
    if err == 0.0:
        best = min(best, E)  # operands exact: only the final rounding remains
    elif err < zmin and (ratio := err / zmin) < 1.0:
        best = min(best, -math.log1p(-ratio) + E)
    return up(best)


def abs_bound(spelling, cls, ab, itv, leaf) -> float:
    op, kids = spelling
    if op == "Var":
        return 0.0
    if op == "Num":
        n = int(leaf[kids[0]])
        return 0.0 if float(n) == n else up(U * abs(float(n)))
    aa = ab[kids[0]]
    if op == "Neg":
        return aa
    m = mag(itv[cls])

    def rounded(pre: float) -> float:
        """`pre` plus the final rounding, u * |computed value|."""
        if pre + m > 1e308:  # the computed value may overflow to infinity
            return INF
        return up(pre + U * (m + pre) + ETA)

    if op == "Sqrt":
        xlo = itv[kids[0]][0]
        if xlo < 0 or aa > xlo:  # operand (or its computed value) may go negative
            return INF
        pre = 0.0 if aa == 0.0 else min(math.sqrt(aa),  # |sqrt x^ - sqrt x| <= sqrt|x^ - x|
                                        aa / math.sqrt(xlo) if xlo > 0 else INF)
        return rounded(pre)
    a, b = itv[kids[0]], itv[kids[1]]
    ba = ab[kids[1]]
    if op in ("Add", "Sub"):
        return rounded(aa + ba)  # cancellation is free in absolute terms
    if op == "Mul":
        return rounded(pmul(mag(a), ba) + pmul(mag(b), aa) + pmul(aa, ba))
    ymin = b[0] if b[0] > 0 else -b[1] if b[1] < 0 else 0.0  # Div
    if ba >= ymin:  # divisor's computed value may reach zero
        return INF
    return rounded((aa + pmul(mag(a), ba) / ymin) / (ymin - ba))


def spelling_cost(spelling, cls, cost, itv, leaf):
    """(relative bound, absolute bound, term size) -- compared
    lexicographically: relative error is the objective, absolute error the
    fallback where no relative bound exists, size the final tiebreak."""
    op, kids = spelling
    if op in ("Var", "Num"):
        return (rel_bound(spelling, cls, {}, {}, itv, leaf),
                abs_bound(spelling, cls, {}, itv, leaf), 1)
    rel = {k: cost[k][0] for k in kids}
    ab = {k: cost[k][1] for k in kids}
    return (rel_bound(spelling, cls, rel, ab, itv, leaf),
            abs_bound(spelling, cls, ab, itv, leaf),
            1 + sum(cost[k][2] for k in kids))


def cost_table(classes, itv, leaf):
    cost = {c: (INF, INF, INF) for c in classes}
    changed = True
    while changed:  # rerun until no class finds a cheaper spelling
        changed = False
        for c, spellings in classes.items():
            best = min(spelling_cost(s, c, cost, itv, leaf) for s in spellings)
            if best < cost[c]:
                cost[c], changed = best, True
    return cost


# ---------------------------------------------------------------------------
# 5. Build the winning term (cheapest spelling per class, recursively).
#    The returned bound is recomputed on the emitted tree itself.
# ---------------------------------------------------------------------------

def build(cls, classes, cost, itv, leaf, ancestors=frozenset()):
    ranked = sorted(classes[cls],
                    key=lambda s: spelling_cost(s, cls, cost, itv, leaf))
    for op, kids in ranked:
        if op in ("Var", "Num"):
            return (leaf[kids[0]],
                    rel_bound((op, kids), cls, {}, {}, itv, leaf),
                    abs_bound((op, kids), cls, {}, itv, leaf))
        if any(k == cls or k in ancestors for k in kids):
            continue  # a self-referential spelling would never terminate
        parts = [build(k, classes, cost, itv, leaf, ancestors | {cls})
                 for k in kids]
        rel = {k: r for k, (_, r, _) in zip(kids, parts)}
        ab = {k: a for k, (_, _, a) in zip(kids, parts)}
        return (f"({SPELLING[op]} {' '.join(p[0] for p in parts)})",
                rel_bound((op, kids), cls, rel, ab, itv, leaf),
                abs_bound((op, kids), cls, ab, itv, leaf))
    raise RuntimeError(f"every spelling of {cls} loops back on itself")


def extract(source: str, box: dict, rounds: int):
    """Stages 1-5: (best term over `box`, its two bounds, e-graph literals)."""
    root, classes, leaf = read_egraph(saturate(source, box, rounds))
    itv = analyze_intervals(classes, leaf, box)
    cost = cost_table(classes, itv, leaf)
    term, rel, ab = build(root, classes, cost, itv, leaf)
    literals = {float(leaf[kids[0]]) for spellings in classes.values()
                for op, kids in spellings if op == "Num"}
    return term, rel, ab, literals


# ---------------------------------------------------------------------------
# 6. Branch splitting: when the box straddles a cancellation point, no single
#    term is bounded, but each side of a threshold may be. Try thresholds at
#    zero and at the integer literals the e-graph knows about; the first
#    split where both arms get finite bounds wins. (The arms' boxes share the
#    threshold point, so together they cover the original box.)
# ---------------------------------------------------------------------------

def split_search(source, box, rounds, literals):
    thresholds = sorted(
        ((abs(t), var, t) for var, (lo, hi) in box.items()
         for t in {0.0} | literals if lo < t < hi))
    for _, var, t in thresholds[:8]:
        arms = []
        for side in ("<=", ">"):
            lo, hi = box[var]
            sub = box | {var: (lo, min(hi, t)) if side == "<=" else (max(lo, t), hi)}
            arms.append(extract(source, sub, rounds))
        rel = max(arms[0][1], arms[1][1])
        label = (f"{growth(rel) / ULP:.1f} ulp" if math.isfinite(rel)
                 else "unbounded")
        print(f"  split {var} <= {fmt(t)}: {label}")
        if math.isfinite(rel):
            return var, t, arms
    return None


def fmt(t: float) -> str:
    return str(int(t)) if t == int(t) else repr(t)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def read_benchmark(name: str):
    source = (HERE / "benchmarks" / "egglog" / f"{name}.egglog").read_text()
    reference = source.splitlines()[0].removeprefix(";; ")
    raw = json.loads((HERE / "benchmarks" / "intervals.json").read_text())
    box = {v: tuple(float(x) for x in span.strip("[]").split(","))
           for v, span in raw.get(name, {}).items()}
    return source, reference, box


def run(name: str, rounds: int) -> dict:
    source, reference, box = read_benchmark(name)
    print(f"\n{name}   box: {box or '(none)'}\n  reference: {reference}")

    term, rel, ab, literals = extract(source, box, rounds)
    branches = None
    if not math.isfinite(rel) and box:
        if (found := split_search(source, box, rounds, literals)) is not None:
            var, t, ((then_term, tr, ta, _), (else_term, er, ea, _)) = found
            rel, ab = max(tr, er), max(ta, ea)
            if then_term == else_term:  # same form on both sides: skip the if
                term = then_term
            else:
                term = f"(if (<= {var} {fmt(t)}) {then_term} {else_term})"
                branches = {"var": var, "threshold": t,
                            "then": then_term, "else": else_term}

    variables = re.match(r"\(FPCore \(([^)]*)\)", reference).group(1)
    program = f"(FPCore ({variables}) {term})"
    bound = (f"~{growth(rel) / ULP:.1f} ulp" if math.isfinite(rel) else
             f"abs {ab:.1e}" if math.isfinite(ab) else "unbounded")
    print(f"  extracted ({bound}): {program}")
    return {"reference": reference, "box": box, "program": program,
            "body": term, "branches": branches,
            "predicted_ulps": growth(rel) / ULP if math.isfinite(rel) else None,
            "predicted_abs": ab if math.isfinite(ab) else None}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("benchmark", help="benchmark name, or `all`")
    p.add_argument("--rounds", type=int, default=4,
                   help="saturation rounds (more = bigger e-graph, slower)")
    args = p.parse_args()
    names = (sorted(f.stem for f in (HERE / "benchmarks" / "egglog").glob("*.egglog"))
             if args.benchmark == "all" else [args.benchmark])

    path = HERE / "results.json"  # merged, so single-benchmark reruns just update
    results = json.loads(path.read_text()) if path.exists() else {}
    for name in names:
        try:
            results[name] = run(name, args.rounds)
        except Exception as e:
            print(f"  !! {name} failed: {e!r}")
    path.write_text(json.dumps(results, indent=2, sort_keys=True))
    print(f"\nwrote {path} -- `uv run check.py` adds FPTaylor measurements")


if __name__ == "__main__":
    main()
