"""Collapse import loops (SCCs) and keep the mapping back to member files."""
from __future__ import annotations

import networkx as nx


def to_nx(nodes, edges) -> nx.DiGraph:
    g = nx.DiGraph()
    g.add_nodes_from(nodes)
    for (a, b), w in edges.items():
        g.add_edge(a, b, weight=w)
    return g


def condense(g: nx.DiGraph) -> tuple[nx.DiGraph, dict[int, list[str]], dict[str, int]]:
    """Returns (condensation DAG, clump id -> sorted member files, file -> clump id).

    Clump ids are assigned in sorted order of each clump's smallest member path, so they
    are stable across runs (networkx's own numbering depends on iteration order).
    """
    sccs = sorted((sorted(c) for c in nx.strongly_connected_components(g)), key=lambda c: c[0])
    member = {f: i for i, c in enumerate(sccs) for f in c}
    dag = nx.DiGraph()
    dag.add_nodes_from(range(len(sccs)))
    for a, b in g.edges:
        if member[a] != member[b]:
            dag.add_edge(member[a], member[b])
    return dag, dict(enumerate(sccs)), member
