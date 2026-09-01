"""FPTaylor: a sound analyser over symbolic Taylor forms.

    FPTAYLOR=~/FPTaylor       its checkout
    FPTAYLOR_STUBLIBS=...     the opam switch's stublibs, for bytecode builds
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from functools import partial

from . import common

FPTAYLOR = os.path.expanduser(os.environ.get("FPTAYLOR", "~/FPTaylor"))
STUBLIBS = os.path.expanduser(
    os.environ.get("FPTAYLOR_STUBLIBS", "~/.opam/fptaylor/lib/stublibs"))

OPTS = ("-v", "0", "-abs", "true", "-rel", "true")


def env() -> dict:
    return dict(os.environ, CAML_LD_LIBRARY_PATH=STUBLIBS)


def version() -> str:
    exe = os.path.join(FPTAYLOR, "fptaylor")
    if not os.path.exists(exe):
        raise RuntimeError(f"no fptaylor at {exe}; set FPTAYLOR to its directory")
    run = subprocess.run([exe, "--help"], cwd=FPTAYLOR, env=env(),
                         capture_output=True, text=True, errors="replace")
    m = re.search(r"FPTaylor, version (\S+)", run.stdout)
    if not m:
        raise RuntimeError("cannot read the FPTaylor version; it printed:\n"
                           + (run.stdout + run.stderr)[:600])
    return m.group(1)


_BLOCK_NAME = re.compile(r"\b([a-z]+\d{5})\s*=")


def blocks(path: str) -> dict:
    """name -> the { ... } block defining it."""
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
    """The message after "**ERROR**:", which runs onto the next lines."""
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
        if len(out) == 2:          # the complaint, then the subterm
            break
    return " ".join(out)[:160] or "no bound in the output"


def parse(text: str) -> dict:
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
    """A private FPTaylor directory per process: b_and_b/compile.sh builds a
    helper binary in place, so concurrent runs would race.  b_and_b is copied
    (72K) and tmp/log made; the rest is symlinked."""
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


def run_one(item: tuple, *, opts: tuple, timeout: float, workdir: str) -> tuple:
    name, text = item
    root = _root(workdir)
    path = os.path.join(root, "tmp", f"{name}.txt")
    with open(path, "w") as f:
        f.write(text)
    t0 = time.time()
    try:
        run = subprocess.run([os.path.join(root, "fptaylor"), *opts, path], cwd=root,
                             env=env(), capture_output=True, text=True, errors="replace",
                             timeout=timeout)
    except subprocess.TimeoutExpired:
        return name, {"status": "timeout", "seconds": round(time.time() - t0, 2)}
    took = round(time.time() - t0, 2)
    if run.returncode != 0:
        return name, {"status": "error", "seconds": took,
                      "error": (run.stderr or run.stdout)[-300:].strip()}
    report = parse(run.stdout)
    if report["abs"] is None:
        # e.g. "num_of_float: inf": it exits 0 having bounded nothing, which
        # is its answer, not a failure
        return name, {"status": "nobound", "seconds": took,
                      "error": _why(run.stderr + run.stdout)}
    return name, {"status": "ok", "seconds": took, **report}


def analyze(todo: list, *, opts: tuple, timeout: float, jobs: int,
            workdir: str) -> dict:
    found = blocks(common.fpbench(todo, os.path.join(workdir, "ft"), "fptaylor"))
    missing = {u["name"] for u in todo} - set(found)
    if missing:
        raise RuntimeError(f"fpbench dropped {len(missing)} of {len(todo)} cores, "
                           f"e.g. {sorted(missing)[:3]}")
    work = partial(run_one, opts=opts, timeout=timeout, workdir=workdir)
    items = [(u["name"], found[u["name"]]) for u in todo]
    out = {}
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for i, (name, report) in enumerate(pool.map(work, items), 1):
            out[name] = report
            if i % 25 == 0:
                print(f"    fptaylor {i}/{len(items)}", flush=True)
    return out


SPEC = {"version": version, "opts": OPTS, "run": analyze}
