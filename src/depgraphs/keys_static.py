"""Step 5b: the two answer-key sources that need no Docker (ROADMAP 5b, sources 1 and 2).

Per sampled PR, at its base commit with the gold patch applied:
  co-edited : non-test `.py` files the patch modifies that exist at the base commit
  new files : non-test `.py` files the patch creates (G2) — counted, never in the key
  symbol    : for every name on an added line of a modified source file, the repository
              file that defines it (jedi `goto`, follow_imports=True); stdlib, third-party,
              test files and new files excluded

Writes data/keys_static/<instance_id>.json and results/step5/keys_static_summary.csv.
Failures (patch does not apply, jedi errors, time budget hit) are recorded per PR.
"""
from __future__ import annotations

import io
import json
import keyword
import subprocess
import tempfile
import time
import tokenize
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path, PurePosixPath

import pandas as pd

from depgraphs import progress
from depgraphs.candidates import CLONES
from depgraphs.datasets import ROOT, load
from depgraphs.patches import is_py, is_test_path, parse

KEYS = ROOT / "data" / "keys_static"
OUT = ROOT / "results" / "step5"
TIME_BUDGET_S = 240          # per PR, for jedi lookups
MAX_NAMES_PER_FILE = 600


def _git(args, cwd, **kw):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          timeout=1800, **kw)


def patches_by_instance(ids: set[str]) -> dict[str, str]:
    out = {}
    for name in ("swebench_full", "swebench_live_full", "swerebench_filtered"):
        df = load(name)
        df = df[df.instance_id.isin(ids)]
        out.update(dict(zip(df.instance_id, df.patch)))
    # the external test set's sources, consulted only for ids the D11 sources lack, so the
    # main sample's patches are exactly what they were
    for name in ("swegym", "swebench_pro"):
        missing = ids - set(out)
        if not missing:
            break
        df = load(name)
        df = df[df.instance_id.isin(missing)]
        out.update(dict(zip(df.instance_id, df.patch)))
    return out


def _names(line: str):
    """(col, name) for identifier tokens on one source line."""
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(line + "\n").readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return []
    return [(t.start[1], t.string) for t in toks
            if t.type == tokenize.NAME and not keyword.iskeyword(t.string)]


def symbol_key(repo_dir: Path, changed, new_files: set[str], deadline: float) -> tuple[dict, dict]:
    import jedi
    roots = [str(repo_dir)] + ([str(repo_dir / "src")] if (repo_dir / "src").is_dir() else [])
    proj = jedi.Project(str(repo_dir), added_sys_path=roots, smart_sys_path=False)
    found: dict[str, set] = {}
    stats = {"names_tried": 0, "names_resolved_in_repo": 0, "defined_in_new_file": 0,
             "defined_in_test_file": 0, "jedi_errors": 0, "truncated": False}
    root = repo_dir.resolve()
    for fc in changed:
        path = repo_dir / fc.path
        try:
            script = jedi.Script(path=str(path), project=proj)
        except Exception:
            stats["jedi_errors"] += 1
            continue
        seen = 0
        for ln, text in zip(fc.added_linenos, fc.added_lines):
            for col, name in _names(text):
                if seen >= MAX_NAMES_PER_FILE or time.time() > deadline:
                    stats["truncated"] = True
                    break
                seen += 1
                stats["names_tried"] += 1
                try:
                    defs = script.goto(ln, col, follow_imports=True)
                except Exception:
                    stats["jedi_errors"] += 1
                    continue
                for d in defs:
                    mp = d.module_path
                    if not mp:
                        continue
                    try:
                        rel = PurePosixPath(Path(mp).resolve().relative_to(root).as_posix())
                    except ValueError:
                        continue            # stdlib or third-party
                    r = str(rel)
                    if not is_py(r):
                        continue
                    if is_test_path(r):
                        stats["defined_in_test_file"] += 1
                        continue
                    if r in new_files:
                        stats["defined_in_new_file"] += 1
                        continue
                    stats["names_resolved_in_repo"] += 1
                    found.setdefault(r, set()).add(name)
    return {k: sorted(v) for k, v in sorted(found.items())}, stats


def pr_job(repo_key: str, rows: list[dict], patches: dict[str, str]) -> list[dict]:
    d = CLONES / repo_key.replace("/", "__")
    out = []
    for r in rows:
        dest = KEYS / f"{r['instance_id']}.json"
        if dest.exists():
            continue
        rec = {"instance_id": r["instance_id"], "repo_key": repo_key,
               "base_commit": r["base_commit"], "status": "ok"}
        t0 = time.time()
        try:
            fetched = _git(["cat-file", "-e", r["base_commit"] + "^{commit}"], d)
            if fetched.returncode != 0:
                _git(["fetch", "-q", "--depth", "1", "origin", r["base_commit"]], d, check=True)
            _git(["-c", "advice.detachedHead=false", "checkout", "-q", "-f", r["base_commit"]], d, check=True)
            _git(["clean", "-q", "-fdx"], d, check=True)
            patch = patches[r["instance_id"]]
            files = parse(patch)
            src = [f for f in files if is_py(f.path) and not is_test_path(f.path)]
            new = {f.path for f in src if f.is_new}
            rec["co_edited"] = sorted(f.path for f in src if not f.is_new and not f.is_deleted)
            rec["deleted"] = sorted(f.path for f in src if f.is_deleted)
            rec["new_files"] = sorted(new)
            with tempfile.NamedTemporaryFile("w", suffix=".diff", delete=False,
                                             encoding="utf-8", newline="\n") as tf:
                tf.write(patch if patch.endswith("\n") else patch + "\n")
            ap = _git(["apply", "--whitespace=nowarn", tf.name], d)
            Path(tf.name).unlink(missing_ok=True)
            if ap.returncode != 0:
                rec["status"] = "patch_failed"
                rec["error"] = ap.stderr.strip()[-300:]
                rec["symbol"], rec["symbol_stats"] = {}, {}
            else:
                changed = [f for f in src if not f.is_deleted]
                rec["symbol"], rec["symbol_stats"] = symbol_key(
                    d, changed, new, time.time() + TIME_BUDGET_S)
        except Exception as e:
            rec["status"] = "error"
            rec["error"] = f"{type(e).__name__}: {getattr(e, 'stderr', '') or e}"[-300:]
        rec["seconds"] = round(time.time() - t0, 1)
        KEYS.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(rec, indent=1))
        out.append(rec)
    _git(["checkout", "-q", "-f", "HEAD"], d)
    _git(["clean", "-q", "-fdx"], d)
    return out


def main(workers: int = 6):
    tasks = pd.read_csv(ROOT / "data" / "sample_tasks.csv")
    patches = patches_by_instance(set(tasks.instance_id))
    groups = {rk: d.to_dict("records") for rk, d in tasks.groupby("repo_key")}
    done = 0
    with ProcessPoolExecutor(workers) as ex:
        futs = {ex.submit(pr_job, rk, rows, patches): rk for rk, rows in groups.items()}
        for f in as_completed(futs):
            done += 1
            try:
                f.result()
            except Exception as e:
                print("repo job failed", futs[f], e, flush=True)
            progress.update("keys_static", repos_done=done, repos_total=len(groups))
    summarise()


def summarise():
    rows = []
    for p in sorted(KEYS.glob("*.json")):
        r = json.loads(p.read_text())
        st = r.get("symbol_stats") or {}
        rows.append({"instance_id": r["instance_id"], "repo_key": r["repo_key"],
                     "status": r["status"], "n_co_edited": len(r.get("co_edited", [])),
                     "n_new_files": len(r.get("new_files", [])),
                     "n_symbol_files": len(r.get("symbol", {})),
                     "names_tried": st.get("names_tried"),
                     "names_resolved_in_repo": st.get("names_resolved_in_repo"),
                     "jedi_errors": st.get("jedi_errors"), "truncated": st.get("truncated"),
                     "seconds": r.get("seconds")})
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / "keys_static_summary.csv", index=False)


if __name__ == "__main__":
    main()
