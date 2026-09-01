"""The external analysers, one module each."""

from __future__ import annotations

from . import common, daisy, fptaylor, gappa, herbie

TOOLS = {"fptaylor": fptaylor.SPEC, "daisy": daisy.SPEC, "gappa": gappa.SPEC}
REWRITERS = {"daisy": daisy.REWRITE_SPEC, "herbie": herbie.REWRITE_SPEC}

CACHEABLE = ("ok", "nobound", "unsupported", "crash",
             "nooutput", "unparsed", "argcount")

REWRITE_CACHEABLE = CACHEABLE + ("timeout",)


def _cached(cache: str, us: list, ver: str, opts: tuple, run, label: str,
            keep=CACHEABLE) -> dict:
    """name -> report for every unit, running only what is not cached."""
    reports, todo = {}, []
    for u in us:
        hit = common.cached(cache, common.key(cache, u, ver, opts))
        if hit is None:
            todo.append(u)
        else:
            reports[u["name"]] = hit
    print(f"  {label}: {len(us)} programs, {len(us) - len(todo)} cached, "
          f"{len(todo)} to run", flush=True)
    if todo:
        fresh = run(todo)
        by_name = {u["name"]: u for u in todo}
        for name, report in fresh.items():
            reports[name] = report
            if report["status"] in keep:
                common.store(cache, common.key(cache, by_name[name], ver, opts), report)
    return reports


def analyze(tool: str, us: list, *, timeout: float, jobs: int, workdir: str) -> tuple:
    spec = TOOLS[tool]
    ver, opts = spec["version"](), spec["opts"]

    def run(todo):
        return spec["run"](todo, opts=opts, timeout=timeout, jobs=jobs, workdir=workdir)

    return _cached(tool, us, ver, opts, run, tool), ver


def rewrite(tool: str, us: list, *, seed: int, timeout: float, jobs: int,
            workdir: str) -> tuple:
    """Cached like an analysis; the seed rides in the key through opts, so
    changing it re-runs."""
    spec = REWRITERS[tool]
    ver = spec["version"]()
    opts = spec["opts"] + spec["seed_opts"](seed)

    def run(todo):
        return spec["run"](todo, seed=seed, timeout=timeout, jobs=jobs,
                           workdir=workdir)

    return _cached(f"{tool}-rewrite", us, ver, opts, run, f"{tool} rewrite",
                   keep=REWRITE_CACHEABLE), ver
