"""Analysis for the structure-vs-words study.

The unit of analysis is the pull request: task AUCs are averaged within an instance first,
so a PR that touches many files does not count many times. Paired tests are Wilcoxon
signed-rank with Vargha-Delaney A12 and Holm correction within each family of comparisons;
confidence intervals are 2000-resample bootstraps over repositories.

Writes results/study2/*.csv and results/study2/findings.json
"""
from __future__ import annotations

import gzip
import json
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats

from depgraphs.lexfeat import ROOT
from depgraphs.study2 import (BUDGETS, FUSION, FUSION_CTL, GLOBAL, LEXICAL, METHODS,
                              REDACTED, REDACTED_ALL, ARM_SUFFIX, RRF_K_VARIANTS, STRUCTURE,
                              OUT)

SEED = 20260923
SOURCES = ["co_edited", "symbol", "union_static"]
FAMILY = ({m: "structure" for m in STRUCTURE} | {m: "global" for m in GLOBAL}
          | {m: "lexical" for m in LEXICAL} | {m: "fusion" for m in FUSION}
          | {m: "fusion-control" for m in FUSION_CTL}
          | {m: "redacted" for m in REDACTED_ALL}
          | {m: "rrf-k" for m in RRF_K_VARIANTS}
          | {"same_dir": "reference", "random": "reference", "oracle": "reference"})


def pr_level(rows: pd.DataFrame, source: str) -> pd.DataFrame:
    """method x instance_id matrix of AUC, averaged over the tasks of a PR."""
    d = rows[rows["source"] == source]
    return d.pivot_table(index="instance_id", columns="method", values="auc", aggfunc="mean")


def a12(x: np.ndarray, y: np.ndarray) -> float:
    """P(x > y) + 0.5 P(x == y), computed from the rank-sum."""
    n, m = len(x), len(y)
    r = stats.rankdata(np.concatenate([x, y]))[:n].sum()
    return (r / n - (n + 1) / 2) / m


def holm(pvals: list[float]) -> list[float]:
    order = np.argsort(pvals)
    adj = np.empty(len(pvals))
    running = 0.0
    for i, idx in enumerate(order):
        running = max(running, (len(pvals) - i) * pvals[idx])
        adj[idx] = min(1.0, running)
    return adj.tolist()


def boot_ci(values: np.ndarray, groups: np.ndarray, n=2000, seed=SEED):
    """Bootstrap the mean by resampling repositories, not tasks."""
    rng = np.random.default_rng(seed)
    uniq = np.unique(groups)
    idx = {g: np.flatnonzero(groups == g) for g in uniq}
    out = []
    for _ in range(n):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        sel = np.concatenate([idx[g] for g in pick])
        out.append(values[sel].mean())
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def auc_table(rows: pd.DataFrame, sources=None, prs: pd.Index | None = None,
              tasks: set | None = None, ci: bool = True) -> pd.DataFrame:
    """Mean AUC per method, with a bootstrap CI over repositories, on a subpopulation.

    `prs` restricts to a set of pull requests (the population-matching control) and
    `tasks` to a set of tasks (the leakage control); passing both applies them jointly.
    """
    if tasks is not None:
        rows = rows[rows["task_id"].isin(tasks)]
    recs = []
    for src in (sources or SOURCES):
        mat = pr_level(rows, src)
        if prs is not None:
            mat = mat.loc[mat.index.intersection(prs)]
        repo = (rows[rows["source"] == src].groupby("instance_id")["repo_key"].first()
                .reindex(mat.index))
        for m in mat.columns:
            v = mat[m].to_numpy()
            ok = ~np.isnan(v)
            if not ok.any():
                continue
            lo, hi = (boot_ci(v[ok], repo.to_numpy()[ok])
                      if ci else (float("nan"), float("nan")))
            recs.append({"source": src, "method": m, "family": FAMILY.get(m, "?"),
                         "n_pr": int(ok.sum()), "auc": float(v[ok].mean()),
                         "ci_lo": lo, "ci_hi": hi})
    df = pd.DataFrame(recs)
    # One rank scale for the whole paper: over the orderings we propose or compare against,
    # oracle included. The fusion controls exist only to answer "is a fusion just more
    # input?" and are not candidate reading orders, so they are scored but not ranked;
    # including them would shift every rank in every table by up to two places.
    rankable = ~df["method"].isin(list(FUSION_CTL) + list(REDACTED_ALL)
                                  + list(RRF_K_VARIANTS))
    df["rank"] = (df[rankable].groupby("source")["auc"]
                  .rank(ascending=False, method="min").astype(int))
    return df.sort_values(["source", "rank"])


def shared_prs(rows: pd.DataFrame) -> pd.Index:
    """Pull requests that have a non-empty key under *both* evidence sources.

    A co-edited key exists only for a PR that touches more than one graph file, while a
    symbol key exists for single-file PRs too. Comparing the full per-source tables
    therefore compares two different populations, and single-file PRs are exactly the ones
    where a seed's import neighbourhood is most of what there is to find. Restricting to
    the intersection is what isolates the effect of the key from the effect of the sample.
    """
    idx = None
    for src in ("co_edited", "symbol"):
        here = pr_level(rows, src).dropna(how="all").index
        idx = here if idx is None else idx.intersection(here)
    return idx


def leak_strata(rows: pd.DataFrame) -> dict[str, set]:
    """Task subsets that survive each level of the issue-text leakage control.

    no_full_path  no key file's full path appears verbatim in the issue.
    no_explicit   no key file is named *as code*: no "core.py", no "simbad/core",
                  nothing inside a code span. Bare-word overlap ("models" for models.py)
                  is left in, because a project's prose and its filenames share a domain
                  vocabulary and using that is retrieval, not leakage. Primary.
    no_stem       strictest: no key file's stem appears at all, which over-corrects by
                  removing legitimate vocabulary signal and selects for vaguer issues.
    """
    leak = pd.read_csv(OUT / "issue_path_leak.csv")
    all_tasks = set(rows["task_id"])
    return {
        "all": all_tasks,
        "no_full_path": set(leak.loc[leak["full"] == 0, "task_id"]),
        "no_explicit": set(leak.loc[(leak["full"] == 0) & (leak["explicit"] == 0),
                                    "task_id"]),
        "no_stem": set(leak.loc[(leak["full"] == 0) & (leak["stem"] == 0), "task_id"]),
        # the complement of no_explicit: issues that *do* name a key file as code. Not a
        # control but the other side of one, so that the contribution of issue text can
        # be compared between the tasks where the issue names the answer and the tasks
        # where it does not, instead of only being removed.
        "explicit": set(leak.loc[(leak["full"] > 0) | (leak["explicit"] > 0), "task_id"]),
    }


def table_joint(rows: pd.DataFrame) -> pd.DataFrame:
    """Both controls at once: the leakage strata, each on its own matched population.

    The two controls were introduced separately, and each dissolved one half of the
    reversal reported by the uncontrolled comparison. Applying them one at a time leaves
    open the objection that a claim surviving each might still fail under both, which
    matters most on the symbol key: the leakage strata on their own still contain the
    single-file pull requests that the matching control removes. For each stratum the
    matched population is recomputed inside that stratum, so "carries both keys" is
    always a statement about the tasks actually being scored.
    """
    out = []
    for name, tasks in leak_strata(rows).items():
        sub = rows[rows["task_id"].isin(tasks)]
        t = auc_table(sub, ("co_edited", "symbol"), prs=shared_prs(sub))
        t.insert(0, "stratum", name)
        out.append(t)
    return pd.concat(out, ignore_index=True)


def pairwise(rows: pd.DataFrame, source: str, methods: list[str], unit: str = "pr",
             population: pd.Index | None = None, tasks: set | None = None,
             stratum: str = "all") -> pd.DataFrame:
    """Paired tests between every pair of methods on one evidence source.

    unit="pr" treats pull requests as independent. They are not: they cluster in 112
    repositories, which is what makes the PR-level p-values as small as they are. With
    unit="repo" the PR scores are averaged within a repository first and the test runs
    over repositories, so the effect sizes are unchanged but the evidence is counted at
    the level at which the sampling actually happened.
    """
    if tasks is not None:
        rows = rows[rows["task_id"].isin(tasks)]
    mat = pr_level(rows, source)[methods].dropna()
    if population is not None:
        mat = mat.loc[mat.index.intersection(population)]
    if unit == "repo":
        repo = rows.groupby("instance_id")["repo_key"].first()
        mat = mat.groupby(repo.reindex(mat.index).to_numpy()).mean()
    recs, pvals = [], []
    for a, b in combinations(methods, 2):
        x, y = mat[a].to_numpy(), mat[b].to_numpy()
        try:
            p = stats.wilcoxon(x, y, zero_method="wilcox").pvalue
        except ValueError:
            p = 1.0
        recs.append({"source": source, "unit": unit, "stratum": stratum,
                     "population": "shared" if population is not None else "all",
                     "a": a, "b": b, "n_pr": len(x),
                     "mean_a": float(x.mean()), "mean_b": float(y.mean()),
                     "delta": float(x.mean() - y.mean()), "a12": a12(x, y), "p": p})
        pvals.append(p)
    df = pd.DataFrame(recs)
    df["p_holm"] = holm(pvals)
    return df


def complementarity(top_path, k=20):
    """How each key file is reachable: by structure only, words only, both, neither."""
    struct = ["ppr_und", "hops_lines"]
    lex = ["bm25_issue", "path_issue"]
    tally = {s: {"struct_only": 0, "lex_only": 0, "both": 0, "neither": 0, "total": 0}
             for s in SOURCES}
    with gzip.open(top_path, "rt", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            S = set().union(*[rec["lists"].get(m, [])[:k] for m in struct])
            L = set().union(*[rec["lists"].get(m, [])[:k] for m in lex])
            for src in SOURCES:
                for p in rec["keys"].get(src, []):
                    t = tally[src]
                    t["total"] += 1
                    if p in S and p in L:
                        t["both"] += 1
                    elif p in S:
                        t["struct_only"] += 1
                    elif p in L:
                        t["lex_only"] += 1
                    else:
                        t["neither"] += 1
    recs = []
    for src, t in tally.items():
        n = t["total"] or 1
        recs.append({"source": src, "k": k, "n_key_files": t["total"],
                     **{c: t[c] / n for c in ["both", "struct_only", "lex_only", "neither"]}})
    return pd.DataFrame(recs)


def overlap(top_path, k=20):
    """Jaccard between the top-k sets of the structural and lexical families."""
    pairs = [("ppr_und", "bm25_issue"), ("ppr_und", "path_issue"),
             ("ppr_und", "pagerank"), ("bm25_issue", "path_issue"),
             ("ppr_und", "bm25_seed"), ("bm25_issue", "bm25_seed")]
    acc = {p: [] for p in pairs}
    with gzip.open(top_path, "rt", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            for a, b in pairs:
                A, B = set(rec["lists"].get(a, [])[:k]), set(rec["lists"].get(b, [])[:k])
                if A or B:
                    acc[(a, b)].append(len(A & B) / len(A | B))
    return pd.DataFrame([{"a": a, "b": b, "k": k, "jaccard": float(np.mean(v)),
                          "n": len(v)} for (a, b), v in acc.items()])


def leak_sensitivity(rows: pd.DataFrame, methods: list[str]) -> pd.DataFrame:
    """Re-rank on the tasks whose issue text does not name the key files.

    Path-matching methods would look good for a trivial reason if issue reports simply
    named the files that had to change, so the comparison is repeated with those tasks
    removed, at three levels of strictness (see leak_strata).
    """
    recs = []
    for name, clean in leak_strata(rows).items():
        if name in ("all", "explicit"):
            continue
        sub = rows[rows["task_id"].isin(clean)]
        for src in SOURCES:
            mat = pr_level(sub, src)
            for m in methods:
                if m in mat:
                    v = mat[m].dropna()
                    recs.append({"stratum": name, "source": src, "method": m,
                                 "n_pr": len(v), "auc_no_leak": float(v.mean())})
    df = pd.DataFrame(recs)
    df["rank_no_leak"] = df.groupby(["stratum", "source"])["auc_no_leak"].rank(
        ascending=False, method="min").astype(int)
    return df


def heldout(rows: pd.DataFrame, methods: list[str], seed: int = SEED,
            n_splits: int = 200) -> pd.DataFrame:
    """Split the repositories in half, choose on one half, report on the other, many times.

    Both the fusion recipe and the criterion that picks it were settled after seeing the
    full results, which makes the recommendation exploratory however large its margin. One
    split would not fix that: with five candidate fusions and a winner that is already best
    overall, a single 56/56 draw is close to a foregone conclusion. So the split is repeated
    200 times and we report how often each fusion is selected and what rank it then attains
    on the half that did not select it. Splitting by repository rather than by pull request
    keeps every task of a repository on one side, as the clustering demands.
    """
    repos = np.array(sorted(rows["repo_key"].unique()))
    rng = np.random.default_rng(seed)
    fusions = [m for m in methods if m in FUSION]
    recs = []
    for it in range(n_splits):
        pick = rng.permutation(len(repos))
        halves = {"select": set(repos[pick[: len(repos) // 2]]),
                  "confirm": set(repos[pick[len(repos) // 2:]])}
        tab = {}
        for half, keep in halves.items():
            sub = rows[rows["repo_key"].isin(keep)]
            # no bootstrap here: the split needs ranks and means, and 200 splits
            # times 2,000 resamples times every method is hours of nothing
            tab[half] = auc_table(sub, ("co_edited", "symbol"), prs=shared_prs(sub),
                                  ci=False)
        sel = tab["select"].pivot(index="method", columns="source", values="rank")
        worst = sel.loc[[m for m in fusions if m in sel.index]].max(axis=1)
        chosen = worst.sort_values().index[0]
        con = tab["confirm"]
        rec = {"split": it, "chosen": chosen}
        for src in ("co_edited", "symbol"):
            g = con[con.source == src].set_index("method")
            rec["rank_%s" % src] = int(g.loc[chosen, "rank"])
            rec["auc_%s" % src] = float(g.loc[chosen, "auc"])
            rec["best_%s" % src] = float(g[g.index != "oracle"]["auc"].max())
        recs.append(rec)
    return pd.DataFrame(recs)


def redaction(rows: pd.DataFrame, unit: str = "repo") -> pd.DataFrame:
    """Score the same task twice, once on the issue and once on the issue with the key
    files' names deleted, and report the difference.

    This is the within-task version of the leakage control. Dropping the tasks whose issue
    names a key file compares two sets of *issues* as well as two leakage regimes, and
    issues that carry a stack trace are plausibly better written than those that do not.
    Here the task, the issue, its length and its traceback are all held fixed and only the
    names are removed, so the difference cannot be an issue-quality effect.

    Reported on the tasks where redaction actually changed something, on the tasks where it
    did not (where the difference must be zero, and is, which is the sanity check), and over
    everything scored.
    """
    # exactly the strata of leak_strata, so that this table and the stratified tests in
    # pairwise.csv are about the same tasks and the decomposition is additive
    st = leak_strata(rows)
    groups = {
        "names removed": st["explicit"],
        "nothing removed": st["no_explicit"],
        "all tasks": st["all"],
    }
    repo = rows.groupby("instance_id")["repo_key"].first()
    recs = []
    for label, tasks in groups.items():
        sub = rows[rows["task_id"].isin(tasks)]
        # the matched population, as everywhere else in the results, so that the numbers
        # here and the stratified ones in pairwise.csv decompose additively
        keep = shared_prs(sub)
        for src in ("co_edited", "symbol"):
            mat = pr_level(sub, src).loc[lambda m: m.index.intersection(keep)]
            for rd, plain in REDACTED_ALL.items():
                if rd not in mat or plain not in mat:
                    continue
                pair = mat[[plain, rd]].dropna()
                if unit == "repo":
                    pair = pair.groupby(repo.reindex(pair.index).to_numpy()).mean()
                x, y = pair[plain].to_numpy(), pair[rd].to_numpy()
                if len(x) < 3:
                    continue
                try:
                    p = stats.wilcoxon(x, y, zero_method="wilcox").pvalue
                except ValueError:
                    p = 1.0
                d = x - y
                lo, hi = boot_ci(d, np.arange(len(d)))
                arm = next(k for k, v in ARM_SUFFIX.items() if rd == plain + v)
                recs.append({"arm": arm, "group": label, "source": src, "method": plain,
                             "n": len(x), "auc": float(x.mean()),
                             "auc_redacted": float(y.mean()), "delta": float(d.mean()),
                             "ci_lo": lo, "ci_hi": hi, "a12": a12(x, y), "p": p})
    df = pd.DataFrame(recs)
    # Holm within each arm: each arm is its own question, and correcting the names arm
    # for tests added afterwards would change a result for a reason unrelated to it
    df["p_holm"] = 1.0
    for arm, g in df.groupby("arm"):
        df.loc[g.index, "p_holm"] = holm(g["p"].tolist())
    return df


# The comparisons the paper rests a claim on, re-estimated with a mixed model. Each entry is
# (a, b, source, stratum, population); "b" may be a redacted twin, in which case a - b is
# what the names (or the wider arm) are worth.
HEADLINE = [
    ("rrf_pprpl_issue_path", "path_issue", s, "all", pop)
    for s in ("co_edited", "symbol") for pop in ("all", "shared")
] + [
    (a, "path_issue", s, "all", pop)
    for a in ("ppr_out_pl", "ppr_und_pl", "hops_lines")
    for s in ("co_edited", "symbol") for pop in ("all", "shared")
] + [
    ("rrf_pprpl_issue_path", b, "symbol", st, pop)
    for b in ("ppr_out_pl", "ppr_und_pl", "hops_lines")
    for st in ("all", "no_explicit") for pop in ("all", "shared")
] + [
    ("hops_lines", "path_issue", "co_edited", st, "shared")
    for st in ("no_full_path", "no_explicit", "no_stem")
] + [
    ("ppr_out_pl", "ppr_in_pl", "symbol", "all", pop) for pop in ("all", "shared")
] + [
    ("rrf_pprpl_issue_path", "rrf_pprpl_issue_path_rd", s, st, "shared")
    for s in ("co_edited", "symbol") for st in ("explicit", "no_explicit")
] + [
    ("rrf_pprpl_issue_path", "rrf_pprpl_seedpath", s, st, "shared")
    for s in ("co_edited", "symbol") for st in ("explicit", "no_explicit")
]


def mixed_effects(rows: pd.DataFrame) -> pd.DataFrame:
    """The headline paired comparisons as a random-intercept model, pull request as the row.

    The repository-level Wilcoxon test averages within a repository first, so a repository
    contributing one pull request weighs as much as one contributing a hundred. The mixed
    model keeps every pull request as an observation of its paired difference a - b and
    gives each repository a random intercept, so clustering is modelled rather than
    averaged away. Reported beside the Wilcoxon tests, not instead of them.
    """
    import warnings

    import statsmodels.formula.api as smf

    strata = leak_strata(rows)
    repo = rows.groupby("instance_id")["repo_key"].first()
    recs = []
    for a, b, src, st, pop in HEADLINE:
        sub = rows[rows["task_id"].isin(strata[st])]
        mat = pr_level(sub, src)
        if pop == "shared":
            mat = mat.loc[mat.index.intersection(shared_prs(sub))]
        if a not in mat or b not in mat:
            continue
        d = (mat[a] - mat[b]).dropna().rename("d").to_frame()
        d["repo"] = repo.reindex(d.index).to_numpy()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit = smf.mixedlm("d ~ 1", d, groups=d["repo"]).fit(reml=True)
        lo, hi = fit.conf_int().loc["Intercept"]
        recs.append({"a": a, "b": b, "source": src, "stratum": st, "population": pop,
                     "n_pr": len(d), "n_repo": d["repo"].nunique(),
                     "estimate": float(fit.params["Intercept"]), "ci_lo": float(lo),
                     "ci_hi": float(hi), "p": float(fit.pvalues["Intercept"]),
                     "repo_var": float(fit.cov_re.iloc[0, 0]),
                     "resid_var": float(fit.scale)})
    df = pd.DataFrame(recs)
    df["p_holm"] = holm(df["p"].tolist())
    return df


def rank_agreement(per_source: pd.DataFrame) -> dict:
    """Spearman correlation between the method rankings induced by two evidence sources.

    Reported twice: over everything scored, and over the contenders only. The references
    (random, same_dir, oracle) sit at the same end of both rankings by construction and
    inflate the agreement, so the contender-only figure is the one that answers the
    question "does it matter which evidence you grade against".
    """
    out = {}
    # the fusion controls are not candidate reading orders, so they stay out of both scales
    ctl = set(FUSION_CTL) | set(REDACTED_ALL) | set(RRF_K_VARIANTS)
    for label, drop in (("all", {"oracle"} | ctl),
                        ("contenders", {"oracle", "random", "same_dir"} | ctl)):
        piv = per_source[~per_source.method.isin(drop)].pivot(
            index="method", columns="source", values="auc")
        r, p = stats.spearmanr(piv["co_edited"], piv["symbol"])
        out[label] = {"spearman": float(r), "p": float(p), "n_methods": int(len(piv))}
    return out


def corpus_counts() -> dict:
    """Size of the whole task corpus, before tasks with an empty key are dropped."""
    import json as _json
    tasks = [_json.loads(l) for l in
             open(ROOT / "data" / "tasks.jsonl", encoding="utf-8")]
    return {"tasks": len(tasks),
            "pull_requests": len({t["instance_id"] for t in tasks}),
            "repositories": len({t["repo_key"] for t in tasks})}


def by_size(rows: pd.DataFrame, methods: list[str]) -> pd.DataFrame:
    """Repeat the per-source ranking within quartiles of repository size.

    The corpus skews small (median 131 graph nodes), so the reversal has to be shown to
    survive in the largest repositories rather than being an artefact of small ones.
    """
    q = rows.groupby("task_id")["n_nodes"].first()
    rows = rows.assign(size_q=rows["task_id"].map(
        pd.qcut(q, 4, labels=["Q1", "Q2", "Q3", "Q4"])))
    # Rank on the same scale as every other table: all scored orderings, oracle included,
    # less the two fusion controls, which are scored but never ranked.
    skip = set(FUSION_CTL) | set(REDACTED_ALL) | set(RRF_K_VARIANTS)
    rankable = [m for m in rows["method"].unique() if m not in skip]
    recs = []
    for src in SOURCES:
        d = rows[(rows["source"] == src) & (rows["method"].isin(rankable))]
        t = d.pivot_table(index="method", columns="size_q", values="auc",
                          aggfunc="mean", observed=True)
        rk = t.rank(ascending=False)
        t = t.loc[[m for m in methods if m in t.index]]
        rk = rk.loc[t.index]
        for m in t.index:
            for col in t.columns:
                recs.append({"source": src, "size_q": str(col), "method": m,
                             "auc": float(t.loc[m, col]), "rank": int(rk.loc[m, col])})
    out = pd.DataFrame(recs)
    out.attrs["bounds"] = q.quantile([0, .25, .5, .75, 1]).astype(int).to_dict()
    return out


def lines_table(rows: pd.DataFrame, methods: list[str]) -> pd.DataFrame:
    """Median lines that must be read to reach half, then all, of the key files."""
    recs = []
    for src in SOURCES:
        d = rows[(rows["source"] == src) & (rows["method"].isin(methods))]
        for m, g in d.groupby("method"):
            recs.append({"source": src, "method": m,
                         "lines_half_median": float(g["lines_half"].median()),
                         "lines_all_median": float(g["lines_all"].median()),
                         "n_task": int(len(g))})
    return pd.DataFrame(recs).sort_values(["source", "lines_half_median"])


def main():
    rows = pd.read_parquet(OUT / "rows.parquet")
    curves = pd.read_parquet(OUT / "curves.parquet")

    per_source = auc_table(rows)
    per_source.to_csv(OUT / "per_source.csv", index=False)

    contenders = ["ppr_und", "ppr_und_pl", "ppr_out", "ppr_out_pl", "ppr_in",
                  "ppr_in_pl", "hops_lines", "pagerank", "bm25_issue",
                  "bm25_issue_pl", "path_issue", "bm25_seed", "path_seed",
                  "rrf_ppr_issue", "rrf_ppr_issue_path", "rrf_hops_path",
                  "rrf_hops_issue_path", "rrf_pprpl_issue_path",
                  "rrf_hops_pathseed", "rrf_pprpl_seedpath",
                  "bm25_issue_rd", "path_issue_rd", "rrf_hops_path_rd",
                  "rrf_pprpl_issue_path_rd", "same_dir", "random"]
    shared = shared_prs(rows)
    # Four views of the same comparisons: PR-level and repository-level, over everything
    # and over the PRs that carry both keys. The repository-level tests on the shared
    # population are the conservative ones, and the ones the claims rest on.
    pw = [pairwise(rows, s, contenders, unit=u, population=pop)
          for s in SOURCES for u in ("pr", "repo") for pop in (None, shared)]
    # The same tests inside each leakage stratum, on the population matched within it,
    # so that every rank change the paper reports carries a test rather than a gap.
    strata = leak_strata(rows)
    for name, tasks in strata.items():
        if name == "all":
            continue
        sub = rows[rows["task_id"].isin(tasks)]
        pw += [pairwise(rows, s, contenders, unit="repo", population=pop,
                        tasks=tasks, stratum=name)
               for s in ("co_edited", "symbol")
               for pop in (None, shared_prs(sub))]
    pd.concat(pw).to_csv(OUT / "pairwise.csv", index=False)

    auc_table(rows, ("co_edited", "symbol"), prs=shared).to_csv(
        OUT / "per_source_shared.csv", index=False)
    table_joint(rows).to_csv(OUT / "per_source_joint.csv", index=False)
    heldout(rows, contenders).to_csv(OUT / "heldout.csv", index=False)
    redaction(rows).to_csv(OUT / "redaction.csv", index=False)
    mixed_effects(rows).to_csv(OUT / "mixed.csv", index=False)

    cur = (curves.groupby(["source", "method", "budget"])["coverage"].mean()
           .reset_index())
    cur.to_csv(OUT / "curves_mean.csv", index=False)

    comp = pd.concat([complementarity(OUT / "top.jsonl.gz", k) for k in (10, 20, 50)])
    comp.to_csv(OUT / "complementarity.csv", index=False)
    ov = pd.concat([overlap(OUT / "top.jsonl.gz", k) for k in (10, 20, 50)])
    ov.to_csv(OUT / "overlap.csv", index=False)

    # Robustness across key sources, two ways. Worst-case *rank* is easy to read but moves
    # when the competitor set changes: adding four directed walks reshuffles everything
    # below them. Worst-case *shortfall* -- the largest AUC gap to the best non-oracle
    # ordering under either key -- says the same thing in units that do not depend on who
    # else was scored, and is the criterion we ask readers to check against.
    rk = per_source[per_source["rank"].notna()]
    piv = rk.pivot(index="method", columns="source", values="rank").astype(int)
    piv["worst_case"] = piv[["co_edited", "symbol"]].max(axis=1)
    au = rk.pivot(index="method", columns="source", values="auc")
    for src in ("co_edited", "symbol"):
        best = au.loc[au.index != "oracle", src].max()
        piv["gap_" + src] = (best - au[src]).round(4)
    piv["worst_gap"] = piv[["gap_co_edited", "gap_symbol"]].max(axis=1)
    piv.sort_values("worst_case").to_csv(OUT / "rank_by_source.csv")

    leak = leak_sensitivity(rows, contenders)
    leak.to_csv(OUT / "leak_sensitivity.csv", index=False)

    lines_table(rows, contenders + ["oracle"]).to_csv(OUT / "lines_to_reach.csv",
                                                      index=False)

    sz = by_size(rows, contenders)
    sz.to_csv(OUT / "by_size.csv", index=False)
    size_bounds = sz.attrs["bounds"]

    findings = {
        "rank_agreement": rank_agreement(per_source),
        # scored = tasks with a non-empty key under at least one source; the corpus
        # figures below are larger because 711 tasks have no key file in the graph
        "n_tasks_scored": int(rows["task_id"].nunique()),
        "n_prs_scored": int(rows["instance_id"].nunique()),
        "n_repos_scored": int(rows["repo_key"].nunique()),
        "corpus": corpus_counts(),
        "budgets": BUDGETS,
        "per_source_top5": {s: per_source[per_source.source == s]
                            .nsmallest(6, "rank")[["method", "auc", "rank"]]
                            .to_dict("records") for s in SOURCES},
        "rank_reversal": piv.to_dict("index"),
        "n_prs_shared": int(len(shared)),
        "repo_size_quartile_bounds": {str(k): int(v) for k, v in size_bounds.items()},
    }
    (OUT / "findings.json").write_text(json.dumps(findings, indent=1))
    print(per_source[per_source.source == "union_static"]
          [["method", "family", "auc", "ci_lo", "ci_hi", "rank"]].to_string(index=False))
    print()
    print(piv.to_string())


if __name__ == "__main__":
    main()
