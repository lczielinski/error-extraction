"""The tables of the evaluation, from results/*.json into results/tables/<name>.tex. A tool that fails
counts as returning its input, and each table says how many did. A relative bound of 1 or more says
nothing, so it counts as no bound."""

import math
import os
import statistics

import run
from run import BOUNDS, SIZES

INF = math.inf
LN10 = math.log(10)
NAMES = {"fptaylor": "FPTaylor", "gappa": "Gappa", "daisy": "Daisy", "herbie": "Herbie", "ours": "Ours",
         "ours-plain": "No branch", "greedy": "Greedy readout", "abs-only": "Absolute error only",
         "rel-only": "Relative error only"}


def num(x):
    if x is None:
        return "--"
    return str(int(x)) if float(x).is_integer() and abs(x) < 1e6 else f"{x:.3g}"


def lognum(x):
    """A ratio given by its log, written out even past the float range."""
    if x is None:
        return "--"
    e = math.floor(x / LN10)
    return num(math.exp(x)) if abs(e) < 300 else f"{math.exp(x - e * LN10):.3g}e{e:+d}"


def geomean(xs):
    return math.exp(statistics.fmean(map(math.log, xs))) if xs else None


def mean(xs):
    return statistics.fmean(xs) if xs else None


def median(xs):
    return statistics.median(xs) if xs else None


def said(m, x):
    """A bound, or INF for a missing one and for a relative bound of 1 or more."""
    return INF if x is None or (m == "rel" and x >= 1) else x


def ratio(a, b):
    """log(a / b) for finite a and b, 0 when they are equal, or None, so a ratio past the float
    range still counts."""
    if a is None or b is None or max(a, b) == INF:
        return None
    if a == b:
        return 0.0
    return math.log(a) - math.log(b) if min(a, b) > 0 else None


def ratios(pairs):
    return [r for r in (ratio(a, b) for a, b in pairs) if r is not None]


def shared(rows, names, pair):
    """Each row's log ratios over the cores where every row has one, so the rows of a column cover
    the same cores; and how many cores those are."""
    names = [n for n in names if all(ratio(*pair(r, n)) is not None for r in rows)]
    return {r: [ratio(*pair(r, n)) for n in names] for r in rows}, len(names)


def spread(logs):
    return [lognum(mean(logs)), lognum(median(logs))]


def table(caption, label, columns, head, rows, small=False):
    """A row is a list of cells, or a string such as \\midrule."""
    body = "\n".join(r if isinstance(r, str) else " & ".join(map(str, r)) + " \\\\" for r in rows)
    size = " \\small" if small else ""
    return (f"\\begin{{table}}[H] \\centering{size}\n\\caption{{{caption}}}\\label{{{label}}}\n"
            f"\\begin{{tabular}}{{{columns}}}\n\\toprule\n{head} \\\\\n\\midrule\n{body}\n"
            "\\bottomrule\n\\end{tabular}\n\\end{table}\n")


def metric(name):
    return run.ours_metric(run.ours()[name])


def sound(name, who):
    """The smaller of FPTaylor's and Gappa's bounds on who's program, on the core's metric."""
    m = metric(name)
    return min(said(m, run.bounds()[name][t].get(who, {}).get(m)) for t in ("fptaylor", "gappa"))


def accuracy():
    measured, speeds = run.measured(), run.speeds()
    names = [n for n in run.benchmark2() if "error" not in measured[n]]
    tools = ("herbie", "daisy", "ours")

    def got(t, n):
        """t's program, or the input if t returned none or one that disagrees with it over the reals."""
        return t if measured[n].get(t, {}).get("equivalent") else "original"

    def sampled(key):
        return lambda t, n: (measured[n][got(t, n)][key], measured[n]["original"][key])

    columns = [shared(tools, names, f) for f in (lambda t, n: (sound(n, got(t, n)), sound(n, "original")),
                                                 sampled("ulps"), sampled("mean"),
                                                 lambda t, n: (speeds[n].get(got(t, n)), speeds[n].get("original")))]
    (bound, n_bound), (worst, n_worst), (avg, n_avg), (speed, n_speed) = columns
    rows = [[NAMES[t], *spread(bound[t]), *spread(worst[t]), *spread(avg[t]), lognum(mean(speed[t])),
             sum(got(t, n) == "original" for n in names)] for t in tools]
    rows += ["\\midrule", ["Cores", *(f"\\multicolumn{{2}}{{c}}{{{k}}}" for k in (n_bound, n_worst, n_avg)), n_speed,
                           len(names)]]
    head = ("& \\multicolumn{2}{c}{Sound Bound Ratio} & \\multicolumn{2}{c}{Max Sampled Ratio} & "
            "\\multicolumn{2}{c}{Avg Sampled Ratio} & & \\\\\n"
            "\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\\cmidrule(lr){6-7}\n"
            "Tool & Geomean & Median & Geomean & Median & Geomean & Median & Speed & Failed")
    left = len(run.benchmark2()) - len(names)
    return table("Accuracy of rewritten programs on Benchmark (2), divided by the input. A tool that returns no "
                 "program, or one that disagrees with its input over the reals at a sampled input, counts as "
                 "returning its input (Failed). Each column covers the cores where every program's value is finite "
                 "and nonzero (Cores). Speed is the geomean of run time divided by the input's, so above 1 is slower."
                 + f" Cores whose measurement failed are left out ({left})." * bool(left),
                 "tab:accuracy", "lrrrrrrrr", head, rows)


def tightness():
    ours, bounds = run.ours(), run.bounds()
    rows = []
    for m, label in (("abs", "Absolute"), ("rel", "Relative")):
        b = {n: said(m, ours[n].get("bound", {}).get(m)) for n in ours}
        rows.append([label, NAMES["ours"], sum(x < INF for x in b.values()), "--", "--", "--"])
        for t in ("fptaylor", "gappa", "daisy"):
            a = {n: said(m, bounds[n][t].get("original", {}).get(m)) for n in ours}
            either = [n for n in ours if min(a[n], b[n]) < INF]
            wins = "/".join(str(sum(f(b[n], a[n]) for n in either))
                            for f in (lambda x, y: x < y, lambda x, y: x == y, lambda x, y: x > y))
            rows.append(["", NAMES[t], sum(x < INF for x in a.values()), *spread(ratios((a[n], b[n]) for n in ours)),
                         wins])
        rows.append("\\midrule")
    return table(f"Bounds on the {len(ours)} inputs of Benchmark (1), divided by ours, so a ratio above 1 means ours "
                 "is tighter. Bounded counts the inputs each tool bounds, where a relative bound of 1 or more counts "
                 "as none. The ratios cover the inputs both bound, and tighter/tie/looser covers every input either "
                 "bounds, so an input that only one bounds counts as tighter for that one.", "tab:tightness", "llrrrc",
                 "Error & Tool & Bounded & Geomean Ratio & Median Ratio & Ours tighter/tie/looser", rows[:-1],
                 small=True)


def sampled():
    ours, originals = run.ours(), run.originals()
    rows = []
    for m, label in (("abs", "Absolute"), ("rel", "Relative")):
        b = {n: said(m, ours[n].get("bound", {}).get(m)) for n in ours}
        xs = sorted(ratios((b[n], originals[n].get(m)) for n in ours))
        rows.append([label, sum(x == INF for x in b.values()),
                     *map(lognum, (xs[0], median(xs), mean(xs), xs[-1]) if xs else [None] * 4)])
    return table(f"Our bounds on the {len(ours)} inputs of Benchmark (1), divided by their max sampled error, over the "
                 "inputs where both are finite and nonzero; Unbounded counts the inputs we do not bound.",
                 "tab:sampled", "lrrrrr", "Error & Unbounded & Min & Median & Geomean & Max", rows)


def raw(name, who, m):
    """The m-bound of who's program on a Benchmark (2) core, with our analysis in our e-graph."""
    o = run.ours()[name]
    if who == "ours":
        x = o["bounds"][m] if o.get("programs") else None
    elif who == "original":
        x = (o.get("original") or o.get("bound") or {}).get(m)
    else:
        x = run.alternatives()[name].get(who, {}).get(m, {}).get(m)
    return said(m, x)


def picked(name, who, m):
    """who, or the input if who has no program with a finite m-bound."""
    return who if raw(name, who, m) < INF else "original"


def bound(name, who, m):
    return raw(name, picked(name, who, m), m)


def seconds(name, who):
    o, a = run.ours()[name], run.alternatives()[name]
    if who == "ours":
        return o["egglog_s"] + o["extract_s"] if "egglog_s" in o else o.get("seconds", 0)
    return a[who]["seconds"] if who in a else a.get("seconds", 0)


def extraction():
    measured, names = run.measured(), run.benchmark2()
    m = {n: metric(n) for n in names}
    methods = [f"size{n}" for n in SIZES]

    def ulps(n, w):
        return measured[n].get(picked(n, w, m[n]), {}).get("ulps")

    bounds, n_bound = shared(methods, names, lambda w, n: (bound(n, w, m[n]), bound(n, "ours", m[n])))
    worst, n_worst = shared(methods, names, lambda w, n: (ulps(n, w), ulps(n, "ours")))
    rows = [[f"Size, top-{w[4:]}", *spread(bounds[w]), *spread(worst[w]),
             sum(bound(n, "ours", m[n]) < bound(n, w, m[n]) for n in names),
             sum(picked(n, w, m[n]) == "original" for n in names), num(sum(seconds(n, w) for n in names))]
            for w in methods]
    rows.append(["Ours", *["--"] * 5, sum(picked(n, "ours", m[n]) == "original" for n in names),
                 num(sum(seconds(n, "ours") for n in names))])
    head = ("& \\multicolumn{2}{c}{Bound Ratio} & \\multicolumn{2}{c}{Max Sampled Ratio} & & & \\\\\n"
            "\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\n"
            "Method & Geomean & Median & Geomean & Median & Ours strictly better & Failed & Time (s)")
    return table(f"Extracting by size and then bounding, divided by our extraction, on the {len(names)} cores of "
                 "Benchmark (2), so a ratio above 1 means ours is better. A method with no program whose bound is "
                 "finite counts as returning the input (Failed), and a relative bound of 1 or more counts as none. "
                 f"Bound ratios cover the {n_bound} cores where every bound is finite and nonzero, and sampled "
                 f"ratios the {n_worst} where every program was measured and none is exact. Time is the total over "
                 "all cores.", "tab:extraction", "lrrrrrrr", head, rows)


def runtime():
    ours, bounds, rewrites, names = run.ours(), run.bounds(), run.rewrites(), run.benchmark2()

    def row(task, tool, reports):
        xs = [r["seconds"] for r in reports if r.get("seconds")]
        return [task, NAMES[tool], *map(num, (median(xs), geomean(xs), max(xs, default=None))),
                sum(r.get("status") == "timeout" for r in reports),
                sum(r.get("status") not in ("ok", "timeout") for r in reports)]

    def status(o):
        if o.get("cut") or o.get("failed") == "timeout":
            return "timeout"
        return "error" if "failed" in o or "error" in o else "ok"

    rows = [row("Bounding" if t == "fptaylor" else "", t, [bounds[n][t]["original"] for n in bounds])
            for t in ("fptaylor", "gappa", "daisy")]
    rows += [row("", "ours", [{"seconds": o.get("bound_s"), "status": "ok" if "bound_s" in o else "error"}
                              for o in ours.values()]), "\\midrule"]
    rows += [row("Rewriting" if t == "herbie" else "", t, [rewrites[n][t] for n in names]) for t in ("herbie", "daisy")]
    rows.append(row("", "ours", [{"seconds": seconds(n, "ours"), "status": status(ours[n])} for n in names]))
    return table(f"Running times in seconds: bounding the {len(bounds)} inputs of Benchmark (1), and rewriting the "
                 f"{len(names)} of Benchmark (2). Timeouts are runs stopped by a time limit. Our extraction stopped "
                 "by its limit still returns the frontier of the last round it finished, but an e-graph not built "
                 "within its limit gives no program. Failed counts other failures.", "tab:runtime", "llrrrrr",
                 "Task & Tool & Median & Geomean & Max & Timeouts & Failed", rows)


def stats():
    names = run.benchmark2()
    rs = [run.ours()[n] for n in names if "nodes" in run.ours()[n]]
    rows = []
    for key, label in (("nodes", "E-nodes"), ("classes", "E-classes"), ("root_frontier", "Root frontier size"),
                       ("max_frontier", "Max frontier size (any class)"), ("rounds", "Extraction iterations"),
                       ("egglog_s", "E-graph time (s)"), ("extract_s", "Extraction time (s)")):
        xs = [r[key] for r in rs]
        rows.append([label, *map(num, (median(xs), geomean([x for x in xs if x > 0]), max(xs, default=None)))])
    empty = sum(r["root_frontier"] == 0 for r in rs)
    timeouts = sum(run.ours()[n].get("failed") == "timeout" for n in names)
    failed = len(names) - len(rs) - timeouts
    return table(f"Cost breakdown of our tool on the {len(rs)} cores of Benchmark (2) whose e-graph was built "
                 f"({timeouts} timed out and {failed} failed), without branching. On {empty} of them no program has "
                 "a bound, so the root frontier is empty; geomeans leave out zeros.",
                 "tab:stats", "lrrr", "Metric & Median & Geomean & Max", rows)


def conditions(text):
    """The conditions of the ifs in a program's text."""
    out, i = [], text.find("(if (")
    while i >= 0:
        out.append(text[i + 4:text.index(")", i + 4) + 1])
        i = text.find("(if (", i + 1)
    return out


def branching():
    rows = []
    for name, r in run.branching().items():
        base = r.get("ours-plain", {}).get("ns")
        for who in ("ours-plain", "ours", "daisy", "herbie"):
            first = who == "ours-plain"
            cells = [os.path.basename(name)[:-7] if first else "", r.get("expected", "") if first else "", NAMES[who]]
            p = r.get(who) or {}
            if "program" not in p or not p["measured"].get("equivalent"):
                status = "error" if "error" in r else p.get("status", "not equivalent" if "program" in p else "n/a")
                rows.append(cells + [status, "--", "--", "--"])
                continue
            points = "--" if first else ", ".join(conditions(p["program"])) or "none"
            rows.append(cells + [points, num(said("rel", p["bound"].get("rel"))), num(p["measured"]["ulps"]),
                                 num(p["ns"] / base) if base and "ns" in p else "--"])
        rows.append("\\midrule")
    found = [a for a in run.alternatives().values() if a.get("proposed") is not None]
    print(f"Benchmark (2): {sum(a['proposed'] for a in found)} additions in the e-graphs may have a condition "
          f"number above ten, and {sum(a['split'] for a in found)} conditionals were inserted.")
    return table("Branching on Benchmark (3). Bound is our bound on the relative error (inf where it is 1 or more), "
                 "max sampled error is in ulps, and Speed is run time divided by our unbranched program's.",
                 "tab:branching", "llllrrr",
                 "Benchmark & Expected & Tool & Branch points & Bound & Max sampled error & Speed", rows[:-1],
                 small=True)


def ablation():
    names, variants = run.benchmark2(), ("greedy", "abs-only", "rel-only", "ours")
    tracks = {"abs": ("greedy", "abs-only", "ours"), "rel": ("greedy", "rel-only", "ours")}
    by = {m: shared(tracks[m], names, lambda w, n: (bound(n, w, m), raw(n, "original", m))) for m in BOUNDS}

    def cells(w, m):
        if w not in tracks[m]:
            return ["--"] * 3
        return [*spread(by[m][0][w]), sum(picked(n, w, m) == "original" for n in names)]

    rows = [[NAMES[w], *cells(w, "abs"), *cells(w, "rel"), num(sum(seconds(n, w) for n in names))] for w in variants]
    head = ("& \\multicolumn{3}{c}{Absolute Bound Ratio} & \\multicolumn{3}{c}{Relative Bound Ratio} & \\\\\n"
            "\\cmidrule(lr){2-4}\\cmidrule(lr){5-7}\n"
            "Variant & Geomean & Median & Failed & Geomean & Median & Failed & Time (s)")
    return table(f"Ablations on the {len(names)} cores of Benchmark (2), without branching: bounds divided by the "
                 "input's. A variant with no program whose bound is finite counts as returning the input (Failed), "
                 "and a relative bound of 1 or more counts as none. "
                 f"Each metric compares the variants that track it, over the {by['abs'][1]} (absolute) and "
                 f"{by['rel'][1]} (relative) cores where the input's bound is finite and nonzero. Time is the total "
                 "over all cores.", "tab:ablation", "lrrrrrrr", head, rows)


if __name__ == "__main__":
    broken = [n for n, r in run.originals().items() if "error" in r]
    if broken:
        print(f"warning: {len(broken)} inputs could not be measured, so Benchmark (2) leaves them out: {broken}")
    os.makedirs(os.path.join(run.RESULTS, "tables"), exist_ok=True)
    for f in (accuracy, tightness, sampled, extraction, runtime, stats, branching, ablation):
        with open(os.path.join(run.RESULTS, "tables", f.__name__ + ".tex"), "w") as out:
            out.write(f())
