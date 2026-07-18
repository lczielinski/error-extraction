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
  4. cost_table       a sound relative-error bound per e-class
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
# 4. Cost: a sound bound on relative rounding error, composed per operator.
#
#    rel[c] = d means: evaluating class c's chosen term in doubles gives
#    computed = exact*(1+e) with |e| <= d, at every point of the box.
#    Each operation's own rounding contributes a factor (1+u), |u| <= 2^-53
#    (the standard model; assumes no overflow/underflow, like NumFuzz).
#
#    Multiplicative ops compose cleanly.  Addition of same-signed operands
#    can't cancel, so errors average: max(da, db).  Otherwise we pay the
#    condition number  (|a|max*da + |b|max*db) / min|a+b|,  taken from the
#    intervals -- infinite when the sum's enclosure contains zero, because
#    then no finite relative error bound exists (this is the case NumFuzz's
#    type system rules out; here it simply loses to bounded spellings).
# ---------------------------------------------------------------------------

def compose(a: float, b: float) -> float:
    """(1+a)(1+b) - 1: how two relative errors stack. Written as a + b + a*b
    so the formula itself never cancels (naively, 1 + 2^-53 - 1 == 0.0!)."""
    return a + b + a * b if a < INF and b < INF else INF


def worst_abs_error(iv, d):
    """|computed - exact| <= max|value| * d, over the interval."""
    return 0.0 if d == 0.0 else max(abs(iv[0]), abs(iv[1])) * d


def rel_bound(spelling, cls, rel, itv, leaf):
    op, kids = spelling
    if op == "Var":
        return 0.0  # inputs are doubles, taken as exact (as FPTaylor does)
    if op == "Num":
        n = int(leaf[kids[0]])
        return 0.0 if float(n) == n else U  # int literals over 2^53 round once
    da = rel[kids[0]]
    if op == "Neg":
        return da  # sign flip is exact
    if op == "Sqrt":
        if da > 1.0:
            return INF  # operand may have lost its sign entirely
        # sqrt(1 +- da) pulls the error toward 1 (~halves it), then one rounding;
        # sqrt(1+x)-1 is spelled x/(sqrt(1+x)+1) to avoid cancelling, as above
        over = compose(da / (math.sqrt(1 + da) + 1), U)
        under = da / (1 + math.sqrt(1 - da)) + U * math.sqrt(1 - da)
        return up(max(over, under))
    db = rel[kids[1]]
    if op == "Mul":
        return up(compose(compose(da, db), U))
    if op == "Div":  # 1/(1-db) == 1 + db/(1-db)
        return INF if db >= 1.0 else up(compose(compose(da, db / (1 - db)), U))

    # Add/Sub; treat a - b as a + (-b) so one analysis covers both
    a, b = itv[kids[0]], itv[kids[1]]
    if op == "Sub":
        b = (-b[1], -b[0])
    if (a[0] >= 0 and b[0] >= 0) or (a[1] <= 0 and b[1] <= 0):
        return up(compose(max(da, db), U))  # same signs: no cancellation
    err = worst_abs_error(a, da) + worst_abs_error(b, db)
    if err == 0.0:
        return U  # both operands exact; only the final rounding remains
    zlo, zhi = itv[cls]
    zmin = zlo if zlo > 0 else -zhi if zhi < 0 else 0.0  # min |exact result|
    return INF if zmin == 0.0 else up(compose(err / zmin, U))


def spelling_cost(spelling, cls, cost, itv, leaf):
    """(relative error bound, term size) -- compared lexicographically, so
    size breaks ties, and picks smallest terms when nothing is bounded."""
    op, kids = spelling
    if op in ("Var", "Num"):
        return (rel_bound(spelling, cls, {}, itv, leaf), 1)
    return (rel_bound(spelling, cls, {k: cost[k][0] for k in kids}, itv, leaf),
            1 + sum(cost[k][1] for k in kids))


def cost_table(classes, itv, leaf):
    cost = {c: (INF, INF) for c in classes}
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
            return leaf[kids[0]], rel_bound((op, kids), cls, {}, itv, leaf)
        if any(k == cls or k in ancestors for k in kids):
            continue  # a self-referential spelling would never terminate
        parts = [build(k, classes, cost, itv, leaf, ancestors | {cls})
                 for k in kids]
        rel = {k: r for k, (_, r) in zip(kids, parts)}
        return (f"({SPELLING[op]} {' '.join(text for text, _ in parts)})",
                rel_bound((op, kids), cls, rel, itv, leaf))
    raise RuntimeError(f"every spelling of {cls} loops back on itself")


def extract(source: str, box: dict, rounds: int):
    """Run stages 1-5: (best term over `box`, its bound, e-graph's literals)."""
    root, classes, leaf = read_egraph(saturate(source, box, rounds))
    itv = analyze_intervals(classes, leaf, box)
    cost = cost_table(classes, itv, leaf)
    term, rel = build(root, classes, cost, itv, leaf)
    literals = {float(leaf[kids[0]]) for spellings in classes.values()
                for op, kids in spellings if op == "Num"}
    return term, rel, literals


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
        (then_term, then_rel, _), (else_term, else_rel, _) = arms
        rel = max(then_rel, else_rel)
        print(f"  split {var} <= {fmt(t)}: "
              f"{f'{rel / ULP:.1f} ulp' if math.isfinite(rel) else 'unbounded'}")
        if math.isfinite(rel):
            return var, t, then_term, else_term, rel
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

    term, rel, literals = extract(source, box, rounds)
    branches = None
    if not math.isfinite(rel) and box:
        if (found := split_search(source, box, rounds, literals)) is not None:
            var, t, then_term, else_term, rel = found
            if then_term == else_term:  # same form on both sides: skip the if
                term = then_term
            else:
                term = f"(if (<= {var} {fmt(t)}) {then_term} {else_term})"
                branches = {"var": var, "threshold": t,
                            "then": then_term, "else": else_term}

    variables = re.match(r"\(FPCore \(([^)]*)\)", reference).group(1)
    program = f"(FPCore ({variables}) {term})"
    bound = f"~{rel / ULP:.1f} ulp" if math.isfinite(rel) else "unbounded"
    print(f"  extracted ({bound}): {program}")
    return {"reference": reference, "box": box, "program": program,
            "body": term, "branches": branches,
            "predicted_ulps": rel / ULP if math.isfinite(rel) else None}


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
