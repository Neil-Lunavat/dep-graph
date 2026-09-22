# Check-in 01 — Steps 0, 1, 2 (Gate A) — 2026-09-22

## 1. Status in one line

Step 0 is done and checked. Step 1's draft is written. Step 2's counts are done. Waiting on you for 4 decisions (D16, D11, D19, D10) and a seed number.

## 2. What I need from you — do this first

- **Decisions:** D16, D11, D19, D10 (cards at the bottom). D11, D19 and D10 are really one decision. Read them together.
- **Write a seed number** for the repo draw in `DECISIONS.md` (line "Sampling seed"). Any whole number. Pick it without looking at which repos it selects.
- **Things to look at:**
  - `paper/rqs.md`: wording of RQ1–RQ6. Edit freely. Each RQ has a measurement and a way it could come out negative.
  - `results/step2/gate_a_repos.csv`: one row per candidate repo, with every rule result. Check 5 random rows if you have time.
  - §5 below: two places where the runbook was wrong, and bugs I fixed.
- **Time needed from you:** about 25 minutes (15 for reading, 10 for the cards).

## 3. What I did (plain, 8 lines max)

1. Set up the project: pinned Python 3.12 and every library, one entry point (`python run.py all`), a git repo, 19 unit tests. A fresh copy installs, passes the tests, and reproduces the counts byte for byte.
2. Downloaded 9 task datasets at fixed versions, with checksums.
3. Checked the machine and Docker (§4).
4. Drafted `paper/rqs.md` (the research questions).
5. Recounted the runbook's section 9.2 table from the raw data.
6. Checked Docker Hub for all 13,428 tasks: does a ready-made test box (prebuilt Docker image) exist? Nothing was downloaded.
7. Removed tasks that appear in two datasets. Downloaded the code of the 181 repos with 10+ usable tasks, and measured each against rules R1–R5 and the exclusion rules.
8. Groundwork for Gate B, which needs none of today's decisions: a graph builder, toy-repo tests, and a comparison of 4 builders on 2 repos. **No method was run and there are no method numbers.**

## 4. What I saw

**Machine (section 13 check)**
- Windows 11, not Ubuntu. Docker Desktop works: `hello-world` ran, and the machine is x86_64. *Which means: the ready-made test boxes should run, but the runbook assumes Ubuntu, so expect some friction.*
- 16 threads, 15.3 GB RAM, 187 GB free disk. Docker's own share is **7.9 GB RAM**; the SWE-bench harness recommends 16 GB. *Which means: some test boxes may run out of memory. Docker Desktop's settings can raise this.*
- No GitHub token. Not needed so far (the GitHub API allows 60 calls an hour, which was slow but enough). No Anthropic key. Not needed until Gate G.

**The 9.2 table, recounted** (`results/step2/recount_9_2.csv`)
- All 3 SWE-bench rows match the runbook exactly. *Which means: the counting method is the same.*
- SWE-Gym, SWE-bench-Live, SWE-rebench, Pro and Loc-Bench come out **1–2% higher** than the runbook (e.g. SWE-rebench 2,253 vs 2,228 usable tasks). §5 explains why.
- The line cap barely matters. Going from 200 lines to no cap adds 1–4% more tasks. *Which means: D19's real question is the file-count filter, not the cap.*
- The file-count filter matters a lot. **66% of usable tasks change a single file.** *Which means: 2–10 throws away two thirds of the data.*

**Ready-made test boxes** (`results/step2/env_availability_summary.csv`)
- 100% of tasks have one in SWE-bench, SWE-rebench and Pro. 99.9% in SWE-bench-Live (1 missing). 98.5% in SWE-Gym (37 missing). *Which means: the execution answer key is possible for almost every task.*
- Compressed download size per box: about 0.6 GB (SWE-bench-Live, Pro), 1.6 GB (SWE-bench), 2.0 GB (SWE-rebench), 2.9 GB (SWE-Gym). Sample of 8 per dataset. *Which means: 2,000 tasks ≈ 3 TB of downloads. Boxes must be pulled, used and deleted one at a time.*

**Duplicate tasks (G18)**
- 13,428 tasks → 13,220 after removing duplicates. 204 PRs appear in two datasets; none disagree on the base commit. One PR appears twice inside SWE-bench-Live itself.

**Candidate repos** (`results/step2/gate_a_repos.csv`)
- 181 repos have 10+ usable tasks under the widest option. 180 were measured. 1 no longer exists on GitHub (NREL/hescore-hpxml).
- Rule results out of 180: R2 (≥80% Python) fails 17. R3 (≥50 non-test `.py` files) fails 48. R5 (licence) fails 0. 3 are excluded as >30% vendored or generated (bleach, pip, pydicom). 0 forks. 0 notebook-heavy repos. **116 pass everything.**
- 9 repos are flagged for you to glance at as possible monorepos (5+ `setup.py`/`pyproject.toml` files), e.g. azure-cli, cloud-custodian, hydra, mypy. The flag does not exclude them.
- 4 repos are archived on GitHub (python-storage, instructlab, synapse, bleach). No rule mentions archiving; I'm only telling you.

**What each option leaves** (K = at least 10 usable tasks per repo; all rules applied; tasks without a test box removed)

| Task source (D11) | Files (D19) | Repos | Tasks | Median tasks/repo |
|---|---|---|---|---|
| A. SWE-bench only | 2–10 | 9 | 471 | 38 |
| A. SWE-bench only | 1–10 | 9 | 2,081 | 178 |
| B. SWE-bench + SWE-Gym | 1–10 | 17 | 3,392 | 138 |
| C. Fresh only | 2–10 | 43 | 956 | 15 |
| C. Fresh only | 1–10 | 105 | 3,217 | 18 |
| D. Mixed | 2–10 | 49 | 1,438 | 16 |
| **D. Mixed** | **1–10** | **109** | **5,298** | **19** |
| D + SWE-Gym + Pro | 1–10 | 116 | 6,687 | 21 |

Full table with K = 15 and 20: `results/step2/gate_a_options.csv`. *Which means: only 1–10 gives RQ2 more than ~50 repos. Only SWE-bench gives many tasks per repo.*

**How much the RQ2 test can see** (`results/step2/gate_a_power.csv`): the weakest correlation between repo shape and method score it could reliably detect (80% chance).

| Repos | 1 pair tested | 20 pairs tested (after correction) |
|---|---|---|
| 12 | 0.74 | 0.87 |
| 30 | 0.50 | 0.64 |
| 60 | 0.36 | 0.48 |
| 109 | ~0.27 | ~0.37 |

*Which means: with SWE-bench's 12 repos, RQ2 can only see very strong links. A "nothing found" would be weak evidence.*

**Cost per repo** (`results/step2/cost_per_repo.csv`, 24 repos spread by size)
- Code snapshot: median 9 MB; 2.5 GB for all 116. Download: 3–17 seconds.
- Building one graph: 0.1–2 s for most repos, 13 s for statsmodels, 32 s for checkov. 94% of tasks have their own base commit. *Which means: "graph per task commit" (D17, Gate B) is roughly one graph per task. That costs minutes to a few hours, not days.*

**Gate B groundwork (builders only, no methods)** (`results/step3_prep/builders_summary.csv`)
- On pytest and cekit (picked by rule), my `ast` builder, tree-sitter and grimp produce **exactly the same edges** (100% overlap). pydeps finds more edges: 19% more on pytest, 47% more on cekit. Most of the extras (86% on pytest, 74% on cekit) are edges to parent package `__init__.py` files, which Python runs first. I haven't yet explained the rest; that's Gate B work.
- This is only for D9 at Gate B. Nothing is decided.

## 5. What went wrong or looks odd

1. **Runbook 9.2 numbers were computed with a different rule than 9.2 states.** 9.2 says the 200-line cap counts "the source patch only". The runbook's numbers reproduce almost exactly (one task off) when the cap counts *every* file in the patch: docs, changelogs and tests too. I used the rule as written. The gap is 1–2%. It's part of D19.
2. **"125 repos appear in more than one dataset" (runbook G18):** I count 126 (including Loc-Bench). Small, but I'm noting it.
3. **Bug, fixed: silent zero line counts.** The line counter (pygount) misread 879 UTF-8 files on Windows, gave each 0 lines, and raised no error. Fixed and rerun. It changed one rule result: aio-libs/yarl went from failing R2 to passing (72% → 84% Python). Logged in `POSTHOC.md`.
4. **Bug, fixed: licence check.** matplotlib keeps its licence in a `LICENSE/` folder, which the first check missed. Fixed; matplotlib now passes R5.
5. **Bug, fixed: builder crash.** checkov has *folders* named `something.py`. The builder crashed on them. Fixed; unreadable files are now logged. Separately, `.py` files the builder skips (e.g. under folders like `my-example/`, which Python cannot import by name) were not being counted, even though a code comment said they were. Now they're counted: 886 in pylint (doc examples) and 329 in sphinx (test fixtures).
6. **My slip, fixed:** for the builder comparison, I first ran seaborn and django-rest-framework-json-api from memory instead of applying the selection rule. The rule picks pytest and cekit. I reran with those. The first two stay in the results, labelled "extra".
7. **R2 depends on definitions.** 6 R2 failures come from what counts as "Python" or "test", not from real other-language code: mypy (bundled `.pyi` type stubs), pandas (79.5%, `.pyi`/Cython), attrs (`.pyi`), sqlfluff (1,991 `.sql` test fixtures in a `test/` folder, which the 9.2 rule doesn't treat as a test folder), astropy (bundled C in `cextern/`), dimod (79.9%). I measured both definitions. You choose in D10. I haven't applied either.
8. **Dropped items, with counts:** 1 repo can't be downloaded (deleted from GitHub). 38 tasks have no test box (37 SWE-Gym, 1 SWE-bench-Live). Loc-Bench has no fixing-test list and no test boxes, so it fails R1 as the runbook expected.
9. **SWE-Gym images:** 2 of 8 sampled images had no `latest` tag, so their size is unknown. They exist, but the tag scheme differs from what I assumed.

## 6. What I'm unsure about

- **Whether the Windows machine can run the test boxes at scale.** Docker works, but I haven't run a real SWE-bench box yet (that's Step 5). If it's too slow or runs out of memory, an Ubuntu machine or a cloud box may be needed. I'll know at the pilot.
- **Download volume.** The execution key needs one test box per task. At ~2 GB each, 5,000 tasks is ~10 TB. That's why I added a "tasks per repo cap" option to D10. D12 (Gate C) could also use the execution key only on a subset.
- **"Task" means one PR.** A PR that changes 3 files later becomes 3 tasks, one per starting file (roadmap 5e). The counts here are PRs.
- **The monorepo flag** (5+ packaging files) is crude. Look at the 9 names. None are auto-excluded.
- The provisional snapshot I measured each repo at is the base commit of its newest usable task. The rules could come out slightly differently at another commit.

## 7. What runs next when you say go

After D16, D11, D19, D10 and the seed:
1. Draw the repo sample by the seed-and-hash rule (code is written and tested: `src/depgraphs/sampling.py`). Pin one commit per repo. Write `data/repos.csv`. **About 10 minutes.**
2. Domain labels from each repo's own GitHub description, using the fixed list in the D10 card. **About 20 minutes.** You spot-check.
3. Then Step 3 work up to Gate B: full builder comparison with disagreement examples, the numbers for D17 and D18, hand-checks of 20 files per repo, and 5 files for you. **2–4 hours**, depending on the sample size.

Already done and waiting for Gate B: the graph builder with every Appendix A rule as a switch, 19 unit tests, and the 4-builder comparison.

## 8. Paper words from this step

- ready-made test box → prebuilt Docker execution environment
- usable task → eligible instance
- fixing test → fail-to-pass (F2P) test
- line cap → maximum changed lines in the source diff
- duplicate task → the same PR in two benchmarks (cross-benchmark deduplication)
- group (for sampling) → stratum
- how much the RQ2 test can see → statistical power; minimum detectable effect
- snapshot → pinned commit SHA
- parent package edge → import of a package's `__init__` module implied by a submodule import

---

## Decision cards

### D16 — Which research questions go in this paper?

Why it matters: each RQ adds steps, time and cost. It's cheap to cut one now and expensive after the freeze.

Options:
  A. All six (RQ1–RQ6).
     Good: the full picture.   Bad: RQ6 needs formal proofs that you must check yourself; RQ5 costs money.   A reviewer might say: "two papers in one".
  B. RQ1–RQ5. RQ5 only if Gate G approves a budget. RQ6 deferred to a follow-up.
     Good: one clear empirical paper, and the proof work doesn't block it.   Bad: loses the formal angle.   A reviewer might say: "why no theory?"
  C. RQ1–RQ4 only (all free).
     Good: fastest, no spend.   Bad: never tests whether order changes what a model needs (RQ5), which is the practical question.   A reviewer might say: "a stand-in with no check against the real thing".

What changes later if you pick A vs B: A adds Step 11 (formal) before writing. B leaves Step 11 out; RQ5 still depends on D15.
Cost to change later: cheap now; medium after the freeze.
Numbers you should see first: `paper/rqs.md`.
My suggestion: B, because RQ1–RQ4 stand alone, RQ5 answers the practical question, and RQ6 has its own proof-checking cost. This is a suggestion; it's your call.
While waiting I will: nothing that depends on this.

Reply with: "D16: B"   (or write your own option)

### D11 — Where do tasks come from?

Why it matters: it fixes how many repos RQ2 can compare, how comparable we are to published work, and whether Step 10 can use tasks newer than the model's training.

Options (numbers use 1–10 files, K = 10, all rules):
  A. SWE-bench only — 9 repos, 2,081 tasks. Tasks from 2012–2023.
     Good: best known; closest to LocAgent and CoSIL.   Bad: 9 repos is too few for RQ2 (see the power table). Step 10 would be almost certainly contaminated.   A reviewer might say: "RQ2 on 9 repos is anecdote".
  B. SWE-bench + SWE-Gym — 17 repos, 3,392 tasks. All before mid-2024.
     Good: lots of tasks per repo.   Bad: still few repos; all old.
  C. Fresh only (SWE-bench-Live + SWE-rebench) — 105 repos, 3,217 tasks, 2016–2025.
     Good: many repos; newer tasks.   Bad: few tasks per repo (median 18); no comparability block.
  D. Mixed: SWE-bench as a fixed comparability block, plus fresh repos drawn by rule — 109 repos, 5,298 tasks.
     Good: RQ2 gets ~100 repos; comparability kept; Step 10 can use the newer tasks.   Bad: two populations to keep apart in analysis.   A reviewer might say: "mixing benchmarks mixes curation styles" (answer: report per block).
  (E. D plus SWE-Gym and Pro — 116 repos, 6,687 tasks. Adds 7 repos; Pro's repos are copyleft.)

What changes later if you pick A vs D: sample size in every later step; whether RQ2 is worth running.
Cost to change later: expensive — the graphs, keys and test-box runs are all per task.
Numbers you should see first: `results/step2/gate_a_options.csv`, the power table in §4.
My suggestion: D, because it's the only option giving RQ2 enough repos while keeping a SWE-bench block. This is a suggestion; it's your call.
While waiting I will: Gate B groundwork only (builders), which uses no task data.

Reply with: "D11: D"

### D19 — Which tasks count: file-count range, line cap, and what the cap counts

Why it matters: 66% of usable tasks change one file. The 2–10 filter was set when the answer key came only from co-edited files. Now single-file tasks still have a key (symbol and execution sources; G4).

Options:
  A. Keep 2–10 as written. Mixed option: 49 repos, 1,438 tasks.
     Good: every task has a co-edited file.   Bad: loses two thirds of the data; RQ2 drops to 49 repos.
  B. 1–10. Mixed option: 109 repos, 5,298 tasks.
     Good: much more data.   Bad: single-file tasks rest on the symbol and execution keys only.
  C. 1–10, and report single-file and multi-file tasks separately everywhere.
     Good: B's data, plus the difference stays visible.   Bad: more tables.

Line cap: 200 changed lines, counted on **non-test `.py` files only** (as 9.2 is written), or on the whole patch (how 9.2's numbers were actually made). The difference is 1–2% of tasks. Raising the cap to 300 or dropping it adds 1–4%.

What changes later if you pick A vs C: task count; RQ2 repo count; every per-task step's run time.
Cost to change later: expensive.
Numbers you should see first: `results/step2/linecap_grid.csv`, the options table in §4.
My suggestion: C, with a 200-line cap on non-test `.py` files only. It keeps the data, keeps the difference visible, and follows 9.2 as written. This is a suggestion; it's your call.
While waiting I will: nothing that depends on this.

Reply with: "D19: C, cap 200 source-only"

### D10 — Which repos, and how many?

Why it matters: this is the sample every result is measured on. It must be fixed by rules and a seed before anything is measured.

This card has 5 parts. Reply to each.

**D10a — Minimum usable tasks per repo (K).** 10 / 15 / 20. With the Mixed option and 1–10: 109 / 73 / 54 repos.
  Suggestion: 10. RQ2 needs repos more than it needs tasks per repo.

**D10b — Which R2/R3 definition.**
  a. As written: `.pyi` and Cython files count as other languages; only `tests/` and `testing/` are test folders; `cextern/` isn't vendored.
  b. `.pyi/.pyx/.pxd/.pxi` count as Python; `test/` is also a test folder; `cextern/` is vendored. Adds astropy, pandas, mypy, sqlfluff, dimod; drops cekit (46 files); attrs still fails R3. Mixed + 1–10 + K=10: 109 → 113 repos.
  Neither mentions graph structure. `results/step2/r2_variants.csv` lists every repo under both.
  Suggestion: b. Stub and Cython files are part of the Python code, and `test/` is a common test-folder name. This is a suggestion; it's your call.

**D10c — How many repos, and drawn how.**
  A. Take every repo that passes (~109). No draw is needed; the rules alone fix the sample.
  B. SWE-bench repos as a fixed block, plus 20 drawn per size group (small/medium/large) from the rest: ~69 repos.
  C. The same, but 10 per size group: ~39 repos.
  Size groups by non-test `.py` files (Mixed + 1–10 + K=10): under 115 / 115–249 / 250+.
  Suggestion: A, if the test-box cost in D10d is acceptable. Otherwise B. It's your call.

**D10d — Cap on tasks per repo** (drawn by the same seed; the key cost is one test box per task).
  None: 5,298 tasks (~10 TB downloaded). Cap 30: 2,215 tasks. Cap 20: 1,819 tasks.
  Suggestion: cap 20 or 30, drawn by seed. That keeps the repo count for RQ2 and cuts downloads by 58–66%.

**D10e — Domain labels (G17).** Fixed list before labelling: web/API, scientific/numeric, data/ML, developer tools/testing, CLI/infrastructure, other. Assigned from each repo's own GitHub description. You spot-check.
  Suggestion: approve as is.

**Plus: the seed.** Write it in `DECISIONS.md`.

Pilot repos (N1) will be the two smallest in the drawn sample, by rule.
Cost to change later: expensive after Step 5.
Numbers you should see first: `results/step2/gate_a_repos.csv`, `gate_a_options.csv`, `gate_a_strata.csv`, `r2_variants.csv`, `cost_per_repo.csv`.
While waiting I will: only builder work that doesn't depend on which repos are chosen.

Reply with: "D10: K=10, R2=b, draw=A, cap=20, labels OK, seed=____"
