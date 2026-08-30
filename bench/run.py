"""The whole benchmark in one command.

    uv run python bench/run.py

    bounds.md    costex, FPTaylor and Daisy bounding every core's seed
    rewrites.md  costex's rewrites against Daisy's, by measured error

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

from tools import TOOLS, analyze, common, daisy, rewrite, sample  # noqa: E402

from costex import analysis as A                               # noqa: E402
from costex import egg, extract                                # noqa: E402
from costex.fpcore import parse_expr, parse_fpcore, parse_sexps, to_sexp  # noqa: E402

SCORE = "ulps"                    # reported as bits, its log2
FIELDED = common.BY_NAME["rel"]   # which costex program competes
NOISE_P50, NOISE_P90 = 1.0, 1.75  # measured, by resampling
MARGIN = 2.0                      # a win needs one bit, above the noise
SLACK = 1 / MARGIN
HEADROOM = 4.0                    # ulps the seed must lose before a core counts
HEADROOM_STEPS = (2.0, 4.0, 8.0, 64.0)
ITERS = egg.DEFAULT_ITERS
MAX_STEPS = extract.DEFAULT_MAX_STEPS
EGGLOG_TIMEOUT = 60.0
EXTRACT_TIMEOUT = 30.0       # a step cap alone does not bound extraction
TOOL_TIMEOUT = 300.0
REWRITE_SEED = 1490          # Daisy's genetic seed, so a run is repeatable
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


# -- costex --


def _f(x):
    x = float(x)
    return None if math.isinf(x) else x


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


# -- fptaylor and daisy --


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
    """Every program of one core at once, so each is scored at the others'
    worst points too, and against its seed, so a rewrite that changed the
    function scores as wrong rather than as accurate."""
    file, box, precision, seed, progs = group
    bodies = {name: parse_expr(parse_sexps(expr)[0]) for name, expr in progs.items()}
    return sample.measure_group(bodies, file, box, precision,
                                parse_expr(parse_sexps(seed)[0]))


def sample_reports(us: list) -> dict:
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


def _score(rep):
    """Never zero, so ratios are safe."""
    if not rep or rep.get("status") != "ok":
        return None
    return rep.get(SCORE)


def candidates(results: list, rewrites: dict) -> tuple:
    """The distinct programs to measure, and (file, who) -> which one."""
    cands, index = [], {}
    for i, r in enumerate(results):
        progs = {"seed": r["expr"], "costex": r.get(FIELDED.best_expr)}
        rw = rewrites.get(f"cx{i:05d}", {})
        if rw.get("status") == "ok":
            progs["daisy"] = rw["expr"]
        seen = {}
        for who, expr in progs.items():
            if not expr:
                continue
            if expr not in seen:
                seen[expr] = f"j{len(cands):05d}"
                cands.append(common.unit(seen[expr], r["file"], expr,
                                         seed=r["expr"]))
            index[(r["file"], who)] = seen[expr]
    return cands, index


def h2h(out: list) -> list:
    """A side with no measurement loses, so a core counts if either has one."""
    rows = []
    for e in out:
        m = e["measured"]
        cx, dy = _score(m.get("costex")), _score(m.get("daisy"))
        if cx is None and dy is None:
            continue
        rows.append({"file": e["file"], "name": e.get("name"), "kind": kind(e["file"]),
                     "seed": _score(m.get("seed")), "seed_expr": e["seed_expr"],
                     "cx": cx, "cx_expr": e.get("costex_expr"),
                     "cx_note": "" if cx else _note(m.get("costex")),
                     "dy": dy, "dy_expr": e.get("daisy_expr"),
                     "dy_note": "" if dy else (e["daisy_status"]
                                               if e["daisy_status"] != "ok"
                                               else _note(m.get("daisy")))})
    return rows


def _note(rep) -> str:
    return rep["status"] if rep else "no program"


def _verdicts(rows: list) -> tuple:
    """A dead tie is a real result, usually the same program from both."""
    cxw, dyw, tied, close = [], [], [], []
    for r in rows:
        cx, dy = r["cx"], r["dy"]
        if dy is None or (cx and cx < dy * SLACK):
            cxw.append(r)
        elif cx is None or (dy and dy < cx * SLACK):
            dyw.append(r)
        elif cx == dy:
            tied.append(r)
        else:
            close.append(r)
    return cxw, dyw, tied, close


def _headroom(rows: list, floor: float) -> list:
    """Cores where the seed loses more than floor ulps, so a rewriter has
    something to win.  Counting the rest as ties reports the corpus."""
    return [r for r in rows if r["seed"] and r["seed"] > floor]


def _saved(rows: list, key: str) -> float:
    """Mean bits of error a rewriter took off the seed."""
    got = [math.log2(r["seed"] / r[key]) for r in rows if r["seed"] and r[key]]
    return sum(got) / len(got) if got else 0.0


def step_rewrite(results: list) -> dict:
    results = [r for r in results if r["status"] == "ok"]
    seeds = common.seed_units(results)
    workdir = tempfile.mkdtemp(prefix="costex-rw-")
    t0 = time.time()
    try:
        rewrites, daisy_ver = rewrite(seeds, seed=REWRITE_SEED, timeout=TOOL_TIMEOUT,
                                      jobs=JOBS, workdir=workdir)
        cands, index = candidates(results, rewrites)
        scores = sample_reports(cands)
    except Exception:
        print(f"  work kept in {workdir}")
        raise
    else:
        shutil.rmtree(workdir, ignore_errors=True)

    out = []
    for u, r in zip(seeds, results):
        rw = rewrites.get(u["name"], {})
        out.append({"file": r["file"], "name": r.get("name"),
                    "seed_expr": r["expr"],
                    "costex_expr": r.get(FIELDED.best_expr),
                    "daisy_expr": rw.get("expr"),
                    "daisy_status": rw.get("status"),
                    "daisy_error": rw.get("error"),
                    "measured": {who: scores.get(index[(r["file"], who)])
                                 for who in ("seed", "costex", "daisy")
                                 if (r["file"], who) in index}})
    elapsed = time.time() - t0
    payload = {"daisy_version": daisy_ver, "rewrite_seed": REWRITE_SEED,
               "daisy_options": list(daisy.REWRITE_OPTS),
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
    return "0" if x == 0 else f"{x:.3g}"     # costex can report -0.0


def _code(expr: str) -> str:
    if len(expr) > WIDTH:
        expr = expr[:WIDTH - 1] + "…"
    return "`" + expr.replace("|", "\\|") + "`"


def _geomean(xs: list) -> float:
    return math.exp(sum(map(math.log, xs)) / len(xs))


def _spread(xs: list) -> str:
    if not xs:
        return "no ratio"
    return (f"geomean {_geomean(xs):.3g}x, median {xs[len(xs) // 2]:.3g}x, "
            f"p10 {xs[int(0.1 * (len(xs) - 1))]:.3g}x, "
            f"p90 {xs[int(0.9 * (len(xs) - 1))]:.3g}x")


# -- bounds.md --


def _rows(res: dict, ext: dict) -> list:
    """One row per core: costex's seed bounds beside each tool's report."""
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


def coverage_rows(rows: list, tools: list) -> list:
    out = ["", "## Coverage", "",
           "| Analyser | seeds |"
           + "".join(f" bounded {m.label} |" for m in common.METRICS)
           + " bounded neither | why not |",
           "|---|--:|" + "--:|" * (len(common.METRICS) + 1) + "---|"]
    for who in ["costex"] + tools:
        got = [[seed_bound(r, who, m) for m in common.METRICS] for r in rows]
        why = Counter(rep.get("error", "")[:52] for r in rows
                      if who != "costex" and (rep := r["tools"].get(who))
                      and rep["status"] != "ok")
        out.append(f"| {who} | {len(rows)} |"
                   + "".join(f" {sum(1 for g in got if g[i] is not None)} |"
                             for i in range(len(common.METRICS)))
                   + f" {sum(1 for g in got if not any(v is not None for v in g))} | "
                   + ("; ".join(f"{v}x {k}" for k, v in why.most_common(3)) or NONE)
                   + " |")
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
    return "| " + " | ".join(cells) + " |"


def bounds_markdown(res: dict, ext: dict) -> str:
    rows = _rows(res, ext)
    tools = sorted({t for r in rows for t in r["tools"]})
    out = ["# Bounds: " + " vs ".join(["costex"] + tools), ""]
    out += [f"- {t} {ext.get('versions', {}).get(t, '?')}, "
            f"`{' '.join(ext.get('options', {}).get(t, []))}`" for t in tools]

    out += ["", "## Summary", "",
            "Every analyser bounds the same program, the seed.  "
            "`their bound / ours`, so above 1x means our bound is tighter.", "",
            "| Metric | vs | both bounded | we are tighter | looser | tie "
            "| only we bound it | only they do | their bound / ours |",
            "|---|---|--:|--:|--:|--:|--:|--:|---|"]
    for m in common.METRICS:
        for t in tools:
            n, ratios = tightness(rows, t, m)
            out.append(f"| {m.label} | {t} | {n['both']} | {n['tighter']} | "
                       f"{n['looser']} | {n['tie']} | {n['only ours']} | "
                       f"{n['only theirs']} | {_spread(ratios)} |")

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
            f"{NONE} the analyser ran and bounded the other metric but not this "
            "one, almost always a range containing zero, which leaves relative "
            "error unbounded.  `n/b` it ran cleanly and bounded nothing; `t/o` "
            "timed out; `err` or a bare status, it failed."]
    return "\n".join(out) + "\n"


# -- rewrites.md --


def _bits(v) -> str:
    return NONE if v is None else f"{math.log2(v):.1f}"


def _vs_seed(seed: float, got: float) -> str:
    """Bits saved, blank inside the noise."""
    r = seed / got
    return NONE if SLACK < r < 1 / SLACK else f"{math.log2(r):+.1f}"


def _edge(r: dict) -> float:
    if r["cx"] is None:
        return -math.inf
    if r["dy"] is None:
        return math.inf
    return r["dy"] / r["cx"]


def h2h_markdown(rw: dict) -> str:
    sp = rw.get("sampling", {})
    every = h2h(rw["results"])
    rows = [r for r in every if r["kind"] != "analysis"]
    cxw, dyw, tied, close = _verdicts(rows)
    same_prog = sum(1 for r in tied if r["cx_expr"] == r["dy_expr"])
    st = Counter(e["daisy_status"] for e in rw["results"])
    same = sum(1 for e in rw["results"] if e.get("daisy_expr") == e["seed_expr"])

    head = _headroom(rows, HEADROOM)
    hcxw, hdyw, htied, hclose = _verdicts(head)

    out = ["# Rewriting: costex vs Daisy", "",
           "Both rewriters get the same seed, and both are scored by measuring "
           f"error in bits rather than bounding it: {sp.get('points')} uniform "
           "points of the core's box, the same ones for every program of that "
           "core, plus the worst points a hill climb reaches from them -- "
           "pooled, so every program is scored at every other program's worst "
           "case as well.  That makes the score a lower bound on the worst "
           "case -- but neither rewriter optimises measured error, so neither "
           "can game it.  For bounds, see `bounds.md`.",
           "",
           f"A verdict needs a **{MARGIN}x** margin in ulps.  Resampling with "
           f"independent point sets moves the ratio by {NOISE_P50}x at the median "
           f"and {NOISE_P90}x at the 90th percentile, so a smaller gap is not "
           "distinguishable from having drawn different points, and is reported "
           "as too close to call.",
           "",
           f"- {len(rows)} of {len(rw['results'])} cores get a verdict; the "
           f"{sum(1 for r in every if r['kind'] == 'analysis')} tagged optimal are left "
           f"out, as are {len(rw['results']) - len(every)} where neither side produced a "
           "program that could be measured",
           f"- of those {len(rows)}, **{len(head)} have headroom**: the seed "
           f"loses more than {HEADROOM:.0f} ulps, so there is something for a "
           "rewriter to take off",
           f"- sampling {sp.get('version')}, {sp.get('points')} points drawn "
           f"uniformly over the {sp.get('distribution')}s of each box, "
           f"seed {sp.get('seed')}, then {sp.get('search_seeds')} climbs per "
           f"program over a ladder of {sp.get('search_levels')} step sizes",
           f"- daisy {rw.get('daisy_version')}, seed {rw.get('rewrite_seed')}, "
           f"`{' '.join(rw.get('daisy_options', []))}`",
           "- daisy: " + ", ".join(f"{v} {k}" for k, v in st.most_common())
           + f", and returned the seed unchanged on {same}",
           "",
           "## Summary", "",
           "Only a core whose seed is inaccurate can be made more accurate.  "
           "The corpus is mostly seeds that are already right to a couple of "
           "ulps, and on those every rewriter ties by construction, so the "
           "headline is the cores with headroom:", "",
           f"- **on the {len(head)} cores with headroom: costex wins "
           f"{len(hcxw)}, daisy wins {len(hdyw)}, dead tie {len(htied)}, "
           f"too close to call {len(hclose)}**",
           f"- **bits of error taken off the seed, mean over those cores: "
           f"costex {_saved(head, 'cx'):+.2f}, daisy {_saved(head, 'dy'):+.2f}**",
           "",
           "How that moves with where the bar is put:", "",
           "| seed loses more than | cores | costex | daisy | dead tie | "
           "too close | costex bits | daisy bits |",
           "|---|--:|--:|--:|--:|--:|--:|--:|"]
    for floor in HEADROOM_STEPS:
        sel = _headroom(rows, floor)
        a, b, c, d = _verdicts(sel)
        out.append(f"| {floor:.0f} ulps{' (the bar)' if floor == HEADROOM else ''} "
                   f"| {len(sel)} | {len(a)} | {len(b)} | {len(c)} | {len(d)} "
                   f"| {_saved(sel, 'cx'):+.2f} | {_saved(sel, 'dy'):+.2f} |")

    out += ["",
            "The whole corpus, headroom or not, for completeness:", "",
            f"- costex wins {len(cxw)}, daisy wins {len(dyw)}, "
            f"dead tie {len(tied)}, too close to call {len(close)}",
            f"- a side whose program could not be measured loses: "
            f"{sum(1 for r in cxw if r['dy'] is None)} of costex's wins and "
            f"{sum(1 for r in dyw if r['cx'] is None)} of Daisy's",
            f"- of the {len(tied)} dead ties, {same_prog} are cores where both "
            "rewriters returned the same program, so there was nothing to "
            f"separate; the other {len(tied) - same_prog} returned different programs "
            "that measure identically",
            f"- the {len(close)} too close to call differ by less than the "
            f"{MARGIN}x margin",
            "- daisy ulps / costex ulps, "
            f"{sum(1 for r in rows if r['cx'] and r['dy'])} both measured: "
            + _spread(sorted(r["dy"] / r["cx"] for r in rows if r["cx"] and r["dy"])),
            "",
            "Each rewriter against the seed it was given, same points:", ""]
    out += ["| Rewriter | measured | improved | unchanged | regressed | seed / theirs |",
            "|---|--:|--:|--:|--:|---|"]
    for label, key in (("costex", "cx"), ("daisy", "dy")):
        g = sorted(r["seed"] / r[key] for r in rows if r["seed"] and r[key])
        up = sum(1 for x in g if x > 1 / SLACK)
        down = sum(1 for x in g if x < SLACK)
        out.append(f"| {label} | {len(g)} | {up} | {len(g) - up - down} | {down} "
                   f"| {_spread(g)} |")

    bad = {who: sorted(e["file"] for e in rw["results"]
                       if (rep := (e["measured"] or {}).get(who))
                       and rep.get("status") == "ok"
                       and rep.get("equivalent") is False)
           for who in ("costex", "daisy")}
    out += ["",
            "Every rewrite is measured against the **seed's** exact value, so a "
            "rewrite that changed the function scores as wrong rather than as "
            "accurate.  Equivalence is checked directly, by comparing exact "
            f"values at up to {sample.EQUIV_POINTS} points of the box:", "",
            "| Rewriter | rewrote | not equivalent to the seed |",
            "|---|--:|---|"]
    for who, k in (("costex", "cx"), ("daisy", "dy")):
        n = sum(1 for r in rows if r[f"{k}_expr"] and r[f"{k}_expr"] != r["seed_expr"])
        b = bad[who]
        out.append(f"| {who} | {n} | {len(b)}"
                   + (": " + ", ".join(f"`{f[:44]}`" for f in b[:3]) if b else "")
                   + " |")

    out += ["", "## Every core", "",
            "- sorted by how far costex's rewrite beats Daisy's, so Daisy's wins are last",
            f"- a core with headroom -- seed above {HEADROOM:.0f} ulps -- is marked *",
            "",
            "| Core | Program | bits of error | bits saved vs seed |",
            "|---|---|---:|---:|"]
    with_head = {id(r) for r in head}
    for r in sorted(rows, key=lambda r: -_edge(r)):
        progs = [("seed", r["seed_expr"], r["seed"], ""),
                 ("costex", r["cx_expr"], r["cx"], r["cx_note"]),
                 ("daisy", r["dy_expr"], r["dy"], r["dy_note"])]
        out.append("| " + " | ".join([
            f"**{r['name'] or r['file']}**" + ("&nbsp;\\*" if id(r) in with_head else ""),
            "<br>".join(f"{who}: {_code(e) if e else NONE}" for who, e, _, _ in progs),
            "<br>".join(note or _bits(v) for _, _, v, note in progs),
            "<br>".join(NONE if who == "seed" or v is None or not r["seed"]
                        else _vs_seed(r["seed"], v) for who, _, v, _ in progs),
        ]) + " |")
    return "\n".join(out) + "\n"


# -- driving --


def unavailable() -> list:
    out = []
    if not (shutil.which(egg.EGGLOG) or os.path.exists(egg.EGGLOG)):
        out.append(f"no egglog at {egg.EGGLOG}; set EGGLOG")
    if not os.path.exists(os.path.join(common.FPBENCH, "fpbench.rkt")):
        out.append(f"no fpbench.rkt under {common.FPBENCH}; set FPBENCH")
    for tool in sorted(TOOLS):
        try:
            TOOLS[tool]["version"]()
        except RuntimeError as e:
            out.append(str(e))
    return out


def _read(name: str):
    path = os.path.join(common.RESULTS, name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def main() -> int:
    missing = unavailable()
    if missing:
        # stale either way, so reuse all of it rather than mix old with new
        res, ext, rw = (_read("results.json"), _read("external.json"),
                        _read("rewrite.json"))
        if not (res and ext and rw):
            return _die(missing)
        print("\n".join(f"  {m}" for m in missing))
        print(f"\n  reusing the JSON in {os.path.relpath(common.RESULTS)}, "
              "rewriting only the markdown")
    else:
        print(f"\n== costex ==  {len(corpus())} cores")
        results = step_costex()
        res = {"results": results}
        print("\n== external ==")
        ext = step_external(results)
        print("\n== rewrite ==")
        rw = step_rewrite(results)

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
