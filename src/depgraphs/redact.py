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

Writes data/issue_bags_redacted.json: {task_id: {"bag": {token: count}, "removed": n}}

Usage:  python -m depgraphs.redact
"""
from __future__ import annotations

import json
import re

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


def redact(text: str, keys: list[str]) -> tuple[str, int]:
    spans = code_spans(text)
    cuts: list[tuple[int, int]] = []
    for path in keys:
        cuts += explicit_spans(text, spans, path.rsplit("/", 1)[-1][:-3])
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


def main():
    # every task, not just the scored ones: study2 reads this file, so it cannot depend
    # on study2's output without making the pipeline circular
    tasks = [json.loads(l) for l in open(ROOT / "data" / "tasks.jsonl", encoding="utf-8")]
    text_of = load_statements()

    out, n_changed, n_cuts = {}, 0, 0
    for t in tasks:
        text = text_of.get(t["instance_id"], "")
        keys = sorted(set(t["keys"]["co_edited"]) | set(t["keys"]["symbol"]))
        clean, k = redact(text, keys)
        out[t["task_id"]] = {"bag": bag_of(clean), "removed": k}
        n_changed += k > 0
        n_cuts += k

    p = ROOT / "data" / "issue_bags_redacted.json"
    p.write_text(json.dumps(out))
    print("tasks: %d -> %s" % (len(out), p.name))
    # the rate over *scored* tasks is what the paper quotes; leakage.py computes it,
    # since only that module knows which tasks were scored
    print("  tasks with at least one name removed: %d" % n_changed)
    print("  mentions removed in total: %d" % n_cuts)


if __name__ == "__main__":
    main()
