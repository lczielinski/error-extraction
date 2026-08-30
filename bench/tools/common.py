"""Paths, FPCore export and the run cache, shared by the tool modules."""

from __future__ import annotations

import functools
import hashlib
import json
import os
import subprocess
import sys

BENCH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(BENCH))

from costex.analysis import METRICS as _MU                                   # noqa: E402
from costex.fpcore import parse_expr, parse_sexps, parse_fpcore, to_fpcore   # noqa: E402

CORES = os.path.join(BENCH, "cores")
RESULTS = os.path.join(BENCH, "results")
CACHE = os.path.join(BENCH, ".cache")

FPBENCH = os.path.expanduser(os.environ.get("FPBENCH", "~/fpbench"))


class Metric:
    """An error metric and the results.json keys naming it, derived in one
    place so the record and the reports cannot drift apart."""

    __slots__ = ("name", "label", "seed", "best", "best_expr")

    def __init__(self, name: str):
        self.name = name
        self.label = f"mu_{name}"
        self.seed = f"seed_{name}"
        self.best = f"best_{name}"
        self.best_expr = f"best_expr_{name}"

    def __repr__(self):
        return f"Metric({self.name!r})"


METRICS = tuple(Metric(m) for m in _MU)     # costex's order is the reports' order
BY_NAME = {m.name: m for m in METRICS}


def has_const(expr: str) -> bool:
    """Does it mention PI or E?  FPBench's Scala backend refuses those."""
    def walk(e):
        return e[0] == "const" or any(walk(a) for a in e[1:] if isinstance(a, tuple))
    return walk(parse_expr(parse_sexps(expr)[0]))


@functools.lru_cache(maxsize=None)
def core(file: str):
    return parse_fpcore(open(os.path.join(CORES, file)).read())


def unit(name: str, file: str, expr: str, **extra) -> dict:
    """One program to hand a tool: the expression plus the core it came from."""
    c = core(file)
    return {"name": name, "file": file, "args": c.args, "box": c.box,
            "precision": c.precision, "consts": has_const(expr), "expr": expr,
            **extra}


def seed_units(results: list) -> list:
    """The bounds report compares analysers on the seed alone."""
    return [unit(f"cx{i:05d}", r["file"], r["expr"])
            for i, r in enumerate(r for r in results if r["status"] == "ok")]


def key(tool: str, u: dict, ver: str, opts: tuple) -> str:
    payload = repr((tool, u["expr"], sorted(u["box"].items()),
                    u["precision"], opts, ver))
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def cached(tool: str, k: str):
    path = os.path.join(CACHE, tool, k + ".json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def store(tool: str, k: str, report: dict) -> None:
    os.makedirs(os.path.join(CACHE, tool), exist_ok=True)
    with open(os.path.join(CACHE, tool, k + ".json"), "w") as f:
        json.dump(report, f)


def fpbench(batch: list, stem: str, lang: str, extra: list = ()) -> str:
    """FPCore -> a tool's input format, one racket call for the whole batch."""
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
