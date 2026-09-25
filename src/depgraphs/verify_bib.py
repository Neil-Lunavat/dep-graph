"""Check every arXiv entry in paper/references.bib against arXiv itself.

For each entry with an `eprint`, fetch the abstract page and compare its title and first
author's family name with the bibliography's. Anything that does not match is printed as
CHECK; the exit status is the number of such entries. Needs network access to arxiv.org.

Usage:  python -m depgraphs.verify_bib
"""
from __future__ import annotations

import html
import re
import subprocess
import sys

from depgraphs.lexfeat import ROOT


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", html.unescape(s).lower())


def family(name: str) -> str:
    name = name.strip()
    return norm(name.split(",")[0] if "," in name else name.split()[-1]) if name else ""


def main() -> int:
    bib = (ROOT / "paper" / "references.bib").read_text(encoding="utf-8")
    bad = 0
    for e in re.split(r"\n@", bib):
        m = re.search(r"eprint\s*=\s*\{([^}]+)\}", e)
        if not m:
            continue
        key = e.split("{", 1)[1].split(",", 1)[0]
        t = re.search(r"\btitle\s*=\s*\{(.+?)\},\s*\n", e, re.S)
        a = re.search(r"author\s*=\s*\{(.+?)\},\s*\n", e, re.S)
        bib_title = re.sub(r"[{}\\\s]+", " ", t.group(1)).strip() if t else ""
        bib_author = a.group(1).split(" and ")[0] if a else ""
        page = subprocess.run(["curl", "-sSL", "https://arxiv.org/abs/" + m.group(1)],
                              capture_output=True, text=True).stdout
        at = re.search(r'citation_title" content="([^"]*)"', page)
        aa = re.search(r'citation_author" content="([^"]*)"', page)
        ax_title = html.unescape(at.group(1)) if at else ""
        ax_author = html.unescape(aa.group(1)) if aa else ""
        ok = norm(bib_title) == norm(ax_title) and family(bib_author) == norm(
            ax_author.split(",")[0])
        bad += not ok
        print("%-5s %-32s %s%s" % ("ok" if ok else "CHECK", key, m.group(1), "" if ok else
              "  bib: %r / %r   arXiv: %r / %r" % (bib_title, bib_author, ax_title, ax_author)))
    print("%d entr%s to check" % (bad, "y" if bad == 1 else "ies"))
    return bad


if __name__ == "__main__":
    sys.exit(main())
