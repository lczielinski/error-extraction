"""Run the tool over the benchmark corpus in bench/cores.

    uv run python bench/run.py                     # everything, 4 iterations
    uv run python bench/run.py --iters 3 --limit 50
    uv run python bench/run.py --summarize          # re-read results.json, run nothing

Writes bench/results.json and prints a summary.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from functools import partial

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from costex import analysis as A                              # noqa: E402
from costex import egg, extract, interval                     # noqa: E402
from costex.fpcore import parse_fpcore, to_sexp               # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CORES = os.path.join(HERE, "cores")
METRICS = ("d", "rel", "abs")


def _f(x):
    x = float(x)
    return None if math.isinf(x) else x


def run_one(path, *, iters, timeout, max_steps, prec, extract_timeout) -> dict:
    name = os.path.basename(path)
    out = {"file": name}
    t0 = time.time()
    try:
        interval.set_precision(prec)
        core = parse_fpcore(open(path).read())
        A.set_target(53 if core.precision == "binary64" else 24)
        out.update(name=core.name, vars=len(core.args),
                   box_source=str(core.props.get(":cx-box", "pre")),
                   source=str(core.props.get(":cx-source", "")),
                   expr=to_sexp(core.body), precision=core.precision)
        g = egg.build(core.body, core.box, iters=iters, timeout=timeout)
        t1 = time.time()
        front = extract.extract(g, max_steps=max_steps, time_limit=extract_timeout)
        Ic = g.interval[g.root]
        seed = extract.analyze_program(g, core.body)

        out.update(status="ok",
                   classes=len(g.nodes), nodes=sum(map(len, g.nodes.values())),
                   egglog_s=round(t1 - t0, 3), extract_s=round(time.time() - t1, 3),
                   steps=front.steps, truncated=front.truncated,
                   frontier=len(front.entries.get(g.root, [])),
                   root_interval=[_f(Ic.lo), _f(Ic.hi)])
        for m in METRICS:
            out[f"seed_{m}"] = None if seed is A.BOTTOM else _f(A.METRICS[m](seed, Ic))
            best = front.best(g.root, Ic, m)
            out[f"best_{m}"] = _f(best[0]) if best else None
            out[f"best_expr_{m}"] = to_sexp(best[2]) if best else None
    except subprocess.TimeoutExpired:
        out.update(status="timeout", egglog_s=round(time.time() - t0, 3))
    except egg.BadBox as ex:
        out.update(status="badbox", error=str(ex)[:200])
    except Exception as ex:                    # noqa: BLE001
        out.update(status="error", error=f"{type(ex).__name__}: {ex}"[:200])
    return out


def _metric_lines(group: list, m: str) -> list:
    seed, best = f"seed_{m}", f"best_{m}"
    live = [r for r in group if r[best] is not None]
    improved = [r for r in live if r[seed] is None or r[best] < r[seed]]
    equal = [r for r in live if r[seed] is not None and r[best] == r[seed]]
    ratios = sorted(r[seed] / r[best] for r in improved if r[seed] and r[best])
    out = [f"    mu_{m:<3} bounded for {len(live):3}, improved {len(improved):3},"
           f" unchanged {len(equal):3}"]
    if ratios:
        out.append(f"           median {ratios[len(ratios) // 2]:.3g}x, "
                   f"90th pct {ratios[int(0.9 * (len(ratios) - 1))]:.3g}x, "
                   f"max {ratios[-1]:.3g}x")
    return out


def summarize(results: list) -> None:
    st = Counter(r["status"] for r in results)
    print(f"\n{len(results)} cores: " + ", ".join(f"{v} {k}" for k, v in st.most_common()))

    ok = [r for r in results if r["status"] == "ok"]
    if not ok:
        return
    trunc = sum(1 for r in ok if r.get("truncated"))
    print()
    for m in METRICS:
        print("\n".join(_metric_lines(ok, m)))
    print(f"\n  extractions stopped early (not provably optimal): {trunc}")

    slow = sorted(ok, key=lambda r: -(r["egglog_s"] + r["extract_s"]))[:3]
    print("\n  slowest: " + ", ".join(f"{r['file'][:34]} {r['egglog_s'] + r['extract_s']:.1f}s"
                                      for r in slow))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=egg.DEFAULT_ITERS)
    ap.add_argument("--timeout", type=float, default=60.0, help="egglog seconds per core")
    ap.add_argument("--max-steps", type=int, default=extract.DEFAULT_MAX_STEPS)
    ap.add_argument("--extract-timeout", type=float, default=30.0,
                    help="extraction seconds per core; a step cap alone does not bound it")
    ap.add_argument("--prec", type=int, default=interval.DEFAULT_PRECISION)
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", default=os.path.join(HERE, "results.json"))
    ap.add_argument("--summarize", action="store_true",
                    help="re-summarize the existing --out file without running anything")
    args = ap.parse_args(argv)

    if args.summarize:
        summarize(json.load(open(args.out))["results"])
        return 0

    files = sorted(os.path.join(CORES, f) for f in os.listdir(CORES) if f.endswith(".fpcore"))
    if args.limit:
        files = files[:args.limit]
    work = partial(run_one, iters=args.iters, timeout=args.timeout, max_steps=args.max_steps,
                   prec=args.prec, extract_timeout=args.extract_timeout)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        results = []
        for i, r in enumerate(pool.map(work, files), 1):
            results.append(r)
            if i % 25 == 0:
                print(f"  {i}/{len(files)}", flush=True)
    elapsed = time.time() - t0

    with open(args.out, "w") as fh:
        json.dump({"iters": args.iters, "elapsed_s": round(elapsed, 1),
                   "results": results}, fh, indent=1)
    summarize(results)
    print(f"\n  {elapsed:.1f}s wall, {args.jobs} jobs -> {os.path.relpath(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
