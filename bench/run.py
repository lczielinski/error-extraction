"""The whole benchmark in one command: costex, the external tools, the tables.

    uv run python bench/run.py                  # every phase, the whole corpus
    uv run python bench/run.py --probe          # check the toolchain and exit
    uv run python bench/run.py --summarize      # re-read the results, run nothing
    uv run python bench/run.py --phases report  # just redraw the tables

Phases run in this order, handing on through bench/results, so each can be run
alone against what the last one left:

    costex    equality saturation over bench/cores       -> results.json
    external  FPTaylor and Daisy, same programs and box  -> external.json
    rewrite   Daisy's rewriter against costex's, judged  -> rewrite.json
    report    the bounds, and the two rewriters          -> report.md, rewrites.md

--limit, --only and --kind pick the cores, in every phase alike.  The tools live
in bench/tools, one module each.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from functools import partial

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from tools import TOOLS, analyze, common, daisy                # noqa: E402

from costex import analysis as A                               # noqa: E402
from costex import egg, extract                                # noqa: E402
from costex.fpcore import parse_fpcore, to_sexp                # noqa: E402

# The head-to-head and the tool-tightness check are on absolute error alone.
JUDGED = common.BY_NAME["abs"]
KINDS = ("rewrite", "analysis")
SLACK = 0.999                # a bound has to beat another by this much to count
EGGLOG_TIMEOUT = 60.0        # seconds per core
EXTRACT_TIMEOUT = 30.0       # a step cap alone does not bound extraction
TOOL_TIMEOUT = 300.0         # seconds per expression per tool
REWRITE_SEED = 1490          # Daisy's genetic seed, so a run is repeatable
WIDTH = 70                   # the tables truncate expressions to this


def kind(file: str) -> str:
    """The core's :cx-kind tag.  analysis means believed optimal, so there is no
    rearrangement to try and the run only measures the bound."""
    return str(common.core(file).props.get(":cx-kind", "rewrite"))


def _path(args, name: str) -> str:
    return os.path.join(args.results_dir, name)


def corpus(args) -> list:
    files = sorted(f for f in os.listdir(common.CORES) if f.endswith(".fpcore"))
    if args.only:
        files = [f for f in files if args.only in f]
    if args.kind:
        files = [f for f in files if kind(f) == args.kind]
    return files[:args.limit] if args.limit else files


def _read(args, name: str, required: bool = True):
    path = _path(args, name)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    if required:
        sys.exit(f"no {os.path.relpath(path)}; run the phase that writes it first")
    return None


def _results(args, name: str = "results.json") -> list:
    keep = set(corpus(args))
    return [r for r in _read(args, name)["results"] if r["file"] in keep]


def _write(args, name: str, payload: dict) -> str:
    os.makedirs(args.results_dir, exist_ok=True)
    with open(_path(args, name), "w") as f:
        json.dump(payload, f, indent=1)
    return os.path.relpath(_path(args, name))


# -- costex --


def _f(x):
    x = float(x)
    return None if math.isinf(x) else x


def run_one(path, *, iters, max_steps) -> dict:
    name = os.path.basename(path)
    out = {"file": name}
    t0 = time.time()
    try:
        core = parse_fpcore(open(path).read())
        A.set_target(53 if core.precision == "binary64" else 24)
        out.update(name=core.name, vars=len(core.args),
                   box_source=str(core.props.get(":cx-box", "pre")),
                   source=str(core.props.get(":cx-source", "")),
                   expr=to_sexp(core.body), precision=core.precision)
        g = egg.build(core.body, core.box, iters=iters, timeout=EGGLOG_TIMEOUT)
        t1 = time.time()
        front = extract.extract(g, max_steps=max_steps, time_limit=EXTRACT_TIMEOUT)
        Ic = g.interval[g.root]
        seed = extract.analyze_program(g, core.body)

        out.update(status="ok",
                   classes=len(g.nodes), nodes=sum(map(len, g.nodes.values())),
                   egglog_s=round(t1 - t0, 3), extract_s=round(time.time() - t1, 3),
                   steps=front.steps, truncated=front.truncated,
                   frontier=len(front.entries.get(g.root, [])),
                   root_interval=[_f(Ic.lo), _f(Ic.hi)])
        for m in common.METRICS:
            out[m.seed] = None if seed is A.BOTTOM else _f(A.METRICS[m.name](seed, Ic))
            best = front.best(g.root, Ic, m.name)
            out[m.best] = _f(best[0]) if best else None
            out[m.best_expr] = to_sexp(best[2]) if best else None
    except subprocess.TimeoutExpired:
        out.update(status="timeout", egglog_s=round(time.time() - t0, 3))
    except egg.BadBox as ex:
        out.update(status="badbox", error=str(ex)[:200])
    except Exception as ex:                    # noqa: BLE001
        out.update(status="error", error=f"{type(ex).__name__}: {ex}"[:200])
    return out


def _metric_lines(group: list, m) -> list:
    seed, best = m.seed, m.best
    live = [r for r in group if r[best] is not None]
    gains = sorted(r[seed] / r[best] for r in live
                   if r[seed] and r[best] and r[best] < r[seed])
    out = [f"    {m.label:<6} bounded {len(live)} of {len(group)}"]
    if gains:
        out.append(f"           {len(gains)} improved, median {gains[len(gains) // 2]:.3g}x, "
                   f"90th pct {gains[int(0.9 * (len(gains) - 1))]:.3g}x, max {gains[-1]:.3g}x")
    return out


def summarize(results: list) -> None:
    st = Counter(r["status"] for r in results)
    print(f"\n{len(results)} cores: " + ", ".join(f"{v} {k}" for k, v in st.most_common()))

    ok = [r for r in results if r["status"] == "ok"]
    if not ok:
        return
    groups = {k: [r for r in ok if kind(r["file"]) == k] for k in KINDS}
    print(f"\n  {len(groups['rewrite'])} rewrite cores, {len(groups['analysis'])} "
          f"analysis cores (:cx-kind, believed optimal)")
    for k in KINDS:
        if groups[k]:
            print(f"\n  {k}")
            for m in common.METRICS:
                print("\n".join(_metric_lines(groups[k], m)))

    trunc = sum(1 for r in ok if r.get("truncated"))
    print(f"\n  extractions stopped early (not provably optimal): {trunc}")
    slow = sorted(ok, key=lambda r: -(r["egglog_s"] + r["extract_s"]))[:3]
    print("  slowest: " + ", ".join(f"{r['file'][:34]} {r['egglog_s'] + r['extract_s']:.1f}s"
                                    for r in slow))


def phase_costex(args) -> None:
    files = [os.path.join(common.CORES, f) for f in corpus(args)]
    work = partial(run_one, iters=args.iters, max_steps=args.max_steps)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        results = []
        for i, r in enumerate(pool.map(work, files), 1):
            results.append(r)
            if i % 25 == 0:
                print(f"  {i}/{len(files)}", flush=True)
    elapsed = time.time() - t0
    out = _write(args, "results.json", {"iters": args.iters,
                                        "elapsed_s": round(elapsed, 1),
                                        "results": results})
    summarize(results)
    print(f"\n  {elapsed:.1f}s wall, {args.jobs} jobs -> {out}")


# -- the external tools --


def collect(results: list, us: list, per_tool: dict) -> list:
    """One record per core: costex's numbers beside each tool's, per variant."""
    per_core = {}
    for tool, reports in per_tool.items():
        for u in us:
            per_core.setdefault(u["file"], {}).setdefault(tool, {})
            for v in u["variants"]:
                per_core[u["file"]][tool][v] = reports[u["name"]]
    keep = ("name", "expr", "root_interval") + tuple(
        k for m in common.METRICS for k in (m.best_expr, m.seed, m.best))
    return [{"file": r["file"], "costex": {k: r.get(k) for k in keep},
             "tools": per_core[r["file"]]}
            for r in results if r["file"] in per_core]


def _seed_bounds(records: list, tool: str) -> str:
    """costex against a tool on the seed: both bound the same thing."""
    n = Counter()
    for r in records:
        rep = r["tools"].get(tool, {}).get("seed")
        ours = r["costex"].get(JUDGED.seed)
        theirs = rep.get(JUDGED.name) if rep and rep["status"] == "ok" else None
        if ours is None:
            n["no costex bound"] += 1
        elif theirs is None:
            n["only costex"] += 1
        else:
            n["tighter" if ours < theirs else "looser" if theirs < ours else "tie"] += 1
    return ", ".join(f"{v} {k}" for k, v in n.most_common())


def _health(records: list) -> None:
    """What landed, why anything did not, and how tight our bounds are."""
    analysis = [r for r in records if kind(r["file"]) == "analysis"]
    print(f"  {len(records)} cores, {len(analysis)} of them analysis cores")
    for tool in sorted({t for r in records for t in r["tools"]}):
        reps = [rep for r in records for rep in r["tools"].get(tool, {}).values()]
        st = Counter(rep["status"] for rep in reps)
        print(f"  {tool:<9} {len(reps)} analyses: "
              + ", ".join(f"{v} {k}" for k, v in st.most_common()))
        why = Counter(rep.get("error", "")[:48] for rep in reps
                      if rep["status"] in ("nobound", "crash", "unsupported"))
        for reason, n in why.most_common(6):
            print(f"      {n:4} x {reason}")
        print(f"      {JUDGED.label} on the analysis cores' seed: "
              f"{_seed_bounds(analysis, tool)}")


def phase_external(args) -> None:
    results = _results(args)
    us = common.units(results)
    workdir = tempfile.mkdtemp(prefix="costex-ext-")
    t0 = time.time()
    per_tool, versions = {}, {}
    try:
        for tool in args.tools:
            per_tool[tool], versions[tool] = analyze(tool, us, timeout=TOOL_TIMEOUT,
                                                     jobs=args.jobs, workdir=workdir)
    except Exception:
        print(f"  work kept in {workdir}")
        raise
    else:
        shutil.rmtree(workdir, ignore_errors=True)
    records = collect(results, us, per_tool)
    elapsed = time.time() - t0
    out = _write(args, "external.json",
                 {"versions": versions,
                  "options": {t: list(TOOLS[t]["opts"]) for t in args.tools},
                  "elapsed_s": round(elapsed, 1), "results": records})
    print()
    _health(records)
    print(f"\n  {elapsed:.1f}s wall, {args.jobs} jobs -> {out}")


# -- the two rewriters, head to head --


WHO = (common.SEED,) + tuple(m.judge for m in common.METRICS) + ("daisy",)


def _score(rep):
    """The judge's bound for one program; a zero bound counts as none, since
    every ratio downstream divides by it."""
    v = rep.get(JUDGED.name) if rep and rep.get("status") == "ok" else None
    return v or None


def candidates(results: list, seeds: list, rewrites: dict) -> tuple:
    """The distinct programs to score, and (file, who) -> which one."""
    by_file = {r["file"]: r for r in results}
    cands, index = [], {}
    for u in seeds:
        r = by_file[u["file"]]
        progs = {common.SEED: r["expr"]}
        progs.update({m.judge: r.get(m.best_expr) for m in common.METRICS})
        rw = rewrites.get(u["name"], {})
        if rw.get("status") == "ok":
            progs["daisy"] = rw["expr"]
        seen = {}
        for who, expr in progs.items():
            if not expr:
                continue
            if expr not in seen:
                seen[expr] = f"j{len(cands):05d}"
                cands.append(common.unit(seen[expr], u["file"], expr))
            index[(u["file"], who)] = seen[expr]
    return cands, index


def _judged(e: dict, who: str) -> tuple:
    """(score, program, note) for one side; None and a reason if it has no bound."""
    j = e["judge"]
    if who == "costex":
        got = [(v, e.get(m.judge_expr)) for m in common.METRICS
               if (v := _score(j.get(m.judge)))]
        if got:
            return (*min(got), "")
        rep = next((j[m.judge] for m in common.METRICS if j.get(m.judge)), {})
        return None, None, rep.get("status", "no program")
    v = _score(j.get("daisy"))
    if v:
        return v, e.get("daisy_expr"), ""
    note = e["daisy_status"] if e["daisy_status"] != "ok" else \
        (j.get("daisy") or {}).get("status", "no program")
    return None, e.get("daisy_expr"), note


def h2h(out: list) -> list:
    """Per core, FPTaylor's score for the seed and for each rewriter's program.

    costex offers both its optima and its best is taken.  A side with no bound
    loses by default, so a core counts if either side has one.
    """
    rows = []
    for e in out:
        cx, cx_expr, cx_note = _judged(e, "costex")
        dy, dy_expr, dy_note = _judged(e, "daisy")
        if cx is None and dy is None:
            continue
        rows.append({"file": e["file"], "name": e.get("name"), "kind": kind(e["file"]),
                     "seed": _score(e["judge"].get(common.SEED)),
                     "seed_expr": e["seed_expr"],
                     "cx": cx, "cx_expr": cx_expr, "cx_note": cx_note,
                     "dy": dy, "dy_expr": dy_expr, "dy_note": dy_note})
    return rows


def _wins(rows: list) -> tuple:
    cxw = [r for r in rows if r["dy"] is None or (r["cx"] and r["cx"] < r["dy"] * SLACK)]
    dyw = [r for r in rows if r["cx"] is None or (r["dy"] and r["dy"] < r["cx"] * SLACK)]
    return cxw, dyw


def _improves(rows: list, who: str) -> set:
    return {r["file"] for r in rows if r["seed"] and r[who] and r[who] < r["seed"] * SLACK}


def head_to_head(out: list) -> None:
    every = h2h(out)
    rows = [r for r in every if r["kind"] != "analysis"]
    if not rows:
        print("  no core has a scored rewrite")
        return
    cxw, dyw = _wins(rows)
    cx_imp, dy_imp = _improves(rows, "cx"), _improves(rows, "dy")
    both = cx_imp & dy_imp
    print(f"\n  {len(rows)} rewrite cores with a verdict "
          f"({len(out) - len(every)} where neither side produced a bound, "
          f"{sum(1 for r in every if r['kind'] == 'analysis')} optimal, left out)")
    print(f"    costex wins {len(cxw)}, daisy wins {len(dyw)}, "
          f"tie {len(rows) - len(cxw) - len(dyw)}")
    print(f"    by default, the other side having crashed: costex "
          f"{sum(1 for r in cxw if r['dy'] is None)}, daisy "
          f"{sum(1 for r in dyw if r['cx'] is None)}")
    print(f"    improves on the seed: costex {len(cx_imp)}, daisy {len(dy_imp)}; "
          f"both {len(both)}, only daisy {len(dy_imp - both)}, "
          f"only costex {len(cx_imp - both)}")
    wrong = [r["file"] for r in every if r["kind"] == "analysis"
             and (r["file"] in _improves(every, "cx") | _improves(every, "dy"))]
    if wrong:
        print(f"    MISTAGGED: a tool improved {len(wrong)} core(s) tagged analysis: "
              + ", ".join(f[:40] for f in sorted(wrong)[:3]))
    print("    largest costex gains (costex x, daisy x):")
    for r in sorted((r for r in rows if r["seed"] and r["cx"]),
                    key=lambda r: -r["seed"] / r["cx"])[:5]:
        dy = f"{r['seed'] / r['dy']:.4g}x" if r["dy"] else r["dy_note"]
        print(f"      {r['file'][:46]:<46} costex {r['seed'] / r['cx']:.4g}x   daisy {dy}")


def phase_rewrite(args) -> None:
    """Daisy's genetic search against equality saturation, both scored by
    FPTaylor so this compares rewriters and not analyses."""
    results = [r for r in _results(args) if r["status"] == "ok"]
    seeds = [common.unit(f"cx{i:05d}", r["file"], r["expr"])
             for i, r in enumerate(results)]
    workdir = tempfile.mkdtemp(prefix="costex-rw-")
    t0 = time.time()
    try:
        daisy_ver = daisy.version()      # before the export, so a missing tool is quick
        rewrites = daisy.run_rewriter(seeds, seed=REWRITE_SEED,
                                      timeout=TOOL_TIMEOUT, jobs=args.jobs,
                                      workdir=workdir)
        cands, index = candidates(results, seeds, rewrites)
        print("  judging every distinct program with FPTaylor")
        scores, ft_ver = analyze("fptaylor", cands, timeout=TOOL_TIMEOUT,
                                 jobs=args.jobs, workdir=workdir)
    except Exception:
        print(f"  work kept in {workdir}")
        raise
    else:
        shutil.rmtree(workdir, ignore_errors=True)

    out = []
    for u, r in zip(seeds, results):
        rw = rewrites.get(u["name"], {})
        entry = {"file": u["file"], "name": r.get("name"), "seed_expr": r["expr"],
                 **{m.judge_expr: r.get(m.best_expr) for m in common.METRICS},
                 "daisy_expr": rw.get("expr"), "daisy_status": rw.get("status"),
                 "daisy_error": rw.get("error"),
                 "daisy_before": rw.get("daisy_before"),
                 "daisy_after": rw.get("daisy_after"), "judge": {}}
        for who in WHO:
            nm = index.get((u["file"], who))
            if nm:
                entry["judge"][who] = scores.get(nm)
        out.append(entry)
    elapsed = time.time() - t0
    path = _write(args, "rewrite.json",
                  {"daisy_version": daisy_ver, "fptaylor_version": ft_ver,
                   "rewrite_seed": REWRITE_SEED,
                   "daisy_options": list(daisy.REWRITE_OPTS),
                   "elapsed_s": round(elapsed, 1), "results": out})
    st = Counter(e["daisy_status"] for e in out)
    print(f"\n  daisy rewriter over {len(out)} cores: "
          + ", ".join(f"{v} {k}" for k, v in st.most_common()))
    head_to_head(out)
    print(f"  {elapsed:.1f}s wall -> {path}")


# -- the table --


STATUS = {"nobound": "n/b", "timeout": "t/o", "error": "err"}
NONE = "&mdash;"                    # no bound exists
NA = "&middot;"                     # not recorded for this program


def _num(x) -> str:
    if x is None:
        return NONE
    return "0" if x == 0 else f"{x:.3g}"     # costex can report -0.0


def _code(expr: str) -> str:
    if len(expr) > WIDTH:
        expr = expr[:WIDTH - 1] + "…"
    return "`" + expr.replace("|", "\\|") + "`"


def programs(r: dict) -> list:
    """(labels, variant, expression) per distinct program, seed first."""
    order, labels, variant = [], {}, {}
    entries = [(common.SEED, common.SEED, r["expr"])]
    entries += [(m.name, m.variant, r.get(m.best_expr)) for m in common.METRICS]
    for label, v, expr in entries:
        if not expr:
            continue
        if expr not in labels:
            order.append(expr)
            labels[expr], variant[expr] = [], v
        labels[expr].append(label)
    return [(labels[e], variant[e], e) for e in order]


def _costex(r: dict, labels: list, m) -> str:
    """costex bounds only the metric it optimised for."""
    if m.name in labels:
        return _num(r.get(m.best))
    if common.SEED in labels:
        return _num(r.get(m.seed))
    return NA


def _tool(reps: dict, variant: str, m) -> str:
    rep = (reps or {}).get(variant)
    if rep is None:
        return NA
    if rep["status"] != "ok":
        return STATUS.get(rep["status"], rep["status"])
    return _num(rep.get(m.name))


def gain(r: dict) -> float:
    """The best ratio costex claims, for sorting."""
    out = 1.0
    for m in common.METRICS:
        seed, best = r.get(m.seed), r.get(m.best)
        if seed and best and best > 0:
            out = max(out, seed / best)
    return out


def row(r: dict, tools: dict, names: list) -> str:
    progs = programs(r)
    cells = [
        f"**{r.get('name') or r['file']}**",
        # label and expression on one line: a wrapped expression is not a program
        "<br>".join(f"{', '.join(labels)}: {_code(expr)}"
                    for labels, _, expr in progs),
    ]
    for m in common.METRICS:
        cells.append("<br>".join(_costex(r, labels, m) for labels, _, _ in progs))
        for t in names:
            cells.append("<br>".join(_tool((tools or {}).get(t), v, m)
                                     for _, v, _ in progs))
    return "| " + " | ".join(cells) + " |"


def markdown(rows: list, res: dict, ext: dict, sort: str) -> str:
    by_file = {r["file"]: r["tools"] for r in ext["results"]}
    names = sorted({t for r in ext["results"] for t in r["tools"]})
    rows = sorted(rows, key=(lambda r: -gain(r)) if sort == "gain"
                  else (lambda r: r["file"]))
    kinds = Counter(kind(r["file"]) for r in rows)

    out = ["# " + " vs ".join(["costex"] + names), "",
           f"- {len(rows)} cores, costex at {res.get('iters')} iterations",
           f"- {kinds['rewrite']} rewrite cores, {kinds['analysis']} analysis cores "
           f"(:cx-kind)"]
    out += [f"- {t} {ext.get('versions', {}).get(t, '?')}, "
            f"`{' '.join(ext.get('options', {}).get(t, []))}`" for t in names]
    if names:
        out.append(f"- external data for "
                   f"{sum(1 for r in rows if r['file'] in by_file)} of them")
    out += [f"- sorted by {'costex claimed gain' if sort == 'gain' else 'file name'}",
            "",
            "| Core | Program | "
            + " | ".join(f"{m.label} {t}" for m in common.METRICS
                         for t in ["costex"] + names) + " |",
            "|---|---|" + "---:|" * (len(common.METRICS) * (len(names) + 1))]
    out += [row(r, by_file.get(r["file"]), names) for r in rows]
    return "\n".join(out) + "\n"


def _gain(seed: float, got: float) -> str:
    r = seed / got
    return NONE if SLACK < r < 1 / SLACK else f"{r:.3g}x"


def _edge(r: dict) -> float:
    """How far costex's rewrite beats Daisy's; no bound loses hard."""
    if r["cx"] is None:
        return -math.inf
    if r["dy"] is None:
        return math.inf
    return r["dy"] / r["cx"]


def h2h_markdown(rw: dict) -> str:
    """The two rewriters side by side, scored by the same neutral analyser."""
    every = h2h(rw["results"])
    rows = [r for r in every if r["kind"] != "analysis"]
    cxw, dyw = _wins(rows)
    st = Counter(e["daisy_status"] for e in rw["results"])
    same = sum(1 for e in rw["results"] if e.get("daisy_expr") == e["seed_expr"])

    out = ["# costex's rewrite vs Daisy's", "",
           f"- {len(rows)} of {len(rw['results'])} cores get a verdict; the "
           f"{sum(1 for r in every if r['kind'] == 'analysis')} tagged optimal are left "
           f"out, as are {len(rw['results']) - len(every)} where neither side produced a "
           "program the judge could bound",
           f"- judged by fptaylor {rw.get('fptaylor_version')}, on {JUDGED.label}: "
           "the same "
           "analyser over the same box, so this compares rewriters and not analyses",
           f"- daisy {rw.get('daisy_version')}, seed {rw.get('rewrite_seed')}, "
           f"`{' '.join(rw.get('daisy_options', []))}`",
           "- daisy: " + ", ".join(f"{v} {k}" for k, v in st.most_common())
           + f", and returned the seed unchanged on {same}",
           f"- **costex wins {len(cxw)}, daisy wins {len(dyw)}, "
           f"tie {len(rows) - len(cxw) - len(dyw)}** -- a side that crashed or could "
           "not be bounded loses, which is "
           f"{sum(1 for r in cxw if r['dy'] is None)} of costex's wins and "
           f"{sum(1 for r in dyw if r['cx'] is None)} of Daisy's",
           f"- improves on the seed: costex {len(_improves(rows, 'cx'))}, "
           f"daisy {len(_improves(rows, 'dy'))}",
           "- sorted by how far costex's rewrite beats Daisy's, so Daisy's wins are last",
           "",
           f"| Core | Program | {JUDGED.label} | vs seed |",
           "|---|---|---:|---:|"]
    for r in sorted(rows, key=lambda r: -_edge(r)):
        progs = [(common.SEED, r["seed_expr"], r["seed"], ""),
                 ("costex", r["cx_expr"], r["cx"], r["cx_note"]),
                 ("daisy", r["dy_expr"], r["dy"], r["dy_note"])]
        out.append("| " + " | ".join([
            f"**{r['name'] or r['file']}**",
            "<br>".join(f"{who}: {_code(e) if e else NONE}" for who, e, _, _ in progs),
            "<br>".join(note or _num(v) for _, _, v, note in progs),
            "<br>".join(NONE if who == common.SEED or v is None or not r["seed"]
                        else _gain(r["seed"], v) for who, _, v, _ in progs),
        ]) + " |")
    return "\n".join(out) + "\n"


def phase_report(args) -> None:
    res = _read(args, "results.json")
    keep = set(corpus(args))
    rows = [r for r in res["results"] if r["file"] in keep and r["status"] == "ok"]
    ext = _read(args, "external.json", required=False) or {"results": []}
    os.makedirs(args.results_dir, exist_ok=True)
    wrote = [("report.md", markdown(rows, res, ext, args.sort))]
    rw = _read(args, "rewrite.json", required=False)
    if rw:
        wrote.append(("rewrites.md", h2h_markdown(rw)))
    for name, text in wrote:
        with open(_path(args, name), "w") as f:
            f.write(text)
        print(f"  {text.count(chr(10))} lines -> {os.path.relpath(_path(args, name))}")


# -- driving --


PHASES = {"costex": phase_costex, "external": phase_external,
          "rewrite": phase_rewrite, "report": phase_report}


def preflight(args, phases: list) -> None:
    """Check what the phases need before any of them does work."""
    missing = []
    if "costex" in phases and not (shutil.which(egg.EGGLOG) or os.path.exists(egg.EGGLOG)):
        missing.append(f"no egglog at {egg.EGGLOG}; set EGGLOG")
    if {"external", "rewrite"} & set(phases):
        if not os.path.exists(os.path.join(common.FPBENCH, "fpbench.rkt")):
            missing.append(f"no fpbench.rkt under {common.FPBENCH}; set FPBENCH")
        need = set(args.tools) if "external" in phases else set()
        if "rewrite" in phases:
            need |= {"daisy", "fptaylor"}     # Daisy rewrites, FPTaylor judges
        for tool in sorted(need):
            try:
                TOOLS[tool]["version"]()
            except RuntimeError as e:
                missing.append(str(e))
    if missing:
        sys.exit("\n".join(missing) + "\n(--probe reports the whole toolchain)")


def probe(args) -> int:
    print(f"EGGLOG    {egg.EGGLOG}")
    print(f"  {'found  ' if os.path.exists(egg.EGGLOG) else 'MISSING'} egglog")
    path = os.path.join(common.FPBENCH, "fpbench.rkt")
    print(f"FPBENCH   {common.FPBENCH}")
    print(f"  {'found  ' if os.path.exists(path) else 'MISSING'} fpbench.rkt")
    for tool in args.tools:
        print(f"\n{tool}")
        try:
            print(f"  version   {TOOLS[tool]['version']()}")
            print(f"  options   {' '.join(TOOLS[tool]['opts'])}")
        except RuntimeError as e:
            print(f"  UNAVAILABLE: {e}")
    print(f"\ncorpus    {len(corpus(args))} cores in {os.path.relpath(common.CORES)}")
    print(f"results   {os.path.relpath(args.results_dir)}")
    print(f"cache     {os.path.relpath(common.CACHE)}")
    return 0


def _list(value: str, known, what: str, ap) -> list:
    out = [v.strip() for v in value.split(",") if v.strip()]
    unknown = [v for v in out if v not in known]
    if unknown:
        ap.error(f"unknown {what}: {', '.join(unknown)}; have {', '.join(known)}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="bench", description=__doc__.splitlines()[0])
    ap.add_argument("--phases", default=",".join(PHASES),
                    help="comma separated, run in order (default %(default)s)")
    ap.add_argument("--tools", default=",".join(TOOLS),
                    help="comma separated (default %(default)s)")
    ap.add_argument("--probe", action="store_true", help="check the toolchain and exit")
    ap.add_argument("--summarize", action="store_true",
                    help="re-print the summaries, running nothing")
    ap.add_argument("--limit", type=int, help="only the first N cores")
    ap.add_argument("--only", metavar="SUBSTR",
                    help="only cores whose filename contains this")
    ap.add_argument("--kind", choices=KINDS, help="only cores tagged this way")
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--results-dir", default=common.RESULTS)

    ap.add_argument("--iters", type=int, default=egg.DEFAULT_ITERS,
                    help="costex's analysis/rewrite passes (default %(default)s)")
    ap.add_argument("--max-steps", type=int, default=extract.DEFAULT_MAX_STEPS,
                    help="costex's extraction step cap (default %(default)s)")
    ap.add_argument("--sort", choices=("gain", "name"), default="gain",
                    help="the tables' row order (default %(default)s)")

    args = ap.parse_args(argv)
    args.tools = _list(args.tools, tuple(TOOLS), "tool(s)", ap)
    phases = _list(args.phases, PHASES, "phase(s)", ap)

    if args.probe:
        return probe(args)
    if args.summarize:
        summarize(_results(args))
        ext = _read(args, "external.json", required=False)
        if ext:
            print()
            _health(ext["results"])
        return 0
    preflight(args, phases)
    for name, run_phase in PHASES.items():
        if name in phases:
            print(f"\n== {name} ==")
            run_phase(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
