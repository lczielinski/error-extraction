"""Herbie: a search for accurate rewrites, guided by sampled error.

    HERBIE_RACKET=racket     the racket that has the herbie package installed

Installed from a checkout with `make egg-herbie && make update`.  Not plain
`make install`: that also runs `make egglog-herbie`, which cargo-installs its
own egglog-experimental over the one costex runs.  Herbie 2.3 only reaches for
that binary under `generate:egglog`, which is off.

Herbie has no sound mode: nothing it emits is guaranteed equal to its input
over the reals.  Two of its moves are unsound by construction and both are
turned off here, which is as close as it comes:

  generate:taylor    series expansion, which agrees only near a limit point
  reduce:regimes     splitting the box and branching, so no one expression
                     answers for the whole input range

What is left is rewriting under identities, like the other two rewriters, and
`rewrites.md` measures on the points whether the result really is equivalent.

It also searches over the whole of libm by default, and would answer with fma
or hypot, which neither costex nor Daisy can express and this benchmark cannot
evaluate.  `herbie_platform.rkt` cuts the platform down to the operations the
corpus is written in, so all three search one language.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import time

from costex.fpcore import parse_fpcore, to_fpcore, to_sexp, variables

RACKET = os.environ.get("HERBIE_RACKET", "racket")
PLATFORM = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "herbie_platform.rkt")

_DISABLE = ("--disable", "generate:taylor",     # not equal over the reals
            "--disable", "reduce:regimes")      # and neither is a branch

# what the report prints and the cache keys on: the platform by name, since
# its contents are already in the version, and its path is this machine's
REWRITE_OPTS = ("--platform", os.path.basename(PLATFORM)) + _DISABLE
RUN_OPTS = ("--platform", PLATFORM) + _DISABLE

NOTE = ("series expansion and branch splitting are off, and the platform is "
        "cut down to this corpus's operations, so what is left is rewriting "
        "under identities over the same language as the others")


def _cmd(*args) -> list:
    return [RACKET, "-l", "herbie", "--", *args]


def version() -> str:
    """The herbie version and a digest of our platform, which decides what it
    is allowed to search over and so belongs in the cache key."""
    run = subprocess.run(_cmd("--version"), capture_output=True, text=True,
                         errors="replace")
    m = re.search(r"(\d+\.\d+(?:\.\d+)?)", run.stdout)
    if run.returncode != 0 or not m:
        raise RuntimeError(
            "cannot run herbie; install it with `make install` in a herbie "
            "checkout, or set HERBIE_RACKET to the racket that has it:\n"
            + (run.stdout + run.stderr)[:400])
    with open(PLATFORM, "rb") as f:
        plat = hashlib.sha256(f.read()).hexdigest()[:8]
    return f"{m.group(1)}-{plat}"


# -- the output file --

_NOTE = re.compile(r"^;;\s*(.*)$")
_TIMEOUT = re.compile(r"times out in\b")


def split_output(text: str) -> list:
    """[(note, source)] per core.  A failed test still gets an FPCore -- the
    input echoed back -- with a comment above it saying so, and taking that
    for an answer would score herbie as having returned the seed."""
    out, note, pending, cur = [], "", "", None

    def close():
        nonlocal cur
        if cur is not None:
            out.append((note, "".join(cur)))
            cur = None

    for line in text.splitlines(True):
        if line.startswith(";"):          # only ever between cores
            close()
            m = _NOTE.match(line.strip())
            if m and not m.group(1).startswith("seed:"):
                pending = m.group(1).strip()
        elif line.startswith("(FPCore"):
            close()
            cur, note, pending = [line], pending, ""
        elif cur is not None:
            cur.append(line)
    close()
    return out


def status_of(note: str) -> str:
    if not note:
        return "ok"
    return "timeout" if _TIMEOUT.search(note) else "crash"


def report_one(note: str, src: str, args: list) -> dict:
    st = status_of(note)
    if st != "ok":
        return {"status": st, "error": note[:160]}
    try:
        core = parse_fpcore(src)
    except SyntaxError as e:
        # only reachable if herbie leaves the platform's operations, or wraps
        # the body in a precision annotation
        return {"status": "unparsed", "error": str(e)[:160]}
    unknown = variables(core.body) - set(args)
    if unknown or len(core.args) != len(args):
        return {"status": "argcount",
                "error": f"herbie returned {core.args} for {args}"}
    return {"status": "ok", "expr": to_sexp(core.body)}


# -- running --


def _name(src: str) -> str:
    m = re.search(r':name\s+"([^"]+)"', src)
    if m is None:
        raise RuntimeError(f"herbie emitted a core with no :name:\n{src[:200]}")
    return m.group(1)


def run_rewriter(us: list, *, seed: int, timeout: float, jobs: int,
                 workdir: str) -> dict:
    """One herbie invocation for the whole batch: it runs its own worker pool
    and times each core out on its own, so a slow core costs only itself."""
    d = os.path.join(workdir, "herbie")
    os.makedirs(d, exist_ok=True)
    src = os.path.join(d, "in.fpcore")
    dst = os.path.join(d, "out.fpcore")
    with open(src, "w") as f:
        f.write("".join(to_fpcore(u["name"], u["args"], u["box"], u["expr"],
                                  u["precision"]) for u in us))
    opts = RUN_OPTS + ("--seed", str(seed), "--timeout", str(int(timeout)),
                       "--threads", str(jobs))
    t0 = time.time()
    # herbie's own timeout is per core, so the batch gets that much per core
    # it could still be working on, and a wide margin for startup and sampling
    cap = timeout * (len(us) / max(jobs, 1) + 1) + 600
    try:
        run = subprocess.run(_cmd("improve", *opts, src, dst), capture_output=True,
                             text=True, errors="replace", timeout=cap)
    except subprocess.TimeoutExpired:
        return {u["name"]: {"status": "timeout", "seconds": round(time.time() - t0, 2),
                            "error": f"the whole batch passed {cap:.0f}s"}
                for u in us}
    took = round((time.time() - t0) / max(len(us), 1), 2)
    if run.returncode != 0 or not os.path.exists(dst):
        raise RuntimeError("herbie failed on the whole batch:\n"
                           + (run.stdout + run.stderr)[-600:])
    with open(dst) as f:
        chunks = split_output(f.read())
    by_name = {u["name"]: u for u in us}
    out = {}
    for note, chunk in chunks:
        name = _name(chunk)
        if name not in by_name:
            raise RuntimeError(f"herbie returned an unknown core {name!r}")
        out[name] = dict(report_one(note, chunk, by_name[name]["args"]),
                         seconds=took)
    missing = set(by_name) - set(out)
    for name in missing:
        out[name] = {"status": "nooutput", "seconds": took,
                     "error": "herbie returned no core for it"}
    return out


REWRITE_SPEC = {"version": version, "opts": REWRITE_OPTS, "run": run_rewriter,
                "seed_opts": lambda s: ("--seed", str(s)), "note": NOTE}
