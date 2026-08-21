"""Head to head: costex's rewrite against Daisy's, judged by a neutral analyser.

    uv run python bench/rewrite.py --limit 20
    uv run python bench/rewrite.py            # writes bench/rewrite.json

Daisy improves accuracy with a genetic search over algebraic identities, so it
is a direct competitor to equality saturation.  Scoring costex's rewrite with
costex and Daisy's rewrite with Daisy would compare two *analyses* as much as
two rewriters, so both rewritten programs -- and the seed -- are scored with
FPTaylor, over the same box and the same target format.

Daisy's genetic search is seeded (--rewrite-seed) so runs are reproducible.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from functools import partial

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import external as X                                             # noqa: E402
from costex.fpcore import parse_fpcore, to_sexp                  # noqa: E402

# the same analysis options as bench/external.py, plus the rewriting phase
REWRITE_OPTS = ("--rewrite", "--analysis=dataflow", "--rangeMethod=interval",
                "--errorMethod=affine", "--codegen", "--lang=FPCore")
BEFORE = re.compile(r"error before:\s*([-\d.eE+]+)")
AFTER = re.compile(r"error after:\s*([-\d.eE+]+)")


def _rename_vars(e, mapping: dict):
    """FPBench's Scala backend escapes characters illegal in identifiers -- a
    core with an argument `x.re` comes back from Daisy as `x_46re` -- so the
    names are mapped back by position before we hand the program on."""
    if e[0] == "var":
        return ("var", mapping.get(e[1], e[1]))
    return (e[0],) + tuple(_rename_vars(a, mapping) if isinstance(a, tuple) else a
                           for a in e[1:])


def _rename_object(text: str, name: str) -> str:
    """Daisy names its generated file after the enclosing object, so each core
    needs its own or parallel runs overwrite each other's output."""
    return text.replace("object main {", f"object {name} {{", 1)


def daisy_rewrite(item: tuple, *, seed: int, precision: str, timeout: float,
                  workdir: str) -> tuple:
    """Run Daisy's rewriter and read back the program it produced."""
    name, text, args = item
    d = os.path.join(workdir, "rw", name)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "a.scala")
    with open(path, "w") as f:
        f.write(_rename_object(text, name))
    out_fpcore = os.path.join(X.DAISY, "output", f"{name}.fpcore")
    if os.path.exists(out_fpcore):
        os.remove(out_fpcore)
    t0 = time.time()
    try:
        run = subprocess.run(["./daisy", *REWRITE_OPTS, f"--rewrite-seed={seed}",
                              f"--precision={precision}", path],
                             cwd=X.DAISY, env=X._daisy_env(), capture_output=True,
                             text=True, errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return name, {"status": "timeout", "seconds": round(time.time() - t0, 2)}
    took = round(time.time() - t0, 2)
    text_out = X._ANSI.sub("", run.stdout + run.stderr)
    before, after = BEFORE.search(text_out), AFTER.search(text_out)
    if not os.path.exists(out_fpcore):
        hits = X._EXC.findall(text_out)
        hit = next((h for h in hits if h[0].startswith("daisy")),
                   hits[0] if hits else None)
        return name, {"status": "crash" if hit else "nooutput", "seconds": took,
                      "error": (f"{hit[0]}: {hit[1]}".strip(": ") if hit
                                else "no fpcore emitted")[:160]}
    try:
        core = parse_fpcore(open(out_fpcore).read())
    except SyntaxError as e:
        return name, {"status": "unparsed", "seconds": took, "error": str(e)[:160]}
    if len(core.args) != len(args):
        return name, {"status": "argcount", "seconds": took,
                      "error": f"daisy returned {core.args} for {args}"}
    expr = to_sexp(_rename_vars(core.body, dict(zip(core.args, args))))
    return name, {"status": "ok", "seconds": took, "expr": expr,
                  "daisy_before": float(before.group(1)) if before else None,
                  "daisy_after": float(after.group(1)) if after else None}


def run_daisy_rewriter(us: list, *, seed: int, timeout: float, jobs: int,
                       workdir: str) -> dict:
    """One racket export per target format, then one Daisy run per core."""
    out = {}
    doable = [u for u in us if not u["consts"]]
    for u in us:
        if u["consts"]:
            out[u["name"]] = {"status": "unsupported",
                              "error": "the Scala backend does not support PI or E"}
    for prec, flag in (("binary64", "Float64"), ("binary32", "Float32")):
        batch = [u for u in doable if u["precision"] == prec]
        if not batch:
            continue
        texts = X.split_scala(X.fpbench(batch, os.path.join(workdir, f"rw-{flag}"),
                                        "scala"))
        if len(texts) != len(batch):
            raise RuntimeError(f"fpbench emitted {len(texts)} functions for "
                               f"{len(batch)} cores")
        work = partial(daisy_rewrite, seed=seed, precision=flag, timeout=timeout,
                       workdir=workdir)
        items = [(u["name"], t, u["args"]) for u, t in zip(batch, texts)]
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            for i, (name, rep) in enumerate(pool.map(work, items), 1):
                out[name] = rep
                if i % 25 == 0:
                    print(f"    daisy rewrite {flag} {i}/{len(items)}", flush=True)
    return out


def judge(cands: list, *, timeout: float, jobs: int, workdir: str) -> dict:
    """Score every candidate program with FPTaylor, in one batch."""
    ver = X.fptaylor_version()
    todo, reports = [], {}
    for u in cands:
        hit = X._cached("fptaylor", X._key("fptaylor", u, ver, X.FT_OPTS))
        if hit is None:
            todo.append(u)
        else:
            reports[u["name"]] = hit
    print(f"  judging {len(cands)} programs with FPTaylor, "
          f"{len(cands) - len(todo)} cached, {len(todo)} to run")
    if todo:
        fresh = X.analyze_fptaylor(todo, opts=X.FT_OPTS, timeout=timeout, jobs=jobs,
                                   workdir=workdir)
        by_name = {u["name"]: u for u in todo}
        for name, rep in fresh.items():
            reports[name] = rep
            if rep["status"] in ("ok", "nobound"):
                X._store("fptaylor", X._key("fptaylor", by_name[name], ver, X.FT_OPTS),
                         rep)
    return reports


def _abs(rep):
    return rep["abs"] if rep and rep.get("status") == "ok" and rep.get("abs") else None


def summarise(out: list) -> None:
    """Both rewriters scored by FPTaylor, against the same seed."""
    rows = []
    for e in out:
        j = e["judge"]
        seed = _abs(j.get("seed"))
        cx = [v for v in (_abs(j.get("costex_abs")), _abs(j.get("costex_rel"))) if v]
        dy = _abs(j.get("daisy"))
        if seed and cx and dy:
            rows.append((e["file"], seed, min(cx), dy))
    if not rows:
        print("  no core has all three scored")
        return
    cxw = sum(1 for _, _, c, d in rows if c < d * 0.999)
    dyw = sum(1 for _, _, c, d in rows if d < c * 0.999)
    cx_imp = sum(1 for _, s, c, _ in rows if c < s * 0.999)
    dy_imp = sum(1 for _, s, _, d in rows if d < s * 0.999)
    dy_same = sum(1 for e in out if e.get("daisy_expr") == e["seed_expr"])
    print(f"\n  {len(rows)} cores with all three scored by FPTaylor")
    print(f"    costex's rewrite beats Daisy's on {cxw}, Daisy's beats costex's on {dyw},"
          f" tie {len(rows) - cxw - dyw}")
    print(f"    improves on the seed:  costex {cx_imp},  daisy {dy_imp}")
    print(f"    Daisy returned the seed unchanged on {dy_same} of {len(out)} cores")
    gain = sorted(((s / c, s / d, f) for f, s, c, d in rows), reverse=True)
    print("    largest costex gains (costex x, daisy x):")
    for c, d, f in gain[:5]:
        print(f"      {f[:46]:<46} costex {c:.4g}x   daisy {d:.4g}x")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rewrite")
    ap.add_argument("--results", default=os.path.join(HERE, "results.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "rewrite.json"))
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only", metavar="SUBSTR")
    ap.add_argument("--rewrite-seed", type=int, default=1490,
                    help="Daisy's genetic seed; 0 means use the clock (default %(default)s)")
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--keep-work", action="store_true")
    args = ap.parse_args(argv)

    with open(args.results) as f:
        results = json.load(f)["results"]
    if args.only:
        results = [r for r in results if args.only in r["file"]]
    if args.limit:
        results = results[:args.limit]
    results = [r for r in results if r["status"] == "ok"]

    # one unit per core, carrying the seed program: what Daisy's rewriter sees
    seeds = []
    for r in results:
        core = parse_fpcore(open(os.path.join(X.CORES, r["file"])).read())
        seeds.append({"name": f"cx{len(seeds):05d}", "file": r["file"],
                      "args": core.args, "box": core.box,
                      "precision": core.precision,
                      "consts": X._has_const(r["expr"]), "expr": r["expr"]})

    workdir = tempfile.mkdtemp(prefix="costex-rw-")
    t0 = time.time()
    rewrites = run_daisy_rewriter(seeds, seed=args.rewrite_seed, timeout=args.timeout,
                                  jobs=args.jobs, workdir=workdir)

    # score seed, costex's rewrite and Daisy's rewrite with the same analyser
    by_file = {r["file"]: r for r in results}
    cands, index = [], {}
    for u in seeds:
        r = by_file[u["file"]]
        # costex emits a whole frontier; results.json keeps the per-metric
        # optima, so both are offered and its best is taken.  Daisy emits one.
        progs = {"seed": r["expr"], "costex_abs": r.get("best_expr_abs"),
                 "costex_rel": r.get("best_expr_rel")}
        rw = rewrites.get(u["name"], {})
        if rw.get("status") == "ok":
            progs["daisy"] = rw["expr"]
        seen = {}
        for who, expr in progs.items():
            if not expr:
                continue
            if expr not in seen:
                seen[expr] = f"j{len(cands):05d}"
                cands.append(dict(u, name=seen[expr], expr=expr,
                                  consts=X._has_const(expr)))
            index[(u["file"], who)] = seen[expr]
    scores = judge(cands, timeout=args.timeout, jobs=args.jobs, workdir=workdir)

    out = []
    for u in seeds:
        r = by_file[u["file"]]
        rw = rewrites.get(u["name"], {})
        entry = {"file": u["file"], "name": r.get("name"), "seed_expr": r["expr"],
                 "costex_abs_expr": r.get("best_expr_abs"),
                 "costex_rel_expr": r.get("best_expr_rel"),
                 "daisy_expr": rw.get("expr"), "daisy_status": rw.get("status"),
                 "daisy_error": rw.get("error"),
                 "daisy_before": rw.get("daisy_before"),
                 "daisy_after": rw.get("daisy_after"), "judge": {}}
        for who in ("seed", "costex_abs", "costex_rel", "daisy"):
            nm = index.get((u["file"], who))
            if nm:
                entry["judge"][who] = scores.get(nm)
        out.append(entry)
    elapsed = time.time() - t0

    with open(args.out, "w") as f:
        json.dump({"daisy_version": X.daisy_version(),
                   "fptaylor_version": X.fptaylor_version(),
                   "rewrite_seed": args.rewrite_seed,
                   "daisy_options": list(REWRITE_OPTS),
                   "elapsed_s": round(elapsed, 1), "results": out}, f, indent=1)

    st = Counter(e["daisy_status"] for e in out)
    print(f"\n  daisy rewriter over {len(out)} cores: "
          + ", ".join(f"{v} {k}" for k, v in st.most_common()))
    summarise(out)
    if args.keep_work:
        print(f"  {elapsed:.1f}s wall; work kept in {workdir}")
    else:
        shutil.rmtree(workdir, ignore_errors=True)
        print(f"  {elapsed:.1f}s wall")
    print(f"  -> {os.path.relpath(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
