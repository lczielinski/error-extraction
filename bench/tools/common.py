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

from costex.fpcore import parse_expr, parse_sexps, parse_fpcore, to_fpcore   # noqa: E402

CORES = os.path.join(BENCH, "cores")
RESULTS = os.path.join(BENCH, "results")
CACHE = os.path.join(BENCH, ".cache")

FPBENCH = os.path.expanduser(os.environ.get("FPBENCH", "~/fpbench"))

VARIANTS = ("seed", "best_abs", "best_rel")


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


def units(results: list) -> list:
    """The distinct (core, expression) pairs, with the variants sharing each."""
    out = []
    for r in results:
        if r["status"] != "ok":
            continue
        shared = {}
        for v in VARIANTS:
            e = r["expr"] if v == "seed" else r.get(f"best_expr_{v[len('best_'):]}")
            if e:
                shared.setdefault(e, []).append(v)
        for expr, variants in shared.items():
            out.append(unit(f"cx{len(out):05d}", r["file"], expr, variants=variants))
    return out


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
