"""The tables of Section 6, from results/*.json into results/tables/<name>.tex."""

import math
import os
import statistics

import run
from run import BOUNDS, SIZES, fielded

NAMES = {"fptaylor": "FPTaylor", "gappa": "Gappa", "daisy": "Daisy", "herbie": "Herbie", "ours": "Ours",
         "ours-plain": "No branch", "greedy": "Greedy readout", "abs-only": "Absolute error only",
         "rel-only": "Relative error only"}


def num(x):
    if x is None:
        return "--"
    return str(int(x)) if float(x).is_integer() and abs(x) < 1e6 else f"{x:.3g}"


def geomean(xs):
    return math.exp(statistics.fmean(map(math.log, xs))) if xs else None


def median(xs):
    return statistics.median(xs) if xs else None


def ratios(pairs):
    """a / b for the pairs where both are finite and positive."""
    return [a / b for a, b in pairs if a and b and 0 < a < math.inf and 0 < b < math.inf]


def shared(rows, names, pair):
    """Each row's ratios a / b over the cores where every row's pair (a, b) has a ratio, so
    the rows of a column summarize the same cores; and how many cores those are."""
    names = [n for n in names if all(ratios([pair(r, n)]) for r in rows)]
    return {r: ratios(pair(r, n) for n in names) for r in rows}, len(names)


def spread(xs):
    return [num(geomean(xs)), num(median(xs))]


def table(caption, label, columns, head, rows, small=False):
    """A row is a list of cells, or a string such as \\midrule."""
    body = "\n".join(r if isinstance(r, str) else " & ".join(map(str, r)) + " \\\\" for r in rows)
    size = " \\small" if small else ""
    return (f"\\begin{{table}}[H] \\centering{size}\n\\caption{{{caption}}}\\label{{{label}}}\n"
            f"\\begin{{tabular}}{{{columns}}}\n\\toprule\n{head} \\\\\n\\midrule\n{body}\n"
            "\\bottomrule\n\\end{tabular}\n\\end{table}\n")


def sound(name, who):
    """The smaller of FPTaylor's and Gappa's bounds, on the metric our program is chosen by."""
    m = fielded(run.ours()[name]["bounds"])
    found = [run.bounds()[name][t].get(who, {}).get(m) for t in ("fptaylor", "gappa")]
    return min((b for b in found if b is not None), default=None)


def accuracy():
    measured, speeds = run.measured(), run.speeds()
    tools = ("herbie", "daisy", "ours")
    names = [n for n in run.benchmark2() if all(measured[n].get(t, {}).get("equivalent") for t in tools)]
    bound, n_bound = shared(tools, names, lambda t, n: (sound(n, t), sound(n, "original")))
    worst, n_sampled = shared(tools, names, lambda t, n: (measured[n][t]["ulps"], measured[n]["original"]["ulps"]))
    mean, _ = shared(tools, names, lambda t, n: (measured[n][t]["mean"], measured[n]["original"]["mean"]))
    speed, _ = shared(tools, names, lambda t, n: (speeds[n][t], speeds[n]["original"]))
    rows = [[NAMES[t], *spread(bound[t]), *spread(worst[t]), *spread(mean[t]), num(geomean(speed[t]))] for t in tools]
    head = ("& \\multicolumn{2}{c}{Sound Bound Ratio} & \\multicolumn{2}{c}{Max Sampled Ratio} & "
            "\\multicolumn{2}{c}{Avg Sampled Ratio} & \\\\\n"
            "\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\\cmidrule(lr){6-7}\n"
            "Tool & Geomean & Median & Geomean & Median & Geomean & Median & Speed")
    return table(f"Accuracy of rewritten programs on Benchmark (2), over the {len(names)} cores where every tool "
                 f"returned a program equal to its input; the sound bounds cover the {n_bound} of them where FPTaylor "
                 f"or Gappa bounds every program, and sampled errors the {n_sampled} where none is exact.",
                 "tab:accuracy", "lrrrrrrr", head, rows)


def tightness():
    ours, bounds = run.ours(), run.bounds()
    rows = []
    for m, label, tools in (("abs", "Absolute", ("fptaylor", "gappa", "daisy")),
                            ("rel", "Relative", ("fptaylor", "gappa"))):
        for t in tools:
            pairs = [(bounds[n][t]["original"].get(m), ours[n]["bound"][m]) for n in ours if "bound" in ours[n]]
            got = [(a, b) for a, b in pairs if a is not None]
            wins = f"{sum(b < a for a, b in got)}/{sum(b == a for a, b in got)}/{sum(b > a for a, b in got)}"
            rows.append([label if t == tools[0] else "", NAMES[t], len(got), len(pairs) - len(got),
                         *spread(ratios(got)), wins])
        rows += [["", "Numerors", "--", "--", "--", "--", "--"], "\\midrule"]
    return table("Bounds on Benchmark (1), relative to ours, over the cores where both bound the error; "
                 "a core only the tool bounds counts as ours looser.", "tab:tightness", "llrrrrc",
                 "Error & Tool & Supported & Failed & Geomean Ratio & Median Ratio & Ours tighter/tie/looser",
                 rows[:-1], small=True)


def sampled():
    ours, originals = run.ours(), run.originals()
    rows = []
    for m, label in (("abs", "Absolute"), ("rel", "Relative")):
        xs = sorted(ratios((ours[n]["bound"][m], originals[n].get(m)) for n in ours if "bound" in ours[n]))
        rows.append([label, *map(num, (xs[0], median(xs), geomean(xs), xs[-1]) if xs else [None] * 4)])
    return table("Our bounds on Benchmark (1), relative to max sampled error.", "tab:sampled", "lrrrr",
                 "Error & Min & Median & Geomean & Max", rows)


def bound(name, who, m):
    """The m-bound of who's program on a Benchmark (2) core, with our analysis in our e-graph."""
    o = run.ours()[name]
    return o["bounds"][m] if who == "ours" else run.alternatives()[name][who][m][m]


def seconds(name, who):
    o = run.ours()[name]
    return o["egglog_s"] + o["extract_s"] if who == "ours" else run.alternatives()[name][who]["seconds"]


def extraction():
    measured, names = run.measured(), run.benchmark2()
    m = {n: fielded(run.ours()[n]["bounds"]) for n in names}
    methods = [f"size{n}" for n in SIZES] + ["ours"]
    bounds, n_bound = shared(methods, names, lambda w, n: (bound(n, w, m[n]), run.ours()[n]["original"][m[n]]))
    worst, n_sampled = shared(methods, names,
                              lambda w, n: (measured[n].get(w, {}).get("ulps"), measured[n]["original"]["ulps"]))
    rows = []
    for who in methods:
        better = sum(bound(n, "ours", m[n]) < bound(n, who, m[n]) for n in names)
        rows.append(["Ours" if who == "ours" else f"Size, top-{who[4:]}", *spread(bounds[who]),
                     *spread(worst[who]), "--" if who == "ours" else better,
                     num(sum(seconds(n, who) for n in names))])
    head = ("& \\multicolumn{2}{c}{Bound Ratio} & \\multicolumn{2}{c}{Max Sampled Ratio} & & \\\\\n"
            "\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\n"
            "Method & Geomean & Median & Geomean & Median & Ours strictly better & Time (s)")
    return table(f"Extracting by size and then bounding, compared to our extraction, on Benchmark (2); bound "
                 f"ratios cover the {n_bound} cores where every method's program has a bound, and sampled ratios "
                 f"the {n_sampled} where every program was measured.", "tab:extraction", "lrrrrrr", head, rows)


def runtime():
    ours, bounds, rewrites, names = run.ours(), run.bounds(), run.rewrites(), run.benchmark2()

    def row(task, tool, reports):
        xs = [r["seconds"] for r in reports if r.get("seconds")]
        return [task, NAMES[tool], *map(num, (median(xs), geomean(xs), max(xs, default=None))),
                sum(r.get("status") == "timeout" for r in reports)]

    rows = [row("Bounding" if t == "fptaylor" else "", t, [bounds[n][t]["original"] for n in bounds])
            for t in ("fptaylor", "gappa", "daisy")]
    rows += [row("", "ours", [{"seconds": o["bound_s"]} for o in ours.values() if "bound_s" in o]), "\\midrule"]
    rows += [row("Rewriting" if t == "herbie" else "", t, [rewrites[n][t] for n in names]) for t in ("herbie", "daisy")]
    rows.append(row("", "ours", [{"seconds": seconds(n, "ours"), "status": "timeout" if ours[n]["cut"] else "ok"}
                                 for n in names]))
    return table(f"Running times in seconds: bounding the {len(bounds)} inputs of Benchmark (1), and rewriting the "
                 f"{len(names)} of Benchmark (2). When our extraction times out, it still returns the frontier of "
                 "the last round it finished.", "tab:runtime", "llrrrr",
                 "Task & Tool & Median & Geomean & Max & Timeouts", rows)


def stats():
    rs = [run.ours()[n] for n in run.benchmark2()]
    rows = []
    for key, label in (("nodes", "E-nodes"), ("classes", "E-classes"), ("root_frontier", "Root frontier size"),
                       ("max_frontier", "Max frontier size (any class)"), ("rounds", "Extraction iterations"),
                       ("egglog_s", "E-graph time (s)"), ("extract_s", "Extraction time (s)")):
        xs = [r[key] for r in rs]
        rows.append([label, *map(num, (median(xs), geomean([x for x in xs if x > 0]), max(xs)))])
    empty = sum(r["root_frontier"] == 0 for r in rs)
    return table(f"Cost breakdown of our tool on the {len(rs)} cores of Benchmark (2), without branching. On {empty} "
                 "of them no program has a bound, so the root frontier is empty; geomeans leave out zeros.",
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
        for who in ("ours-plain", "ours", "daisy", "herbie"):
            first = who == "ours-plain"
            cells = [os.path.basename(name)[:-7] if first else "", r["expected"] if first else "", NAMES[who]]
            p = r.get(who)
            if p is None:
                rows.append(cells + ["n/a", "--", "--", "--"])
                continue
            points = "--" if first else ", ".join(conditions(p["program"])) or "none"
            rows.append(cells + [points, num(p["bound"].get("rel")), num(p["measured"]["ulps"]),
                                 num(p["ns"] / r["ours-plain"]["ns"])])
        rows.append("\\midrule")
    found = [a for a in run.alternatives().values() if "proposed" in a]
    print(f"Benchmark (2): {sum(a['proposed'] for a in found)} additions in the e-graphs may have a condition "
          f"number above ten, and {sum(a['split'] for a in found)} conditionals were inserted.")
    return table("Branching on Benchmark (3). Bound is our bound on the relative error, and max sampled error is "
                 "in ulps.", "tab:branching", "llllrrr",
                 "Benchmark & Expected & Tool & Branch points & Bound & Max sampled error & Speed", rows[:-1],
                 small=True)


def ablation():
    names, variants = run.benchmark2(), ("greedy", "abs-only", "rel-only", "ours")
    tracks = {"abs": ("greedy", "abs-only", "ours"), "rel": ("greedy", "rel-only", "ours")}
    by = {m: shared(tracks[m], names, lambda w, n: (bound(n, w, m), run.ours()[n]["original"][m])) for m in BOUNDS}

    def none(n, w):
        return not (run.ours()[n]["programs"] if w == "ours" else any("program" in run.alternatives()[n][w][m]
                                                                       for m in BOUNDS))

    rows = [[NAMES[w], *[c for m in BOUNDS for c in (spread(by[m][0][w]) if w in tracks[m] else ["--", "--"])],
             sum(none(n, w) for n in names), num(sum(seconds(n, w) for n in names))] for w in variants]
    head = ("& \\multicolumn{2}{c}{Abs.\\ Bound Ratio} & \\multicolumn{2}{c}{Rel.\\ Bound Ratio} & & \\\\\n"
            "\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\n"
            "Variant & Geomean & Median & Geomean & Median & No program & Time (s)")
    return table(f"Ablations on Benchmark (2), without branching. Each metric compares the variants that track it, "
                 f"over the {by['abs'][1]} (absolute) and {by['rel'][1]} (relative) cores where all of them have a "
                 "bound.", "tab:ablation", "lrrrrrr", head, rows)


if __name__ == "__main__":
    os.makedirs(os.path.join(run.RESULTS, "tables"), exist_ok=True)
    for f in (accuracy, tightness, sampled, extraction, runtime, stats, branching, ablation):
        with open(os.path.join(run.RESULTS, "tables", f.__name__ + ".tex"), "w") as out:
            out.write(f())
