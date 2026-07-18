# /// script
# requires-python = ">=3.10"
# ///
"""Score the extracted programs against Daisy (Darulova et al.) -- the closest
incumbent: Daisy also optimizes a *sound worst-case* error bound, but by
genetic search over rewrites with a static analysis in the loop, where this
repo extracts the optimum from an e-graph against a compositional bound.

For each benchmark, the reference becomes a Daisy input; `daisy --rewrite
--codegen` runs its rewriting optimization and reports its certified
absolute/relative bounds; the rewritten program is then measured with
FPTaylor over the same box and compared against ours (check.py's
measurements in results.json). Writes daisy.md; inputs and Daisy's outputs
land under daisy-work/.

Needs a Daisy checkout built with `sbt compile && sbt script` (default
~/daisy, override with DAISY_DIR) and java on PATH (or Homebrew's openjdk).

Usage:
    uv run daisy.py [--timeout 300]
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import check  # FPTaylor plumbing and the s-expression parser

HERE = Path(__file__).parent
DAISY = Path(os.environ.get("DAISY_DIR", Path.home() / "daisy"))
ULP = 2.0 ** -52


def to_scala(node) -> str:
    """FPCore body -> Daisy's Real expression (integer literals as doubles)."""
    if isinstance(node, str):
        return f"{node}.0" if re.fullmatch(r"-?\d+", node) else node
    op, *args = node
    if op == "sqrt":
        return f"sqrt({to_scala(args[0])})"
    if op == "-" and len(args) == 1:
        return f"(-({to_scala(args[0])}))"
    return f"({to_scala(args[0])} {op} {to_scala(args[1])})"


def daisy_input(name: str, r: dict) -> str:
    ast = check.parse(r["reference"])
    variables, body = ast[1], ast[2]
    args = ", ".join(f"{v}: Real" for v in variables)
    pre = " && ".join(f"{lo} <= {v} && {v} <= {hi}"
                      for v, (lo, hi) in r["box"].items())
    return (f"import daisy.lang._\nimport Real._\n\n"
            f"object {name} {{\n"
            f"  def f({args}): Real = {{\n"
            f"    require({pre})\n"
            f"    {to_scala(body)}\n"
            f"  }}\n}}\n")


def grab(label: str, out: str):
    m = re.search(rf"{label}:\s*([0-9.eE+-]+)", out)
    return float(m.group(1)) if m else None


def rewritten_body(name: str) -> str | None:
    """The single-expression body of Daisy's generated output/<name>.scala --
    already infix, which is FPTaylor's syntax for our operator subset."""
    path = DAISY / "output" / f"{name}.scala"
    if not path.exists():  # daisy failed on this benchmark
        return None
    src = path.read_text()
    m = re.search(r"\): Double = \{\n(.*?)\n\s*\}", src, re.DOTALL)
    if m is None:
        return None
    lines = [l.strip() for l in m.group(1).splitlines() if l.strip()]
    if len(lines) != 1 or lines[0].startswith("val"):
        return None  # let-bound output; skip rather than mis-measure
    return lines[0]


def run_daisy(name: str, r: dict, timeout: int) -> dict:
    work = HERE / "daisy-work"
    work.mkdir(exist_ok=True)
    src = work / f"{name}.scala"
    src.write_text(daisy_input(name, r))
    env = os.environ | {"PATH": "/opt/homebrew/opt/openjdk/bin:"
                                + os.environ["PATH"]}
    try:
        out = subprocess.run(
            [str(DAISY / "daisy"), "--rewrite", "--rewrite-seed=1",
             "--codegen", str(src)],
            cwd=DAISY, env=env, capture_output=True, text=True,
            timeout=timeout)
        out = re.sub(r"\x1b\[[0-9;]*m", "", out.stdout + out.stderr)
    except subprocess.TimeoutExpired:
        return {"timeout": True}
    result = {"certified_abs": grab("Absolute error", out),
              "certified_rel": grab("Relative error", out),
              "program": rewritten_body(name)}
    if result["program"] is not None:
        result["measured"] = check.fptaylor(result["program"], r["box"])
    return result


def cell(m: dict | None, rel_key: str, abs_key: str) -> str:
    if not m:
        return "-"
    if m.get("timeout"):
        return "timeout"
    if m.get(rel_key) is not None:
        return f"{m[rel_key] / ULP:.1f} ulp"
    if m.get(abs_key) is not None:
        return f"{m[abs_key]:.1e} abs"
    return "-"


def winner(ours: dict | None, daisy: dict | None) -> str:
    for key in ("rel_err", "abs_err"):
        if (ours or {}).get(key) is not None and (daisy or {}).get(key) is not None:
            return ("daisy" if daisy[key] < ours[key] else
                    "ours" if ours[key] < daisy[key] else "tie")
    return "-"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--timeout", type=int, default=300,
                   help="daisy budget per benchmark, seconds")
    args = p.parse_args()
    if not (DAISY / "daisy").exists():
        sys.exit(f"no daisy script at {DAISY} -- build it, or set DAISY_DIR")
    results = json.loads((HERE / "results.json").read_text())

    rows, score = [], {"ours": 0, "daisy": 0, "tie": 0, "-": 0}
    for name, r in sorted(results.items()):
        d = run_daisy(name, r, args.timeout)
        ours = {"rel_err": (r.get("predicted_ulps") or None) and
                           r["predicted_ulps"] * ULP,
                "abs_err": r.get("predicted_abs")}
        w = winner(r.get("measured"), d.get("measured"))
        score[w] += 1
        rows.append((name, ours, d, w))
        print(f"{name:32s} ours={cell(r.get('measured'), 'rel_err', 'abs_err'):>14} "
              f"daisy={cell(d.get('measured'), 'rel_err', 'abs_err'):>14}  {w}",
              flush=True)

    lines = [
        "# Cost-based extraction vs Daisy (worst-case error over the box)", "",
        "Daisy rewrites by genetic search against its own sound static bound",
        "(seed 1, default 30x30). `certified` = each tool's own bound;",
        "`measured` = FPTaylor on each tool's output program, same box --",
        "the neutral judge and the basis of `winner` (relative error where",
        "both sides have it, else absolute). `-` for Daisy's measured column",
        "means its output used let-bindings and was not re-measured.", "",
        f"measured winner: ours {score['ours']} / daisy {score['daisy']} / "
        f"tie {score['tie']} / uncompared {score['-']}", "",
        "| benchmark | ours certified | daisy certified | ours measured "
        "| daisy measured | winner |",
        "|---|--:|--:|--:|--:|---|",
    ]
    for name, ours, d, w in rows:
        r = results[name]
        lines.append(
            f"| {name} | {cell(ours, 'rel_err', 'abs_err')} "
            f"| {cell({'rel_err': d.get('certified_rel'), 'abs_err': d.get('certified_abs'), 'timeout': d.get('timeout')}, 'rel_err', 'abs_err')} "
            f"| {cell(r.get('measured'), 'rel_err', 'abs_err')} "
            f"| {cell(d.get('measured'), 'rel_err', 'abs_err')} | {w} |")
    (HERE / "daisy.md").write_text("\n".join(lines) + "\n")
    print(f"\nwrote {HERE / 'daisy.md'}")


if __name__ == "__main__":
    main()
