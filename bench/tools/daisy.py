"""Daisy's bounds and rewrites. DAISY names its checkout (default ~/daisy), built with
`sbt compile`; DAISY_JAVA_HOME names a JDK."""

import os
import re
from concurrent.futures import ThreadPoolExecutor

from costex.fpcore import expr, parse, read, show

from .common import cached, export, run

HOME = os.path.expanduser(os.environ.get("DAISY", "~/daisy"))
JAVA = os.environ.get("DAISY_JAVA_HOME", "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home")
ENV = dict(os.environ, JAVA_HOME=JAVA, PATH=os.path.join(JAVA, "bin") + ":" + os.environ["PATH"])
ANALYSIS = ["--analysis=dataflow", "--rangeMethod=interval", "--errorMethod=affine"]


def objects(texts, workdir):
    """One Scala object per program, named p0, p1, ...: Daisy reports only at the end of a
    file, so one crash would lose every program in it. FPBench writes 1e3 as 1e3.0."""
    scala = re.sub(r"([0-9][0-9.]*[eE][+-]?[0-9]+)\.0\b", r"\1", export(texts, "scala", os.path.join(workdir, "daisy")))
    defs = re.findall(r"\tdef ex\d+\b.*?\n\t\}\n", scala, re.S)
    assert len(defs) == len(texts), "FPBench dropped a program"
    return [f"import daisy.lang._\nimport Real._\n\nobject p{i} {{\n{exact(d)}}}\n" for i, d in enumerate(defs)]


def exact(d):
    """Daisy rounds every input with no stated error, but the inputs are floats: state zero."""
    names = re.findall(r"(\w+): Real", re.search(r"def ex\d+\(([^)]*)\)", d).group(1))
    zero = "".join(f" && {x} +/- 0.0" for x in names)
    return re.sub(r"require\((.*)\)\n", lambda m: f"require(({m.group(1)}){zero})\n", d, count=1)


def daisy(i, scala, text, options, workdir, timeout):
    path = os.path.join(workdir, f"p{i}.scala")
    with open(path, "w") as f:
        f.write(scala)
    precision = "Float32" if ":precision binary32" in text else "Float64"
    out, seconds = run(["./daisy", *options, f"--precision={precision}", path], timeout, cwd=HOME, env=ENV)
    return out and re.sub(r"\x1b\[[0-9;]*m", "", out), seconds


def bound(texts, workdir, timeout, jobs):
    def one(i, scala, text):
        out, seconds = daisy(i, scala, text, ANALYSIS, workdir, timeout)
        report = {"seconds": seconds, "status": "timeout" if out is None else "ok"}
        for key, label in (("abs", "Absolute"), ("rel", "Relative")):
            m = re.search(rf"{label} error:\s*(\S+)", out or "")
            report[key] = float(m.group(1)) if m else None
        if out is not None and report["abs"] is None:
            report["status"] = "fail"
        return report

    def work(todo):
        with ThreadPoolExecutor(jobs) as pool:
            return dict(zip(todo, pool.map(one, range(len(todo)), objects(todo, workdir), todo)))

    return cached(f"daisy {ANALYSIS} {timeout}", texts, work)


def rewrite(texts, workdir, timeout, jobs, seed=1):
    """Daisy's genetic search over algebraic identities, seeded so a run repeats."""
    def one(i, scala, text):
        result = os.path.join(HOME, "output", f"p{i}.fpcore")
        if os.path.exists(result):
            os.remove(result)
        options = ANALYSIS + ["--rewrite", "--codegen", "--lang=FPCore", f"--rewrite-seed={seed}"]
        out, seconds = daisy(i, scala, text, options, workdir, timeout)
        if out is None or not os.path.exists(result):
            return {"seconds": seconds, "status": "timeout" if out is None else "fail"}
        try:
            with open(result) as f:
                form = next(f for f in read(f.read()) if f[:1] == ["FPCore"])
            names = dict(zip(form[1], parse(text).args))
            program = show(expr(form[-1]))
        except Exception:
            return {"seconds": seconds, "status": "fail"}
        return {"seconds": seconds, "status": "ok",
                "program": re.sub(r"[^\s()]+", lambda m: names.get(m.group(0), m.group(0)), program)}

    def work(todo):
        with ThreadPoolExecutor(jobs) as pool:
            return dict(zip(todo, pool.map(one, range(len(todo)), objects(todo, workdir), todo)))

    return cached(f"daisy-rewrite {ANALYSIS} {seed} {timeout}", texts, work)
