"""Single entry point. `python run.py all` regenerates every result from scratch.

Stages are added as steps are completed. Each stage is idempotent and cached.
"""
from __future__ import annotations

import sys

STAGES = {}


def stage(fn):
    STAGES[fn.__name__] = fn
    return fn


@stage
def datasets():
    from depgraphs import datasets as d
    d.download()


@stage
def recount():
    from depgraphs import recount as r
    r.main()


@stage
def candidates():
    from depgraphs import candidates as c
    c.main()


def main(argv):
    names = argv[1:] or ["all"]
    if names == ["all"]:
        names = list(STAGES)
    for n in names:
        if n not in STAGES:
            sys.exit(f"unknown stage {n!r}; choose from: all, {', '.join(STAGES)}")
        print(f"== {n}", flush=True)
        STAGES[n]()


if __name__ == "__main__":
    main(sys.argv)
