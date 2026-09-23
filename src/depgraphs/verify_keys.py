"""Pull the ground-truth passages out of the related-work PDFs.

Every row of the prior-work table in the paper asserts what a published system grades
itself against. Those assertions have to come from the papers, so this extracts the
candidate passages and prints them for reading. It decides nothing on its own: it narrows
a 12-page PDF to the handful of sentences where a ground-truth definition can live, and a
human (or a model that has actually read the output) makes the call.

Usage:  python -m depgraphs.verify_keys [name-fragment ...]
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PAPERS = ROOT / "papers"

# Phrases that sit next to a ground-truth definition. Deliberately broad: a missed
# passage is a silent error, an extra one costs a few seconds of reading.
CUES = [
    "ground truth", "ground-truth", "groundtruth",
    "gold patch", "gold patches", "golden", "oracle patch",
    "target location", "target file", "correct location",
    "modified file", "modified function", "files modified", "changed file",
    "we consider", "is considered", "are considered",
    "localization accuracy", "localisation accuracy", "acc@", "recall@", "hit@",
    "evaluation metric", "we evaluate", "evaluation setup",
    "annotat",  # covers annotated / annotators / annotation
    "relevant file", "relevance",
]

SENT = re.compile(r"(?<=[.;:])\s+")


def text_of(pdf: pathlib.Path) -> str:
    try:
        import fitz
        with fitz.open(pdf) as doc:
            return "\n".join(p.get_text() for p in doc)
    except Exception:
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(str(pdf)).pages)


def clean(t: str) -> str:
    t = t.replace("­", "").replace("-\n", "")
    return re.sub(r"\s+", " ", t)


def passages(t: str, window: int = 240) -> list[str]:
    low = t.lower()
    hits, seen = [], []
    for cue in CUES:
        start = 0
        while True:
            i = low.find(cue, start)
            if i < 0:
                break
            start = i + len(cue)
            a, b = max(0, i - window), min(len(t), i + window)
            if any(abs(i - j) < window for j in seen):
                continue
            seen.append(i)
            hits.append("... " + t[a:b].strip() + " ...")
    return hits


def main(frags: list[str]):
    if not PAPERS.exists():
        print("no papers/ directory yet"); return
    pdfs = sorted(PAPERS.glob("*.pdf"))
    if frags:
        pdfs = [p for p in pdfs if any(f.lower() in p.name.lower() for f in frags)]
    for pdf in pdfs:
        t = clean(text_of(pdf))
        ps = passages(t)
        print("=" * 78)
        print(pdf.name, " chars=%d  passages=%d" % (len(t), len(ps)))
        print("=" * 78)
        for p in ps[:14]:
            print(" -", p.replace("\n", " ")[:520])
            print()
        if not ps:
            print("  NO CUE MATCHED - read this one manually")
        print()


if __name__ == "__main__":
    main(sys.argv[1:])
