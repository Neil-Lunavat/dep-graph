"""Remove the key files' names from the issue text, leaving the issue otherwise intact.

The leakage strata in `leakage.py` answer the question by dropping tasks, which cannot
separate "the issue names the answer" from "issues that name the answer are better issues".
Reports containing a stack trace are plausibly longer, more technical and more tractable
than vague feature requests, so a comparison across strata compares issues as well as
leakage.

This file does the within-task version. For every task we take the same issue and delete
only the occurrences of its key files' stems that `leakage.classify` would call explicit --
`core.py`, `simbad/core`, a dotted module path, a mention inside a code span. Everything
else stays: the prose, the traceback, the surrounding directory names, the length. Scoring
the same task twice, once on each bag, isolates the contribution of the names themselves.

Two deliberate choices:

  * Only the stem and an immediately following ".py" are removed, not the whole path.
    Deleting "astroquery/simbad/core.py" outright would also remove "astroquery" and
    "simbad", which are directory names the issue is entitled to mention, and would
    over-state the effect. The residual directory signal is a weaker channel and we say so.
  * Incidental mentions are left alone, since removing them is what the strictest stratum
    already does and it removes ordinary vocabulary along with them.

Two wider arms answer a review that the names-only arm is a *lower* bound on leakage:

  paths    also deletes every component of each key file's path -- the directories and
           the package -- wherever it is written as code. Path BM25 tokenises paths, so
           "astroquery.simbad." left behind by the names arm still points at the file.
  symbols  paths, plus every function, class and method name *defined* in a key file,
           wherever it is written as code: a traceback's "in query_object", a
           backticked `Simbad.query_object`. This is the symbol-level channel a content
           ranking like bm25_issue can use and the names arm does not touch.

Neither is a clean estimate. The wider arms also delete words an issue is entitled to use
-- a directory called "models", a method a user calls by name -- so they over-remove, and
the three arms bracket the leakage rather than measure it.

Writes data/issue_bags_redacted.json          names arm
       data/issue_bags_redacted_paths.json    paths arm
       data/issue_bags_redacted_symbols.json  symbols arm
each {task_id: {"bag": {token: count}, "removed": n}}

Usage:  python -m depgraphs.redact
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import warnings

from depgraphs.issues import load_statements
from depgraphs.leakage import code_spans, in_code
from depgraphs.lexfeat import ROOT, bag_of


def explicit_spans(text: str, spans: list[tuple[int, int]], stem: str) -> list[tuple[int, int]]:
    """Character ranges of this stem's explicit mentions, with any trailing .py."""
    out = []
    rx = re.compile(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(stem), re.I)
    for m in rx.finditer(text):
        i, j = m.start(), m.end()
        before, after = text[max(0, i - 1):i], text[j:j + 3]
        if after.lower().startswith(".py"):
            out.append((i, j + 3))
        elif before in ("/", "\\") or before == "." or after.startswith("."):
            out.append((i, j))
        elif in_code(i, spans):
            out.append((i, j))
    return out


def component_spans(text: str, spans: list[tuple[int, int]], word: str) -> list[tuple[int, int]]:
    """A path component written as code: next to a path or module separator, or in code."""
    out = []
    rx = re.compile(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(word), re.I)
    for m in rx.finditer(text):
        i, j = m.start(), m.end()
        before, after = text[max(0, i - 1):i], text[j:j + 1]
        if before in ("/", "\\", ".") or after in ("/", "\\", ".") or in_code(i, spans):
            out.append((i, j))
    return out


def symbol_spans(text: str, spans: list[tuple[int, int]], name: str) -> list[tuple[int, int]]:
    """An identifier written as code: in a code span, after a dot, or before a call."""
    out = []
    rx = re.compile(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(name))
    for m in rx.finditer(text):
        i, j = m.start(), m.end()
        if in_code(i, spans) or text[max(0, i - 1):i] == "." or text[j:j + 1] == "(":
            out.append((i, j))
    return out


def defined_names(source: str) -> set[str]:
    """Functions, classes and methods defined in a file; dunders and short names excluded."""
    try:
        with warnings.catch_warnings():
            # old code in these repositories uses escapes Python now warns about
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return set()
    return {n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and not n.name.startswith("__") and len(n.name) >= 3}


def redact(text: str, keys: list[str], mode: str = "names",
           symbols: set[str] = frozenset()) -> tuple[str, int]:
    spans = code_spans(text)
    cuts: list[tuple[int, int]] = []
    for path in keys:
        cuts += explicit_spans(text, spans, path.rsplit("/", 1)[-1][:-3])
        if mode in ("paths", "symbols"):
            for part in path.split("/")[:-1]:
                if len(part) >= 2:
                    cuts += component_spans(text, spans, part)
    if mode == "symbols":
        for name in symbols:
            cuts += symbol_spans(text, spans, name)
    if not cuts:
        return text, 0
    cuts.sort()
    merged = [cuts[0]]
    for a, b in cuts[1:]:
        if a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    out, prev = [], 0
    for a, b in merged:
        out.append(text[prev:a])
        prev = b
    out.append(text[prev:])
    # a space, not nothing, so that removing a name cannot weld two words together
    return " ".join(out), len(merged)


ARMS = {"names": "issue_bags_redacted.json",
        "paths": "issue_bags_redacted_paths.json",
        "symbols": "issue_bags_redacted_symbols.json"}


def key_symbols(repo_key: str, sha: str, paths: list[str]) -> set[str]:
    """Names defined in the key files at the task's base commit, read from the clone."""
    d = ROOT / "data" / "repos" / repo_key.replace("/", "__")
    out: set[str] = set()
    for p in paths:
        r = subprocess.run(["git", "cat-file", "-p", "%s:%s" % (sha, p)], cwd=d,
                           capture_output=True)
        if r.returncode == 0:
            out |= defined_names(r.stdout.decode("utf-8", "replace"))
    return out


def main():
    # every task, not just the scored ones: study2 reads this file, so it cannot depend
    # on study2's output without making the pipeline circular
    tasks = [json.loads(l) for l in open(ROOT / "data" / "tasks.jsonl", encoding="utf-8")]
    text_of = load_statements()

    for mode, fname in ARMS.items():
        out, n_changed, n_cuts, n_nosrc = {}, 0, 0, 0
        for t in tasks:
            text = text_of.get(t["instance_id"], "")
            keys = sorted(set(t["keys"]["co_edited"]) | set(t["keys"]["symbol"]))
            syms: set[str] = set()
            if mode == "symbols" and keys:
                syms = key_symbols(t["repo_key"], t["base_commit"], keys)
                n_nosrc += not syms
            clean, k = redact(text, keys, mode, syms)
            out[t["task_id"]] = {"bag": bag_of(clean), "removed": k}
            n_changed += k > 0
            n_cuts += k

        p = ROOT / "data" / fname
        p.write_text(json.dumps(out))
        print("[%s] tasks: %d -> %s" % (mode, len(out), p.name))
        # the rate over *scored* tasks is what the paper quotes; leakage.py computes it,
        # since only that module knows which tasks were scored
        print("  tasks with at least one mention removed: %d" % n_changed)
        print("  mentions removed in total: %d" % n_cuts)
        if mode == "symbols":
            print("  tasks whose key files yielded no definitions: %d" % n_nosrc)


if __name__ == "__main__":
    main()
