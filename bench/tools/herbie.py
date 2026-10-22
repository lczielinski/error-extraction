"""Herbie's rewrites, over the operations of herbie_platform.rkt and with series expansion
off, so each rewrite equals its input over the reals. Regime inference is Herbie's branching."""

import json
import os
import re

from milo.fpcore import expr, read, show

from .common import cached, rename, run

PLATFORM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "herbie_platform.rkt")


def fpcore(program):
    """Herbie's internal syntax, (+.f64 x #s(literal 1 binary64)), as FPCore."""
    program = re.sub(r"#s\(literal (\S+) \w+\)", r"\1", program)
    program = re.sub(r"\(neg\.f(32|64) ", "(- ", program)
    return show(expr(read(re.sub(r"\.f(32|64)\b", "", program))[0]))


def rewrite(texts, workdir, timeout, jobs, branch, seed=1):
    def work(todo):
        source, outdir = os.path.join(workdir, "herbie.fpcore"), os.path.join(workdir, "herbie")
        with open(source, "w") as f:
            f.write("\n".join(rename(t, f"p{i}") for i, t in enumerate(todo)))
        options = ["--platform", PLATFORM, "--disable", "generate:taylor", "--seed", str(seed),
                   "--timeout", str(timeout), "--threads", str(jobs)] + ["--disable", "reduce:regimes"] * (not branch)
        run(["racket", "-l", "herbie", "--", "report", *options, source, outdir], timeout * (len(todo) / jobs + 2))
        out = {t: {"status": "fail"} for t in todo}
        with open(os.path.join(outdir, "results.json")) as f:
            for test in json.load(f)["tests"]:
                report = {"status": test["status"], "seconds": test["time"] / 1000}
                if test["status"] not in ("timeout", "crash", "error"):
                    try:
                        report.update(status="ok", program=fpcore(test["output"]))
                    except SyntaxError:
                        report["status"] = "unparsed"
                out[todo[int(test["name"][1:])]] = report
        return out

    return cached(f"herbie {os.path.basename(PLATFORM)} taylor-off regimes-{branch} {seed} {timeout}", texts, work)
