# /// script
# requires-python = ">=3.10"
# ///
"""Score the extracted programs against Herbie, inside Herbie's own harness.

Each benchmark becomes one FPCore whose body is the reference and whose
extracted program is attached as an `:alt` target; a single `herbie report`
then scores all three -- reference (`start`), ours (`target`), Herbie's own
rewrite (`end`) -- on the same sampled points with Herbie's average-bits
metric (lower is better). Herbie runs on this directory's arithmetic-only
platform (herbie_platform.rkt) so the comparison is search-vs-search, not
vocabulary. A second table compares *worst-case* FPTaylor bounds of our
program (from check.py's measurements) against Herbie's output program.

Reads results.json (run extract.py first, and check.py for the worst-case
table); writes herbie.md and the raw report under herbie/.

Usage:
    uv run herbie.py [--timeout 300]   # needs herbie, or racket + herbie pkg
"""

import argparse
import json
import re
import shutil
import subprocess
import sys

import check  # FPTaylor plumbing and the s-expression parser

from pathlib import Path

HERE = Path(__file__).parent


def herbie_cmd() -> list[str] | None:
    if shutil.which("herbie"):
        return ["herbie"]
    if shutil.which("racket"):
        return ["racket", "-l", "herbie", "--"]
    return None


def body_of(program: str) -> str:
    """The body text of '(FPCore (vars) BODY)'."""
    return program[program.index(") ") + 2:-1]


def programs_of(r: dict) -> list[str]:
    return list(dict.fromkeys(  # every distinct portfolio candidate
        c["program"] for c in r.get("candidates") or [r]))


def to_fpcore(name: str, r: dict) -> str:
    """The reference as an FPCore: box as :pre, each candidate as an :alt."""
    variables = " ".join(check.parse(r["reference"])[1])
    pre = " ".join(f"(<= {lo} {v} {hi})" for v, (lo, hi) in r["box"].items())
    alts = "\n".join(f" :alt {body_of(p)}" for p in programs_of(r))
    return (f"(FPCore ({variables})\n :name \"{name}\"\n"
            f" :pre (and {pre})\n{alts}\n"
            f" {body_of(r['reference'])})")


def herbie_to_ast(output: str):
    """Herbie's typed output -> plain prefix AST; ValueError on an operator
    outside the subset (then we can't FPTaylor it)."""
    output = re.sub(r"#s\(literal ([^ ]+) \w+\)", r"\1", output)

    def convert(node):
        if isinstance(node, str):
            if re.fullmatch(r"-?\d+/\d+", node):
                return ["/", *node.split("/")]
            return node.removesuffix(".f64")
        head = node[0].removesuffix(".f64")
        args = [convert(a) for a in node[1:]]
        if head == "neg":
            return ["-", args[0]]
        if head in ("+", "-", "*", "/", "sqrt"):
            return [head, *args]
        raise ValueError(f"{head!r} outside the subset")

    return convert(check.parse(output))


def worst_cell(m: dict | None) -> str:
    if not m:
        return "-"
    if m.get("rel_err_ulps") is not None:
        return f"{m['rel_err_ulps']:.1f} ulp" + ("*" if m.get("derived") else "")
    if m.get("abs_err") is not None:
        return f"{m['abs_err']:.1e} abs"
    return "-"


def winner(ours, herb, margin=0.0) -> str:
    if ours is None or herb is None:
        return "-"
    return ("herbie" if herb < ours - margin else
            "ours" if ours < herb - margin else "tie")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--timeout", type=int, default=300,
                   help="herbie budget per benchmark, seconds")
    args = p.parse_args()
    if herbie_cmd() is None:
        sys.exit("herbie not found: install it, or racket with the herbie package")
    results = json.loads((HERE / "results.json").read_text())

    hdir = HERE / "herbie"
    hdir.mkdir(exist_ok=True)
    cores = [to_fpcore(name, r) for name, r in sorted(results.items())]
    (hdir / "input.fpcore").write_text("\n\n".join(cores) + "\n")
    print(f"herbie report on {len(cores)} benchmarks (runs Herbie's full search"
          f" -- takes a while)")
    subprocess.run(
        herbie_cmd() + ["report", "--platform", str(HERE / "herbie_platform.rkt"),
                        "--seed", "1", "--timeout", str(args.timeout),
                        str(hdir / "input.fpcore"), str(hdir / "report")],
        timeout=(len(cores) + 2) * args.timeout)
    tests = json.loads((hdir / "report" / "results.json").read_text())["tests"]

    # average-bits scores (Herbie's own metric); target = our :alt program
    rows = []
    for t in sorted(tests, key=lambda t: t["name"]):
        num = lambda x: x if isinstance(x, (int, float)) else None
        targets = [num(x[1]) for x in (t.get("target") or [])]  # [[cost, bits]]
        targets = [x for x in targets if x is not None]
        rows.append({"name": t["name"], "reference": num(t.get("start")),
                     "ours": min(targets, default=None),  # best candidate
                     "herbie": num(t.get("end")),
                     "herbie_program": t.get("output")})

    # worst-case bounds: ours from check.py's measurements, Herbie's measured
    # here (branch-free outputs only -- FPTaylor doesn't take `if`)
    for row in rows:
        r = results[row["name"]]
        row["ours_worst"] = r.get("measured")
        row["herbie_worst"] = None
        try:
            ast = herbie_to_ast(row["herbie_program"])
            if "if" not in row["herbie_program"]:
                row["herbie_worst"] = check.fptaylor(check.infix(ast), r["box"])
        except (ValueError, TypeError):
            pass

    avg = ["| benchmark | reference | ours | herbie | winner |",
           "|---|--:|--:|--:|---|"]
    f = lambda x: f"{x:.2f}" if x is not None else "-"
    score = {"ours": 0, "herbie": 0, "tie": 0, "-": 0}
    for r in rows:
        w = winner(r["ours"], r["herbie"], margin=0.1)
        score[w] += 1
        avg.append(f"| {r['name']} | {f(r['reference'])} | {f(r['ours'])} "
                   f"| {f(r['herbie'])} | {w} |")

    worst = ["| benchmark | ours (measured) | herbie (measured) | winner |",
             "|---|--:|--:|---|"]
    wscore = {"ours": 0, "herbie": 0, "tie": 0, "-": 0}
    for r in rows:
        o, h = r["ours_worst"] or {}, r["herbie_worst"] or {}
        key = next((k for k in ("rel_err", "abs_err")
                    if o.get(k) is not None and h.get(k) is not None), None)
        w = winner(o.get(key), h.get(key)) if key else "-"
        wscore[w] += 1
        worst.append(f"| {r['name']} | {worst_cell(r['ours_worst'])} "
                     f"| {worst_cell(r['herbie_worst'])} | {w} |")

    md = ("# Cost-based extraction vs Herbie\n\n"
          "## Average bits of error (Herbie's metric, same sampled points)\n\n"
          f"Lower is better. ours {score['ours']} / herbie {score['herbie']} / "
          f"tie {score['tie']} / unscored {score['-']}\n\n" + "\n".join(avg) +
          "\n\n## Worst-case error over the box (FPTaylor)\n\n"
          "`-` for Herbie means its output branches or left the subset, so it "
          f"wasn't bounded. ours {wscore['ours']} / herbie {wscore['herbie']} / "
          f"tie {wscore['tie']} / uncompared {wscore['-']}\n\n" + "\n".join(worst) + "\n")
    (HERE / "herbie.md").write_text(md)
    print(md)
    print(f"wrote {HERE / 'herbie.md'}")


if __name__ == "__main__":
    main()
