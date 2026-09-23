# AI_USE — what Claude Code did, when, with which model (G15)

Model for every row unless stated: Claude Opus 5 (`claude-opus-5`), via Claude Code CLI.
Neil writes the final ACM disclosure statement from this log.

| Date | Step | What Claude Code did | Kind of content | Checked by Neil? |
|---|---|---|---|---|
| 2026-09-22 | 0 | Created repo skeleton, `pyproject.toml` + `uv.lock`, `run.py`, `Makefile`, `.gitignore` | code | no |
| 2026-09-22 | 0 | Ran machine check (disk, RAM, CPU, Docker, accounts); started Docker Desktop and ran `hello-world` | environment | no |
| 2026-09-22 | 0 | Wrote `src/depgraphs/datasets.py`; downloaded 9 datasets from Hugging Face at pinned revisions with SHA-256 checksums | code, data | no |
| 2026-09-22 | 0 | Wrote `DECISIONS.md`, `GLOSSARY.md`, `POSTHOC.md`, this file | text | no |
| 2026-09-22 | 1 | Drafted `paper/rqs.md` (problem statement, RQ1–RQ6 with measurement and negative outcome) | text (paper voice) | no — D16 |
| 2026-09-22 | 2 | Wrote patch parser `src/depgraphs/patches.py` + unit tests | code | no |
| 2026-09-22 | 2 | Wrote and ran `src/depgraphs/recount.py`: recounted RUNBOOK 9.2; found how the original numbers were computed (line cap over all files) | code, data | no |
| 2026-09-22 | 2 | Wrote and ran `src/depgraphs/envs.py`: checked each task's Docker image exists on Docker Hub (no pulls) | code, data | no |
| 2026-09-22 | 2 | Wrote and ran `src/depgraphs/candidates.py`: G18 dedup; shallow-fetched 181 candidate repos at a provisional commit; measured R2/R3 inputs with pygount | code, data | no |
| 2026-09-22 | 2 | Wrote and ran `src/depgraphs/ghmeta.py`: GitHub metadata (fork, licence, description) for candidates | code, data | no |
| 2026-09-22 | 2 | Wrote `src/depgraphs/sampling.py` (9.4 hash draw) + tests. Not run: needs Neil's seed and rules | code | no |
| 2026-09-22 | 3 (prep) | Wrote custom `ast` import-graph builder with every Appendix A rule as a switch, SCC condensation, toy-repo tests (G13). No real-repo graphs built for results | code | no |
| 2026-09-22 | 2 | Measured R2/R3 under an alternative definition (`src/depgraphs/r2_variant.py`); not applied | code, data | no — D10 |
| 2026-09-22 | 2 | Wrote and ran `src/depgraphs/gate_a.py`, `gate_a_extra.py`: option tables, power table, strata, cost per repo | code, data | no |
| 2026-09-22 | 3 (prep) | Added tree-sitter extraction and 4-builder comparison (`src/depgraphs/graph/compare.py`) on 2 rule-picked repos plus 2 mistakenly picked ones (kept, labelled) | code, data | no — D9 |
| 2026-09-22 | 0–3 | Found and fixed 4 bugs in its own tooling (line counting, licence check, builder crash, uncounted skipped files); logged in `POSTHOC.md` | code | no |
| 2026-09-22 | 0–2 | Wrote check-in `reports/01-step0-1-2.md` and decision cards | text (Neil voice) | — |
| 2026-09-22 | 3–9 | Built 1,872 import graphs; Table 1; static and execution answer keys; features, co-change, method driver, scoring, statistics; ran everything on a rented server (151.185.58.54) | code, data | no |
| 2026-09-22 | 5 | Assigned domain labels to 113 repos from their GitHub descriptions (`data/domain_labels.csv`) | data (AI annotation) | no — spot-check advised |
| 2026-09-22 | 8–12 | Wrote analysis, RQ4 summary, and the findings page (`reports/findings.html`, published privately as an Artifact) | code, text | no |
| 2026-09-22 | 12 | Drafted `paper/paper.tex` (ACM TOSEM, acmsmall) and `paper/references.bib`; every number copied from `results/analysis/`; bib written from memory, uncertain entries marked VERIFY; related-work claim about other papers' keys left as TODO | text (Neil voice), bib | no — Neil must review; check every bib entry |
| 2026-09-23 | 13 | Reframed the study after a design review with Neil: built `src/depgraphs/{lexfeat,issues,study2,analysis2,ball}.py`, ran 19 reading orders over 2,412 tasks on the laptop (no server, no GPU), and rewrote `paper/paper.tex` around the structure-vs-issue-text reversal. Every number copied from `results/study2/`. Two claims I had made earlier and have now retracted are recorded in POSTHOC.md | code, data, text | no — Neil must review; bib still unverified |
| 2026-09-24 | 14 | Added the token cost axis and ceiling analysis (`src/depgraphs/{tokcost,ceiling,verify_keys}.py`), reframed the paper around context budgets, and pre-registered the downstream agent experiment as §7 rather than running it. Bibliography expanded 20 → 60 entries. **Every row of the prior-work table was checked against the evaluation section of the downloaded PDF**; that check found two of my own rows wrong and one novelty claim overstated, all recorded in POSTHOC.md | code, data, text, bib | no — Neil must review; the 8 statistics and classical entries are verified from publisher listings, not PDFs |
| 2026-09-24 | 15 | Responded to an external review of the draft. Added directed PPR (4 methods) and a stem-level leakage control, re-ran the study, and rewrote the results and abstract around the new numbers. **The stricter leakage control contradicted the paper's co-edited headline and the claim was narrowed rather than defended.** Six prose claims that disagreed with our own tables were corrected, and two tools added so the class of error cannot recur: `maketables.py` generates every numeric table row from the CSVs, `checknums.py` recomputes each prose-level claim | code, data, text | no — Neil must review; the 8 statistics and classical bib entries are verified from publisher listings, not PDFs |
