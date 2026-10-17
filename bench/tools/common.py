import hashlib
import json
import os
import re
import signal
import subprocess
import time

BENCH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(BENCH, ".cache")
FPBENCH = os.path.expanduser(os.environ.get("FPBENCH", "~/fpbench"))


def run(cmd, timeout, **kw):
    """(output, seconds), or (None, seconds) if it timed out, in which case its whole
    process group is killed: Daisy's launcher leaves a JVM behind otherwise."""
    start = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            errors="replace", start_new_session=True, **kw)
    try:
        out = proc.communicate(timeout=timeout)[0]
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        out = None
    return out, round(time.time() - start, 2)


def export(texts, lang, stem):
    """FPCore texts in another language, in order, through one FPBench call."""
    with open(stem + ".fpcore", "w") as f:
        f.write("\n".join(rename(t, f"p{i}") for i, t in enumerate(texts)))
    fpbench = ["racket", os.path.join(FPBENCH, "fpbench.rkt"), "export", "--lang", lang]
    run(fpbench + [stem + ".fpcore", f"{stem}.{lang}"], 3600, cwd=FPBENCH)
    with open(f"{stem}.{lang}") as f:
        return f.read()


def rename(text, name):
    """The FPCore with a new :name, since some exporters drop programs whose names repeat."""
    return re.sub(r':name "[^"]*"', f':name "{name}"', text, count=1)


def cached(tool, texts, work):
    """{text: report} for FPCore texts, calling work(texts) on the ones not yet cached. tool
    names the tool and its options; delete .cache/ after upgrading a tool."""
    def path(text):
        return os.path.join(CACHE, tool, hashlib.sha256(text.encode()).hexdigest()[:32] + ".json")

    out = {}
    for text in texts:
        if os.path.exists(path(text)):
            with open(path(text)) as f:
                out[text] = json.load(f)
    todo = [t for t in dict.fromkeys(texts) if t not in out]
    for text, report in (work(todo) if todo else {}).items():
        os.makedirs(os.path.dirname(path(text)), exist_ok=True)
        with open(path(text), "w") as f:
            json.dump(report, f)
        out[text] = report
    return out
