"""Every experiment of Section 6, in order. A step saves results/<step>.json and is skipped
when that file exists; the external tools also cache each program in .cache/.

    uv run python bench/run.py && uv run python bench/tables.py
"""

import json
import math
import os
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor

BENCH = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BENCH))

import sample  # noqa: E402
import speed  # noqa: E402
import variants  # noqa: E402
from costex.analysis import BOUNDS, FAIL, set_format  # noqa: E402
from costex.egraph import build  # noqa: E402
from costex.extract import best, extract  # noqa: E402
from costex.fpcore import expr, fpcore, parse, read, show  # noqa: E402
from tools import daisy, fptaylor, gappa, herbie  # noqa: E402

RESULTS = os.path.join(BENCH, "results")
JOBS = os.cpu_count()
EGGLOG_LIMIT, EXTRACT_LIMIT, TOOL_LIMIT = 300, 120, 300
HEADROOM = 4
SIZES = (1, 10, 100)


def cores(directory):
    return sorted(f"{directory}/{f}" for f in os.listdir(os.path.join(BENCH, directory)) if f.endswith(".fpcore"))


def load(name):
    with open(os.path.join(BENCH, name)) as f:
        core = parse(f.read())
    set_format(core.precision)
    return core


def program(text):
    return expr(read(text)[0])


def step(f):
    loaded = []

    def cached():
        path = os.path.join(RESULTS, f.__name__ + ".json")
        if not os.path.exists(path):
            print(f.__name__, flush=True)
            result = f()
            os.makedirs(RESULTS, exist_ok=True)
            with open(path, "w") as out:
                json.dump(result, out, indent=1)
        if not loaded:
            with open(path) as saved:
                loaded.append(json.load(saved))
        return loaded[0]
    return cached


def each(f, *args):
    """f over the zipped args in parallel, keyed by the first; an exception becomes {"error"}."""
    with ProcessPoolExecutor(JOBS) as pool:
        return dict(zip(args[0], pool.map(safe, [f] * len(args[0]), *args)))


def safe(f, *args):
    try:
        return f(*args)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"[:300]}


def bound(g, e):
    I = g.interval[g.root]
    return {m: math.inf if e is FAIL else float(b(e, I)) for m, b in BOUNDS.items()}


def fielded(bounds):
    """The metric our program is chosen by: relative error, unless no program bounds it."""
    return "rel" if bounds["rel"] < math.inf else "abs"


def bound_input(core, body):
    """Our bound on a program as it is: no rewriting, no new branches."""
    g = build(core._replace(body=body), 0, False)
    F, _, _ = extract(g)
    return bound(g, F[g.root][0][0] if F[g.root] else FAIL)


def ours_one(name):
    core = load(name)
    start = time.time()
    out = {"bound": bound_input(core, core.body), "bound_s": time.time() - start}
    start = time.time()
    g = build(core, 4, False, EGGLOG_LIMIT)
    built = time.time()
    F, k, cut = extract(g, EXTRACT_LIMIT)
    I = g.interval[g.root]
    chosen = {m: best(F[g.root], I, b) for m, b in BOUNDS.items()} if F[g.root] else {}
    return dict(out, egglog_s=built - start, extract_s=time.time() - built, rounds=k, cut=cut,
                nodes=sum(map(len, g.nodes.values())), classes=len(g.nodes), root_frontier=len(F[g.root]),
                max_frontier=max(map(len, F.values())), original=bound(g, variants.analyze(g, core.body)),
                programs={m: show(p) for m, (e, p) in chosen.items()},
                bounds={m: bound(g, e)[m] for m, (e, p) in chosen.items()} or bound(g, FAIL))


@step
def ours():
    """Benchmark (1): our bound on each input, and our rewrite of it without branches."""
    return each(ours_one, cores("cores"))


def original_one(name):
    core = load(name)
    return sample.measure(core, core.body, {"original": core.body})["original"]


@step
def originals():
    """Benchmark (1): the measured error of each input."""
    return each(original_one, cores("cores"))


def benchmark2():
    """The cores whose input loses more than HEADROOM ulps somewhere."""
    return [n for n, r in originals().items() if (r.get("ulps") or 0) > HEADROOM]


@step
def rewrites():
    """Benchmark (2): Herbie's and Daisy's rewrites, without branches."""
    texts = {n: fpcore(load(n)) for n in benchmark2()}
    with tempfile.TemporaryDirectory() as d:
        found = {"herbie": herbie.rewrite(list(texts.values()), d, TOOL_LIMIT, JOBS, branch=False),
                 "daisy": daisy.rewrite(list(texts.values()), d, TOOL_LIMIT, JOBS)}
    return {n: {tool: got[t] for tool, got in found.items()} for n, t in texts.items()}


def variants_one(name):
    core = load(name)
    start = time.time()
    g = build(core, 4, False, EGGLOG_LIMIT)
    built = time.time() - start

    def chosen(p):
        return {"program": show(p), **bound(g, variants.analyze(g, p))} if p else bound(g, FAIL)

    out = {}
    for n in SIZES:
        start = time.time()
        found = [(p, bound(g, variants.analyze(g, p))) for p in variants.smallest(g, n, EXTRACT_LIMIT)]
        out[f"size{n}"] = {m: chosen(min(found, key=lambda f: f[1][m])[0] if found else None) for m in BOUNDS}
        out[f"size{n}"]["seconds"] = built + time.time() - start
    start = time.time()
    out["greedy"] = {}
    for m in BOUNDS:
        F, _, _ = extract(g, EXTRACT_LIMIT, leq=variants.greedy(m))
        out["greedy"][m] = chosen(F[g.root][0][1] if F[g.root] else None)
    out["greedy"]["seconds"] = built + time.time() - start
    for m in BOUNDS:
        start = time.time()
        p = chosen(variants.single(g, m, EXTRACT_LIMIT))
        out[f"{m}-only"] = {"abs": p, "rel": p, "seconds": built + time.time() - start}
    g = build(core, 4, True, EGGLOG_LIMIT)
    nodes = [(c, n) for c, ns in g.nodes.items() for n in ns]
    out["proposed"] = sum(n.op == "Add" and sum(g.interval[x].mag for x in n.children) > 10 * g.interval[c].mig
                          for c, n in nodes)
    out["split"] = sum(n.op == "If" for c, n in nodes)
    return out


@step
def alternatives():
    """Benchmark (2): extraction by size, greedy readout, and single-metric analyses."""
    return each(variants_one, benchmark2())


def candidates(name):
    """The programs of a Benchmark (2) core that are compared, by who produced them."""
    o, r, v = ours()[name], rewrites()[name], alternatives()[name]
    out = {"ours": o["programs"].get(fielded(o["bounds"]))}
    out.update({tool: r[tool].get("program") for tool in r})
    out.update({f"size{n}": v[f"size{n}"][fielded(o["bounds"])].get("program") for n in SIZES})
    return {who: p for who, p in out.items() if p}


def measured_one(name, texts):
    core = load(name)
    return sample.measure(core, core.body, {"original": core.body, **{w: program(t) for w, t in texts.items()}})


@step
def measured():
    """Benchmark (2): the measured error of every compared program."""
    names = benchmark2()
    return each(measured_one, names, [candidates(n) for n in names])


@step
def bounds():
    """Sound bounds from FPTaylor, Gappa and Daisy: on every input, and on Benchmark (2)'s rewrites."""
    texts, b2 = {}, set(benchmark2())
    for n in cores("cores"):
        core = load(n)
        texts[n] = {"original": fpcore(core)}
        if n in b2:
            rewritten = {w: t for w, t in candidates(n).items() if w in ("ours", "herbie", "daisy")}
            texts[n].update({w: fpcore(core, program(t)) for w, t in rewritten.items()})
    every = [t for ts in texts.values() for t in ts.values()]
    with tempfile.TemporaryDirectory() as d:
        found = {"fptaylor": fptaylor.bound(every, d, TOOL_LIMIT, JOBS),
                 "gappa": gappa.bound(every, d, TOOL_LIMIT, JOBS),
                 "daisy": daisy.bound([ts["original"] for ts in texts.values()], d, TOOL_LIMIT, JOBS)}
    return {n: {tool: {w: got[t] for w, t in ts.items() if t in got} for tool, got in found.items()}
            for n, ts in texts.items()}


def speed_one(name, texts):
    core = load(name)
    programs = {"original": core.body, **{w: program(t) for w, t in texts.items()}}
    return speed.measure(core, programs, sample.points(core, 1000))


@step
def speeds():
    """Benchmark (2): run time of the input and of each rewrite, one core at a time."""
    return {n: safe(speed_one, n, {w: t for w, t in candidates(n).items() if w in ("ours", "herbie", "daisy")})
            for n in benchmark2()}


def branching_one(name, herbie_report):
    core = load(name)
    programs = {"original": core.body}
    for who, branch in (("ours-plain", False), ("ours", True)):
        g = build(core, 4, branch, EGGLOG_LIMIT)
        F, _, _ = extract(g, EXTRACT_LIMIT)
        I = g.interval[g.root]
        m = fielded({m: min(float(b(e, I)) for e, _ in F[g.root]) for m, b in BOUNDS.items()})
        programs[who] = best(F[g.root], I, BOUNDS[m])[1]
    if herbie_report.get("program"):
        programs["herbie"] = program(herbie_report["program"])
    out = {"expected": core.props.get(":cx-expected", "").strip('"')}
    measured = sample.measure(core, core.body, programs)
    for who, p in programs.items():
        out[who] = {"program": show(p), "measured": measured[who], "bound": safe(bound_input, core, p)}
    return out


@step
def branching():
    """Benchmark (3): our branches against Herbie's regimes, timed one core at a time."""
    names = cores("branching")
    texts = [fpcore(load(n)) for n in names]
    with tempfile.TemporaryDirectory() as d:
        found = herbie.rewrite(texts, d, TOOL_LIMIT, JOBS, branch=True)
    out = each(branching_one, names, [found[t] for t in texts])
    for name, r in out.items():
        whos = [w for w in r if w != "expected"]
        times = speed.measure(load(name), {w: program(r[w]["program"]) for w in whos}, sample.points(load(name), 1000))
        for w in whos:
            r[w]["ns"] = times[w]
    return out


if __name__ == "__main__":
    for f in (ours, originals, rewrites, alternatives, measured, bounds, speeds, branching):
        f()
