"""The external analysers, one module each."""

from __future__ import annotations

from . import common, daisy, fptaylor

TOOLS = {"fptaylor": fptaylor.SPEC, "daisy": daisy.SPEC}

CACHEABLE = ("ok", "nobound", "unsupported", "crash")   # a timeout is not


def analyze(tool: str, us: list, *, timeout: float, jobs: int, workdir: str) -> tuple:
    """name -> report for every unit, running only what is not cached."""
    spec = TOOLS[tool]
    ver, opts = spec["version"](), spec["opts"]
    reports, todo = {}, []
    for u in us:
        hit = common.cached(tool, common.key(tool, u, ver, opts))
        if hit is None:
            todo.append(u)
        else:
            reports[u["name"]] = hit
    print(f"  {tool}: {len(us)} programs, {len(us) - len(todo)} cached, "
          f"{len(todo)} to run")
    if todo:
        fresh = spec["run"](todo, opts=opts, timeout=timeout, jobs=jobs,
                            workdir=workdir)
        by_name = {u["name"]: u for u in todo}
        for name, report in fresh.items():
            reports[name] = report
            if report["status"] in CACHEABLE:
                common.store(tool, common.key(tool, by_name[name], ver, opts), report)
    return reports, ver
