"""Does the issue text name the files in the answer key?

Path-based lexical retrieval scores a query against the file's path, so an issue that
writes out "astroquery/simbad/core.py" hands that method the answer. The looser form
matters just as much: BM25 tokenises the path into subtokens, so a bare stem ("core") is
enough. Both are recorded here, over the union of the two keys, one row per task.

The union is deliberate. A task's issue either names a key file or it does not, and using
a different stratum per evidence source would compare the two keys on different subsets,
which is the confound this file exists to measure.

A stem match is not automatically leakage. An issue about "models" and a key file called
models.py share a word because the project's vocabulary is its domain vocabulary, which is
signal a retrieval method is entitled to use. So each stem mention is also classified:

  explicit     the mention is written as code -- "core.py", "simbad/core", a dotted module
               path, inside backticks, or inside a fenced or indented code block
  incidental   the stem occurs only as an ordinary English word

Writes results/study2/issue_path_leak.csv

Usage:  python -m depgraphs.leakage
"""
from __future__ import annotations

import json
import re

import pandas as pd

from depgraphs.issues import load_statements
from depgraphs.lexfeat import ROOT
from depgraphs.study2 import OUT

# Spans of an issue that are code rather than prose. Fenced blocks first, so that a stray
# backtick inside a fence cannot start a span of its own.
FENCE = re.compile(r"```.*?```|~~~.*?~~~", re.S)
INLINE = re.compile(r"`[^`\n]*`")
INDENTED = re.compile(r"^(?: {4,}|\t)\S.*$", re.M)


def code_spans(text: str) -> list[tuple[int, int]]:
    out = []
    for rx in (FENCE, INLINE, INDENTED):
        out += [(m.start(), m.end()) for m in rx.finditer(text)]
    return out


def in_code(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(a <= pos < b for a, b in spans)


def classify(text: str, spans: list[tuple[int, int]], stem: str) -> str:
    """"none", "incidental" or "explicit" for one key file's stem."""
    # Case-insensitive, because the retrieval tokeniser lowercases: an issue saying "not"
    # does put the token that Not.py contributes into the query.
    seen = False
    rx = re.compile(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(stem), re.I)
    for m in rx.finditer(text):
        seen = True
        i, j = m.start(), m.end()
        before, after = text[max(0, i - 1):i], text[j:j + 3]
        if after.lower().startswith(".py"):   # core.py
            return "explicit"
        if before in ("/", "\\"):             # simbad/core
            return "explicit"
        if before == "." or after.startswith("."):   # pkg.core / core.fn
            return "explicit"
        if in_code(i, spans):                 # `core`, or inside a block
            return "explicit"
    return "incidental" if seen else "none"


def main():
    tasks = [json.loads(l) for l in open(ROOT / "data" / "tasks.jsonl", encoding="utf-8")]
    scored = set(pd.read_parquet(OUT / "rows.parquet")["task_id"].unique())
    text_of = load_statements()

    recs = []
    for t in tasks:
        if t["task_id"] not in scored:
            continue
        text = text_of.get(t["instance_id"], "")
        spans = code_spans(text)
        keys = sorted(set(t["keys"]["co_edited"]) | set(t["keys"]["symbol"]))
        kinds = [classify(text, spans, p.rsplit("/", 1)[-1][:-3]) for p in keys]
        recs.append({
            "task_id": t["task_id"],
            "instance_id": t["instance_id"],
            "key_n": len(keys),
            "full": int(any(p in text for p in keys)),
            "stem": int(any(k != "none" for k in kinds)),
            "explicit": int(any(k == "explicit" for k in kinds)),
            "incidental": int(any(k == "incidental" for k in kinds)),
            "seed_full": t["seed"] in text,
            "any_full": any(p in text for p in keys),
        })

    df = pd.DataFrame(recs)
    p = OUT / "issue_path_leak.csv"
    df.to_csv(p, index=False)
    n = len(df)
    print("tasks: %d -> %s" % (n, p.name))
    for c in ("full", "stem", "explicit", "incidental"):
        print("  %-11s %5d  (%.1f%%)" % (c, df[c].sum(), 100 * df[c].mean()))
    strict = df[(df["full"] == 0) & (df["stem"] == 0)]
    print("  strict stratum (no full path, no stem): %d (%.1f%%)"
          % (len(strict), 100 * len(strict) / n))


if __name__ == "__main__":
    main()
