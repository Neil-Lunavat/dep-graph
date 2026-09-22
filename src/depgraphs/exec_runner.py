"""Execution answer key runner (Step 5b source 3). Runs on a Linux machine with Docker.

Standard library only, so it runs on a bare VM:
    python3 exec_runner.py data/exec_bundle.jsonl out/ --workers 8

Per PR, inside the task's prebuilt image:
  1. apply the gold patch (and the test patch, unless the dataset's eval script does it)
  2. install coverage into the test environment; start it in every Python process
     (COVERAGE_PROCESS_START + a .pth file) with dynamic_context = test_function
  3. run the dataset's own test command on the PR's test files
  4. run a do-nothing test the same way (for D20 option C), pytest runners only
  5. write, per repository file: executed lines by test context, and the lines that sit
     inside function/method bodies (for D20 option B)
Output: out/<instance_id>.json (+ .log.gz). The image is deleted afterwards.
Nothing is dropped: every failure is written with its stage and error.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

TEST_TIMEOUT = 1800
PULL_TIMEOUT = 1800

# Runs inside the container with the container's own python (3.5+). Reads coverage's data file
# directly (no giant JSON report) and keeps: all executed lines, lines run by each fail-to-pass
# test's context, and the lines inside function bodies.
POST = r"""
import ast, json, sys
from coverage import CoverageData
data_file, out_file, f2p_file = sys.argv[1], sys.argv[2], sys.argv[3]
f2p = json.load(open(f2p_file))
# Django lists some tests by docstring. Its verbose log prints "test_x (module.Class)" and, on
# the next line, the docstring followed by " ... ok"; use that to translate.
import re
doc2name = {}
try:
    log = open("/work/tests.log", encoding="utf-8", errors="replace").read().splitlines()
    for i, line in enumerate(log[:-1]):
        m = re.match(r"^(test\w*) \(([\w.]+)\)$", line.strip())
        if m:
            doc = re.split(r" \.\.\. ", log[i + 1].strip())[0]
            doc2name[doc] = "%s (%s)" % (m.group(1), m.group(2))
except Exception:
    pass
f2p = [doc2name.get(t, t) for t in f2p]
want = set()
for t in f2p:
    t = t.split("[")[0]
    if " (" in t and t.endswith(")"):            # django: test_x (module.Class)
        fn, cls = t.split(" (")[0], t[:-1].split(" (")[1].split(".")[-1]
    elif "::" in t:                              # pytest: path::Class::test_x
        parts = t.split("::")
        fn, cls = parts[-1], (parts[-2] if len(parts) > 2 else None)
    else:                                        # sympy and others: test_x
        fn, cls = t.strip(), None
    want.add((fn, cls))
def is_f2p(ctx):
    segs = ctx.split("|")[0].split(".")
    if not segs or not segs[-1]:
        return False
    fn = segs[-1].split("[")[0]
    cls = segs[-2] if len(segs) > 1 else None
    return (fn, cls) in want or (fn, None) in want
d = CoverageData(basename=data_file)
d.read()
out = {}
for path in d.measured_files():
    rel = path[len("/testbed/"):] if path.startswith("/testbed/") else path
    lines = sorted(d.lines(path) or [])
    f2p_lines = set()
    try:
        by = d.contexts_by_lineno(path)
        for ln, cs in by.items():
            if any(is_f2p(c) for c in cs):
                f2p_lines.add(int(ln))
    except Exception:
        by = None
    fn = set()
    try:
        tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                body = node.body if isinstance(node.body, list) else [node.body]
                for stmt in body:
                    for n in ast.walk(stmt):
                        if hasattr(n, "lineno"):
                            fn.add(n.lineno)
    except Exception:
        fn = None
    out[rel] = {"executed": lines, "f2p_lines": sorted(f2p_lines),
                "fn_lines": sorted(fn) if fn is not None else None}
json.dump({"files": out, "n_contexts": len(d.measured_contexts()) if hasattr(d, "measured_contexts") else None,
           "f2p_wanted": sorted(str(w) for w in want)}, open(out_file, "w"))
"""

RC = """[run]
parallel = True
data_file = /work/{name}/.coverage
source = /testbed
dynamic_context = test_function

[report]
ignore_errors = True
"""

NOOP = "def test_noop():\n    pass\n"


def sh(cmd, timeout=600, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)


def runner_prefix(cmd: str) -> str:
    for p in ("pdm run ", "poetry run ", "pipenv run ", "uv run ", "hatch run "):
        if p in cmd:
            return cmd[:cmd.index(p) + len(p)].split("&&")[-1].strip() + " "
    return ""


VALUE_OPTS = {"-n", "--numprocesses", "--dist", "-p", "-W", "-k", "-m", "-c", "--rootdir",
              "--timeout", "--maxfail", "-o", "--durations", "--color", "--tb"}


def strip_pytest_paths(cmd: str) -> str:
    """Drop positional path arguments after `pytest` (e.g. `pytest -rA keras`), so only the
    PR's test files run. Options and their values are kept."""
    toks = shlex.split(cmd)
    idx = next((i for i, t in enumerate(toks) if t.endswith("pytest")), None)
    if idx is None:
        return cmd
    keep, i = toks[: idx + 1], idx + 1
    while i < len(toks):
        t = toks[i]
        if t in ("&&", "||", ";", "|"):
            keep += toks[i:]
            break
        if t.startswith("-"):
            keep.append(t)
            if t in VALUE_OPTS and i + 1 < len(toks):
                keep.append(toks[i + 1])
                i += 1
        i += 1
    return " ".join(shlex.quote(t) if (" " in t or not t) else t for t in keep)


def test_command(rec: dict) -> tuple[str, bool]:
    """(bash command that runs the PR's tests, whether it applies the test patch itself)."""
    files = " ".join(shlex.quote(f) for f in rec["test_files"])
    if rec["dataset"] == "swebench_full":
        return "bash /work/eval.sh", True
    if rec["dataset"] == "swerebench_filtered":
        return f"{strip_pytest_paths(rec['test_cmd'])} {files}", False
    cmds = [c for c in rec["test_cmds"] if "pytest" in c or "test" in c] or rec["test_cmds"]
    return f"{strip_pytest_paths(cmds[-1])} {files}", False


def container_script(rec: dict) -> str:
    cmd, self_applies = test_command(rec)
    prefix = runner_prefix(cmd) if rec["dataset"] != "swebench_full" else ""
    py = f"{prefix}python"
    # coverage >= 5.5 is needed for per-test contexts; old environments may ship 4.x
    install = ("uv pip install -q -U 'coverage>=5.5'" if prefix.startswith("uv run")
               else f"{py} -m pip install -q -U 'coverage>=5.5'")
    noop = ""
    if "pytest" in cmd or rec["dataset"] == "swebench_full":
        noop_runner = (f"{prefix}python -m pytest" if rec["dataset"] != "swebench_full"
                       else "python -m pytest")
        noop = f"""
echo '== noop'
cp /work/zz_noop_test.py /testbed/zz_noop_test.py
export COVERAGE_PROCESS_START=/work/noop.rc
( {noop_runner} -p no:cacheprovider /testbed/zz_noop_test.py ) > /work/noop.log 2>&1
echo "noop_exit=$?"
"""
    apply_tests = "" if self_applies else \
        "git apply --whitespace=nowarn /work/test.diff || { echo STAGE=test_patch; exit 21; }"
    return f"""#!/bin/bash
set -o pipefail
if [ -f /opt/miniconda3/bin/activate ]; then source /opt/miniconda3/bin/activate; conda activate testbed 2>/dev/null || true; fi
cd /testbed
git config --global --add safe.directory /testbed >/dev/null 2>&1
git apply --whitespace=nowarn /work/gold.diff || {{ echo STAGE=gold_patch; exit 20; }}
{apply_tests}
{install} || {{ echo STAGE=install_coverage; exit 22; }}
SITE=$({py} -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")
echo "import coverage; coverage.process_startup()" > "$SITE/zz_coverage_startup.pth" || {{ echo STAGE=pth; exit 23; }}
mkdir -p /work/main /work/noop
# a repo's own pytest-cov would take the tracer away from ours
if {py} -c "import pytest_cov" >/dev/null 2>&1; then export PYTEST_ADDOPTS="--no-cov"; fi
export COVERAGE_PROCESS_START=/work/main.rc
echo '== tests'
( timeout {TEST_TIMEOUT} bash -c {shlex.quote(cmd)} ) > /work/tests.log 2>&1
echo "tests_exit=$?"
{noop}
unset COVERAGE_PROCESS_START
rm -f "$SITE/zz_coverage_startup.pth"
for n in main noop; do
  if ls /work/$n/.coverage* >/dev/null 2>&1; then
    {py} -m coverage combine --rcfile=/work/$n.rc /work/$n >>/work/post.log 2>&1
    {py} /work/post.py /work/$n/.coverage /work/$n.compact.json /work/f2p.json >>/work/post.log 2>&1 || echo "post_failed_$n"
  else
    echo "no_coverage_$n"
  fi
done
rm -f /testbed/zz_noop_test.py
tail -c 1500 /work/post.log
echo DONE
"""


def run_one(rec: dict, out: Path, keep_image: bool = False) -> dict:
    iid = rec["instance_id"]
    res = {"instance_id": iid, "image": rec["image"], "status": "ok", "stages": {}}
    t0 = time.time()
    name = f"ek_{iid.replace('/', '_')}"[:120]
    work = Path(tempfile.mkdtemp(prefix="ek_"))
    try:
        (work / "gold.diff").write_text(rec["patch"] if rec["patch"].endswith("\n") else rec["patch"] + "\n")
        (work / "test.diff").write_text(rec["test_patch"] if rec["test_patch"].endswith("\n") else rec["test_patch"] + "\n")
        if rec.get("eval_script"):
            (work / "eval.sh").write_text(rec["eval_script"])
        (work / "post.py").write_text(POST)
        (work / "main.rc").write_text(RC.format(name="main"))
        (work / "noop.rc").write_text(RC.format(name="noop"))
        (work / "zz_noop_test.py").write_text(NOOP)
        (work / "f2p.json").write_text(json.dumps(rec["f2p"]))
        (work / "run.sh").write_text(container_script(rec))

        p = sh(["docker", "pull", "-q", rec["image"]], timeout=PULL_TIMEOUT)
        res["stages"]["pull_s"] = round(time.time() - t0, 1)
        if p.returncode != 0:
            res.update(status="pull_failed", error=p.stderr[-500:])
            return res
        t1 = time.time()
        sh(["docker", "rm", "-f", name])      # a leftover container from a stopped run
        r = sh(["docker", "run", "--rm", "--name", name, "--memory", "7g", "--cpus", "2",
                "-v", f"{work}:/work", "--entrypoint", "bash", rec["image"], "/work/run.sh"],
               timeout=TEST_TIMEOUT + 900)
        res["stages"]["run_s"] = round(time.time() - t1, 1)
        res["run_stdout"] = r.stdout[-3000:]
        res["run_stderr"] = r.stderr[-1500:]
        res["exit_code"] = r.returncode
        for line in r.stdout.splitlines():
            if line.startswith("STAGE="):
                res["status"] = "failed_" + line[6:]
            if line.startswith("tests_exit="):
                res["tests_exit"] = int(line.split("=")[1])
            if line.startswith("noop_exit="):
                res["noop_exit"] = int(line.split("=")[1])
        for n in ("main", "noop"):
            f = work / f"{n}.compact.json"
            res[n] = json.loads(f.read_text()) if f.exists() else None
        if res["status"] == "ok" and res["main"] is None:
            res["status"] = "no_coverage"
        elif res["status"] == "ok" and not any(v["f2p_lines"] for v in res["main"]["files"].values()):
            res["status"] = "no_f2p_lines"     # tests ran, but no line was attributed to a F2P test
        for n in ("tests", "noop"):
            f = work / f"{n}.log"
            if f.exists():
                with gzip.open(out / f"{iid}.{n}.log.gz", "wt", encoding="utf-8") as g:
                    g.write(f.read_text(errors="replace"))
    except subprocess.TimeoutExpired as e:
        res.update(status="timeout", error=str(e)[-300:])
        sh(["docker", "rm", "-f", name])
    except Exception:
        res.update(status="error", error=traceback.format_exc()[-1500:])
    finally:
        res["seconds"] = round(time.time() - t0, 1)
        if not keep_image:
            sh(["docker", "rmi", "-f", rec["image"]])
        subprocess.run(["sudo", "rm", "-rf", str(work)], capture_output=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle")
    ap.add_argument("out")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    recs = [json.loads(l) for l in open(a.bundle, encoding="utf-8")]
    if a.only:
        recs = [r for r in recs if r["instance_id"] in set(a.only)]
    # Seeded random order (seed 20260922, as for the sample), so stopping early at any point
    # leaves a random subset rather than an alphabetical one.
    import hashlib
    recs.sort(key=lambda r: hashlib.sha256(f"20260922{r['instance_id']}".encode()).hexdigest())
    recs = [r for r in recs if not (out / f"{r['instance_id']}.json").exists()]
    if a.limit:
        recs = recs[: a.limit]
    done = 0
    counts = {}
    with ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(run_one, r, out): r for r in recs}
        for f in as_completed(futs):
            res = f.result()
            (out / f"{res['instance_id']}.json").write_text(json.dumps(res))
            done += 1
            counts[res["status"]] = counts.get(res["status"], 0) + 1
            (out / "_progress.json").write_text(json.dumps(
                {"done": done, "total": len(recs), "by_status": counts,
                 "updated": time.strftime("%Y-%m-%d %H:%M:%S")}))
            print(done, len(recs), res["instance_id"], res["status"], res.get("seconds"), flush=True)


if __name__ == "__main__":
    main()
