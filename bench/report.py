"""Join results.json and external.json into a markdown table, one row per core.

    uv run python bench/report.py                      # -> bench/report.md
    uv run python bench/report.py --sort gain
    uv run python bench/report.py --width 0            # do not truncate expressions
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
METRICS = ("abs", "rel")            # the two FPTaylor also reports
STATUS = {"nobound": "n/b", "timeout": "t/o", "error": "err"}
NONE = "&mdash;"                    # no bound exists
NA = "&middot;"                     # not recorded for this program


def _num(x) -> str:
    if x is None:
        return NONE
    return "0" if x == 0 else f"{x:.3g}"     # costex can report -0.0


def _code(expr: str, width: int) -> str:
    if width and len(expr) > width:
        expr = expr[:width - 1] + "…"
    return "`" + expr.replace("|", "\\|") + "`"


def programs(r: dict) -> list:
    """(labels, variant, expression) for the seed and each distinct rewrite.

    The abs-, rel- and d-optimal programs are often one expression, and often
    the seed itself, so they collapse onto one labelled line.
    """
    order, labels, variant = [], {}, {}
    entries = [("seed", "seed", r["expr"])]
    entries += [(m, f"best_{m}", r.get(f"best_expr_{m}"))
                for m in ("abs", "rel", "d")]
    for label, v, expr in entries:
        if not expr:
            continue
        if expr not in labels:
            order.append(expr)
            labels[expr], variant[expr] = [], v
        labels[expr].append(label)
    return [(labels[e], variant[e], e) for e in order]


def _costex(r: dict, labels: list, m: str) -> str:
    """costex records a bound only for the metric it optimised, so a rewrite
    chosen for one metric has no entry under the other."""
    if m in labels:
        return _num(r.get(f"best_{m}"))
    if "seed" in labels:
        return _num(r.get(f"seed_{m}"))
    return NA


def _fptaylor(ft: dict, variant: str, m: str) -> str:
    rep = (ft or {}).get(variant)
    if rep is None:
        return NA
    if rep["status"] != "ok":
        return STATUS.get(rep["status"], rep["status"])
    return _num(rep.get(m))


def gain(r: dict) -> float:
    """The best ratio costex claims over its own metrics, for sorting."""
    out = 1.0
    for m in METRICS:
        seed, best = r.get(f"seed_{m}"), r.get(f"best_{m}")
        if seed and best and best > 0:
            out = max(out, seed / best)
    return out


def row(r: dict, ft: dict, width: int) -> str:
    progs = programs(r)
    cells = [
        f"**{r.get('name') or r['file']}**",
        # label and expression on one line, so a wrapped expression is never
        # mistaken for a second program: every program starts at a "labels:"
        "<br>".join(f"{', '.join(labels)}: {_code(expr, width)}"
                    for labels, _, expr in progs),
    ]
    for m in METRICS:
        cells.append("<br>".join(_costex(r, labels, m) for labels, _, _ in progs))
        cells.append("<br>".join(_fptaylor(ft, v, m) for _, v, _ in progs))
    return "| " + " | ".join(cells) + " |"


def markdown(res: dict, ext: dict, sort: str, width: int) -> str:
    ft_by_file = {r["file"]: r["ft"] for r in ext["results"]}
    rows = [r for r in res["results"] if r["status"] == "ok"]
    rows.sort(key=(lambda r: -gain(r)) if sort == "gain" else (lambda r: r["file"]))

    out = ["# costex vs FPTaylor", "",
           f"- {len(rows)} cores, costex at {res.get('iters')} iterations",
           f"- FPTaylor {ext.get('fptaylor_version')}, "
           f"`{' '.join(ext.get('options', []))}`",
           f"- FPTaylor data for {sum(1 for r in rows if r['file'] in ft_by_file)} of them",
           f"- sorted by {'costex claimed gain' if sort == 'gain' else 'file name'}",
           "",
           "| Core | Program | costex mu_abs | FPTaylor abs "
           "| costex mu_rel | FPTaylor rel |",
           "|---|---|---:|---:|---:|---:|"]
    out += [row(r, ft_by_file.get(r["file"]), width) for r in rows]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="report")
    ap.add_argument("--results", default=os.path.join(HERE, "results.json"))
    ap.add_argument("--external", default=os.path.join(HERE, "external.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "report.md"))
    ap.add_argument("--sort", choices=("name", "gain"), default="name")
    ap.add_argument("--width", type=int, default=70,
                    help="truncate expressions to this many chars, 0 for no limit "
                         "(default %(default)s)")
    args = ap.parse_args(argv)

    with open(args.results) as f:
        res = json.load(f)
    with open(args.external) as f:
        ext = json.load(f)
    text = markdown(res, ext, args.sort, args.width)
    with open(args.out, "w") as f:
        f.write(text)
    print(f"{text.count(chr(10)) } lines -> {os.path.relpath(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
