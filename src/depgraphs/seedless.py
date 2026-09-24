"""Without a free seed: localise from the issue first, then read.

Every task in study2 hands the orderings the file being changed. An agent is not handed it;
it must find it from the issue, which is where agents are known to struggle. This module
removes the free seed. For each pull request, the issue alone picks a starting file -- the
top of the reciprocal-rank fusion of BM25 over file contents and BM25 over file paths, the
two issue-only lexical rankings of study2 -- and every seed-conditioned ordering then walks
from that *predicted* file, which it reads first. Issue-only orderings need no seed and are
scored unchanged, over the whole repository.

The unit is the pull request, not the task, since there is no seed to make tasks from. Two
keys, restricted to graph nodes as usual:
  edited  every existing source file the pull request edits, the true seeds included, so
          that finding the file to change is part of what is scored (single-file pull
          requests have a one-file key)
  symbol  every file defining a name the change uses (keys_static), the edited ones included

Added after review and exploratory: nothing in it was fixed in advance (POSTHOC.md). It
changes no result of study2 and uses its methods unchanged.

Writes results/seedless/rows.parquet, results/seedless/tests.csv, results/seedless/summary.json
Usage:  python -m depgraphs.seedless [workers]      score, then summarise
        python -m depgraphs.seedless summarise      summarise only
"""
from __future__ import annotations

import collections
import json
import random
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd

from depgraphs.issues import load_statements
from depgraphs.leakage import classify, code_spans
from depgraphs.lexfeat import ROOT
from depgraphs.study2 import (OUT as S2, RUNS, bm25, by_score, coverage_curve, load_embeddings,
                              load_graph, load_repo, orderings, path_bag, rrf, skip_mask,
                              coverage_skip)

OUT = ROOT / "results" / "seedless"
FROM_SEED = ["hops_lines", "ppr_und_pl", "ppr_out_pl", "rrf_hops_path",
             "rrf_pprpl_issue_path", "rrf_pprpl_dense_path"]
ISSUE_ONLY = ["bm25_issue", "path_issue", "dense_issue"]


def named(text: str, files: list[str]) -> bool:
    """Does the issue name any of these files as code (leakage.classify's 'explicit')?"""
    spans = code_spans(text)
    return any(f in text or classify(text, spans, f.rsplit("/", 1)[-1][:-3]) == "explicit"
               for f in files)


def run_repo(repo_key, prs, issues, texts, qvecs):
    repo_dir = repo_key.replace("/", "__")
    commits, blobs = load_repo(repo_dir)
    blob_vecs = load_embeddings(repo_dir) if qvecs else {}
    rows = []
    for pr in prs:
        sha = pr["base_commit"]
        nodes, edges, lines = load_graph(repo_dir, sha)
        nodeset = set(nodes)
        ks = json.loads((ROOT / "data" / "keys_static" / (pr["instance_id"] + ".json"))
                        .read_text())
        keys = {"edited": set(ks.get("co_edited", [])) & nodeset,
                "symbol": set(ks.get("symbol", {})) & nodeset}
        if not keys["edited"]:
            continue
        mapping = commits.get(sha, {})
        bags = {p: blobs.get(mapping.get(p, ""), {}) for p in nodes}
        ib = issues.get(pr["instance_id"], {})
        cost = {p: max(lines.get(p, 0), 1) for p in nodes}
        emb = ({p: blob_vecs[mapping[p]] for p in nodes if mapping.get(p) in blob_vecs}
               if blob_vecs else None)
        qv = qvecs.get(pr["instance_id"]) if qvecs else None

        per_run, guess, guess_d = [], None, None
        for r in range(RUNS):
            rng = random.Random("%s|seedless|%d" % (pr["instance_id"], r))
            docs = {p: bags.get(p, {}) for p in nodes}
            pdocs = {p: path_bag(p) for p in nodes}
            b = by_score(bm25(ib, docs), rng) if ib else []
            pth = by_score(bm25(ib, pdocs), rng) if ib else []
            loc = by_score(rrf(b, pth), rng) if ib else []
            if not loc:
                break
            s = loc[0]
            if r == 0:
                guess = s
            o = orderings(nodes, edges, lines, s, bags, ib, rng, None, None, emb,
                          {"none": qv} if qv is not None else None)
            run = {m: [s] + o[m] for m in FROM_SEED if m in o}
            run["bm25_issue"], run["path_issue"], run["localiser"] = b, pth, loc
            sh = sorted(nodes)
            rng.shuffle(sh)
            run["random"] = sh
            # last, so that adding embeddings leaves every other draw unchanged
            if emb is not None and qv is not None:
                run["dense_issue"] = by_score(
                    {p: float(np.dot(qv, emb[p])) if p in emb else -2.0 for p in nodes}, rng)
                # the same walk and fusions from the dense retriever's own top file, so that
                # the seed is picked by the reader the winning fusion uses (suffix _ds)
                s2 = run["dense_issue"][0]
                if r == 0:
                    guess_d = s2
                o2 = orderings(nodes, edges, lines, s2, bags, ib, rng, None, None, emb,
                               {"none": qv})
                for m in ("hops_lines", "ppr_und_pl", "rrf_pprpl_issue_path",
                          "rrf_pprpl_dense_path"):
                    if m in o2:
                        run[m + "_ds"] = [s2] + o2[m]
            per_run.append(run)
        if not per_run:
            continue
        text = texts.get(pr["instance_id"], "")
        is_named = named(text, sorted(keys["edited"]))
        gdir = guess.rsplit("/", 1)[0] if "/" in guess else ""
        top = guess.split("/", 1)[0]
        same_dir = any((f.rsplit("/", 1)[0] if "/" in f else "") == gdir for f in keys["edited"])
        same_top = any(f.split("/", 1)[0] == top for f in keys["edited"])
        for src, key in keys.items():
            if not key:
                continue
            ideal = sorted(key, key=lambda p: cost[p])
            for m in list(per_run[0]) + ["oracle"]:
                cs, sk = [], []
                for run in per_run:
                    order = ideal if m == "oracle" else run[m]
                    cs.append(coverage_curve(order, key, cost))
                    sk.append(coverage_skip(order, key, skip_mask(order, cost)))
                rows.append({"instance_id": pr["instance_id"], "repo_key": repo_key,
                             "file_group": pr["file_group"], "method": m, "source": src,
                             "key_size": len(key), "named": is_named,
                             "guess_correct": guess in keys["edited"],
                             "guess_dense_correct": (guess_d in keys["edited"]
                                                     if guess_d else None),
                             "guess_same_dir": same_dir, "guess_same_top": same_top,
                             "auc": float(np.mean(cs)), "auc_skip": float(np.mean(sk))})
    return rows


# does walking from the guessed file add anything to what the issue alone retrieves? Every
# comparison is the fusion against an ordering that is not given the guess's neighbourhood,
# or the fusion's own structural input
VERSUS = ["localiser", "path_issue", "bm25_issue", "dense_issue", "ppr_und_pl", "hops_lines"]


def summarise():
    from depgraphs.analysis2 import holm, pairwise

    df = pd.read_parquet(OUT / "rows.parquet")
    strata = {"all": df, "named": df[df.named], "not named": df[~df.named]}
    tests = []
    for label, sub in strata.items():
        for src in ("edited", "symbol"):
            have = set(sub[sub.source == src].method)
            for a in ("rrf_pprpl_issue_path", "rrf_pprpl_dense_path",
                      "rrf_pprpl_dense_path_ds"):
                for b in VERSUS:
                    if a not in have or b not in have:
                        continue
                    tests.append(pairwise(sub, src, [a, b], unit="repo")
                                 .assign(stratum=label))
    tests = pd.concat(tests, ignore_index=True)
    tests["p_holm"] = holm(tests["p"].tolist())
    tests.to_csv(OUT / "tests.csv", index=False)
    pr = df.drop_duplicates("instance_id")
    auc = (df.groupby(["source", "named", "method"]).auc.mean().unstack([0, 1]).round(4))
    summary = {
        "n_prs": int(pr.instance_id.nunique()), "n_repos": int(pr.repo_key.nunique()),
        "named_share": float(pr.named.mean()),
        "guess_correct": float(pr.guess_correct.mean()),
        "guess_correct_named": float(pr[pr.named].guess_correct.mean()),
        "guess_correct_not_named": float(pr[~pr.named].guess_correct.mean()),
        "wrong_guess_same_dir": float(pr[~pr.guess_correct].guess_same_dir.mean()),
        "guess_dense_correct": float(pr.guess_dense_correct.astype(float).mean()),
        "guess_dense_correct_named": float(pr[pr.named].guess_dense_correct.astype(float).mean()),
        "guess_dense_correct_not_named": float(
            pr[~pr.named].guess_dense_correct.astype(float).mean()),
        "wrong_guess_same_top": float(pr[~pr.guess_correct].guess_same_top.mean()),
        "n_named": int(pr.named.sum()), "n_not_named": int((~pr.named).sum()),
        "auc_all": df.groupby(["source", "method"]).auc.mean().unstack(0).round(4)
        .to_dict(),
        "auc_skip_all": df.groupby(["source", "method"]).auc_skip.mean().unstack(0).round(4)
        .to_dict(),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    pd.set_option("display.width", 200)
    print(auc.to_string())
    print({k: v for k, v in summary.items() if not k.startswith("auc")})
    print(tests[["stratum", "source", "a", "b", "n_pr", "delta", "p_holm"]].round(4)
          .to_string(index=False))


def main(workers: int = 4):
    tasks = [json.loads(l) for l in open(ROOT / "data" / "tasks.jsonl", encoding="utf-8")]
    scored = set(pd.read_parquet(S2 / "rows.parquet", columns=["instance_id"]).instance_id)
    prs = {}
    for t in tasks:
        if t["instance_id"] in scored:
            prs.setdefault(t["instance_id"], t)
    raw = json.loads((ROOT / "data" / "issue_bags.json").read_text())
    issues = {k: v["bag"] for k, v in raw.items()}
    texts = load_statements()
    qpath = ROOT / "data" / "embeddings" / "issues.npz"
    qvecs = {}
    if qpath.exists():
        z = np.load(qpath)
        first = {}
        for t in tasks:
            first.setdefault(t["instance_id"], t["task_id"])
        want = {tid: iid for iid, tid in first.items()}
        for i, v in zip(z["ids"].tolist(), z["vecs"].astype(np.float32)):
            tid, arm = i.rsplit("|", 1)
            if arm == "none" and tid in want:
                qvecs[want[tid]] = v
    by = collections.defaultdict(list)
    for p in prs.values():
        by[p["repo_key"]].append(p)
    rows = []
    with ProcessPoolExecutor(workers) as ex:
        futs = {ex.submit(run_repo, rk, v, issues, texts,
                          {p["instance_id"]: qvecs[p["instance_id"]] for p in v
                           if p["instance_id"] in qvecs}): rk for rk, v in by.items()}
        for i, f in enumerate(as_completed(futs)):
            rows += f.result()
            print("[%d/%d] %s" % (i + 1, len(futs), futs[f]), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_parquet(OUT / "rows.parquet", index=False)
    summarise()


if __name__ == "__main__":
    if sys.argv[1:] == ["summarise"]:
        summarise()
    else:
        main(int(sys.argv[1]) if len(sys.argv) > 1 else 4)
