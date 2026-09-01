"""Daisy: a sound analyser, and a rewriter over algebraic identities.

    DAISY=~/daisy            its checkout, built with `sbt compile`
    DAISY_JAVA_HOME=...      a real JDK
"""

from __future__ import annotations

import hashlib
import os
import re
import signal
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from costex.fpcore import parse_fpcore, to_sexp

from . import common

DAISY = os.path.expanduser(os.environ.get("DAISY", "~/daisy"))
# /usr/bin/java on macOS is a stub with no runtime
JAVA_HOME = os.environ.get(
    "DAISY_JAVA_HOME", "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home")

# --FPTaylor is looser and crashes; affine ranges crash on sqrt; --subdiv wants z3
OPTS = ("--analysis=dataflow", "--rangeMethod=interval", "--errorMethod=affine")
REWRITE_OPTS = OPTS + ("--rewrite", "--codegen", "--lang=FPCore")

FORMATS = (("binary64", "Float64"), ("binary32", "Float32"))
UNSUPPORTED = {"status": "unsupported",
               "error": "the Scala backend does not support PI or E"}


def env() -> dict:
    return dict(os.environ, JAVA_HOME=JAVA_HOME,
                PATH=os.path.join(JAVA_HOME, "bin") + ":" + os.environ["PATH"])


CLASSES = os.path.join(DAISY, "target", "scala-2.13", "classes")


def build_id() -> str:
    """A digest of the compiled classes.  The cache must key on what actually
    runs: an uncommitted edit or a plain rebuild does not move HEAD, and the
    old results would be served for a Daisy that no longer produces them."""
    h = hashlib.sha256()
    paths = sorted(os.path.join(d, n) for d, _, ns in os.walk(CLASSES)
                   for n in ns if n.endswith(".class"))
    for path in paths:
        st = os.stat(path)
        h.update(f"{os.path.relpath(path, CLASSES)}|{st.st_size}|"
                 f"{st.st_mtime_ns}\n".encode())
    return h.hexdigest()[:8]


def version() -> str:
    if not os.path.exists(os.path.join(DAISY, "daisy")):
        raise RuntimeError(f"no daisy launcher at {DAISY}; set DAISY to its directory")
    if not os.path.isdir(CLASSES):
        raise RuntimeError(f"daisy is not built; run `sbt compile` in {DAISY}")
    run = subprocess.run(["git", "-C", DAISY, "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True, errors="replace")
    return f"{run.stdout.strip() or 'unknown'}-{build_id()}"


_DEF = re.compile(r"\tdef (ex\d+)\b.*?\n\t\}\n", re.S)
_SCALA_HEAD = "import daisy.lang._\nimport Real._\n\nobject main {\n"

# FPBench renders 1000.0 as "1e3.0", which Scala rejects.  An exponent-form
# literal is never followed by ".0", so dropping it is safe.
_BAD_LIT = re.compile(r"([0-9][0-9.]*[eE][+-]?[0-9]+)\.0\b")


def split_scala(path: str) -> list:
    """One function per file: Daisy reports in a final phase, so one crash
    would lose a whole batch."""
    with open(path) as f:
        src = _BAD_LIT.sub(r"\1", f.read())
    return [_SCALA_HEAD + m.group(0) + "}\n" for m in _DEF.finditer(src)]


def batches(us: list, workdir: str, stem: str) -> tuple:
    """One export per target format: (skipped, [(flag, units, sources)]).

    The Scala backend drops :precision, so each format needs its own batch and
    --precision flag, and it cannot express PI or E at all.
    """
    skipped = {u["name"]: dict(UNSUPPORTED) for u in us if u["consts"]}
    doable = [u for u in us if not u["consts"]]
    out = []
    for prec, flag in FORMATS:
        batch = [u for u in doable if u["precision"] == prec]
        if not batch:
            continue
        texts = split_scala(common.fpbench(batch, os.path.join(workdir, f"{stem}-{flag}"),
                                           "scala"))
        if len(texts) != len(batch):
            raise RuntimeError(f"fpbench emitted {len(texts)} scala functions for "
                               f"{len(batch)} cores")
        out.append((flag, batch, texts))
    return skipped, out


ANSI = re.compile(r"\x1b\[[0-9;]*m")
_EXC = re.compile(r"^([\w.$]+(?:Exception|Error))(?::\s*(.*))?$", re.M)
_ABS = re.compile(r"Absolute error:\s*([-\d.eE+]+)")
_REL = re.compile(r"Relative error:\s*([-\d.eE+]+)")
_RANGE = re.compile(r"Real range:\s*\[([-\d.eE+]+),\s*([-\d.eE+]+)\]")


def _exception(text: str) -> str:
    """Daisy's own exception, preferred over the launcher's wrapper."""
    hits = _EXC.findall(text)
    hit = next((h for h in hits if h[0].startswith("daisy")), hits[0] if hits else None)
    return f"{hit[0]}: {hit[1]}".strip(": ")[:160] if hit else ""


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


def _run(text: str, opts: tuple, precision: str, timeout: float, d: str) -> tuple:
    """Daisy over one file, in its own scratch directory and process group.
    The launcher pipes java into tee, so the JVM is a grandchild: killing only
    the script on timeout would leave a 2G JVM spinning."""
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "a.scala")
    with open(path, "w") as f:
        f.write(text)
    t0 = time.time()
    proc = subprocess.Popen(["./daisy", *opts, f"--precision={precision}", path],
                            cwd=DAISY, env=env(), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            errors="replace", start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate()
        return None, round(time.time() - t0, 2)
    return ANSI.sub("", out), round(time.time() - t0, 2)


def _pool(work, items: list, what: str, flag: str, jobs: int) -> dict:
    """Threads are enough: Daisy's time goes in a subprocess."""
    out = {}
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for i, (name, report) in enumerate(pool.map(work, items), 1):
            out[name] = report
            if i % 25 == 0:
                print(f"    daisy {what} {flag} {i}/{len(items)}", flush=True)
    return out


def run_one(item: tuple, *, opts: tuple, precision: str, timeout: float,
            workdir: str) -> tuple:
    name, text = item
    text_out, took = _run(text, opts, precision, timeout,
                          os.path.join(workdir, "daisy", name))
    if text_out is None:
        return name, {"status": "timeout", "seconds": took}
    report = parse(text_out)
    if report["abs"] is None:
        why = _exception(text_out)
        return name, {"status": "crash" if why else "nobound", "seconds": took,
                      "error": why or "no bound in the output"}
    return name, {"status": "ok", "seconds": took, **report}


def analyze(todo: list, *, opts: tuple, timeout: float, jobs: int,
            workdir: str) -> dict:
    out, work = batches(todo, workdir, "daisy")
    for flag, batch, texts in work:
        run = partial(run_one, opts=opts, precision=flag, timeout=timeout,
                      workdir=workdir)
        items = list(zip((u["name"] for u in batch), texts))
        out.update(_pool(run, items, "analyse", flag, jobs))
    return out


SPEC = {"version": version, "opts": OPTS, "run": analyze}


_BEFORE = re.compile(r"error before:\s*([-\d.eE+]+)")
_AFTER = re.compile(r"error after:\s*([-\d.eE+]+)")


def _rename_vars(e, mapping: dict):
    """FPBench escapes what Scala forbids, so `x.re` comes back as `x_46re`;
    names are mapped back by position."""
    if e[0] == "var":
        return ("var", mapping.get(e[1], e[1]))
    return (e[0],) + tuple(_rename_vars(a, mapping) if isinstance(a, tuple) else a
                           for a in e[1:])


def _rename_object(text: str, name: str) -> str:
    """Daisy names its output after the object, so parallel runs need
    distinct ones."""
    return text.replace("object main {", f"object {name} {{", 1)


def rewrite_one(item: tuple, *, seed: int, precision: str, timeout: float,
                workdir: str) -> tuple:
    name, text, args = item
    out_fpcore = os.path.join(DAISY, "output", f"{name}.fpcore")
    if os.path.exists(out_fpcore):
        os.remove(out_fpcore)
    opts = REWRITE_OPTS + (f"--rewrite-seed={seed}",)
    text_out, took = _run(_rename_object(text, name), opts, precision, timeout,
                          os.path.join(workdir, "rw", name))
    if text_out is None:
        return name, {"status": "timeout", "seconds": took}
    if not os.path.exists(out_fpcore):
        why = _exception(text_out)
        return name, {"status": "crash" if why else "nooutput", "seconds": took,
                      "error": why or "no fpcore emitted"}
    try:
        core = parse_fpcore(open(out_fpcore).read())
    except SyntaxError as e:
        return name, {"status": "unparsed", "seconds": took, "error": str(e)[:160]}
    if len(core.args) != len(args):
        return name, {"status": "argcount", "seconds": took,
                      "error": f"daisy returned {core.args} for {args}"}
    before, after = _BEFORE.search(text_out), _AFTER.search(text_out)
    return name, {"status": "ok", "seconds": took,
                  "expr": to_sexp(_rename_vars(core.body, dict(zip(core.args, args)))),
                  "daisy_before": float(before.group(1)) if before else None,
                  "daisy_after": float(after.group(1)) if after else None}


def run_rewriter(us: list, *, seed: int, timeout: float, jobs: int,
                 workdir: str) -> dict:
    """The genetic search is seeded, so a run is repeatable."""
    out, work = batches(us, workdir, "rw")
    for flag, batch, texts in work:
        run = partial(rewrite_one, seed=seed, precision=flag, timeout=timeout,
                      workdir=workdir)
        items = [(u["name"], t, u["args"]) for u, t in zip(batch, texts)]
        out.update(_pool(run, items, "rewrite", flag, jobs))
    return out


REWRITE_SPEC = {"version": version, "opts": REWRITE_OPTS, "run": run_rewriter,
                "seed_opts": lambda s: (f"--rewrite-seed={s}",),
                "note": "a genetic search over algebraic identities"}
