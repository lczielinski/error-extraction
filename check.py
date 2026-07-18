# /// script
# requires-python = ">=3.10"
# ///
"""Measure every program in results.json (written by extract.py) with FPTaylor
and summarize against the reference.

For each benchmark it bounds the worst-case double-rounding error of the
extracted program and of the reference over the same box (a branching program
is bounded per arm over its half of the box, worst arm wins). Measurements are
written back into results.json; the comparison table goes to summary.md.

Usage:
    uv run check.py            # needs `fptaylor` on PATH (eval $(opam env))
"""

import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
ULP = 2.0 ** -52
TIMEOUT = 300  # seconds per FPTaylor call
CONFIG = "abs-error = true\nrel-error = true\n"


# ---------------------------------------------------------------------------
# FPCore text -> FPTaylor's infix syntax
# ---------------------------------------------------------------------------

def parse(text: str):
    """One s-expression as nested lists of tokens."""
    tokens = re.findall(r"\(|\)|[^\s()]+", text)

    def node():
        t = tokens.pop(0)
        if t != "(":
            return t
        out = []
        while tokens[0] != ")":
            out.append(node())
        tokens.pop(0)
        return out

    return node()


def infix(node) -> str:
    if isinstance(node, str):
        return node
    op, *args = node
    if op == "sqrt":
        return f"sqrt({infix(args[0])})"
    if op == "-" and len(args) == 1:
        return f"(-({infix(args[0])}))"
    return f"({infix(args[0])} {op} {infix(args[1])})"


# ---------------------------------------------------------------------------
# Run FPTaylor on one expression over one box
# ---------------------------------------------------------------------------

def fptaylor(expr: str, box: dict) -> dict:
    """Bound `expr` (FPTaylor's infix syntax; use infix(parse(..)) to convert
    an FPCore body) evaluated in doubles over `box`."""
    decls = "\n".join(f"  float64 {v} in [{lo}, {hi}];"
                      for v, (lo, hi) in box.items())
    problem = f"Variables\n{decls}\n\nExpressions\n  result rnd64= {expr};\n"
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as inp, \
         tempfile.NamedTemporaryFile("w", suffix=".cfg", delete=False) as cfg:
        inp.write(problem)
        cfg.write(CONFIG)
    try:
        out = subprocess.run(["fptaylor", inp.name, "-c", cfg.name],
                             capture_output=True, text=True, timeout=TIMEOUT)
        out = out.stdout + out.stderr
    except subprocess.TimeoutExpired:
        return {"abs_err": None, "rel_err": None, "rel_err_ulps": None,
                "timeout": True}
    finally:
        Path(inp.name).unlink()
        Path(cfg.name).unlink()

    def grab(label):
        m = re.search(rf"{label} \((?:exact|approximate)\):\s*([0-9.eE+-]+)", out)
        return float(m.group(1)) if m else None

    abs_err, rel_err, derived = grab("Absolute error"), grab("Relative error"), False
    # FPTaylor often skips rel error through divisions; if the value's range
    # excludes zero, abs_err / min|value| is a (crude) rel bound
    m = re.search(r"Bounds \(without rounding\):\s*\[([^,]+),\s*([^\]]+)\]", out)
    lo, hi = (float(m.group(1)), float(m.group(2))) if m else (-1.0, 1.0)
    if rel_err is None and abs_err is not None and (lo > 0 or hi < 0):
        rel_err, derived = abs_err / min(abs(lo), abs(hi)), True
    return {"abs_err": abs_err, "rel_err": rel_err, "derived": derived,
            "rel_err_ulps": rel_err / ULP if rel_err is not None else None}


def measure(record: dict) -> dict:
    """The extracted program's bound; a split program is the worst of its arms."""
    box = record["box"]
    if not record["branches"]:
        return fptaylor(infix(parse(record["body"])), box)
    var, t = record["branches"]["var"], record["branches"]["threshold"]
    lo, hi = box[var]
    arms = [fptaylor(infix(parse(record["branches"]["then"])),
                     box | {var: (lo, min(hi, t))}),
            fptaylor(infix(parse(record["branches"]["else"])),
                     box | {var: (max(lo, t), hi)})]
    worst = {}
    for key in ("abs_err", "rel_err"):  # a bound needs one from *every* arm
        vals = [a.get(key) for a in arms]
        worst[key] = None if None in vals else max(vals)
    worst["rel_err_ulps"] = (worst["rel_err"] / ULP
                             if worst["rel_err"] is not None else None)
    worst["derived"] = any(a.get("derived") for a in arms)
    worst["timeout"] = any(a.get("timeout") for a in arms)
    worst["arms"] = arms
    return worst


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def verdict(ours: dict, ref: dict) -> str:
    for key, label in (("rel_err", ""), ("abs_err", " (abs)")):
        if ours.get(key) is not None and ref.get(key) is not None:
            word = ("improved" if ours[key] < 0.99 * ref[key] else
                    "worse" if ours[key] > 1.01 * ref[key] else "no-change")
            return word + label
    return "unmeasurable"


def ulps(measured: dict) -> str:
    if measured.get("timeout"):
        return "timeout"
    if measured.get("rel_err_ulps") is None:
        return "-"
    return f"{measured['rel_err_ulps']:.1f}" + ("*" if measured.get("derived") else "")


def cells(r: dict) -> tuple[str, str, str]:
    """(predicted, measured, reference) in the row's metric: relative ulps
    when both sides have a relative bound, else absolute error (scientific)."""
    ours, ref = r["measured"], r["measured_reference"]
    if ours.get("rel_err") is not None and ref.get("rel_err") is not None:
        pred = (f"{r['predicted_ulps']:.1f}"
                if r.get("predicted_ulps") is not None else "-")
        return pred, ulps(ours), ulps(ref)

    def sci(m):
        if m.get("timeout"):
            return "timeout"
        return f"{m['abs_err']:.1e}" if m.get("abs_err") is not None else "-"

    pred = (f"{r['predicted_abs']:.1e}"
            if r.get("predicted_abs") is not None else "-")
    return pred, sci(ours), sci(ref)


def main() -> None:
    if shutil.which("fptaylor") is None:
        sys.exit("fptaylor not on PATH -- try `eval $(opam env)` first")
    path = HERE / "results.json"
    if not path.exists():
        sys.exit(f"{path} not found -- run `uv run extract.py all` first")
    results = json.loads(path.read_text())

    for name, r in sorted(results.items()):
        r["measured"] = measure(r)
        r["measured_reference"] = fptaylor(infix(parse(r["reference"])[2]),
                                           r["box"])
        pred, ours, ref = cells(r)
        print(f"{name:35s} predicted={pred:>10} measured={ours:>10} "
              f"reference={ref:>10}  "
              f"{verdict(r['measured'], r['measured_reference'])}", flush=True)
        path.write_text(json.dumps(results, indent=2, sort_keys=True))

    rows = [(name, r) for name, r in sorted(results.items())]
    counts = {}
    for _, r in rows:
        v = verdict(r["measured"], r["measured_reference"])
        counts[v] = counts.get(v, 0) + 1
    lines = [
        "# Cost-based extraction vs reference (FPTaylor worst-case bounds)", "",
        "predicted = this repo's cost bound; measured/reference = FPTaylor on the",
        "extracted program / the original, same box. Relative error in ulps of",
        "2^-52; rows where the value range straddles zero (relative error",
        "undefined) compare absolute error instead, in scientific notation,",
        "and say `(abs)`. `*` = crude bound derived from the absolute one.", "",
        *(f"- {v}: **{n}/{len(rows)}**" for v, n in sorted(counts.items())), "",
        "| benchmark | predicted | measured | reference | vs reference |",
        "|---|--:|--:|--:|---|",
    ]
    for name, r in rows:
        pred, ours, ref = cells(r)
        lines.append(f"| {name} | {pred} | {ours} | {ref} | "
                     f"{verdict(r['measured'], r['measured_reference'])} |")
    (HERE / "summary.md").write_text("\n".join(lines) + "\n")
    print(f"\nwrote {path} and {HERE / 'summary.md'}")


if __name__ == "__main__":
    main()
