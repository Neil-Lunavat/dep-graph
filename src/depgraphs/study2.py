"""Structure vs. words: reading orders from the import graph, from the issue text, or both.

Every method returns an ordering of the graph nodes of a repository (seed excluded) and is
scored with the frozen coverage-cost metric: cumulative lines against budgets
250..32000, AUC = mean coverage over the eight doublings.

Families
  structure  seed-conditioned walks over the import graph (bfs_und, hops_lines,
             ppr_und, and directed personalised PageRank in both edge directions)
  global     query-independent repository priors (pagerank, indegree) - no seed, no issue
  lexical    BM25 over identifier bags, queried by the seed file or by the issue text
  fusion     reciprocal-rank fusion of a structural and a lexical ordering
  dense      cosine similarity of D23 code embeddings (embed.py) to the issue or the seed,
             alone and fused; added after review, scored but never ranked, so that no
             rank or test of the other orderings moves

Every ordering is also scored under two alternative cost rules, to show which conclusions
the whole-file, stop-at-overflow metric produces: `auc_skip` skips a file that does not fit
and keeps reading, and `auc_files` charges one unit per file whatever its length.

Writes results/study2/rows.parquet   per task x method x key source
       results/study2/curves.parquet per task x method x key source x budget
       results/study2/top.jsonl.gz   top-100 ordering per task x method (overlap analysis)
"""
from __future__ import annotations

import collections
import gzip
import json
import math
import random
import re
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

import networkx as nx
import numpy as np
import pandas as pd

from depgraphs.lexfeat import ROOT, split_ident

OUT = ROOT / "results" / "study2"
BUDGETS = [250, 500, 1000, 2000, 4000, 8000, 16000, 32000]
FILE_BUDGETS = [1, 2, 4, 8, 16, 32, 64, 128]
RUNS = 3
TOPN = 100
RRF_K = 60


# ----------------------------------------------------------------- loading

def load_repo(repo_dir: str):
    base = ROOT / "data" / "lexfeat" / repo_dir
    commits = json.loads((base / "commits.json").read_text())
    blobs = {}
    with gzip.open(base / "blobs.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            blobs[r["blob"]] = r["bag"]
    return commits, blobs


def load_graph(repo_dir: str, sha: str):
    with gzip.open(ROOT / "data" / "graphs" / repo_dir / (sha + ".json.gz"), "rt",
                   encoding="utf-8") as f:
        g = json.load(f)
    return g["nodes"], g["edges"], g["lines"]


_PATHSPLIT = re.compile(r"[^A-Za-z0-9]+")


def path_bag(path: str) -> dict[str, int]:
    bag = collections.Counter()
    for part in _PATHSPLIT.split(path):
        bag.update(split_ident(part))
    return dict(bag)


# ----------------------------------------------------------------- scoring helpers

def by_score(scores: dict, rng: random.Random) -> list[str]:
    tb = {k: rng.random() for k in sorted(scores)}
    return sorted(scores, key=lambda k: (-scores[k], tb[k]))


def bm25(query: dict[str, int], docs: dict[str, dict], k1=1.5, b=0.75) -> dict[str, float]:
    """Same parameters as the frozen bm25 method; only the query changes."""
    if not docs or not query:
        return {}
    N = len(docs)
    lens = {p: sum(d.values()) for p, d in docs.items()}
    avg = (sum(lens.values()) / N) or 1.0
    df = collections.Counter(t for d in docs.values() for t in d)
    scores = {}
    for p, d in docs.items():
        sc = 0.0
        for t in query:
            tf = d.get(t, 0)
            if tf:
                idf = math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5))
                sc += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * lens[p] / avg))
        scores[p] = sc
    return scores


def rrf(*orders, k=None):
    sc = collections.defaultdict(float)
    kk = RRF_K if k is None else k
    for o in orders:
        for i, p in enumerate(o):
            sc[p] += 1.0 / (kk + i + 1)
    return dict(sc)


# ----------------------------------------------------------------- the methods

def orderings(nodes, edges, lines, seed, bags, issue_bag, rng, issue_bag_rd=None,
              wider=None, emb=None, qv=None, feats=None):
    others = [p for p in nodes if p != seed]
    if not others:
        return {}
    G = nx.DiGraph()
    G.add_nodes_from(nodes)
    G.add_edges_from(e for e in edges if e[0] != e[1])
    U = G.to_undirected(as_view=False)
    cost = {p: max(lines.get(p, 0), 1) for p in nodes}

    out = {}

    # --- structure, seed-conditioned
    dist = nx.single_source_shortest_path_length(U, seed) if seed in U else {}
    far = len(nodes) + 1
    out["bfs_und"] = by_score({p: -dist.get(p, far) for p in others}, rng)
    out["hops_lines"] = sorted(others, key=lambda p: (dist.get(p, far), cost[p], p))
    if G.number_of_edges() and seed in U:
        ppr = nx.pagerank(U, alpha=0.85, personalization={seed: 1.0})
    else:
        ppr = {p: 0.0 for p in nodes}
    out["ppr_und"] = by_score({p: ppr.get(p, 0.0) for p in others}, rng)
    out["ppr_und_pl"] = by_score({p: ppr.get(p, 0.0) / cost[p] for p in others}, rng)

    # Directed variants. An edge a -> b means a imports b, so walking G reaches what the
    # seed depends on and walking G.reverse() reaches what depends on the seed.
    for tag, H in (("out", G), ("in", G.reverse(copy=False))):
        if G.number_of_edges() and seed in H:
            d = nx.pagerank(H, alpha=0.85, personalization={seed: 1.0})
        else:
            d = {q: 0.0 for q in nodes}
        out["ppr_%s" % tag] = by_score({q: d.get(q, 0.0) for q in others}, rng)
        out["ppr_%s_pl" % tag] = by_score(
            {q: d.get(q, 0.0) / cost[q] for q in others}, rng)

    # --- global priors: no seed, no issue
    pr = nx.pagerank(G, alpha=0.85) if G.number_of_edges() else {p: 1.0 for p in nodes}
    out["pagerank"] = by_score({p: pr.get(p, 0.0) for p in others}, rng)
    indeg = dict(G.in_degree())
    out["indegree"] = by_score({p: indeg.get(p, 0) for p in others}, rng)

    # --- lexical
    docs = {p: bags.get(p, {}) for p in others}
    out["bm25_seed"] = by_score(bm25(bags.get(seed, {}), docs), rng) if bags.get(seed) else []
    issue_scores = bm25(issue_bag, docs)
    out["bm25_issue"] = by_score(issue_scores, rng) if issue_scores else []
    out["bm25_issue_pl"] = (by_score({p: s / cost[p] for p, s in issue_scores.items()}, rng)
                            if issue_scores else [])
    pdocs = {p: path_bag(p) for p in others}
    out["path_issue"] = by_score(bm25(issue_bag, pdocs), rng) if issue_bag else []
    # control: the same path matching, queried by the seed path instead of the issue, so
    # any advantage of path_issue that is really just "files near this one in the tree"
    # shows up here too.
    out["path_seed"] = by_score(bm25(path_bag(seed), pdocs), rng)

    # --- fusion
    if out["bm25_issue"]:
        out["rrf_ppr_issue"] = by_score(rrf(out["ppr_und"], out["bm25_issue"]), rng)
        out["rrf_ppr_issue_path"] = by_score(
            rrf(out["ppr_und"], out["bm25_issue"], out["path_issue"]), rng)
        out["rrf_hops_path"] = by_score(rrf(out["hops_lines"], out["path_issue"]), rng)
        out["rrf_hops_issue_path"] = by_score(
            rrf(out["hops_lines"], out["bm25_issue"], out["path_issue"]), rng)
        out["rrf_pprpl_issue_path"] = by_score(
            rrf(out["ppr_und_pl"], out["bm25_issue"], out["path_issue"]), rng)
    else:
        out["rrf_ppr_issue"] = out["ppr_und"]
        out["rrf_ppr_issue_path"] = out["ppr_und"]
        out["rrf_hops_path"] = out["hops_lines"]
        out["rrf_hops_issue_path"] = out["hops_lines"]
        out["rrf_pprpl_issue_path"] = out["ppr_und_pl"]

    # --- references
    sdir = seed.rsplit("/", 1)[0] if "/" in seed else ""
    out["same_dir"] = by_score(
        {p: 1.0 if p.rsplit("/", 1)[0] == sdir else 0.0 for p in others}, rng)
    shuffled = sorted(others)
    rng.shuffle(shuffled)
    out["random"] = shuffled

    # --- fusion controls.
    # A fusion is given more lists than any single method, so "it wins because it sees
    # more input" is the null hypothesis for the whole fusion result. These two are the
    # winning recipes with every issue-derived input replaced by its seed-derived
    # counterpart: same structural component, same number of lists, same BM25 machinery,
    # but nothing from the issue report. A fusion that wins merely by having more lists
    # to blend should win here too. Appended after "random" so that adding them leaves
    # the random stream of every pre-existing method untouched.
    out["rrf_hops_pathseed"] = by_score(rrf(out["hops_lines"], out["path_seed"]), rng)
    out["rrf_pprpl_seedpath"] = by_score(
        rrf(out["ppr_und_pl"], out["bm25_seed"], out["path_seed"]), rng)

    # --- redaction arm.
    # Dropping tasks whose issue names a key file cannot separate "the issue names the
    # answer" from "issues that name the answer are better written". This arm re-runs the
    # issue-queried rankings on the *same* issue with only those names deleted (redact.py),
    # so the pair differs in the names and in nothing else -- not in length, not in the
    # traceback, not in the task. Appended last, again, to leave the random stream alone.
    if issue_bag_rd is not None:
        rd = bm25(issue_bag_rd, docs)
        out["bm25_issue_rd"] = by_score(rd, rng) if rd else []
        out["path_issue_rd"] = (by_score(bm25(issue_bag_rd, pdocs), rng)
                                if issue_bag_rd else [])
        if out["bm25_issue_rd"]:
            out["rrf_hops_path_rd"] = by_score(
                rrf(out["hops_lines"], out["path_issue_rd"]), rng)
            out["rrf_pprpl_issue_path_rd"] = by_score(
                rrf(out["ppr_und_pl"], out["bm25_issue_rd"], out["path_issue_rd"]), rng)
        else:
            out["rrf_hops_path_rd"] = out["hops_lines"]
            out["rrf_pprpl_issue_path_rd"] = out["ppr_und_pl"]

    # --- RRF's k is a free parameter we never varied. Two more settings an order of
    # magnitude either side of the usual 60, so a reader can see whether the fusion result
    # depends on it. Appended last, as every addition to this function is.
    if out["bm25_issue"]:
        for k in (10, 200):
            out["rrf_pprpl_issue_path_k%d" % k] = by_score(
                rrf(out["ppr_und_pl"], out["bm25_issue"], out["path_issue"], k=k), rng)
    else:
        for k in (10, 200):
            out["rrf_pprpl_issue_path_k%d" % k] = out["ppr_und_pl"]

    # --- wider redaction arms (redact.py): names plus every path component ("_rdp"),
    # and that plus the names of functions and classes defined in the key files
    # ("_rds"). The names-only arm above is a lower bound on leakage; these over-remove,
    # so the three bracket it. Appended last, as every addition to this function is.
    for suffix, bag in (wider or {}).items():
        if bag is None:
            continue
        b = bm25(bag, docs)
        out["bm25_issue" + suffix] = by_score(b, rng) if b else []
        out["path_issue" + suffix] = by_score(bm25(bag, pdocs), rng) if bag else []
        if out["bm25_issue" + suffix]:
            out["rrf_hops_path" + suffix] = by_score(
                rrf(out["hops_lines"], out["path_issue" + suffix]), rng)
            out["rrf_pprpl_issue_path" + suffix] = by_score(
                rrf(out["ppr_und_pl"], out["bm25_issue" + suffix],
                    out["path_issue" + suffix]), rng)
        else:
            out["rrf_hops_path" + suffix] = out["hops_lines"]
            out["rrf_pprpl_issue_path" + suffix] = out["ppr_und_pl"]

    # --- dense retrieval (D23 embeddings; embed.py). `emb` maps path -> unit vector and
    # `qv` maps a redaction arm ("none", "names", "paths", "symbols") -> the issue's unit
    # vector. A file without a vector (no blob recorded) scores lowest. The fusions swap the
    # dense ranking in for BM25 over contents, or add it as a fourth list; the issue-free
    # twin swaps the issue for the seed file, as rrf_pprpl_seedpath does. Appended last, as
    # every addition to this function is.
    if emb is not None and qv:
        def dense(q):
            return {p: float(np.dot(q, emb[p])) if p in emb else -2.0 for p in others}

        di = by_score(dense(qv["none"]), rng) if "none" in qv else []
        out["dense_issue"] = di
        out["dense_seed"] = by_score(dense(emb[seed]), rng) if seed in emb else []
        if di:
            out["rrf_pprpl_dense"] = by_score(rrf(out["ppr_und_pl"], di), rng)
            out["rrf_pprpl_dense_path"] = by_score(
                rrf(out["ppr_und_pl"], di, out["path_issue"]), rng)
            out["rrf_pprpl_issue_path_dense"] = by_score(
                rrf(out["ppr_und_pl"], out["bm25_issue"], out["path_issue"], di), rng)
        out["rrf_pprpl_seeddense_path"] = (
            by_score(rrf(out["ppr_und_pl"], out["dense_seed"], out["path_seed"]), rng)
            if out["dense_seed"] else out["ppr_und_pl"])
        for arm, sfx in ARM_SUFFIX.items():
            if arm not in qv or not di:
                continue
            d = by_score(dense(qv[arm]), rng)
            out["dense_issue" + sfx] = d
            pth = out.get("path_issue" + sfx) or []
            out["rrf_pprpl_dense_path" + sfx] = by_score(
                rrf(out["ppr_und_pl"], d, pth), rng)

    # --- published systems' context selectors, as reading orders (methods.py, study 1):
    # Aider's repository map (PageRank over the definition-reference graph, personalised to
    # the file being edited), RepoGraph's two-hop ego graph and LocAgent's typed BFS. Each
    # returns what it would select; the rest of the repository follows in random order so
    # that every ordering covers every file. Scored, never ranked. Appended last.
    if feats is not None:
        from depgraphs import methods as M

        ctx = M.Ctx(nodes, [tuple(e) for e in edges], feats)
        for name, fn in (("sys_aider_repomap", M.aider_repomap),
                         ("sys_repograph_k2", M.repograph_k2),
                         ("sys_locagent_bfs", M.locagent_bfs)):
            head = [p for p in fn(ctx, seed, rng) if p != seed]
            seen = set(head)
            tail = sorted(p for p in others if p not in seen)
            rng.shuffle(tail)
            out[name] = head + tail
    return out


METHODS = ["bfs_und", "hops_lines", "ppr_und", "ppr_und_pl",
           "ppr_out", "ppr_out_pl", "ppr_in", "ppr_in_pl", "pagerank", "indegree",
           "bm25_seed", "path_seed", "bm25_issue", "bm25_issue_pl", "path_issue",
           "rrf_ppr_issue", "rrf_ppr_issue_path", "rrf_hops_path",
           "rrf_hops_issue_path", "rrf_pprpl_issue_path",
           "rrf_hops_pathseed", "rrf_pprpl_seedpath",
           "bm25_issue_rd", "path_issue_rd", "rrf_hops_path_rd",
           "rrf_pprpl_issue_path_rd",
           "rrf_pprpl_issue_path_k10", "rrf_pprpl_issue_path_k200",
           "bm25_issue_rdp", "path_issue_rdp", "rrf_hops_path_rdp", "rrf_pprpl_issue_path_rdp",
           "bm25_issue_rds", "path_issue_rds", "rrf_hops_path_rds", "rrf_pprpl_issue_path_rds",
           "same_dir", "random"]
STRUCTURE = ["bfs_und", "hops_lines", "ppr_und", "ppr_und_pl",
             "ppr_out", "ppr_out_pl", "ppr_in", "ppr_in_pl"]
GLOBAL = ["pagerank", "indegree"]
LEXICAL = ["bm25_seed", "path_seed", "bm25_issue", "bm25_issue_pl", "path_issue"]
FUSION = ["rrf_ppr_issue", "rrf_ppr_issue_path", "rrf_hops_path",
          "rrf_hops_issue_path", "rrf_pprpl_issue_path"]
# Issue-free counterparts of the two winning fusions, used only as controls.
FUSION_CTL = ["rrf_hops_pathseed", "rrf_pprpl_seedpath"]
# The same rankings with the key files' names deleted from the issue (redact.py). Also
# controls: scored so that each can be paired with its unredacted self, never ranked.
REDACTED = {"bm25_issue_rd": "bm25_issue", "path_issue_rd": "path_issue",
            "rrf_hops_path_rd": "rrf_hops_path",
            "rrf_pprpl_issue_path_rd": "rrf_pprpl_issue_path"}
# The wider arms, by suffix. Controls too, paired with the unredacted method.
ARM_SUFFIX = {"names": "_rd", "paths": "_rdp", "symbols": "_rds"}
REDACTED_ALL = {m + sfx: m for sfx in ARM_SUFFIX.values()
                for m in ("bm25_issue", "path_issue", "rrf_hops_path",
                          "rrf_pprpl_issue_path")}
# Sensitivity of the headline fusion to RRF's k. Scored, never ranked.
RRF_K_VARIANTS = ["rrf_pprpl_issue_path_k10", "rrf_pprpl_issue_path_k200"]
# Dense retrieval, added after review. Scored, never ranked, tested in their own family
# (dense.py), so that adding them moves no rank or corrected p-value reported elsewhere.
DENSE = ["dense_issue", "dense_seed", "rrf_pprpl_dense", "rrf_pprpl_dense_path",
         "rrf_pprpl_issue_path_dense", "rrf_pprpl_seeddense_path"]
DENSE_REDACTED = {m + sfx: m for sfx in ARM_SUFFIX.values()
                  for m in ("dense_issue", "rrf_pprpl_dense_path")}
DENSE_ALL = DENSE + list(DENSE_REDACTED)
METHODS += DENSE_ALL
# Published systems' selectors as reading orders (added after review). Scored, never ranked.
SYSTEMS = ["sys_aider_repomap", "sys_repograph_k2", "sys_locagent_bfs"]
METHODS += SYSTEMS
# everything scored that is not a candidate reading order in the paper's ranking
SCORED_ONLY = (set(FUSION_CTL) | set(REDACTED_ALL) | set(RRF_K_VARIANTS) | set(DENSE_ALL)
               | set(SYSTEMS))


def coverage_curve(order, key, cost):
    if not order:
        return [0.0] * len(BUDGETS)
    cum = np.cumsum([cost[p] for p in order])
    hit = np.cumsum([1 if p in key else 0 for p in order])
    out = []
    for b in BUDGETS:
        k = int(np.searchsorted(cum, b, side="right"))
        out.append(float(hit[k - 1]) / len(key) if k else 0.0)
    return out


def skip_mask(order, cost):
    """Which files are read at each budget when a file that would overflow it is skipped
    and reading continues, rather than stopping. Independent of the key, so computed once
    per ordering."""
    mask = np.zeros((len(BUDGETS), len(order)), dtype=bool)
    for i, b in enumerate(BUDGETS):
        used = 0
        for j, p in enumerate(order):
            c = cost[p]
            if used + c <= b:
                used += c
                mask[i, j] = True
                if used == b:
                    break
    return mask


def coverage_skip(order, key, mask):
    if not order:
        return [0.0] * len(BUDGETS)
    isin = np.fromiter((p in key for p in order), dtype=bool, count=len(order))
    return ((mask & isin).sum(axis=1) / len(key)).tolist()


def coverage_files(order, key):
    """Coverage after the first k files, whatever their length."""
    if not order:
        return [0.0] * len(FILE_BUDGETS)
    hit = np.cumsum([1 if p in key else 0 for p in order])
    return [float(hit[min(k, len(order)) - 1]) / len(key) for k in FILE_BUDGETS]


def lines_to_reach(order, key, cost, fracs=(0.5, 1.0)):
    """Lines that must be read before the ordering has covered a fraction of the key.

    Reported instead of coverage at a fixed budget because it is the number a context
    budget is actually spent against. NaN when the ordering never gets there.
    """
    out = [float("nan")] * len(fracs)
    if not order:
        return out
    need = [int(np.ceil(f * len(key))) for f in fracs]
    run = 0
    found = 0
    for p in order:
        run += cost[p]
        if p in key:
            found += 1
            for i, n in enumerate(need):
                if found >= n and np.isnan(out[i]):
                    out[i] = float(run)
        if all(not np.isnan(v) for v in out):
            break
    return out


# ----------------------------------------------------------------- per repo

def load_embeddings(repo_dir: str) -> dict:
    """blob -> unit vector, from embed.py's output; empty if it has not run."""
    out = {}
    for part in sorted((ROOT / "data" / "embeddings").glob(repo_dir + ".p*.npz")):
        z = np.load(part)
        out.update(zip(z["blobs"].tolist(), z["vecs"].astype(np.float32)))
    return out


def run_repo(repo_key: str, tasks: list, issues: dict, redacted: dict | None = None,
             wider: dict | None = None, qvecs: dict | None = None):
    repo_dir = repo_key.replace("/", "__")
    try:
        commits, blobs = load_repo(repo_dir)
    except FileNotFoundError:
        return [], [], []
    rows, curves, tops = [], [], []
    blob_vecs = load_embeddings(repo_dir) if qvecs else {}
    fdir = ROOT / "data" / "features" / repo_dir
    blob_feats = {}
    if (fdir / "blobs.jsonl.gz").exists():
        with gzip.open(fdir / "blobs.jsonl.gz", "rt", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                blob_feats[r.pop("blob")] = r
    for t in tasks:
        sha = t["base_commit"]
        try:
            nodes, edges, lines = load_graph(repo_dir, sha)
        except FileNotFoundError:
            continue
        seed = t["seed"]
        nodeset = set(nodes)
        if seed not in nodeset:
            continue
        k = {s: set(v) for s, v in t["keys"].items()}
        k["union_static"] = k.get("co_edited", set()) | k.get("symbol", set())
        keys = {s: (v & nodeset) - {seed} for s, v in k.items()}
        if not any(keys.values()):
            continue
        mapping = commits.get(sha, {})
        bags = {p: blobs.get(mapping.get(p, ""), {}) for p in nodes}
        issue_bag = issues.get(t["instance_id"], {})
        # keyed by task, because which names count as the answer depends on the seed
        issue_bag_rd = (redacted or {}).get(t["task_id"])
        wide = {sfx: arm.get(t["task_id"]) for sfx, arm in (wider or {}).items()}
        cost = {p: max(lines.get(p, 0), 1) for p in nodes}
        emb = qv = None
        if blob_vecs:
            emb = {p: blob_vecs[mapping[p]] for p in nodes if mapping.get(p) in blob_vecs}
            qv = (qvecs or {}).get(t["task_id"])

        feats = None
        if blob_feats:
            fmap_p = fdir / "commits" / (sha + ".json")
            if fmap_p.exists():
                fmap = json.loads(fmap_p.read_text())
                feats = {p: blob_feats[b] for p, b in fmap.items() if b in blob_feats}

        per_run = []
        for r in range(RUNS):
            rng = random.Random("%s|%d|20260923" % (t["task_id"], r))
            per_run.append(orderings(nodes, edges, lines, seed, bags, issue_bag, rng,
                                     issue_bag_rd, wide, emb, qv, feats))
        if not per_run[0]:
            continue

        masks = {}
        for src, key in keys.items():
            if not key:
                continue
            ideal = sorted(key, key=lambda p: cost[p])
            for m in METHODS + ["oracle"]:
                if (m in DENSE_ALL or m in SYSTEMS) and m not in per_run[0]:
                    continue
                cs, l50, l100, sk, fc = [], [], [], [], []
                for r, run in enumerate(per_run):
                    order = ideal if m == "oracle" else run.get(m, [])
                    cs.append(coverage_curve(order, key, cost))
                    if m == "oracle":
                        mk = skip_mask(order, cost)
                    else:
                        if (m, r) not in masks:
                            masks[(m, r)] = skip_mask(order, cost)
                        mk = masks[(m, r)]
                    sk.append(coverage_skip(order, key, mk))
                    fc.append(coverage_files(order, key))
                    a, b = lines_to_reach(order, key, cost)
                    l50.append(a)
                    l100.append(b)
                c = np.mean(cs, axis=0)
                rows.append({"task_id": t["task_id"], "instance_id": t["instance_id"],
                             "repo_key": repo_key, "file_group": t["file_group"],
                             "method": m, "source": src, "key_size": len(key),
                             "n_nodes": len(nodes),
                             "auc": float(np.mean(c)),
                             "auc_skip": float(np.mean(sk)),
                             "auc_files": float(np.mean(fc)),
                             "lines_half": float(np.nanmean(l50)) if not all(
                                 np.isnan(l50)) else float("nan"),
                             "lines_all": float(np.nanmean(l100)) if not all(
                                 np.isnan(l100)) else float("nan")})
                for i, b in enumerate(BUDGETS):
                    curves.append({"task_id": t["task_id"], "instance_id": t["instance_id"],
                                   "repo_key": repo_key, "method": m, "source": src,
                                   "budget": b, "coverage": float(c[i])})
        tops.append({"task_id": t["task_id"], "instance_id": t["instance_id"],
                     "repo_key": repo_key, "seed": seed, "n_nodes": len(nodes),
                     "keys": {s: sorted(v) for s, v in keys.items()},
                     "lists": {m: per_run[0].get(m, [])[:TOPN] for m in METHODS
                               if (m not in DENSE_ALL and m not in SYSTEMS)
                               or m in per_run[0]}})
    return rows, curves, tops


def main(workers: int = 8):
    tasks = [json.loads(l) for l in open(ROOT / "data" / "tasks.jsonl", encoding="utf-8")]
    raw = json.loads((ROOT / "data" / "issue_bags.json").read_text())
    issues = {k: v["bag"] for k, v in raw.items()}
    rd_path = ROOT / "data" / "issue_bags_redacted.json"
    redacted = ({k: v["bag"] for k, v in json.loads(rd_path.read_text()).items()}
                if rd_path.exists() else {})
    if not redacted:
        print("no redacted issue bags; run `python -m depgraphs.redact` first", flush=True)
    wider = {}
    for sfx, fname in (("_rdp", "issue_bags_redacted_paths.json"),
                       ("_rds", "issue_bags_redacted_symbols.json")):
        wp = ROOT / "data" / fname
        if wp.exists():
            wider[sfx] = {k: v["bag"] for k, v in json.loads(wp.read_text()).items()}
    qpath = ROOT / "data" / "embeddings" / "issues.npz"
    qvecs = collections.defaultdict(dict)
    if qpath.exists():
        z = np.load(qpath)
        for i, v in zip(z["ids"].tolist(), z["vecs"].astype(np.float32)):
            tid, arm = i.rsplit("|", 1)
            qvecs[tid][arm] = v
    else:
        print("no issue embeddings; dense orderings not scored", flush=True)
    by = collections.defaultdict(list)
    for t in tasks:
        by[t["repo_key"]].append(t)
    OUT.mkdir(parents=True, exist_ok=True)
    rows, curves = [], []
    done = 0
    with gzip.open(OUT / "top.jsonl.gz", "wt", encoding="utf-8") as tf, \
            ProcessPoolExecutor(workers) as ex:
        futs = {ex.submit(run_repo, k, v, issues, redacted, wider,
                          {t["task_id"]: qvecs[t["task_id"]] for t in v
                           if t["task_id"] in qvecs}): k
                for k, v in by.items()}
        for f in as_completed(futs):
            r, c, tops = f.result()
            rows += r
            curves += c
            for rec in tops:
                tf.write(json.dumps(rec) + "\n")
            done += 1
            print("[%d/%d] %s tasks=%d" % (done, len(by), futs[f], len(tops)), flush=True)
    pd.DataFrame(rows).to_parquet(OUT / "rows.parquet", index=False)
    pd.DataFrame(curves).to_parquet(OUT / "curves.parquet", index=False)
    print("rows", len(rows), "curves", len(curves))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
