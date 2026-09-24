# Human-annotated key (ContextBench) — predictions fixed before scoring

Written and committed after the ContextBench tasks were drawn (`src/depgraphs/contextbench.py`)
and **before** any graph, key, ordering or score was computed for them. The commit that adds
this file precedes the commit that adds any result for this set; `git log` is the record.

## Why

Both of the study's answer keys are proxies. The co-edited key is what a fix happened to
touch. The symbol key is built by resolving names through imports, which is the substrate the
structural orderings walk, so every structural-against-lexical comparison on it is open to a
charge of circularity. ContextBench (Li et al., 2026) annotates by hand the code an agent must
see to reconstruct a passing fix. No part of this study's pipeline built it.

## The set

ContextBench's Python tasks drawn from SWE-bench Verified and SWE-bench Pro (409), through the
main sample's eligibility rule (378 pass; the Docker-image condition is dropped since nothing
is executed), seed (20260922) and cap of 20 pull requests per repository: 203 pull requests in
15 repositories, 151 of them single-file. Ten of the repositories are in the main sample, and
24 of ContextBench's pull requests are in the main sample; this is a test of the *key*, not of
generalisation to new repositories, which the external test set addresses.

The `gold` key of a task is the set of Python files in its gold context, minus the seed,
restricted to graph nodes exactly as the other keys are. Tasks whose gold key is empty are not
scored on it.

## What is held fixed

Everything, as for the external test: methods, parameters, tie-breaking seeds, metric, the two
existing keys, leakage classifier, redaction arms and analysis code, run unchanged with
`DEPGRAPHS_ROOT=contextbench`. Failures to build are dropped and counted.

## Inference

The primary test is the mixed model of the paper's appendix (per-pull-request paired
difference, random intercept per repository), Holm-corrected within each prediction. "Gold
population" means the scored tasks with a non-empty gold key.

## Predictions

**G1 — the recommendation holds on a human key.** On the gold population,
`rrf_pprpl_issue_path` is among the three best non-oracle orderings (of the twenty-two ranked
in the paper) on the gold key, and its AUC shortfall to the best non-oracle ordering is at most
0.030. *Fails if* either condition fails.

**G2 — the fusion is never significantly worse than a pure ordering.** On the gold population
and key, the mixed-model estimate of `rrf_pprpl_issue_path` minus each of `hops_lines`,
`ppr_und_pl`, `ppr_out_pl` and `path_issue` (4 tests, Holm) is never significantly negative.
*Fails if* any is negative with p_Holm < 0.05.

**G3 — walking inward is costly.** On the gold population and key, `ppr_out_pl` minus
`ppr_in_pl` is positive with p < 0.05. *Fails if* not.

**G4 — the proxy keys order the methods as the human key does.** On the scored tasks carrying
both the gold key and the symbol key, the Kendall rank correlation between the twenty-two
non-oracle orderings' mean AUC under the gold key and under the symbol key is at least 0.5;
likewise for the co-edited key, on the tasks carrying both it and the gold key. *Fails if*
either correlation is below 0.5.

**Descriptive, no criterion:** the size of the gold key and its overlap with the two proxy
keys; the share of single-file pull requests with a non-empty gold key; the redaction arms on
the gold key; the full table of AUCs under all three keys.

## Reporting

All four outcomes are reported in the paper whichever way they fall, with this file cited.
Nothing on this set will be used to change a method, a parameter or a claim about the main
sample; a failed prediction is reported as such.
