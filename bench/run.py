"""The whole benchmark in one command.

    uv run python bench/run.py

    bounds.md    costex, FPTaylor, Daisy and Gappa bounding every core's seed
    rewrites.md  costex's rewrites against Daisy's and Herbie's, by measured
                 error

The JSON beside them is what each step handed the next.
"""

from __future__ import annotations

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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from tools import REWRITERS, TOOLS, analyze, common, rewrite, sample  # noqa: E402

from costex import analysis as A                               # noqa: E402
from costex import egg, extract                                # noqa: E402
from costex.fpcore import parse_expr, parse_fpcore, parse_sexps, to_sexp  # noqa: E402

SCORE = "ulps"                    # worst measured error
MEAN = "mean_ulps"                # mean over the uniform points alone
FIELDED = common.BY_NAME["rel"]   # which costex program competes
HEADROOM = 4.0                    # ulps the seed must lose before a core counts
HEADROOM_STEPS = (2.0, 4.0, 8.0, 64.0)
ITERS = egg.DEFAULT_ITERS
MAX_STEPS = 1_000_000        # kalman-filter-per-p needs ~770k to reach its root
EGGLOG_TIMEOUT = 60.0
EXTRACT_TIMEOUT = 120.0      # a step cap alone does not bound extraction
TOOL_TIMEOUT = 300.0
REWRITE_SEED = 1490               # every rewriter's, so a run is repeatable
JOBS = os.cpu_count()
WIDTH = 70


def kind(file: str) -> str:
    return str(common.core(file).props.get(":cx-kind", "rewrite"))


def corpus() -> list:
    return sorted(f for f in os.listdir(common.CORES) if f.endswith(".fpcore"))


def _write(name: str, payload: dict) -> str:
    os.makedirs(common.RESULTS, exist_ok=True)
    path = os.path.join(common.RESULTS, name)
    with open(path, "w") as f:
        json.dump(payload, f, indent=1)
    return os.path.relpath(path)


def _f(x):
    x = float(x)
    return None if math.isinf(x) else x


# -- costex --


def run_one(path: str) -> dict:
    out = {"file": os.path.basename(path)}
    t0 = time.time()
    try:
        core = parse_fpcore(open(path).read())
        A.set_target(53 if core.precision == "binary64" else 24)
        out.update(name=core.name, vars=len(core.args),
                   box_source=str(core.props.get(":cx-box", "pre")),
                   source=str(core.props.get(":cx-source", "")),
                   expr=to_sexp(core.body), precision=core.precision)
        g = egg.build(core.body, core.box, iters=ITERS, timeout=EGGLOG_TIMEOUT)
        t1 = time.time()
        front = extract.extract(g, max_steps=MAX_STEPS, time_limit=EXTRACT_TIMEOUT)
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


def step_costex() -> list:
    files = [os.path.join(common.CORES, f) for f in corpus()]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=JOBS) as pool:
        results = []
        for i, r in enumerate(pool.map(run_one, files), 1):
            results.append(r)
            if i % 25 == 0:
                print(f"  {i}/{len(files)}", flush=True)
    elapsed = time.time() - t0
    out = _write("results.json", {"iters": ITERS, "elapsed_s": round(elapsed, 1),
                                  "results": results})
    st = Counter(r["status"] for r in results)
    print(f"  {', '.join(f'{v} {k}' for k, v in st.most_common())}"
          f"   {elapsed:.1f}s -> {out}")
    return results


# -- the external analysers --


def step_external(results: list) -> dict:
    """Seeds only: the bounds report compares nothing else."""
    us = common.seed_units(results)
    workdir = tempfile.mkdtemp(prefix="costex-ext-")
    t0 = time.time()
    per_tool, versions = {}, {}
    try:
        for tool in TOOLS:
            per_tool[tool], versions[tool] = analyze(tool, us, timeout=TOOL_TIMEOUT,
                                                     jobs=JOBS, workdir=workdir)
    except Exception:
        print(f"  work kept in {workdir}")
        raise
    else:
        shutil.rmtree(workdir, ignore_errors=True)
    records = [{"file": u["file"],
                "tools": {t: per_tool[t][u["name"]] for t in TOOLS}}
               for u in us]
    elapsed = time.time() - t0
    payload = {"versions": versions,
               "options": {t: list(TOOLS[t]["opts"]) for t in TOOLS},
               "elapsed_s": round(elapsed, 1), "results": records}
    print(f"  {elapsed:.1f}s -> {_write('external.json', payload)}")
    return payload


def sample_core(group: tuple) -> dict:
    file, box, precision, seed, progs = group
    bodies = {name: parse_expr(parse_sexps(expr)[0]) for name, expr in progs.items()}
    return sample.measure_group(bodies, file, box, precision,
                                parse_expr(parse_sexps(seed)[0]))


def sample_reports(us: list) -> dict:
    """Every program of a core is measured together; see sample.measure_group."""
    groups = {}
    for u in us:
        g = groups.setdefault(u["file"],
                              (u["file"], u["box"], u["precision"], u["seed"], {}))
        g[4][u["name"]] = u["expr"]
    t0 = time.time()
    out = {}
    with ProcessPoolExecutor(max_workers=JOBS) as pool:
        for reports in pool.map(sample_core, list(groups.values())):
            out.update(reports)
    searched = sum(r.get("searched", 0) for r in out.values() if r.get("status") == "ok")
    print(f"  sampled: {len(us)} programs over {len(groups)} cores, "
          f"{sample.SAMPLES} uniform points each plus {searched} found by "
          f"search, {time.time() - t0:.1f}s")
    return out


# -- rewriting --


def _val(rep, key: str):
    if not rep or rep.get("status") != "ok":
        return None
    return rep.get(key)


def candidates(results: list, rewrites: dict) -> tuple:
    """The distinct programs to measure, and (file, who) -> which one."""
    cands, index = [], {}
    for i, r in enumerate(results):
        progs = {"seed": r["expr"], "costex": r.get(FIELDED.best_expr)}
        for tool, reports in rewrites.items():
            rep = reports.get(f"cx{i:05d}", {})
            progs[tool] = rep["expr"] if rep.get("status") == "ok" else None
        seen = {}
        for who, expr in progs.items():
            if not expr:
                continue
            if expr not in seen:
                seen[expr] = f"j{len(cands):05d}"
                cands.append(common.unit(seen[expr], r["file"], expr, seed=r["expr"]))
            index[(r["file"], who)] = seen[expr]
    return cands, index


def _programs(r: dict, rewrites: dict, name: str) -> dict:
    """who -> what it returned for this core, costex included so the report
    reads every rewriter the same way."""
    expr = r.get(FIELDED.best_expr)
    out = {"costex": {"status": "ok" if expr else "noprogram", "expr": expr}}
    for tool, reports in rewrites.items():
        rep = reports.get(name, {})
        out[tool] = {"status": rep.get("status", "nooutput"),
                     "expr": rep.get("expr"), "error": rep.get("error")}
    return out


def step_rewrite(results: list) -> dict:
    results = [r for r in results if r["status"] == "ok"]
    seeds = common.seed_units(results)
    workdir = tempfile.mkdtemp(prefix="costex-rw-")
    t0 = time.time()
    try:
        rewrites, versions = {}, {}
        for tool in REWRITERS:
            rewrites[tool], versions[tool] = rewrite(
                tool, seeds, seed=REWRITE_SEED, timeout=TOOL_TIMEOUT, jobs=JOBS,
                workdir=workdir)
        cands, index = candidates(results, rewrites)
        scores = sample_reports(cands)
    except Exception:
        print(f"  work kept in {workdir}")
        raise
    else:
        shutil.rmtree(workdir, ignore_errors=True)

    out = []
    for u, r in zip(seeds, results):
        progs = _programs(r, rewrites, u["name"])
        out.append({"file": r["file"], "name": r.get("name"),
                    "seed_expr": r["expr"], "rewrites": progs,
                    "measured": {who: scores.get(index[(r["file"], who)])
                                 for who in ("seed", *progs)
                                 if (r["file"], who) in index}})
    elapsed = time.time() - t0
    payload = {"rewriters": {t: {"version": versions[t],
                                 "options": list(REWRITERS[t]["opts"]),
                                 "note": REWRITERS[t].get("note", "")}
                             for t in REWRITERS},
               "rewrite_seed": REWRITE_SEED,
               "sampling": {"version": sample.VERSION, "points": sample.SAMPLES,
                            "seed": sample.SEED,
                            "distribution": sample.DISTRIBUTION,
                            "search_seeds": sample.SEARCH_SEEDS,
                            "search_levels": sample.SEARCH_LEVELS,
                            "search_evals": sample.SEARCH_EVALS},
               "elapsed_s": round(elapsed, 1), "results": out}
    print(f"  {elapsed:.1f}s -> {_write('rewrite.json', payload)}")
    return payload


# -- shared formatting --


STATUS = {"nobound": "n/b", "timeout": "t/o", "error": "err"}
NONE = "&mdash;"


def _num(x) -> str:
    if x is None:
        return NONE
    return "0" if x == 0 else f"{x:.3g}"


def _code(expr: str) -> str:
    if len(expr) > WIDTH:
        expr = expr[:WIDTH - 1] + "…"
    return "`" + expr.replace("|", "\\|") + "`"


def _geomean(xs: list) -> float:
    return math.exp(sum(map(math.log, xs)) / len(xs))


def _pct(xs: list, q: float) -> float:
    return xs[int(q * (len(xs) - 1))]


def _spread(xs: list) -> str:
    if not xs:
        return "no ratio"
    return (f"geomean {_geomean(xs):.3g}x, median {xs[len(xs) // 2]:.3g}x, "
            f"p10 {_pct(xs, 0.1):.3g}x, p90 {_pct(xs, 0.9):.3g}x")


def _row(*cells) -> str:
    return "| " + " | ".join(map(str, cells)) + " |"


# -- bounds.md --


def _rows(res: dict, ext: dict) -> list:
    tools = {r["file"]: r["tools"] for r in ext["results"]}
    return [dict(r, tools=tools[r["file"]]) for r in res["results"]
            if r["file"] in tools]


def seed_bound(r: dict, who: str, m):
    """Every table reads bounds here, so none can disagree."""
    if who == "costex":
        return r.get(m.seed)
    rep = r["tools"].get(who)
    return rep.get(m.name) if rep and rep["status"] == "ok" else None


def tightness(rows: list, tool: str, m) -> tuple:
    n, ratios = Counter(), []
    for r in rows:
        ours, theirs = seed_bound(r, "costex", m), seed_bound(r, tool, m)
        if ours is None and theirs is None:
            n["neither"] += 1
        elif theirs is None:
            n["only ours"] += 1
        elif ours is None:
            n["only theirs"] += 1
        else:
            n["both"] += 1
            n["tighter" if ours < theirs else "looser" if theirs < ours else "tie"] += 1
            if ours > 0 and theirs > 0:
                ratios.append(theirs / ours)
    return n, sorted(ratios)


def _why_not(rows: list, who: str) -> str:
    if who == "costex":
        return NONE
    why = Counter()
    for r in rows:
        rep = r["tools"].get(who)
        if rep and rep["status"] != "ok":
            why[rep.get("error", "")[:52]] += 1
    return "; ".join(f"{v}x {k}" for k, v in why.most_common(3)) or NONE


def coverage_rows(rows: list, tools: list) -> list:
    out = ["", "## Coverage", "",
           "| Analyser | seeds |"
           + "".join(f" bounded {m.label} |" for m in common.METRICS)
           + " bounded neither | why not |",
           "|---|--:|" + "--:|" * (len(common.METRICS) + 1) + "---|"]
    for who in ["costex"] + tools:
        got = [[seed_bound(r, who, m) for m in common.METRICS] for r in rows]
        out.append(_row(
            who, len(rows),
            *(sum(1 for g in got if g[i] is not None)
              for i in range(len(common.METRICS))),
            sum(1 for g in got if not any(v is not None for v in g)),
            _why_not(rows, who)))
    return out


def _bound(rep, m) -> str:
    if rep is None:
        return NONE
    if rep["status"] != "ok":
        return STATUS.get(rep["status"], rep["status"])
    return _num(rep.get(m.name))


def _looseness(r: dict, tools: list) -> float:
    """How many times looser our bound is than the tightest tool's."""
    out = 0.0
    for m in common.METRICS:
        ours = seed_bound(r, "costex", m)
        theirs = [v for t in tools if (v := seed_bound(r, t, m))]
        if ours and theirs:
            out = max(out, ours / min(theirs))
    return out


def bounds_row(r: dict, tools: list) -> str:
    cells = [f"**{r.get('name') or r['file']}**", _code(r["expr"])]
    for m in common.METRICS:
        cells.append(_num(r.get(m.seed)))
        cells += [_bound(r["tools"].get(t), m) for t in tools]
    return _row(*cells)


def bounds_markdown(res: dict, ext: dict) -> str:
    rows = _rows(res, ext)
    tools = sorted({t for r in rows for t in r["tools"]})
    out = ["# Bounds: " + " vs ".join(["costex"] + tools), ""]
    for t in tools:
        opts = " ".join(ext.get("options", {}).get(t, []))
        out.append(f"- {t} {ext.get('versions', {}).get(t, '?')}"
                   + (f", `{opts}`" if opts else ", its defaults"))

    out += ["", "## Summary", "",
            "Every analyser bounds the same program, the seed.  "
            "Above 1x, our bound is tighter.", "",
            "| Metric | vs | both bounded | we are tighter | looser | tie "
            "| only we bound it | only they do | their bound / ours |",
            "|---|---|--:|--:|--:|--:|--:|--:|---|"]
    for m in common.METRICS:
        for t in tools:
            n, ratios = tightness(rows, t, m)
            out.append(_row(m.label, t, n["both"], n["tighter"], n["looser"],
                            n["tie"], n["only ours"], n["only theirs"],
                            _spread(ratios)))

    out += coverage_rows(rows, tools)
    out += ["", "## Every core", "",
            "- sorted by how far our bound trails the tightest tool, worst first",
            "",
            "| Core | Seed | "
            + " | ".join(f"{m.label} {t}" for m in common.METRICS
                         for t in ["costex"] + tools) + " |",
            "|---|---|" + "---:|" * (len(common.METRICS) * (len(tools) + 1))]
    out += [bounds_row(r, tools)
            for r in sorted(rows, key=lambda r: -_looseness(r, tools))]
    out += ["",
            f"{NONE} bounded the other metric but not this one, almost always a "
            "range containing zero.  `n/b` bounded nothing; `t/o` timed out; "
            "`err` or a bare status, it failed."]
    return "\n".join(out) + "\n"


# -- rewrites.md --


def _note(rep) -> str:
    return rep["status"] if rep else "no program"


def who_list(rw: dict) -> list:
    """The rewriters the JSON holds, costex first: the report follows what was
    recorded, not what is installed today."""
    return ["costex"] + list(rw.get("rewriters", {}))


def h2h(out: list, whos: list) -> list:
    rows = []
    for e in out:
        m, rw = e["measured"], e["rewrites"]
        who = {}
        for w in whos:
            rep, prog = m.get(w), rw.get(w, {})
            got = _val(rep, SCORE)
            note = "" if got else (prog.get("status") if prog.get("status") != "ok"
                                   else _note(rep))
            who[w] = {"expr": prog.get("expr"), "ulps": got,
                      "mean": _val(rep, MEAN), "note": note}
        if not any(v["ulps"] for v in who.values()):
            continue
        rows.append({"file": e["file"], "name": e.get("name"), "kind": kind(e["file"]),
                     "zeros": (m.get("seed") or {}).get("ref_zeros", 0),
                     "seed": _val(m.get("seed"), SCORE), "seed_expr": e["seed_expr"],
                     "seed_mean": _val(m.get("seed"), MEAN), "who": who})
    return rows


def _headroom(rows: list, floor: float = HEADROOM) -> list:
    """Cores where the seed loses more than floor ulps, so a rewriter has
    something to win."""
    return [r for r in rows if r["seed"] and r["seed"] > floor]


def _bits(v) -> str:
    return NONE if v is None else f"{math.log2(v):.1f}"


def _edge(r: dict, whos: list) -> float:
    """The best rival's ulps over ours, so the table leads with the cores we
    win by the most."""
    ours = r["who"]["costex"]["ulps"]
    theirs = [r["who"][w]["ulps"] for w in whos
              if w != "costex" and r["who"][w]["ulps"]]
    if ours is None:
        return -math.inf
    if not theirs:
        return math.inf
    return min(theirs) / ours


def _not_equivalent(rw: dict, who: str) -> list:
    out = []
    for e in rw["results"]:
        rep = (e["measured"] or {}).get(who)
        if rep and rep.get("status") == "ok" and rep.get("equivalent") is False:
            out.append(e["file"])
    return sorted(out)


def _tool_lines(rw: dict) -> list:
    out = []
    for tool, info in rw.get("rewriters", {}).items():
        st = Counter(e["rewrites"][tool]["status"] for e in rw["results"])
        same = sum(1 for e in rw["results"]
                   if e["rewrites"][tool].get("expr") == e["seed_expr"])
        out.append(f"- {tool} {info.get('version')}, seed {rw.get('rewrite_seed')}, "
                   f"`{' '.join(info.get('options', []))}`")
        if info.get("note"):
            out.append(f"  - {info['note']}")
        out.append("  - " + ", ".join(f"{v} {k}" for k, v in st.most_common())
                   + f", and returned the seed unchanged on {same}")
    return out


def _h2h_preamble(rw: dict, every: list, rows: list, head: list) -> list:
    sp = rw.get("sampling", {})
    optimal = sum(1 for r in every if r["kind"] == "analysis")
    return [
        "# Rewriting: " + " vs ".join(who_list(rw)), "",
        "Every rewriter gets the same seed and is scored by measured error, "
        f"not bounded: {sp.get('points')} points per core plus everything a "
        "hill climb reaches, pooled so every program is scored at its rivals' "
        "worst points too.  For sound bounds see `bounds.md`.",
        "",
        "Error is in **ulps**; 1 ulp is correctly rounded, and the per-core "
        "table gives log2 of it.",
        "",
        f"- {len(rows)} of {len(rw['results'])} cores measured; "
        f"{optimal} tagged optimal and "
        f"{len(rw['results']) - len(every)} unmeasurable are left out",
        f"- **{len(head)} have headroom** (seed above {HEADROOM:.0f} ulps); "
        "only these are summarised, since elsewhere every rewriter ties by "
        "construction.",
        f"- sampling {sp.get('version')}, seed {sp.get('seed')}",
    ] + _tool_lines(rw)


def _rstats(xs: list) -> list:
    if not xs:
        return [NONE] * 4
    xs = sorted(xs)
    return [f"{_geomean(xs):.3g}x", f"{xs[len(xs) // 2]:.3g}x",
            f"{_pct(xs, 0.1):.3g}x", f"{_pct(xs, 0.9):.3g}x"]


def _vs_seed(rows: list, who: str, key: str, seed_key: str) -> list:
    return [r["who"][who][key] / r[seed_key] for r in rows
            if r["who"][who][key] and r[seed_key]]


def _h2h_summary(head: list, whos: list) -> list:
    """Every rewriter over the same cores: the ones with headroom where all of
    them returned something measurable."""
    both = [r for r in head if all(r["who"][w]["ulps"] for w in whos)]
    out = ["", "## Accuracy", "",
           f"Each rewriter against its own seed, over the same {len(both)} "
           "cores with headroom where all of them produced a measurable "
           "program.  **Below 1x is an improvement.**  *Worst* is the max over "
           "the whole pool; *average* is the mean over the uniform points "
           "alone, since the climbed ones are chosen to be bad.", "",
           "| Ratio to the seed | worst, geomean | worst, median "
           "| average, geomean | average, median |",
           "|---|--:|--:|--:|--:|"]
    for who in whos:
        worst = _rstats(_vs_seed(both, who, "ulps", "seed"))[:2]
        avg = _rstats(_vs_seed(both, who, "mean", "seed_mean"))[:2]
        out.append(_row(who, *worst, *avg))

    out += ["", "### Head to head", "",
            f"costex against each rival over those same {len(both)} cores, by "
            "worst measured error.", "",
            "| vs | costex wins | ties | loses | their ulps / ours |",
            "|---|--:|--:|--:|---|"]
    for who in whos:
        if who == "costex":
            continue
        wins = ties = losses = 0
        ratios = []
        for r in both:
            ours, theirs = r["who"]["costex"]["ulps"], r["who"][who]["ulps"]
            wins += theirs > ours
            ties += theirs == ours
            losses += theirs < ours
            ratios.append(theirs / ours)
        out.append(_row(who, wins, ties, losses, _spread(sorted(ratios))))
    same = [(w, sum(1 for r in both
                    if r["who"][w]["expr"] == r["who"]["costex"]["expr"]))
            for w in whos if w != "costex"]
    out.append("")
    out += [f"- {n} of the {len(both)} are cores where costex and {w} returned "
            "the same program" for w, n in same]
    return out


def _h2h_equivalence(rw: dict, rows: list, whos: list) -> list:
    out = ["", "## Equivalence", "",
           f"All {len(rows)} measured cores.  Exact values compared at up to "
           f"{sample.EQUIV_POINTS} points, to within {sample.EQUIV_TOL:g} of "
           "the input scale:", "",
           "| Rewriter | rewrote | not equivalent to the seed |",
           "|---|--:|---|"]
    for who in whos:
        n = sum(1 for r in rows if r["who"][who]["expr"]
                and r["who"][who]["expr"] != r["seed_expr"])
        bad = _not_equivalent(rw, who)
        out.append(_row(who, n,
                        f"{len(bad)}"
                        + (": " + ", ".join(f"`{f[:44]}`" for f in bad[:3])
                           if bad else "")))
    return out


def _h2h_table(rows: list, whos: list) -> list:
    out = ["", "## Every core", "",
           "- sorted by the best rival's ulps / costex ulps; * marks a core "
           "with headroom", "",
           "| Core | Program | worst bits | mean bits |",
           "|---|---|---:|---:|"]
    for r in sorted(rows, key=lambda r: -_edge(r, whos)):
        progs = [("seed", r["seed_expr"], r["seed"], r["seed_mean"], "")]
        progs += [(w, r["who"][w]["expr"], r["who"][w]["ulps"],
                   r["who"][w]["mean"], r["who"][w]["note"]) for w in whos]
        head = r["seed"] and r["seed"] > HEADROOM
        out.append(_row(
            f"**{r['name'] or r['file']}**" + ("&nbsp;\\*" if head else ""),
            "<br>".join(f"{who}: {_code(e) if e else NONE}"
                        for who, e, _, _, _ in progs),
            "<br>".join(note or _bits(v) for _, _, v, _, note in progs),
            "<br>".join(note or _bits(mu) for _, _, _, mu, note in progs)))
    return out


def h2h_markdown(rw: dict) -> str:
    whos = who_list(rw)
    every = h2h(rw["results"], whos)
    rows = [r for r in every if r["kind"] != "analysis"]
    head = _headroom(rows)
    out = (_h2h_preamble(rw, every, rows, head)
           + _h2h_summary(head, whos)
           + _h2h_equivalence(rw, rows, whos)
           + _h2h_table(rows, whos))
    return "\n".join(out) + "\n"


# -- driving --


def unavailable() -> list:
    out = []
    if not (shutil.which(egg.EGGLOG) or os.path.exists(egg.EGGLOG)):
        out.append(f"no egglog at {egg.EGGLOG}; set EGGLOG")
    if not os.path.exists(os.path.join(common.FPBENCH, "fpbench.rkt")):
        out.append(f"no fpbench.rkt under {common.FPBENCH}; set FPBENCH")
    # daisy analyses and rewrites, and one missing checkout is one complaint
    for check in dict.fromkeys(spec["version"] for spec
                               in (*TOOLS.values(), *REWRITERS.values())):
        try:
            check()
        except RuntimeError as e:
            out.append(str(e))
    return out


def _read(name: str):
    path = os.path.join(common.RESULTS, name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def _reuse(missing: list):
    """Stale either way, so reuse all of the JSON rather than mix old with new."""
    res, ext, rw = _read("results.json"), _read("external.json"), _read("rewrite.json")
    if not (res and ext and rw):
        return None
    print("\n".join(f"  {m}" for m in missing))
    print(f"\n  reusing the JSON in {os.path.relpath(common.RESULTS)}, "
          "rewriting only the markdown")
    return res, ext, rw


def _fresh():
    print(f"\n== costex ==  {len(corpus())} cores")
    results = step_costex()
    print("\n== external ==")
    ext = step_external(results)
    print("\n== rewrite ==")
    rw = step_rewrite(results)
    return {"results": results}, ext, rw


def main() -> int:
    missing = unavailable()
    if missing:
        got = _reuse(missing)
        if got is None:
            return _die(missing)
        res, ext, rw = got
    else:
        res, ext, rw = _fresh()

    print("\n== report ==")
    for name, text in (("bounds.md", bounds_markdown(res, ext)),
                       ("rewrites.md", h2h_markdown(rw))):
        path = os.path.join(common.RESULTS, name)
        with open(path, "w") as f:
            f.write(text)
        print(f"  {text.count(chr(10))} lines -> {os.path.relpath(path)}")
    return 0


def _die(missing: list) -> int:
    print("\n".join(missing), file=sys.stderr)
    print(f"\nand no JSON in {os.path.relpath(common.RESULTS)} to fall back on, so "
          "there is nothing to report.\nInstall the tools above, or restore the "
          "JSON, and run again.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
