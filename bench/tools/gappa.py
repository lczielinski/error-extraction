"""Gappa's bounds, from its own proof search with no hints, on float inputs. GAPPA names
its binary (default ~/gappa/src/gappa)."""

import math
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction

from .common import cached, export, run

GAPPA = os.path.expanduser(os.environ.get("GAPPA", "~/gappa/src/gappa"))
GOAL = re.compile(r"^\s*-> \|(\w+) - (\w+)\| in \? \}$")


def scripts(text):
    """One script per program; each ends with a goal on the absolute error, which is widened
    to ask for the relative error too."""
    out, lines = [], []
    for line in text.splitlines():
        m = GOAL.match(line)
        if m:
            got, exact = m.groups()
            out.append("\n".join(lines) + f"\n  -> (|{got} - {exact}| in ? /\\ {got} -/ {exact} in ?) }}\n")
            lines = []
        else:
            lines.append(line)
    return out


def number(token):
    """Gappa writes exact bounds as mantissa b exponent, base two."""
    if "b" not in token:
        return float(token)
    m, e = token.split("b")
    try:
        return float(Fraction(int(m)) * Fraction(2) ** int(e))
    except OverflowError:
        return math.inf


def one(script, workdir, timeout):
    with tempfile.NamedTemporaryFile("w", suffix=".g", dir=workdir, delete=False) as f:
        f.write(script)
    out, seconds = run([GAPPA, f.name], timeout)
    report = {"seconds": seconds, "status": "timeout" if out is None else "ok", "abs": None, "rel": None}
    for lhs, ends in re.findall(r"^\s+(\S.*?) in \[(.*)\]$", out or "", re.M):
        lo, hi = (number(x) for x in re.sub(r"\s*\{[^}]*\}", "", ends).split(", "))
        key = "rel" if " -/ " in lhs else "abs" if lhs.startswith("|") else None
        if key:
            report[key] = max(abs(lo), abs(hi))
    if out is not None and report["abs"] is None and report["rel"] is None:
        report["status"] = "fail"
    return report


def bound(texts, workdir, timeout, jobs):
    def work(todo):
        floats = [re.sub(r":precision (\S+)", r":precision \1 :var-precision \1", t, count=1) for t in todo]
        found = scripts(export(floats, "gappa", os.path.join(workdir, "gappa")))
        assert len(found) == len(todo), "FPBench dropped a program"
        with ThreadPoolExecutor(jobs) as pool:
            return dict(zip(todo, pool.map(lambda s: one(s, workdir, timeout), found)))

    return cached(f"gappa var-precision {timeout}", texts, work)
