"""Step 6: every method in paper/methods.md. method(ctx, seed, rng) -> ordered list of files.

`Ctx` holds only base-commit information (graph, per-file features, prior history,
embeddings). Nothing here reads the answer key except the `oracle` reference, which is
labelled as such and receives the key explicitly.
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from functools import cached_property

import networkx as nx


@dataclass
class Ctx:
    nodes: list[str]
    edges: list[tuple[str, str]]
    feats: dict[str, dict] = field(default_factory=dict)      # path -> features
    cochange: dict[str, dict[str, float]] = field(default_factory=dict)  # seed -> {file: score}
    embed: dict[str, list[float]] | None = None                # path -> unit vector

    @cached_property
    def G(self) -> nx.DiGraph:
        g = nx.DiGraph()
        g.add_nodes_from(self.nodes)
        g.add_edges_from(e for e in self.edges if e[0] != e[1])
        return g

    @cached_property
    def U(self) -> nx.Graph:
        return self.G.to_undirected(as_view=False)

    @cached_property
    def _defs(self) -> dict[str, list[str]]:
        definers = defaultdict(list)
        for p in self.nodes:
            for d in self.feats.get(p, {}).get("defs", []):
                definers[d].append(p)
        return {k: v for k, v in definers.items() if len(v) <= 5}

    def _ref_graph(self, key: str) -> nx.DiGraph:
        r = nx.DiGraph()
        r.add_nodes_from(self.nodes)
        w = Counter()
        idents = defaultdict(set)
        for a in self.nodes:
            for name in self.feats.get(a, {}).get(key, []):
                for b in self._defs.get(name, ()):
                    if b != a:
                        w[(a, b)] += 1
                        idents[(a, b)].add(name)
        for (a, b), c in w.items():
            r.add_edge(a, b, weight=c, idents=idents[(a, b)])
        return r

    @cached_property
    def R(self) -> nx.DiGraph:
        return self._ref_graph("refs")

    @cached_property
    def C(self) -> nx.DiGraph:
        return self._ref_graph("calls")

    # ---- seed-independent rankings, computed once per commit
    @cached_property
    def pagerank(self):
        return nx.pagerank(self.G, alpha=0.85) if self.G.number_of_edges() else {n: 1 for n in self.nodes}

    @cached_property
    def hits_auth(self):
        if not self.G.number_of_edges():
            return {n: 0 for n in self.nodes}
        try:
            return nx.hits(self.G, max_iter=1000)[1]
        except nx.PowerIterationFailedConvergence:
            return dict(self.G.in_degree())

    @cached_property
    def betweenness(self):
        n = self.G.number_of_nodes()
        return nx.betweenness_centrality(self.G, k=None if n <= 1500 else 500, seed=0)

    @cached_property
    def closeness(self):
        return nx.closeness_centrality(self.U)

    @cached_property
    def louvain(self):
        if not self.U.number_of_edges():
            return [{n} for n in self.nodes]
        return nx.community.louvain_communities(self.U, resolution=1, seed=0)

    @cached_property
    def labelprop(self):
        return list(nx.community.asyn_lpa_communities(self.U, seed=0))

    def lines(self, p: str) -> int:
        return self.feats.get(p, {}).get("lines", 0)


# ------------------------------------------------------------------ helpers

def shuffled(items, rng: random.Random) -> list:
    items = sorted(items)
    rng.shuffle(items)
    return items


def by_score(scores: dict, rng: random.Random, exclude=(), keep=lambda s: True) -> list:
    """Descending score; ties broken by a random key drawn per item (D21)."""
    tb = {k: rng.random() for k in sorted(scores)}
    return [k for k in sorted(scores, key=lambda k: (-scores[k], tb[k]))
            if k not in exclude and keep(scores[k])]


def by_level(levels: dict, rng: random.Random, seed: str, secondary=None) -> list:
    """Ascending level (hop), then optional secondary key, then random."""
    tb = {k: rng.random() for k in sorted(levels)}
    sec = secondary or (lambda k: 0)
    return [k for k in sorted(levels, key=lambda k: (levels[k], sec(k), tb[k])) if k != seed]


def bfs_levels(g, seed):
    return nx.single_source_shortest_path_length(g, seed)


# ------------------------------------------------------------------ traversal

def bfs_fwd(c, s, rng): return by_level(bfs_levels(c.G, s), rng, s)
def bfs_rev(c, s, rng): return by_level(bfs_levels(c.G.reverse(copy=False), s), rng, s)
def bfs_und(c, s, rng): return by_level(bfs_levels(c.U, s), rng, s)


def dfs_und(c, s, rng):
    out, seen, stack = [], {s}, [s]
    # iterative DFS preorder with random neighbour order
    order = {}
    while stack:
        v = stack.pop()
        if v != s:
            out.append(v)
        nbrs = shuffled(c.U.neighbors(v), rng)
        for w in reversed(nbrs):
            if w not in seen:
                seen.add(w)
                stack.append(w)
    return out


def ids_und(c, s, rng):
    out, seen = [], {s}
    maxd = max(bfs_levels(c.U, s).values(), default=0)
    for limit in range(1, maxd + 1):
        stack = [(s, 0)]
        visited = {s}
        while stack:
            v, d = stack.pop()
            if v not in seen:
                seen.add(v)
                out.append(v)
            if d < limit:
                for w in reversed(shuffled(c.U.neighbors(v), rng)):
                    if w not in visited:
                        visited.add(w)
                        stack.append((w, d + 1))
    return out


# ------------------------------------------------------------------ closures

def _reach(g, s): return set(nx.descendants(g, s))
def closure_fwd(c, s, rng): return shuffled(_reach(c.G, s), rng)
def closure_rev(c, s, rng): return shuffled(nx.ancestors(c.G, s), rng)
def closure_comb(c, s, rng): return shuffled(_reach(c.G, s) | nx.ancestors(c.G, s), rng)


def _khop(c, s, k):
    return {n for n, d in nx.single_source_shortest_path_length(c.U, s, cutoff=k).items() if n != s}


def khop1_und(c, s, rng): return shuffled(_khop(c, s, 1), rng)
def khop2_und(c, s, rng): return shuffled(_khop(c, s, 2), rng)
def closure_fwd_trim(c, s, rng): return by_level(bfs_levels(c.G, s), rng, s)  # nearest first


def topo_fwd(c, s, rng):
    reach = _reach(c.G, s)
    if not reach:
        return []
    sub = c.G.subgraph(reach | {s})
    cond = nx.condensation(sub)
    members = cond.graph["mapping"]
    groups = defaultdict(list)
    for f, cid in members.items():
        if f != s:
            groups[cid].append(f)
    # Kahn on the condensation with random tie-breaking; dependencies first = reverse topo
    indeg = {n: 0 for n in cond.nodes}
    for u, v in cond.edges:
        indeg[v] += 1
    ready = [n for n in cond.nodes if indeg[n] == 0]
    topo = []
    while ready:
        ready.sort()
        n = ready.pop(rng.randrange(len(ready)))
        topo.append(n)
        for v in sorted(cond.successors(n)):
            indeg[v] -= 1
            if indeg[v] == 0:
                ready.append(v)
    out = []
    for cid in reversed(topo):
        out += shuffled(groups.get(cid, []), rng)
    return out


# ------------------------------------------------------------------ ranking

def pagerank(c, s, rng): return by_score(c.pagerank, rng, exclude={s})


def _ppr(g, s):
    if g.number_of_edges() == 0:
        return {}
    pers = {n: 0.0 for n in g.nodes}
    pers[s] = 1.0
    return nx.pagerank(g, alpha=0.85, personalization=pers)


def ppr_und(c, s, rng): return by_score(_ppr(c.U, s), rng, exclude={s}, keep=lambda v: v > 0)
def ppr_fwd(c, s, rng): return by_score(_ppr(c.G, s), rng, exclude={s}, keep=lambda v: v > 0)
def indegree(c, s, rng): return by_score(dict(c.G.in_degree()), rng, exclude={s})
def hits_auth(c, s, rng): return by_score(c.hits_auth, rng, exclude={s})
def betweenness(c, s, rng): return by_score(c.betweenness, rng, exclude={s})
def closeness(c, s, rng): return by_score(c.closeness, rng, exclude={s})


def robillard(c, s, rng):
    S = {s}
    out = []
    nbr = {n: set(c.U.neighbors(n)) for n in c.U.nodes}
    while True:
        cand = {x for y in S for x in nbr[y]} - S
        if not cand:
            return out
        scores = {}
        for x in cand:
            k = len(nbr[x] & S)
            scores[x] = (k / len(nbr[x])) * (k / len(S))
        best = by_score(scores, rng)[0]
        S.add(best)
        out.append(best)


# ------------------------------------------------------------------ clustering

def _community(parts, s):
    return next((p for p in parts if s in p), {s}) - {s}


def louvain(c, s, rng): return shuffled(_community(c.louvain, s), rng)
def labelprop(c, s, rng): return shuffled(_community(c.labelprop, s), rng)


def directory(c, s, rng):
    """Folder-tree distance to the seed's folder (steps up + steps down), nearest first."""
    sp = s.split("/")[:-1]

    def dist(p):
        pp = p.split("/")[:-1]
        k = 0
        while k < min(len(sp), len(pp)) and sp[k] == pp[k]:
            k += 1
        return (len(sp) - k) + (len(pp) - k)
    return by_score({p: -dist(p) for p in c.nodes if p != s}, rng)


# ------------------------------------------------------------------ retrieval, history

def bm25(c, s, rng, k1=1.5, b=0.75):
    docs = {p: c.feats.get(p, {}).get("bag", {}) for p in c.nodes if p != s}
    q = c.feats.get(s, {}).get("bag", {})
    if not docs or not q:
        return []
    N = len(docs)
    lens = {p: sum(d.values()) for p, d in docs.items()}
    avg = sum(lens.values()) / N or 1
    df = Counter(t for d in docs.values() for t in d)
    scores = {}
    for p, d in docs.items():
        sc = 0.0
        for t in q:
            tf = d.get(t, 0)
            if tf:
                idf = math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5))
                sc += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * lens[p] / avg))
        scores[p] = sc
    return by_score(scores, rng, keep=lambda v: v > 0)


def embedding(c, s, rng):
    if not c.embed or s not in c.embed:
        return []
    q = c.embed[s]
    scores = {p: sum(a * b for a, b in zip(q, v)) for p, v in c.embed.items() if p != s}
    return by_score(scores, rng)


def cochange(c, s, rng):
    nodes = set(c.nodes)
    scores = {f: v for f, v in c.cochange.get(s, {}).items() if f in nodes}
    return by_score(scores, rng, exclude={s}, keep=lambda v: v > 0)


# ------------------------------------------------------------------ published (adapted)

def _aider_weight(name: str) -> float:
    mul = 1.0
    if len(name) >= 8 and ("_" in name or any(ch.isupper() for ch in name[1:])):
        mul *= 10
    if name.startswith("_"):
        mul *= 0.1
    return mul


def aider_repomap(c, s, rng):
    g = nx.DiGraph()
    g.add_nodes_from(c.nodes)
    for a, b, d in c.R.edges(data=True):
        w = sum(_aider_weight(n) for n in d["idents"]) * math.sqrt(d["weight"]) / max(len(d["idents"]), 1)
        g.add_edge(a, b, weight=w)
    if not g.number_of_edges():
        return []
    pers = {n: 0.0 for n in g.nodes}
    pers[s] = 1.0
    pr = nx.pagerank(g, alpha=0.85, personalization=pers, weight="weight")
    return by_score(pr, rng, exclude={s}, keep=lambda v: v > 0)


def repograph_k1(c, s, rng):
    lv = nx.single_source_shortest_path_length(c.R.to_undirected(as_view=True), s, cutoff=1)
    return shuffled(set(lv) - {s}, rng)


def repograph_k2(c, s, rng):
    lv = nx.single_source_shortest_path_length(c.R.to_undirected(as_view=True), s, cutoff=2)
    return by_level(lv, rng, s)


def locagent_bfs(c, s, rng):
    u = nx.Graph()
    u.add_nodes_from(c.nodes)
    u.add_edges_from(c.U.edges, kind=0)
    for a, b in c.R.to_undirected(as_view=True).edges:
        if not u.has_edge(a, b):
            u.add_edge(a, b, kind=1)
    lv = nx.single_source_shortest_path_length(u, s)
    # edge type of the first edge that reached the node: import (0) before reference (1)
    kind = {}
    for v, d in lv.items():
        if d == 0:
            continue
        kind[v] = min(u.edges[p, v]["kind"] for p in u.neighbors(v) if lv.get(p) == d - 1)
    return by_level(lv, rng, s, secondary=lambda k: kind.get(k, 0))


def cosil_bfs(c, s, rng):
    return by_level(nx.single_source_shortest_path_length(c.C.to_undirected(as_view=True), s), rng, s)


# ------------------------------------------------------------------ references

def random_order(c, s, rng): return shuffled(set(c.nodes) - {s}, rng)


def same_dir(c, s, rng):
    d = s.rsplit("/", 1)[0] if "/" in s else ""
    return shuffled({p for p in c.nodes if p != s and (p.rsplit("/", 1)[0] if "/" in p else "") == d}, rng)


def whole_repo(c, s, rng): return sorted(set(c.nodes) - {s})
def seed_alone(c, s, rng): return []


def oracle(c, s, rng, key: set):
    """Cheat ceiling: key files, cheapest first. Uses the answer key — a reference only."""
    return by_score({p: -c.lines(p) for p in key if p != s and p in set(c.nodes)}, rng)


METHODS = {
    "bfs_fwd": bfs_fwd, "bfs_rev": bfs_rev, "bfs_und": bfs_und, "dfs_und": dfs_und,
    "ids_und": ids_und, "closure_fwd": closure_fwd, "closure_rev": closure_rev,
    "closure_comb": closure_comb, "khop1_und": khop1_und, "khop2_und": khop2_und,
    "closure_fwd_trim": closure_fwd_trim, "topo_fwd": topo_fwd, "pagerank": pagerank,
    "ppr_und": ppr_und, "ppr_fwd": ppr_fwd, "indegree": indegree, "hits_auth": hits_auth,
    "betweenness": betweenness, "closeness": closeness, "robillard": robillard,
    "louvain": louvain, "labelprop": labelprop, "directory": directory, "bm25": bm25,
    "embedding": embedding, "cochange": cochange, "aider_repomap": aider_repomap,
    "repograph_k1": repograph_k1, "repograph_k2": repograph_k2,
    "locagent_bfs": locagent_bfs, "cosil_bfs": cosil_bfs,
    "random": random_order, "same_dir": same_dir, "whole_repo": whole_repo,
    "seed_alone": seed_alone,
}
REFERENCES = {"random", "same_dir", "whole_repo", "seed_alone", "oracle"}
