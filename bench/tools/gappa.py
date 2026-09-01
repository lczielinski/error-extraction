"""Gappa: a sound analyser over intervals, with a proof search on top.

    GAPPA=~/gappa             its checkout, or the binary itself

Built from the release tarball with `./configure && ./remake`, which leaves a
standalone `src/gappa`; there is nothing to install.

Gappa is meant to be driven by hand: the user states a goal, then supplies
hints -- rewritings of the expression, subdivisions of the box -- until the
proof goes through.  Nothing here supplies any, so what it reports is what its
own search finds unaided.  Its automatic dichotomy is on, that being default.

A subexpression whose range holds zero cuts the chain of relative errors it
reasons through, and it falls back to bounding the error by the range of the
function itself: `(/ t (+ t 1))` over `t in [0, 999]` comes back at 0.999, and
over `[1, 999]` at 3.9e-16.  Cancellation does it too.  It bounds each goal
separately, so a core whose relative error is unbounded still reports an
absolute one.

Like Daisy it cannot express PI or E: FPBench's Gappa backend knows only
SQRT2 and SQRT1_2.
"""

from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from functools import partial

from . import common

GAPPA = os.path.expanduser(os.environ.get("GAPPA", "~/gappa"))

OPTS = ()                     # its defaults: 60-bit interval arithmetic, auto-dichotomy
UNSUPPORTED = {"status": "unsupported",
               "error": "the Gappa backend does not support PI or E"}


def exe() -> str:
    """GAPPA names either the binary or the checkout holding it."""
    for path in (GAPPA, os.path.join(GAPPA, "src", "gappa")):
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    found = shutil.which("gappa")
    if found:
        return found
    raise RuntimeError(f"no gappa at {GAPPA}; set GAPPA to its binary or checkout")


def version() -> str:
    run = subprocess.run([exe(), "--version"], capture_output=True, text=True,
                         errors="replace")
    m = re.search(r"Gappa (\S+)", run.stdout + run.stderr)
    if not m:
        raise RuntimeError("cannot read the Gappa version; it printed:\n"
                           + (run.stdout + run.stderr)[:600])
    return m.group(1)


# -- the exported file --

# `  -> |ex0 - Mex0| in ? }`, the last line of a core's script
_GOAL = re.compile(r"^\s*-> \|(\w+) - (\w+)\| in \? \}\s*$")


def split_gappa(path: str) -> list:
    """One script per core.  The backend emits no header or separator, so the
    goal line, which is always last, is what ends a core."""
    out, cur = [], []
    with open(path) as f:
        for line in f:
            cur.append(line)
            if _GOAL.match(line):
                out.append("".join(cur))
                cur = []
    if "".join(cur).strip():
        raise RuntimeError(f"gappa export ended mid-core:\n{''.join(cur)[:300]}")
    return out


def with_goals(text: str) -> str:
    """Ask for all three bounds at once.  FPBench emits a script per metric,
    but Gappa proves a conjunction goal by goal, so one run answers for all
    three and a metric it cannot bound costs only itself."""
    lines = text.splitlines(True)
    m = _GOAL.match(lines[-1])
    if m is None:
        raise RuntimeError(f"no goal in the gappa script:\n{text[-300:]}")
    got, exact = m.group(1), m.group(2)
    lines[-1] = (f"  -> (|{got} - {exact}| in ? /\\ {got} -/ {exact} in ? "
                 f"/\\ {exact} in ?) }}\n")
    return "".join(lines)


# -- its output --

_BRACE = re.compile(r"\s*\{[^}]*\}")          # the decimal gloss on a bound
_RESULT = re.compile(r"^\s+(\S.*?) in \[(.*)\]$")

# 2249548013871563b-51, or a plain integer, or %g from an inexact bound
_DYADIC = re.compile(r"^([-+]?\d+)b([-+]?\d+)$")


def number(tok: str) -> float:
    """Gappa prints bounds exactly, as mantissa`b`exponent base two, so they
    are read exactly and rounded once, here."""
    m = _DYADIC.match(tok)
    if m:
        e = int(m.group(2))
        v = Fraction(int(m.group(1))) * (Fraction(2) ** e)
        try:
            return float(v)
        except OverflowError:
            return math.inf if v > 0 else -math.inf
    return float(tok)


def interval(text: str) -> tuple:
    lo, hi = _BRACE.sub("", text).split(", ")
    return number(lo), number(hi)


def metric(lhs: str) -> str:
    """Which goal a result line answers -- by shape, not by name: Gappa
    inlines an expression it finds trivial, so a core whose body is a bare
    variable reports on `|float<53,-1074,ne>(Mx) - Mx|`, not on the exported
    names."""
    if lhs.startswith("|") and lhs.endswith("|") and " - " in lhs:
        return "abs"
    return "rel" if " -/ " in lhs else "range"


def parse(text: str) -> dict:
    """Only the goals it reached appear.  Gappa writes them to stderr; stdout
    is for the proof, which the null backend does not emit."""
    out = {"abs": None, "rel": None, "range": None}
    for line in text.splitlines():
        m = _RESULT.match(line)
        if m is None:
            continue
        lo, hi = interval(m.group(2))
        key = metric(m.group(1))
        out[key] = [lo, hi] if key == "range" else max(abs(lo), abs(hi))
    return out


_UNSAT = "some properties were not satisfied"


def why(err: str) -> str:
    """Its complaint, which runs onto the next lines."""
    lines = [ln.strip() for ln in err.strip().splitlines() if ln.strip()]
    hit = next((i for i, ln in enumerate(lines) if ln.startswith("Error:")), None)
    if hit is None:
        return (lines[-1][:160] if lines else "") or "no bound in the output"
    return " ".join(lines[hit:])[len("Error:"):161].strip()


def unmet(report: dict) -> str:
    """What it did not bound, named by our metric so `bounds.md` can count
    the reasons across cores."""
    return "no bound on " + ", ".join(k for k, v in report.items() if v is None)


# -- running --


def run_one(item: tuple, *, opts: tuple, timeout: float, workdir: str) -> tuple:
    name, text = item
    d = os.path.join(workdir, "gappa")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{name}.g")
    with open(path, "w") as f:
        f.write(with_goals(text))
    t0 = time.time()
    try:
        run = subprocess.run([exe(), *opts, path], capture_output=True, text=True,
                             errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return name, {"status": "timeout", "seconds": round(time.time() - t0, 2)}
    took = round(time.time() - t0, 2)
    report = parse(run.stderr)
    if report["abs"] is None and report["rel"] is None:
        # it exits 1 whether it proved nothing or could not read the file, and
        # proving nothing is its answer, not a failure
        if _UNSAT in run.stderr:
            return name, {"status": "nobound", "seconds": took,
                          "error": unmet(report)}
        return name, {"status": "error", "seconds": took, "error": why(run.stderr)}
    return name, {"status": "ok", "seconds": took, **report}


def analyze(todo: list, *, opts: tuple, timeout: float, jobs: int,
            workdir: str) -> dict:
    out = {u["name"]: dict(UNSUPPORTED) for u in todo if u["consts"]}
    batch = [u for u in todo if not u["consts"]]
    if not batch:
        return out
    texts = split_gappa(common.fpbench(batch, os.path.join(workdir, "gappa-in"),
                                       "gappa"))
    if len(texts) != len(batch):
        raise RuntimeError(f"fpbench emitted {len(texts)} gappa scripts for "
                           f"{len(batch)} cores")
    work = partial(run_one, opts=opts, timeout=timeout, workdir=workdir)
    items = list(zip((u["name"] for u in batch), texts))
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for i, (name, report) in enumerate(pool.map(work, items), 1):
            out[name] = report
            if i % 25 == 0:
                print(f"    gappa {i}/{len(items)}", flush=True)
    return out


SPEC = {"version": version, "opts": OPTS, "run": analyze}
