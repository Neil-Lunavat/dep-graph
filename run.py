"""Single entry point for the main pipeline: `python run.py <stage> ...`, or `all` in order.

Each stage is idempotent and cached. Two things run outside it: the dense embeddings
(`src/depgraphs/embed.py`, its own environment, before `study2`) and the external and
ContextBench trees, which run these same stages under DEPGRAPHS_ROOT. README.md gives the
full sequence.
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
def envs():
    from depgraphs import envs as e
    e.main()


@stage
def candidates():
    from depgraphs import candidates as c
    c.main()


@stage
def ghmeta():
    from depgraphs import ghmeta as g
    g.main()


@stage
def r2_variant():
    from depgraphs import r2_variant as r
    r.main()


@stage
def gate_a():
    from depgraphs import gate_a as g, gate_a_extra as x
    g.main()
    x.strata()
    x.cost()


@stage
def sample():
    from depgraphs import sample as s
    s.main()


@stage
def graphs():
    from depgraphs import graphs as g
    g.main()


@stage
def keys_static():
    from depgraphs import keys_static as k
    k.main()


@stage
def tasks():
    from depgraphs import tasks as t
    t.main()


@stage
def lexfeat():
    from depgraphs import lexfeat as l
    l.main()


@stage
def issues():
    from depgraphs import issues as i
    i.main()


@stage
def redact():
    from depgraphs import redact as r
    r.main()


@stage
def features():
    from depgraphs import features as f
    f.main()


@stage
def study2():
    from depgraphs import study2 as s
    s.main()


@stage
def tokcost():
    from depgraphs import tokcost as t
    t.main()


@stage
def leakage():
    from depgraphs import leakage as l
    l.main()


@stage
def ceiling():
    from depgraphs import ceiling as c
    c.main()


@stage
def ball():
    from depgraphs import ball as b
    b.main()


@stage
def analysis2():
    from depgraphs import analysis2 as a
    a.main()


@stage
def metric():
    from depgraphs import metric as m
    m.main()


@stage
def dense():
    from depgraphs import dense as d
    d.main()


@stage
def seedless():
    from depgraphs import seedless as s
    s.main()


@stage
def maketables():
    from depgraphs import maketables as t
    t.main()


@stage
def checknums():
    from depgraphs import checknums as c
    c.main()


@stage
def claims():
    from depgraphs import claims as c
    c.main()


@stage
def builders_prep():
    from depgraphs.graph import compare
    compare.main(compare.rule_repos() + compare.EXTRA_REPOS)


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
