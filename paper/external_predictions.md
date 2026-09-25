# External test set — predictions fixed before scoring

Written and committed after the external tasks were drawn and **before** any graph, key,
ordering or score was computed for them. The commit that adds this file precedes the commit
that adds any external result; `git log` is the record.

## Why

The 200 repository splits in the paper are resamples of the same 112 repositories, with a
winner that is already best overall on them. They show the recommendation is stable; they
cannot show it generalises. A review asked for repositories outside the sample.

## The set

Every repository that passes all of the study's sampling rules (R1–R5 and the exclusions,
under variant b, exactly as for the main sample) and was left out only because D11 restricted
the task sources. Their eligible tasks come from SWE-Gym and SWE-bench Pro:

ansible/ansible, facebookresearch/hydra, getmoto/moto, modin-project/modin,
project-monai/monai, pydantic/pydantic, qutebrowser/qutebrowser.

Tasks are drawn by `src/depgraphs/external.py` with the main sample's eligibility rule, seed
(20260922) and cap (20 pull requests per repository): 140 pull requests, 73 single-file.

Known differences from the main sample, stated in advance: these repositories are larger
(105–1,203 non-test Python files, median 289, against a median of 160 in the main sample's
repositories), two use copyleft
licences, and the task sources curate differently. A failure here could reflect any of these
as well as a failure to generalise; a success is the more informative outcome.

## What is held fixed

Everything. The methods, their parameters, the tie-breaking seeds, the metric, the keys, the
leakage classifier, the three redaction arms and the analysis code are the ones committed on
the main study, run unchanged with `DEPGRAPHS_ROOT=external`. Pull requests whose keys or graphs
fail to build are dropped and counted, never repaired by hand.

## Inference

Seven repositories are too few for the paper's repository-level Wilcoxon test: its smallest
two-sided p with n = 7 is 0.016, which no Holm-corrected family can use. The primary test for
every hypothesis below is therefore the mixed model already used in the paper's appendix — the
per-pull-request paired difference, with a random intercept per repository — Holm-corrected
across the tests of that hypothesis. With seven groups the random-intercept variance is
estimated poorly; we say so rather than switch methods after seeing results.

"Matched population" means, as in the paper, the pull requests carrying both keys.

## Predictions

**E1 — the recommendation holds (primary).** On the matched population,
`rrf_pprpl_issue_path` is among the three best non-oracle orderings (of the twenty-two ranked in
the paper) under *both* keys, and its worst-case AUC shortfall to the best non-oracle ordering
across the two keys is at most 0.030.
*Fails if* either condition fails.

**E2 — the fusion is never significantly worse than a pure ordering.** On the matched
population, the mixed-model estimate of `rrf_pprpl_issue_path` minus each of `hops_lines`,
`ppr_und_pl`, `ppr_out_pl` and `path_issue`, under each key (8 tests, Holm), is never
significantly negative.
*Fails if* any of the eight is negative with p_Holm < 0.05.

**E3 — walking inward is costly.** On the full symbol-key population, `ppr_out_pl` minus
`ppr_in_pl` is positive with p < 0.05.
*Fails if* not.

**E4 — filename leakage is causal, and the redaction is clean.** On the matched pull requests
whose issue names a key file as code, deleting the names (names arm) costs
`rrf_pprpl_issue_path` a positive amount with p < 0.05 under each key (2 tests, Holm); on the
matched pull requests whose issue names none, the names arm moves the fusion by at most 0.005
in absolute mean under each key.
*Fails if* either part fails. If fewer than 20 matched pull requests name a key file, E4 is
reported as not testable rather than as a pass or a failure.

**Descriptive, no criterion:** the rate at which issues name a key file as code; the wider
redaction arms; the two-hop ball's share of the repository and its recall; the full table of
AUCs under both keys and both populations.

## Reporting

All four outcomes are reported in the paper whichever way they fall, with this file cited.
Nothing on the external set will be used to change a method, a parameter or a claim about the
main sample; if a prediction fails, the paper says the claim did not replicate on these seven
repositories.
