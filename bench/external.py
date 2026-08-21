"""Check costex's bounds against external sound analysers, on the same programs,
the same box and the same target format.

    uv run python bench/external.py --probe          # check the toolchain
    uv run python bench/external.py --limit 5
    uv run python bench/external.py --tools fptaylor # just one
    uv run python bench/external.py                  # everything, writes external.json

Every tool here reports a sound *upper* bound, so none of them is ground truth;
they bracket the true error from above.  Reads bench/results.json, writes
bench/external.json.  Runs are cached under bench/.cache, keyed by tool,
expression, box, target format, options and tool version.
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
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from functools import partial

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from costex.fpcore import parse_expr, parse_sexps, parse_fpcore, to_fpcore   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CORES = os.path.join(HERE, "cores")
CACHE = os.path.join(HERE, ".cache")

# overridable the same way costex.egg overrides EGGLOG
FPTAYLOR = os.path.expanduser(os.environ.get("FPTAYLOR", "~/FPTaylor"))
FPBENCH = os.path.expanduser(os.environ.get("FPBENCH", "~/fpbench"))
DAISY = os.path.expanduser(os.environ.get("DAISY", "~/daisy"))
# fptaylor is a bytecode build; its stubs live in the opam switch
STUBLIBS = os.path.expanduser(
    os.environ.get("FPTAYLOR_STUBLIBS", "~/.opam/fptaylor/lib/stublibs"))
# /usr/bin/java on macOS is a stub that reports no runtime
JAVA_HOME = os.environ.get(
    "DAISY_JAVA_HOME", "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home")

FT_OPTS = ("-v", "0", "-abs", "true", "-rel", "true")
# --FPTaylor is looser here than dataflow and crashes on some cores; affine
# ranges crash on sqrt and --subdiv shells out to z3, which is not installed
DAISY_OPTS = ("--analysis=dataflow", "--rangeMethod=interval", "--errorMethod=affine")
VARIANTS = ("seed", "best_abs", "best_rel")
METRICS = ("abs", "rel")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


# -- the expressions to analyse ----------------------------------------


def _has_const(expr: str) -> bool:
    """Does the expression mention PI or E?  FPBench's Scala backend refuses
    those, so Daisy cannot see such a core at all."""
    def walk(e):
        return e[0] == "const" or any(walk(a) for a in e[1:] if isinstance(a, tuple))
    return walk(parse_expr(parse_sexps(expr)[0]))


def units(results: list, limit: int = None, only: str = None) -> list:
    """The distinct (core, expression) pairs, with the variants sharing each.

    A core's abs- and rel-optimal programs are often the same expression, and
    often the seed itself, so this is well under the naive three-per-core.
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
                        "precision": core.precision, "consts": _has_const(expr),
                        "expr": expr, "variants": variants})
    return out


def _key(tool: str, unit: dict, ver: str, opts: tuple) -> str:
    payload = repr((tool, unit["expr"], sorted(unit["box"].items()),
                    unit["precision"], opts, ver))
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def _cached(tool: str, key: str):
    path = os.path.join(CACHE, tool, key + ".json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def _store(tool: str, key: str, report: dict) -> None:
    os.makedirs(os.path.join(CACHE, tool), exist_ok=True)
    with open(os.path.join(CACHE, tool, key + ".json"), "w") as f:
        json.dump(report, f)


def fpbench(batch: list, stem: str, lang: str, extra: list = ()) -> str:
    """FPCore -> a tool's input format, one racket call for the whole batch.

    Racket takes about a second to start, so exporting per expression would
    cost more than the analysis does.
    """
    src = "".join(to_fpcore(u["name"], u["args"], u["box"], u["expr"], u["precision"])
                  for u in batch)
    with open(stem + ".fpcore", "w") as f:
        f.write(src)
    out = f"{stem}.{lang}"
    run = subprocess.run(["racket", os.path.join(FPBENCH, "fpbench.rkt"), "export",
                          "--lang", lang, *extra, stem + ".fpcore", out],
                         cwd=FPBENCH, capture_output=True, text=True, errors="replace")
    if run.returncode != 0 or not os.path.exists(out):
        raise RuntimeError(f"fpbench {lang} export failed:\n"
                           f"{(run.stdout + run.stderr)[:600]}")
    return out


# -- FPTaylor -----------------------------------------------------------


def _ft_env() -> dict:
    return dict(os.environ, CAML_LD_LIBRARY_PATH=STUBLIBS)


def fptaylor_version() -> str:
    exe = os.path.join(FPTAYLOR, "fptaylor")
    if not os.path.exists(exe):
        raise RuntimeError(f"no fptaylor at {exe}; set FPTAYLOR to its directory")
    run = subprocess.run([exe, "--help"], cwd=FPTAYLOR, env=_ft_env(),
                         capture_output=True, text=True, errors="replace")
    m = re.search(r"FPTaylor, version (\S+)", run.stdout)
    if not m:
        raise RuntimeError("cannot read the FPTaylor version; it printed:\n"
                           + (run.stdout + run.stderr)[:600])
    return m.group(1)


_BLOCK_NAME = re.compile(r"\b([a-z]+\d{5})\s*=")


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
                        raise RuntimeError(f"no cx/j name in block:\n{text[:300]}")
                    out[m.group(1)] = text
                    cur = None
    return out


_ABS = re.compile(r"^Absolute error \(exact\): ([-\d.e+]+)", re.M)
_REL = re.compile(r"^Relative error \(exact\): ([-\d.e+]+)", re.M)
_RANGE = re.compile(r"^Bounds \(without rounding\): \[([-\d.e+]+), ([-\d.e+]+)\]", re.M)


def _why(text: str) -> str:
    """FPTaylor prints "**ERROR**:" and often puts the message on the next lines."""
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


def parse_fptaylor(text: str) -> dict:
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
    runs sharing that directory race on the object files and the link fails, so
    b_and_b gets a real copy (72K) and tmp/log real dirs.  The rest is read
    only, and is symlinked.
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


def run_fptaylor(item: tuple, *, opts: tuple, timeout: float, workdir: str) -> tuple:
    """Analyse one block in this process's own FPTaylor directory."""
    name, text = item
    root = _root(workdir)
    path = os.path.join(root, "tmp", f"{name}.txt")
    with open(path, "w") as f:
        f.write(text)
    t0 = time.time()
    try:
        run = subprocess.run([os.path.join(root, "fptaylor"), *opts, path], cwd=root,
                             env=_ft_env(), capture_output=True, text=True, errors="replace",
                             timeout=timeout)
    except subprocess.TimeoutExpired:
        return name, {"status": "timeout", "seconds": round(time.time() - t0, 2)}
    took = round(time.time() - t0, 2)
    if run.returncode != 0:
        return name, {"status": "error", "seconds": took,
                      "error": (run.stderr or run.stdout)[-300:].strip()}
    report = parse_fptaylor(run.stdout)
    if report["abs"] is None:
        # e.g. "**ERROR**: num_of_float: inf" on a box reaching 1e308: FPTaylor
        # exits 0 having bounded nothing.  That is its answer, not a failure.
        return name, {"status": "nobound", "seconds": took,
                      "error": _why(run.stderr + run.stdout)}
    return name, {"status": "ok", "seconds": took, **report}


def analyze_fptaylor(todo: list, *, opts: tuple, timeout: float, jobs: int,
                     workdir: str) -> dict:
    found = blocks(fpbench(todo, os.path.join(workdir, "ft"), "fptaylor"))
    missing = {u["name"] for u in todo} - set(found)
    if missing:
        raise RuntimeError(f"fpbench dropped {len(missing)} of {len(todo)} cores, "
                           f"e.g. {sorted(missing)[:3]}")
    work = partial(run_fptaylor, opts=opts, timeout=timeout, workdir=workdir)
    items = [(u["name"], found[u["name"]]) for u in todo]
    out = {}
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for i, (name, report) in enumerate(pool.map(work, items), 1):
            out[name] = report
            if i % 25 == 0:
                print(f"    fptaylor {i}/{len(items)}", flush=True)
    return out


# -- Daisy --------------------------------------------------------------


def _daisy_env() -> dict:
    return dict(os.environ, JAVA_HOME=JAVA_HOME,
                PATH=os.path.join(JAVA_HOME, "bin") + ":" + os.environ["PATH"])


def daisy_version() -> str:
    if not os.path.exists(os.path.join(DAISY, "daisy")):
        raise RuntimeError(f"no daisy launcher at {DAISY}; set DAISY to its directory")
    if not os.path.isdir(os.path.join(DAISY, "target", "scala-2.13", "classes")):
        raise RuntimeError(f"daisy is not built; run `sbt compile` in {DAISY}")
    run = subprocess.run(["git", "-C", DAISY, "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True, errors="replace")
    return run.stdout.strip() or "unknown"


_DEF = re.compile(r"\tdef (ex\d+)\b.*?\n\t\}\n", re.S)
_SCALA_HEAD = "import daisy.lang._\nimport Real._\n\nobject main {\n"


# FPBench's Scala backend renders e.g. 1000.0 as "1e3.0", which Scala will not
# parse.  An exponent-form literal can never be followed by ".0", so dropping it
# is unambiguous.  Affects 9 of 364 binary64 cores here.
_BAD_LIT = re.compile(r"([0-9][0-9.]*[eE][+-]?[0-9]+)\.0\b")


def split_scala(path: str) -> list:
    """The exported object, one function per file, in input order.

    Daisy reports results only in a final phase, so a single crashing function
    loses every result in the file.  One function per file keeps a crash local.
    """
    with open(path) as f:
        src = _BAD_LIT.sub(r"\1", f.read())
    return [_SCALA_HEAD + m.group(0) + "}\n" for m in _DEF.finditer(src)]


_EXC = re.compile(r"^([\w.$]+(?:Exception|Error))(?::\s*(.*))?$", re.M)
_D_ABS = re.compile(r"Absolute error:\s*([-\d.eE+]+)")
_D_REL = re.compile(r"Relative error:\s*([-\d.eE+]+)")
_D_RANGE = re.compile(r"Real range:\s*\[([-\d.eE+]+),\s*([-\d.eE+]+)\]")


def parse_daisy(text: str) -> dict:
    out = {"abs": None, "rel": None, "range": None}
    for key, rx in (("abs", _D_ABS), ("rel", _D_REL)):
        m = rx.search(text)
        if m:
            out[key] = float(m.group(1))
    m = _D_RANGE.search(text)
    if m:
        out["range"] = [float(m.group(1)), float(m.group(2))]
    return out


def run_daisy(item: tuple, *, opts: tuple, precision: str, timeout: float,
              workdir: str) -> tuple:
    name, text = item
    d = os.path.join(workdir, "daisy", name)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "a.scala")
    with open(path, "w") as f:
        f.write(text)
    t0 = time.time()
    try:
        run = subprocess.run(["./daisy", *opts, f"--precision={precision}", path],
                             cwd=DAISY, env=_daisy_env(), capture_output=True,
                             text=True, errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return name, {"status": "timeout", "seconds": round(time.time() - t0, 2)}
    took = round(time.time() - t0, 2)
    text_out = _ANSI.sub("", run.stdout + run.stderr)
    report = parse_daisy(text_out)
    if report["abs"] is None:
        # prefer daisy's own exception over the generic wrapper the runner adds
        hits = _EXC.findall(text_out)
        hit = next((h for h in hits if h[0].startswith("daisy")), hits[0] if hits else None)
        return name, {"status": "crash" if hit else "nobound", "seconds": took,
                      "error": (f"{hit[0]}: {hit[1]}".strip(": ") if hit
                                else "no bound in the output")[:160]}
    return name, {"status": "ok", "seconds": took, **report}


def analyze_daisy(todo: list, *, opts: tuple, timeout: float, jobs: int,
                  workdir: str) -> dict:
    """Export in one racket call per target format, then run one file each.

    The Scala backend drops :precision, so each format needs its own batch and
    its own --precision flag.
    """
    out = {}
    doable = []
    for u in todo:
        if u["consts"]:
            out[u["name"]] = {"status": "unsupported",
                              "error": "the Scala backend does not support PI or E"}
        else:
            doable.append(u)
    for prec, flag in (("binary64", "Float64"), ("binary32", "Float32")):
        batch = [u for u in doable if u["precision"] == prec]
        if not batch:
            continue
        texts = split_scala(fpbench(batch, os.path.join(workdir, f"daisy-{flag}"),
                                    "scala"))
        if len(texts) != len(batch):
            raise RuntimeError(f"fpbench emitted {len(texts)} scala functions for "
                               f"{len(batch)} cores")
        work = partial(run_daisy, opts=opts, precision=flag, timeout=timeout,
                       workdir=workdir)
        items = list(zip((u["name"] for u in batch), texts))
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            for i, (name, report) in enumerate(pool.map(work, items), 1):
                out[name] = report
                if i % 25 == 0:
                    print(f"    daisy {flag} {i}/{len(items)}", flush=True)
    return out


TOOLS = {
    "fptaylor": {"version": fptaylor_version, "opts": FT_OPTS, "run": analyze_fptaylor},
    "daisy": {"version": daisy_version, "opts": DAISY_OPTS, "run": analyze_daisy},
}


# -- driving ------------------------------------------------------------


def analyze(tool: str, us: list, *, timeout: float, jobs: int, workdir: str) -> tuple:
    """name -> report for every unit, running only what is not cached."""
    spec = TOOLS[tool]
    ver, opts = spec["version"](), spec["opts"]
    reports, todo = {}, []
    for u in us:
        hit = _cached(tool, _key(tool, u, ver, opts))
        if hit is None:
            todo.append(u)
        else:
            reports[u["name"]] = hit
    print(f"  {tool}: {len(us)} expressions, {len(us) - len(todo)} cached, "
          f"{len(todo)} to run")
    if todo:
        fresh = spec["run"](todo, opts=opts, timeout=timeout, jobs=jobs,
                            workdir=workdir)
        by_name = {u["name"]: u for u in todo}
        for name, report in fresh.items():
            reports[name] = report
            # ok/nobound/unsupported are facts about the expression; a timeout
            # is a fact about the limit and the machine, so it is not cached
            if report["status"] in ("ok", "nobound", "unsupported", "crash"):
                _store(tool, _key(tool, by_name[name], ver, opts), report)
    return reports, ver


def collect(results: list, us: list, per_tool: dict) -> list:
    """One record per core: costex's numbers beside each tool's, per variant."""
    per_core = {}
    for tool, reports in per_tool.items():
        for u in us:
            per_core.setdefault(u["file"], {}).setdefault(tool, {})
            for v in u["variants"]:
                per_core[u["file"]][tool][v] = reports[u["name"]]
    keep = ("name", "expr", "root_interval", "best_expr_abs", "best_expr_rel",
            "seed_abs", "best_abs", "seed_rel", "best_rel")
    return [{"file": r["file"], "costex": {k: r.get(k) for k in keep},
             "tools": per_core[r["file"]]}
            for r in results if r["file"] in per_core]


def _status(records: list) -> None:
    """Run health: how many analyses landed, and why any of them did not."""
    tools = sorted({t for r in records for t in r["tools"]})
    for tool in tools:
        reps = [rep for r in records for rep in r["tools"].get(tool, {}).values()]
        st = Counter(rep["status"] for rep in reps)
        print(f"  {tool:<9} {len(reps)} analyses: "
              + ", ".join(f"{v} {k}" for k, v in st.most_common()))
        why = Counter(rep.get("error", "")[:48] for rep in reps
                      if rep["status"] in ("nobound", "crash", "unsupported"))
        for reason, n in why.most_common(6):
            print(f"      {n:4} x {reason}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="external")
    ap.add_argument("--results", default=os.path.join(HERE, "results.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "external.json"))
    ap.add_argument("--tools", default=",".join(TOOLS),
                    help="comma separated (default %(default)s)")
    ap.add_argument("--probe", action="store_true", help="check the toolchain and exit")
    ap.add_argument("--limit", type=int, help="only the first N cores")
    ap.add_argument("--only", metavar="SUBSTR", help="only cores whose filename contains this")
    ap.add_argument("--timeout", type=float, default=300.0,
                    help="seconds per expression per tool (default %(default)s)")
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--keep-work", action="store_true",
                    help="keep the scratch tree for debugging")
    args = ap.parse_args(argv)

    chosen = [t.strip() for t in args.tools.split(",") if t.strip()]
    unknown = [t for t in chosen if t not in TOOLS]
    if unknown:
        ap.error(f"unknown tool(s): {', '.join(unknown)}; have {', '.join(TOOLS)}")

    if args.probe:
        print(f"FPBENCH   {FPBENCH}")
        for path, what in ((os.path.join(FPBENCH, "fpbench.rkt"), "fpbench.rkt"),):
            print(f"  {'found  ' if os.path.exists(path) else 'MISSING'} {what}: {path}")
        for tool in chosen:
            print(f"\n{tool}")
            try:
                print(f"  version   {TOOLS[tool]['version']()}")
                print(f"  options   {' '.join(TOOLS[tool]['opts'])}")
            except RuntimeError as e:
                print(f"  UNAVAILABLE: {e}")
        print(f"\ncache     {CACHE}")
        return 0

    with open(args.results) as f:
        results = json.load(f)["results"]
    us = units(results, args.limit, args.only)
    workdir = tempfile.mkdtemp(prefix="costex-ext-")
    t0 = time.time()
    per_tool, versions = {}, {}
    for tool in chosen:
        per_tool[tool], versions[tool] = analyze(tool, us, timeout=args.timeout,
                                                 jobs=args.jobs, workdir=workdir)
    records = collect(results, us, per_tool)
    elapsed = time.time() - t0

    with open(args.out, "w") as f:
        json.dump({"versions": versions,
                   "options": {t: list(TOOLS[t]["opts"]) for t in chosen},
                   "elapsed_s": round(elapsed, 1), "results": records}, f, indent=1)
    print()
    _status(records)
    if args.keep_work:
        print(f"\n  {elapsed:.1f}s wall, {args.jobs} jobs; work kept in {workdir}")
    else:
        shutil.rmtree(workdir, ignore_errors=True)
        print(f"\n  {elapsed:.1f}s wall, {args.jobs} jobs")
    print(f"  -> {os.path.relpath(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
