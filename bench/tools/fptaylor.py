"""FPTaylor's bounds. FPTAYLOR names its checkout (default ~/FPTaylor)."""

import os
import re
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor

from .common import cached, export, run

HOME = os.path.expanduser(os.environ.get("FPTAYLOR", "~/FPTaylor"))
ENV = dict(os.environ, CAML_LD_LIBRARY_PATH=os.path.expanduser("~/.opam/fptaylor/lib/stublibs"))
OPTIONS = ["-v", "0", "-abs", "true", "-rel", "true"]
local = threading.local()


def home(workdir):
    """A copy of FPTaylor's directory per thread: its optimizer compiles a helper in place."""
    if not hasattr(local, "home"):
        local.home = os.path.join(workdir, f"fptaylor-{threading.get_ident()}")
        os.makedirs(os.path.join(local.home, "tmp"))
        os.makedirs(os.path.join(local.home, "log"))
        shutil.copytree(os.path.join(HOME, "b_and_b"), os.path.join(local.home, "b_and_b"))
        for name in set(os.listdir(HOME)) - {"b_and_b", "tmp", "log"}:
            os.symlink(os.path.join(HOME, name), os.path.join(local.home, name))
    return local.home


def one(block, workdir, timeout):
    d = home(workdir)
    with open(os.path.join(d, "tmp", "in.txt"), "w") as f:
        f.write(block)
    out, seconds = run([os.path.join(d, "fptaylor"), *OPTIONS, "tmp/in.txt"], timeout, cwd=d, env=ENV)
    report = {"seconds": seconds, "status": "timeout" if out is None else "ok"}
    for key, label in (("abs", "Absolute"), ("rel", "Relative")):
        m = re.search(rf"^{label} error \(exact\): \S+ \((\S+)\)", out or "", re.M)
        report[key] = float.fromhex(m.group(1)) if m else None
    if out is not None and report["abs"] is None:
        report["status"] = "fail"
    return report


def bound(texts, workdir, timeout, jobs):
    def work(todo):
        blocks = re.findall(r"^\{$.*?^\}$", export(todo, "fptaylor", os.path.join(workdir, "fptaylor")), re.M | re.S)
        assert len(blocks) == len(todo), "FPBench dropped a program"
        with ThreadPoolExecutor(jobs) as pool:
            return dict(zip(todo, pool.map(lambda b: one(b, workdir, timeout), blocks)))

    return cached(f"fptaylor {OPTIONS} {timeout}", texts, work)
