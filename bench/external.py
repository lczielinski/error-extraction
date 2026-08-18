"""Check costex's bounds against FPTaylor, on the same programs and the same box.

    uv run python bench/external.py --probe        # check the toolchain, print the command
    uv run python bench/external.py --limit 5      # a few cores
    uv run python bench/external.py                # everything, writes external.json

Reads bench/results.json, writes bench/external.json.  FPTaylor runs are cached
under bench/.cache, keyed by expression, box, options and tool version.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from functools import partial

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from costex.fpcore import parse_fpcore, to_fpcore              # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CORES = os.path.join(HERE, "cores")
CACHE = os.path.join(HERE, ".cache", "fptaylor")

FPTAYLOR = os.path.expanduser(os.environ.get("FPTAYLOR", "~/FPTaylor"))
FPBENCH = os.path.expanduser(os.environ.get("FPBENCH", "~/fpbench"))
STUBLIBS = os.path.expanduser(
    os.environ.get("FPTAYLOR_STUBLIBS", "~/.opam/fptaylor/lib/stublibs"))

OPTS = ("-v", "0", "-abs", "true", "-rel", "true")
VARIANTS = ("seed", "best_abs", "best_rel")
METRICS = ("abs", "rel")


def _env() -> dict:
    env = dict(os.environ)
    env["CAML_LD_LIBRARY_PATH"] = STUBLIBS
    return env


def version() -> str:
    exe = os.path.join(FPTAYLOR, "fptaylor")
    if not os.path.exists(exe):
        raise RuntimeError(f"no fptaylor at {exe}; set FPTAYLOR to its directory")
    run = subprocess.run([exe, "--help"], cwd=FPTAYLOR, env=_env(),
                         capture_output=True, text=True)
    m = re.search(r"FPTaylor, version (\S+)", run.stdout)
    if not m:
        raise RuntimeError("cannot read the FPTaylor version; it printed:\n"
                           + (run.stdout + run.stderr)[:600])
    return m.group(1)


# -- the expressions to analyse ----------------------------------------


def units(results: list, limit: int = None, only: str = None) -> list:
    """The distinct (core, expression) pairs, with the variants sharing each.

    A core's abs-, rel- and d-optimal programs are often the same expression,
    and often the seed itself, so this is a little under half of the naive
    four-per-core.
    """
    out = []
    if only:
        results = [r for r in results if only in r["file"]]
    for r in (results[:limit] if limit else results):
        if r["status"] != "ok":
            continue
        core = parse_fpcore(open(os.path.join(CORES, r["file"])).read())
        shared = {}
        for v in VARIANTS:
            e = r["expr"] if v == "seed" else r.get(f"best_expr_{v[len('best_'):]}")
            if e:
                shared.setdefault(e, []).append(v)
        for expr, variants in shared.items():
            out.append({"name": f"cx{len(out):05d}", "file": r["file"],
                        "args": core.args, "box": core.box,
                        "precision": core.precision,
                        "expr": expr, "variants": variants})
    return out


def _key(unit: dict, ver: str, opts: tuple) -> str:
    payload = repr((unit["expr"], sorted(unit["box"].items()),
                    unit["precision"], opts, ver))
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def _cached(key: str):
    path = os.path.join(CACHE, key + ".json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def _store(key: str, report: dict) -> None:
    os.makedirs(CACHE, exist_ok=True)
    with open(os.path.join(CACHE, key + ".json"), "w") as f:
        json.dump(report, f)


# -- running ------------------------------------------------------------


def export(batch: list, stem: str) -> str:
    """FPCore -> FPTaylor input for the whole batch, in one racket call."""
    src = "".join(to_fpcore(u["name"], u["args"], u["box"], u["expr"], u["precision"]) for u in batch)
    with open(stem + ".fpcore", "w") as f:
        f.write(src)
    run = subprocess.run(["racket", os.path.join(FPBENCH, "fpbench.rkt"), "export",
                          "--lang", "fptaylor", stem + ".fpcore", stem + ".txt"],
                         cwd=FPBENCH, capture_output=True, text=True)
    if run.returncode != 0:
        raise RuntimeError(f"fpbench export failed:\n{(run.stderr or run.stdout)[:2000]}")
    return stem + ".txt"


_BLOCK_NAME = re.compile(r"\b(cx\d{5})\s*=")


def blocks(path: str) -> dict:
    """name -> the { ... } block that defines it."""
    out, cur = {}, None
    with open(path) as f:
        for line in f:
            if line.strip() == "{":
                cur = [line]
            elif cur is not None:
                cur.append(line)
                if line.strip() == "}":
                    text = "".join(cur)
                    m = _BLOCK_NAME.search(text)
                    if m is None:
                        raise RuntimeError(f"no cxNNNNN name in block:\n{text[:300]}")
                    out[m.group(1)] = text
                    cur = None
    return out


_ABS = re.compile(r"^Absolute error \(exact\): ([-\d.e+]+)", re.M)
_REL = re.compile(r"^Relative error \(exact\): ([-\d.e+]+)", re.M)
_RANGE = re.compile(r"^Bounds \(without rounding\): \[([-\d.e+]+), ([-\d.e+]+)\]", re.M)


def _why(text: str) -> str:
    i = text.find("**ERROR**:")
    if i < 0:
        return "no bound in the output"
    out = []
    for line in text[i + len("**ERROR**:"):].splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("---") or line.startswith("FPTaylor,"):
            break
        out.append(line)
        if len(out) == 2:          # the complaint, then the offending subterm
            break
    return " ".join(out)[:160] or "no bound in the output"


def parse_report(text: str) -> dict:
    out = {"abs": None, "rel": None, "range": None}
    for key, rx in (("abs", _ABS), ("rel", _REL)):
        m = rx.search(text)
        if m:
            out[key] = float(m.group(1))
    m = _RANGE.search(text)
    if m:
        out["range"] = [float(m.group(1)), float(m.group(2))]
    return out


_ROOTS = {}


def _root(workdir: str) -> str:
    """A private FPTaylor directory for this process.

    For harder problems FPTaylor optimises by compiling a helper binary, and
    b_and_b/compile.sh compiles opt_func.ml and opt0.ml *in place*.  Concurrent
    runs sharing that directory therefore race on the object files and the link
    fails, so b_and_b gets a real copy (72K) and tmp/log real dirs.  Everything
    else is only read, and is symlinked.
    """
    root = _ROOTS.get(os.getpid())
    if root is None:
        root = os.path.join(workdir, f"root{os.getpid()}")
        if not os.path.isdir(root):
            os.makedirs(root)
            for name in os.listdir(FPTAYLOR):
                if name not in ("b_and_b", "tmp", "log"):
                    os.symlink(os.path.join(FPTAYLOR, name), os.path.join(root, name))
            shutil.copytree(os.path.join(FPTAYLOR, "b_and_b"),
                            os.path.join(root, "b_and_b"))
            os.mkdir(os.path.join(root, "tmp"))
            os.mkdir(os.path.join(root, "log"))
        _ROOTS[os.getpid()] = root
    return root


def run_block(item: tuple, *, opts: tuple, timeout: float, workdir: str) -> tuple:
    """Analyse one block in this process's own FPTaylor directory."""
    name, text = item
    root = _root(workdir)
    path = os.path.join(root, "tmp", f"{name}.txt")
    with open(path, "w") as f:
        f.write(text)
    cmd = [os.path.join(root, "fptaylor"), *opts, path]
    t0 = time.time()
    try:
        run = subprocess.run(cmd, cwd=root, env=_env(),
                             capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return name, {"status": "timeout", "seconds": round(time.time() - t0, 2)}
    took = round(time.time() - t0, 2)
    if run.returncode != 0:
        return name, {"status": "error", "seconds": took,
                      "error": (run.stderr or run.stdout)[-300:].strip()}
    report = parse_report(run.stdout)
    if report["abs"] is None:
        # e.g. "**ERROR**: num_of_float: inf" on a box that reaches 1e308:
        # FPTaylor exits 0 having bounded nothing.  That is its answer, not ours.
        return name, {"status": "nobound", "seconds": took,
                      "error": _why(run.stderr + run.stdout)}
    return name, {"status": "ok", "seconds": took, **report}


def analyze(us: list, *, opts: tuple, timeout: float, jobs: int, workdir: str) -> tuple:
    """name -> report for every unit, running only what is not cached."""
    ver = version()
    by_name = {u["name"]: u for u in us}
    reports, todo = {}, []
    for u in us:
        hit = _cached(_key(u, ver, opts))
        if hit is None:
            todo.append(u)
        else:
            reports[u["name"]] = hit
    print(f"  {len(us)} expressions, {len(us) - len(todo)} cached, {len(todo)} to run")
    if todo:
        found = blocks(export(todo, os.path.join(workdir, "batch")))
        missing = {u["name"] for u in todo} - set(found)
        if missing:
            raise RuntimeError(f"fpbench dropped {len(missing)} of {len(todo)} cores, "
                               f"e.g. {sorted(missing)[:3]}")
        work = partial(run_block, opts=opts, timeout=timeout, workdir=workdir)
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            items = [(u["name"], found[u["name"]]) for u in todo]
            for i, (name, report) in enumerate(pool.map(work, items), 1):
                reports[name] = report
                # ok and nobound are facts about the expression; a timeout is a
                # fact about the limit and the machine, so it is not cached
                if report["status"] in ("ok", "nobound"):
                    _store(_key(by_name[name], ver, opts), report)
                if i % 25 == 0:
                    print(f"  {i}/{len(todo)}", flush=True)
    return reports, ver


def collect(results: list, us: list, reports: dict) -> list:
    """One record per core: costex's numbers beside FPTaylor's, per variant."""
    per_core = {}
    for u in us:
        for v in u["variants"]:
            per_core.setdefault(u["file"], {})[v] = reports[u["name"]]
    keep = ("name", "expr", "root_interval",
            "best_expr_abs", "best_expr_rel",
            "seed_abs", "best_abs", "seed_rel", "best_rel")
    return [{"file": r["file"], "costex": {k: r.get(k) for k in keep},
             "ft": per_core[r["file"]]}
            for r in results if r["file"] in per_core]


# -- reporting ----------------------------------------------------------


def _status(records: list) -> None:
    """Run health: how many analyses landed, and why any of them did not."""
    st = Counter(rep["status"] for r in records for rep in r["ft"].values())
    print(f"\n{len(records)} cores, {sum(st.values())} (core, variant) analyses: "
          + ", ".join(f"{v} {k}" for k, v in st.most_common()))
    why = Counter(rep.get("error", "")[:48] for r in records
                  for rep in r["ft"].values() if rep["status"] == "nobound")
    for reason, n in why.most_common():
        print(f"    FPTaylor bounded nothing on {n:3}: {reason}")
    for r in records:
        for v, rep in r["ft"].items():
            if rep["status"] == "error":
                print(f"    error {r['file'][:44]} [{v}]: {rep.get('error', '')[:80]}")
                break



def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="external")
    ap.add_argument("--results", default=os.path.join(HERE, "results.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "external.json"))
    ap.add_argument("--probe", action="store_true", help="check the toolchain and exit")
    ap.add_argument("--limit", type=int, help="only the first N cores")
    ap.add_argument("--only", metavar="SUBSTR", help="only cores whose filename contains this")
    ap.add_argument("--timeout", type=float, default=300.0,
                    help="FPTaylor seconds per expression (default %(default)s)")
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--keep-work", action="store_true",
                    help="keep the scratch tree (a few tens of MB) for debugging")
    ap.add_argument("--fail-on-exception", choices=("true", "false"), default="true",
                    help="FPTaylor's default is true: it refuses to bound an expression "
                         "whose definedness it cannot verify.  costex instead *assumes* "
                         "definedness on the box, so false is the closer comparison "
                         "(default %(default)s)")
    args = ap.parse_args(argv)
    opts = OPTS + ("--fail-on-exception", args.fail_on_exception)

    if args.probe:
        print(f"FPTAYLOR  {FPTAYLOR}")
        print(f"FPBENCH   {FPBENCH}")
        print(f"stublibs  {STUBLIBS}")
        for path, what in ((os.path.join(FPTAYLOR, "fptaylor"), "fptaylor"),
                           (os.path.join(FPBENCH, "fpbench.rkt"), "fpbench.rkt"),
                           (STUBLIBS, "stublibs dir")):
            print(f"  {'found  ' if os.path.exists(path) else 'MISSING'} {what}: {path}")
        print(f"version   {version()}")
        print(f"command   {' '.join(('fptaylor',) + OPTS)} IN.txt")
        print(f"          cwd=<a per-process copy of {FPTAYLOR}>")
        print(f"          CAML_LD_LIBRARY_PATH={STUBLIBS}")
        print(f"cache     {CACHE}")
        return 0

    with open(args.results) as f:
        results = json.load(f)["results"]
    us = units(results, args.limit, args.only)
    workdir = tempfile.mkdtemp(prefix="costex-ft-")
    t0 = time.time()
    reports, ver = analyze(us, opts=opts, timeout=args.timeout, jobs=args.jobs,
                           workdir=workdir)
    records = collect(results, us, reports)
    elapsed = time.time() - t0

    with open(args.out, "w") as f:
        json.dump({"fptaylor_version": ver, "options": list(opts),
                   "elapsed_s": round(elapsed, 1), "results": records}, f, indent=1)
    print(f"\nFPTaylor {ver}, options: {' '.join(opts)}")
    _status(records)
    # only reached when nothing raised, so a failed run leaves its scratch behind
    if args.keep_work:
        print(f"\n  {elapsed:.1f}s wall, {args.jobs} jobs; work kept in {workdir}")
    else:
        shutil.rmtree(workdir, ignore_errors=True)
        print(f"\n  {elapsed:.1f}s wall, {args.jobs} jobs")
    print(f"  -> {os.path.relpath(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
