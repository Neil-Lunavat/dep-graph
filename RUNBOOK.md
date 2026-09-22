# RUNBOOK — how this research actually gets done

Companion to `ROADMAP.md`. Written 22 September 2026.
Every dataset, tool, and paper link in sections 9–12 was checked by web search on that date,
and the task counts in section 9 were computed that day from the public dataset files.

---

## 0. For Claude Code — read this first

There are two files.

- `ROADMAP.md` says **what** the research is: the steps, the research questions, the
  appendices.
- `RUNBOOK.md` (this file) says **how** to run it: who does what, how to report to Neil,
  what the roadmap is missing, every decision Neil has to make, and where the data, tools,
  and papers are.

Rules for using them together:

1. **Do not edit `ROADMAP.md`.** Where this file adds to it, the addition has a gap number
   (G1, G2, …). When you apply one, log it in `DECISIONS.md`.
2. **Order of authority** when things disagree:
   (a) the neutrality rule in `ROADMAP.md` — always wins;
   (b) Neil's recorded decisions in `DECISIONS.md`;
   (c) this file;
   (d) the step text in `ROADMAP.md`.
3. **Before every step**, re-read: the neutrality rule, that step in `ROADMAP.md`, that
   step's row in section 8 here, and `DECISIONS.md`.
4. **Facts here are a starting point, not gospel.** Recount every number from the data. If
   something in this file turns out wrong, say so in the next check-in and log it. Do not
   quietly work around it.
5. **You are the hands. Neil is the judgement.** You build, run, measure, and explain. Neil
   decides, checks, interprets, and writes. Section 2 has the exact split.

---

## 1. The whole thing in plain words (for Neil)

Someone has to change one file in a project they don't know.
A method hands them a list of other files, in order.
They read down the list.
A good list gets them to the files the change really needed, early, so they read less.

We try lots of list-making methods on lots of real code changes from real projects.
For each one we measure: how much did you have to read before you had seen the files the
change needed?

Then we check whether the *shape* of a project (how tangled its imports are, whether a few
files are imported by everything) goes along with which method does best.

Then, if there is money for it, we check the real thing: give an AI only the first part of
each list and see whether it can still make the change.

Steps 1–9 cost nothing and measure a **stand-in**: "did the list reach the needed files
early?" Step 10 costs money and measures **the real thing**: "could the change be made with
less context?"

We do not know the answers. Maybe a plain method beats clever ones. Maybe order doesn't
matter at all. Maybe project shape explains nothing. Each of those is a real result and gets
reported exactly like a positive one.

**The answer key, in plain words:** for each real change, the files we have *evidence* it
needed — files changed with it, files that define the names the new code uses, and files
that actually ran during the tests the change fixed. It misses files a developer only read.
So it is a floor, not the full truth. That's why a list is never punished for extra files,
only charged for the reading they cost.

---

## 2. Who does what

| Job | Claude Code | Neil |
|---|---|---|
| Set up the workspace, lockfile, one-command pipeline | Does it | — |
| Check the machine (disk, RAM, CPU, Docker) and accounts | Does it, reports | Provides machine, tokens, keys |
| Write research questions | Drafts `paper/rqs.md` | Decides scope (D16), edits wording |
| Choose repositories | Applies written rules, samples by fixed seed, pins SHAs | Approves the rules and sample size (D10) |
| Build graphs | Compares builders, builds, counts failures, checks 20 files per repo | Picks builder and rules (D9, D17, D18); spot-checks 5 files |
| Measure project shape (Table 1) | Proposes the fixed metric list, computes it | Approves the list **before** computing |
| Tasks and answer key | Filters, builds keys from 3 sources, measures agreement, prepares audit sheet | Decides D11, D12, D19, D20; **does the manual audit** (30–50 tasks) |
| Freeze the design | Writes `paper/metrics.md`, test list, tags `freeze-1` | Approves the freeze |
| Run methods, score, stats, sensitivity | Does all of it | Reads results, asks questions |
| Budget experiment (costs money) | Estimates cost, runs, logs everything | Decides D15, provides API key and spend cap |
| Formal analysis | Drafts definitions, runs exact solutions on small graphs, attempts proofs marked DRAFT | **Checks every proof.** Nothing is called a theorem until Neil has checked it |
| Paper | Builds `results/FACTS.md`, figures, tables, the release package, the AI-use log | **Writes the paper** and the AI-use statement |

Rough hands-on time for Neil (Claude Code must re-estimate and report in each check-in):
decision batches 10–20 minutes each; the manual audit 2–3 hours; proof checking depends on
what comes out of Step 11; writing is Neil's.

---

## 3. How Claude Code talks to Neil

Neil runs several Claude Code sessions at once. He comes back, reads, decides, and leaves.
Everything written *for him* must be quick to read and impossible to misread.

### 3.1 Two voices

**Neil voice** — used in `reports/`, decision cards, and anything addressed to him.

- Short sentences. One idea per sentence.
- Everyday words first. If a technical word is needed, give the plain meaning in brackets
  the first time it appears in each report. Example: "SCC (a clump of files that all import
  each other in a loop)".
- Every number gets a "which means…" line after it.
- What Neil must do goes **first**, not last.
- About one screen per section. Details go in linked files.
- Say plainly what you are unsure about.
- Use the same plain word for the same thing every time. The words live in `GLOSSARY.md`.
  Don't swap synonyms.

**Paper voice** — used in `paper/*.md`, `results/FACTS.md`, figure captions, table headers.
Precise, standard terms. This is the vocabulary Neil will write the paper in.

Every report ends with a short **"Paper words from this step"** list (plain word → paper
term) so Neil picks up the vocabulary while reading.

### 3.2 Neutral words — both voices

Say what was measured. Don't say what it "shows" beyond that.

| Don't write | Write instead |
|---|---|
| "X is better" / "X wins" | "X reached the key with less reading on 7 of 12 repos" |
| "as expected" / "confirms" / "proves" | "measured" / "in this data" |
| "surprisingly, Y failed" | "Y's area under the curve was 0.12 lower" |
| "the graph method works" | "the graph method's curve was above the random floor by …" |
| "no effect, so it failed" | "no difference larger than chance was measured (null result)" |

Direction and size of every effect, including effects in the unexpected direction.

### 3.3 Check-in report template

Write each report to `reports/NN-stepX.md` and copy it to `reports/LATEST.md`.

```
# Check-in NN — Step X — <date>

## 1. Status in one line
(e.g. "Step 3 done. Waiting on you for 2 decisions.")

## 2. What I need from you — do this first
- Decisions: D__ , D__  (cards at the bottom)
- Things to look at: <file>, <what to check>
- Time needed from you: about __ minutes

## 3. What I did (plain, 8 lines max)

## 4. What I saw
- <number> — which means <plain meaning>
(observations only; no conclusions about which method is "better")

## 5. What went wrong or looks odd
(every failure, every dropped item, with counts)

## 6. What I'm unsure about

## 7. What runs next when you say go
(and roughly how long it will take)

## 8. Paper words from this step
- plain word → paper term

## Decision cards
```

### 3.4 Decision card template

```
### D__ — <the question, in one plain sentence>

Why it matters: <one or two plain sentences>

Options:
  A. <what it means>
     Good: …   Bad: …   A reviewer might say: …
  B. …
  (C. …)

What changes later if you pick A vs B: <which steps, how>
Cost to change later: cheap / medium / expensive — because …
Numbers you should see first: <table or file>
My suggestion: <option>, because <one line>. This is a suggestion; it's your call.
While waiting I will: <only work that does not depend on this decision>

Reply with: "D__: A"   (or write your own option)
```

### 3.5 Glossary starter — put this in `GLOSSARY.md` and keep adding

| Plain word (Neil voice) | Paper term |
|---|---|
| starting file | seed file / target file |
| the list | ordered file list; reading order |
| answer key | evidence-based relevant set; ground truth (lower bound) |
| hop | one import edge |
| import loop, clump | strongly connected component (SCC); collapsing them = condensation |
| hub file | high in-degree node |
| tangled | high cyclicity; large share of files inside SCCs |
| reading cost | cumulative files / lines / tokens read |
| the curve | coverage–cost curve; its area = AUC |
| random floor | random-order baseline |
| cheat ceiling | oracle ordering (answer-key files first) — an upper bound, not a method |
| peeking at the future | leakage |
| nothing measurable | null result |
| how big the difference is | effect size |
| lucky-looking wins from testing lots of things | multiple comparisons; correction for them |
| the AI already saw it in training | training-data contamination |
| one PR's tasks aren't separate samples | clustered / non-independent observations |
| changing the plan after seeing results | post-hoc change |

---

## 4. Working rhythm

- **Gates.** Run until the next gate in section 8, write the check-in, stop.
- **Batch decisions.** At the start of each step, list every decision that step will need
  and ask them together. Neil should not be interrupted three times for one step.
- **Never idle, never jump ahead.** While waiting, do work that does not depend on the
  pending decision. Never run the main experiment on a "default" to save time — that quietly
  makes the decision for Neil.
- **Long jobs are resumable.** Cache per repo and per task. Write progress to
  `logs/progress.json` with counts done, failed, and time left.
- **Parallel where independent.** Per-repo and per-task jobs run in parallel within the
  machine's limits (measure these in Step 0).
- **Everything comes from a script.** Every file in `results/` is produced by code in `src/`
  and regenerated by the single entry point. No hand-edited results.
- **Commit often.** Small commits with clear messages. Tag the freeze (section 5, N2).

---

## 5. Neutrality guards added on top of the roadmap

**N1 — Blind pilot.** After Step 5, run the whole pipeline on 2 repos to find bugs. During
the pilot, show Neil only pipeline health: errors, runtimes, counts, how often each key
source produced files. **Do not show method-versus-method numbers.** Store pilot outputs in
`results/pilot/` and keep them out of the paper. The pilot exists to find bugs, not to peek.

**N2 — Freeze before the main run.** Before Step 6 runs on the full task set, tag the repo
`freeze-1`. The tag must contain: the repo sample, task filters, key rules, the Table 1
metric list, `paper/metrics.md` (formulas), the ordering rules, the method adaptation spec,
the statistical tests, and the full list of property/method pairs to be tested in Step 8.

**N3 — No decision uses main results.** If Neil asks to change something after results
exist, say in plain words: "This is a post-hoc change." Log it in `POSTHOC.md` with the
reason, rerun everything affected, and flag that the paper must mention it. Correctness
bug fixes are allowed and also logged there.

**N4 — Report per key source.** Always report results for each key source separately
(co-edited, symbol, execution) as well as their union. Reason: the symbol source overlaps
with the import graph by construction (if new code uses a name, the file usually imports
it). A union-only result could flatter graph methods without anyone noticing.

**N5 — The execution key must not copy the import graph.** When Python imports a module,
every top-level line in it runs. So "any line executed" marks nearly every imported file as
needed, and the execution key becomes a copy of the import closure. See G6 and D20.

**N6 — Reminder from the roadmap.** Never filter tasks on graph distance. Measure it (RQ3).

**N7 — Sampling by seed, not by judgement.** A "blind" helper that picks repos is not
enough. What makes the sample fair is: rules written first, then a fixed random seed written
in `DECISIONS.md`, then a mechanical draw (section 9.4). Anyone can rerun it and get the same
sample.

**N8 — Our numbers are not the same measurement as published numbers.** Our method input is
one file, with no issue text and no language model. LocAgent, CoSIL, and RepoGraph are
evaluated with issue text and a model. Never put our Acc@k beside their reported Acc@k as if
comparable. Say "structure-only adaptation" every time.

---

## 6. What `ROADMAP.md` is missing, and how to fill it

**G1 — Which snapshot of the code does the graph come from?**
Each task has its own base commit, often years apart in the same repo. A graph built at one
pinned commit will contain files that did not exist yet, or miss files that did.
Fill: build the graph at **each task's base commit** (cache by commit hash). Table 1 is
computed at the repo's pinned SHA and also summarised across task commits. → Decision D17.

**G2 — Files the change creates.** They don't exist at the base commit, so they can never be
a seed or in the key. Count them per task and report the count.

**G3 — Test files.** Are they graph nodes? Can they be seeds? Can they be in the key?
Datasets like SWE-bench keep tests in a separate `test_patch`, which helps. → D18.

**G4 — Single-file changes.** The 2–10 file filter was set when the key came only from
co-edited files. Now the key has three sources, so a one-file change still has a key
(symbol and execution sources). This matters a lot in practice: 75% of SWE-bench tasks and
100% of SWE-bench Lite edit one file (section 9.2). → D19.

**G5 — Where the tests run.** The execution key needs each task's test suite to actually
run at its old commit. Mining PRs yourself means building those environments yourself,
which is slow and fragile. Datasets with prebuilt Docker images avoid this. → D11.

**G6 — What counts as "executed".** See N5. → D20.

**G7 — Methods that need more than a graph.** BM25 needs a query. Embeddings need a model.
Published approaches expect issue text and a language model, which we forbid (D4, D7).
Each needs a written adaptation spec, fixed before the freeze. → D22, D23.

**G8 — Turning sets into lists.** Closures and neighbourhoods are sets. Cycle groups are
clumps. Both need a fixed rule to become an ordered list. → D21 (this is the roadmap's
Step 6 "Decide", given a number).

**G9 — The seed's own cost, and a ceiling.** Decide whether the seed file's reading cost
counts in the curve (it is the same for every method). Add a **cheat ceiling**: the answer-key
files first, in the best possible order. It uses the answer, so it is labelled as a
reference, never as a method. It tells Neil how much room there is above every method. → D13.

**G10 — Pilot and freeze timing.** Pilot after Step 5 (N1). Freeze before Step 6 (N2).

**G11 — The statistical unit.** One number per task, averaged within each PR, so each PR
counts once. Then compare. → D14.

**G12 — What the model sees in Step 10.** Issue text + seed file + the first N tokens of the
list. The model outputs a patch. The dataset's own harness judges it. Fresh tasks for the
contamination check come from monthly-updated datasets (section 9.1). → D15.

**G13 — Test the pipeline itself.** Before real data: tiny toy repos with hand-known graphs,
cycles, keys, and curves. Every builder rule and every metric formula gets a unit test with
a hand-computed answer.

**G14 — RQ3 and RQ4 definitions.** RQ3 distance: shortest path from seed to each key file,
reported both following import direction and ignoring direction, plus the share with no path
at all. RQ4 wrong seed: pick uniformly at random, with a fixed seed, among files at exactly
distance d (ignoring direction) from the true seed. → D26.

**G15 — AI-use log.** ACM requires disclosure of generative-AI use for content including code
and data, in the Acknowledgements (section 12, last group). Keep `AI_USE.md`: date, step,
what Claude Code did, which model. Neil writes the final statement from it.

**G16 — Machine and accounts check** in Step 0 (section 13).

**G17 — Domain labels** for Step 2 need a fixed list of categories, decided before labelling
(section 9.4).

**G18 — Duplicate repos across datasets.** 125 repos appear in more than one of the datasets
in section 9. Deduplicate tasks by (repo, PR number or base commit). A repo counts once in
the sample.

**G19 — Formal analysis and writing split.** Claude Code drafts definitions, runs exact or
brute-force solutions on small graphs, and attempts proofs, all marked DRAFT. Neil checks
every proof. For the paper: Claude Code builds `results/FACTS.md` (one line per number, each
pointing to the file it came from), figures, LaTeX tables, and the release package. Neil
writes the prose.

---

## 7. Every decision Neil makes

D1–D8 are already settled in `ROADMAP.md`. These are the open ones.

| ID | Question (plain) | When | What Claude Code must show first | Changing it later |
|---|---|---|---|---|
| D16 | Which research questions are in this paper? | Gate A | `paper/rqs.md` draft; each RQ with its measurement and how it could come out negative | Cheap now |
| D11 | Where do tasks come from? | Gate A | Section 9.2 table recounted; environment availability; date ranges; licences | Expensive |
| D19 | Keep the 2–10 file filter, or allow 1–10? What line cap? | Gate A | Section 9.2 table recounted under both options | Expensive |
| D10 | Which repos, and how many? | Gate A | Candidate table after rules; strata; eligible tasks per repo; disk and time per repo | Expensive after Step 5 |
| D9 | Which graph builder, and the 4 open rules in Appendix A | Gate B | Builders side by side on 2 small repos; disagreements with examples; toy tests | Medium |
| D17 | Graph per task commit, or one pinned commit? | Gate B | Number of distinct base commits; build time per graph | Medium |
| D18 | Role of test files | Gate B | Share of files that are tests; how often tests would enter the key | Medium |
| D12 | Which key sources are primary, which are for checking? | Gate C | Agreement between sources on a small subset (no method results); cost of the execution source | Medium |
| D20 | What counts as "executed" for the execution key | Gate C | On 5 pilot tasks: key sizes under each rule (sizes only, no method results) | Medium |
| D13 | Reading-cost unit, budget grid, seed cost counted or not | Gate E (freeze) | File-size and token-size distributions | Forbidden after freeze |
| D14 | Statistical tests, effect sizes, correction | Gate E | Plain description of options (below) | Forbidden after freeze |
| D21 | Tie-breaking and within-clump order | Gate E | Options (below) | Forbidden after freeze |
| D22 | Adaptation spec for BM25, co-change, and published approaches | Gate E | Written spec per method | Forbidden after freeze |
| D23 | Which embedding model | Gate E | Model sizes, licences, what the machine can run | Forbidden after freeze |
| D24 | Freeze by git tag only, or also public pre-registration (OSF)? | Gate E | What OSF pre-registration involves | — |
| D26 | Wrong-seed sampling rule | Gate E | G14 proposal | Forbidden after freeze |
| D15 | Model, repetitions, budget grid, total spend | Gate G | Cost formula filled with real numbers; task dates vs model training cutoff | Before any spend |

### Notes for the hardest ones

**D11 + D19 + D10 are one decision in practice.** RQ2 compares *repositories*, so it needs
many repos. Per-repo numbers need enough tasks per repo. These pull against each other.
From section 9.2:

- SWE-bench gives 12 repos. With the 2–10 filter, only 9 of them have 15+ usable tasks.
  Verified drops to 68 usable tasks; Lite drops to zero.
- SWE-rebench gives many repos but few tasks each: with 2–10, 32 repos have 10+ usable tasks;
  with 1–10, 124 repos do.

Options Claude Code should put in front of Neil for D11:

- **A. SWE-bench only.** 12 repos, well known, closest to the setting of LocAgent and CoSIL.
  Tasks are from 2012–2023, so for Step 10 they are almost certainly in model training data.
  Few repos for RQ2.
- **B. SWE-bench + SWE-Gym.** 23 repos, all older than mid-2024.
- **C. Fresh only (SWE-rebench and/or SWE-bench-Live).** Hundreds of repos with prebuilt
  environments, newer tasks, few tasks per repo.
- **D. Mixed.** A SWE-bench "comparability block" plus a fresh block drawn by the rules in
  section 9.4.

Suggestion for Claude Code to present (Neil decides): D. It covers both comparability and
number of repos, and it lets Step 10 use the newer tasks.

**D19 options:** A. keep 2–10 as written (co-edits always exist; far fewer tasks);
B. 1–10 (single-file changes enter with symbol + execution keys only);
C. 1–10, but report single-file and multi-file tasks separately everywhere.
Suggestion to present: C.

**D20 options (execution key):**
A. File counts if any of its lines ran. Simple, but import-time lines make it copy the
import graph (N5).
B. File counts if a line **inside a function or method body** ran. Removes import-time noise.
C. B, minus files that also run in a do-nothing test in the same environment (removes
test-framework and fixture noise).
D. Only files on the call path to the changed lines. Most precise, much more work.
Suggestion to present: B as primary, C as a sensitivity check.

**D21 options:** A. alphabetical by path (deterministic, meaningless, same for everyone);
B. random with a fixed seed, averaged over 5 seeds. Suggestion to present: B — it cannot
accidentally favour any directory layout, and it is cheap because no model is involved.

**D14 options, in plain words** (Claude Code explains these in Neil voice):
- Each PR contributes one number (its tasks averaged).
- Two methods over the same PRs: Wilcoxon signed-rank test (compares paired numbers without
  assuming a bell curve) + an effect size such as Vargha–Delaney A12 (the chance that one
  method beats the other on a random PR).
- Many methods over many repos: Friedman test + Nemenyi post-hoc (Demšar 2006).
- Structure vs performance (RQ2): Spearman correlation for each pre-listed (property,
  method) pair across repos, with Holm or Benjamini–Hochberg correction, labelled
  exploratory, every pair reported.
- Confidence intervals by bootstrap that resamples whole repos.

**D15:** Claude Code must fill in: tasks × methods × budgets × repetitions × average input
tokens × current price, plus output tokens. Look up models, prices, and training cutoffs in
the official docs at the time (https://docs.claude.com/en/api/overview), never from memory.

---

## 8. Step by step: Claude Code's job, Neil's job, where to stop

| Step | Claude Code does | Neil does | Stop at |
|---|---|---|---|
| 0 | Repo skeleton; lockfile; `make all`; `DECISIONS.md`, `GLOSSARY.md`, `AI_USE.md`, `POSTHOC.md`, `reports/`; machine check (section 13); download dataset files (section 9.1) | Provide machine and accounts | — |
| 1 | Draft `paper/rqs.md` from the roadmap RQs | D16 | Gate A |
| 2 | Recount section 9.2; apply rules (9.4); build candidate table; propose sample; pin SHAs after approval | D11, D19, D10 | **Gate A** (one batch with Step 1) |
| 3 | Toy-repo tests (G13); compare builders; build graphs per task commit; count unresolved imports; check 20 files per repo by independent reading | D9, D17, D18; spot-check 5 files | **Gate B** |
| 4 | Propose the fixed Table 1 metric list; after approval, compute | Approve the list **before** computing | Gate B |
| 5 | Filters; answer key from 3 sources; agreement; `audit/AUDIT_SHEET.md` for 30–50 randomly drawn tasks | D12, D20 at Gate C; then the manual audit | **Gate C**, then **Gate D** (audit) |
| Pilot | Blind pilot on 2 repos (N1) | Read the health report | — |
| Freeze | `paper/metrics.md`, ordering rules, adaptation spec, test list; tag `freeze-1` | D13, D14, D21, D22, D23, D24, D26; approve freeze | **Gate E** |
| 6 | Run every method on every task; log failures and runtimes | — | — |
| 7 | Curves, AUC, comparability metrics, ordering checks | — | — |
| 8 | Tests, effect sizes, correlations, RQ3 distances, per-source results (N4) | Read; ask questions | **Gate F** |
| 9 | Wrong-seed runs | — | Gate F |
| 10 | Cost estimate first; then run with full logs | D15; API key; spend cap | **Gate G** (before spend), **Gate H** (results) |
| 11 | Formal definitions; exact solutions on small graphs; DRAFT proofs | Check every proof | **Gate I** |
| 12 | `results/FACTS.md`; figures; tables; release package; `AI_USE.md` summary | Write the paper | **Gate J** |

### What the audit sheet (Step 5) looks like

One block per task, sampled at random with a fixed seed. Designed for about 3 minutes each.

```
Task 17 of 40 — <repo> PR #<n>
Issue in one line: …
What the change did, in one line: …
Starting file: …
Answer key:
  - path/a.py   [co-edited]            why: edited in the same PR
  - path/b.py   [symbol]               why: defines `parse_header`, used in the new code
  - path/c.py   [execution]            why: function `load()` ran in the fixing test
Questions:
  1. Is this one change, or several unrelated changes bundled?   one / bundled / unsure
  2. Any key file that looks wrong?                              no / yes: ____
  3. Any clearly needed file missing?                            no / yes: ____
```

Claude Code then counts the answers and records them in `results/manual_audit.csv`,
whatever they say.

---

## 9. Data sources (checked 22 September 2026)

### 9.1 Task datasets

| Dataset | Where | Size | Environments | Task dates | Notes |
|---|---|---|---|---|---|
| SWE-bench (full test) | HF `SWE-bench/SWE-bench` (also `princeton-nlp/SWE-bench`); harness https://github.com/SWE-bench/SWE-bench | 2,294 tasks, 12 repos | Docker, via the official harness | 2012-08 → 2023-08 | Harness recommends x86_64, 120 GB free disk, 16 GB RAM, 8 cores |
| SWE-bench Verified | HF `SWE-bench/SWE-bench_Verified` | 500 tasks, 12 repos | Same | 2013-01 → 2023-08 | OpenAI stopped reporting it on 23 Feb 2026, citing contamination and flawed tests (https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/). Matters for Step 10; much less for Steps 1–9, which use no model |
| SWE-bench Lite | HF `SWE-bench/SWE-bench_Lite` | 300 tasks, 12 repos | Same | 2012-09 → 2023-07 | Every task edits one file |
| SWE-Gym | HF `SWE-Gym/SWE-Gym`; https://github.com/SWE-Gym/SWE-Gym | 2,438 tasks, 11 repos | **Verify** how images are provided | 2018-09 → 2024-05 | MIT licence on the dataset |
| SWE-bench-Live | HF `SWE-bench-Live/SWE-bench-Live`; https://github.com/microsoft/SWE-bench-Live | `full` split: 1,888 tasks, 223 repos | One Docker image per task | 2021-07 → 2025-09 | Adds tasks monthly; `lite` and `verified` splits are frozen; has `issue_numbers` (1,795 of 1,888 link exactly one issue) |
| SWE-rebench | HF `nebius/SWE-rebench`; runner https://github.com/SWE-rebench/SWE-bench-fork | `filtered` split: 6,542 tasks, 1,790 repos (full set ~21k tasks, 3,400+ repos) | Every task in `filtered` has a prebuilt image on Docker Hub (`swerebench/...`) | 2016-04 → 2025-04 | Dataset licence CC-BY-4.0; per-repo licence recorded; `meta.llm_score` is a model-made quality label — **do not filter on it** unless Neil decides to |
| SWE-rebench leaderboard | HF `nebius/SWE-rebench-leaderboard` | Monthly batches | Prebuilt images | Recent months | Source of fresh tasks for Step 10's contamination check |
| SWE-bench Pro (public) | HF `ScaleAI/SWE-bench_Pro`; https://github.com/scaleapi/SWE-bench_Pro-os | 731 tasks, 11 repos, 4 languages; **Python: 266 tasks in 3 repos** | Images on Docker Hub `jefzda/sweap-images` (`dockerhub_tag` column) | not in dataset | Public set comes from copyleft-licensed repos; multi-file heavy |
| Loc-Bench V1 | HF `czlll/Loc-Bench_V1` | 560 tasks, 165 repos | None found | 2015-11 → 2025-02 | No fail-to-pass test list, so it fails the "tests change status" filter as written. Reference only |

### 9.2 What the roadmap's filters leave (counted 22 Sep 2026)

How counted: source `.py` files in the gold patch; test files removed by a path rule
(`tests/`, `testing/`, `test_*.py`, `*_test.py`, `conftest.py`); changed lines counted in the
source patch only; "eligible" = file-count range + at most 200 changed lines + at least one
fail-to-pass test. **Claude Code must recount with the rule Neil approves in D18/D19.**

| Dataset | Tasks | Repos | 1 file | 2–10 files | Eligible (2–10) | Eligible (1–10) | Repos with 15+ eligible (2–10 / 1–10) |
|---|---|---|---|---|---|---|---|
| SWE-bench full | 2,294 | 12 | 75.2% | 23.8% | 511 | 2,228 | 9 / 11 |
| SWE-bench Verified | 500 | 12 | 86.0% | 13.8% | 68 | 497 | 1 / 8 |
| SWE-bench Lite | 300 | 12 | 100% | 0% | 0 | 300 | 0 / 6 |
| SWE-Gym | 2,438 | 11 | 57.2% | 38.4% | 849 | 2,235 | 10 / 11 |
| SWE-bench-Live full | 1,888 | 223 | 59.1% | 36.7% | 585 | 1,675 | 10 / 28 |
| SWE-rebench filtered | 6,542 | 1,790 | 64.0% | 35.5% | 2,228 | 6,380 | 12 / 65 |
| SWE-bench Pro (Python) | 266 | 3 | 39.1% | 60.9% | 116 | 210 | 3 / 3 |
| Loc-Bench V1 | 560 | 165 | 83.6% | 16.4% | (69 without test filter) | (526 without test filter) | — |

Repos with 10+ eligible tasks: SWE-bench-Live 14 (2–10) / 44 (1–10); SWE-rebench filtered
32 (2–10) / 124 (1–10).

A few percent of tasks create new `.py` files (G2): SWE-bench 1.7%, SWE-bench-Live 4.1%,
SWE-bench Pro Python 8.6%.

### 9.3 Per-repo counts (eligible under 2–10 / under 1–10)

**SWE-bench full:** django 172/840 · sympy 77/368 · sphinx 48/183 · scikit-learn 46/220 ·
matplotlib 38/178 · xarray 34/99 · astropy 26/93 · pytest 24/116 · pylint 22/56 ·
requests 11/43 · seaborn 10/21 · flask 3/11.

**SWE-Gym:** pandas 178/633 · MONAI 175/345 · moto 144/320 · dvc 111/212 · mypy 91/253 ·
modin 40/96 · dask 30/142 · pydantic 30/79 · hydra 23/62 · conan 18/70 · bokeh 9/23.

**SWE-bench Pro (Python):** openlibrary 42/66 · ansible 38/70 · qutebrowser 36/74.

**SWE-rebench filtered, top by 2–10:** sqlglot 172/291 · conan 43/71 · dvc 36/71 ·
dask 35/71 · pennylane 24/75 · sqlfluff 19/50 · tox 18/58 · sqllineage 17/40 ·
zarr-python 17/42 · pdm 17/28 · narwhals 17/25 · streamlink 17/67 (full list: recompute).

**SWE-bench-Live full, top by 2–10:** conan 60/161 · cfn-lint 32/89 · haystack 25/79 ·
matplotlib 23/98 · instructlab 22/42 · pdm 19/33 · sphinx 17/39 · reflex 16/40 ·
pylint 15/61 · linkding 15/30 (full list: recompute).

Note the overlaps (G18): conan, dvc, dask, mypy, matplotlib, sphinx, pylint, xarray, pdm,
haystack, sqllineage, and more appear in several datasets.

### 9.4 Repository rules and sampling (draft for D10 — Neil approves or edits)

**Include a repo if all hold:**
- R1. It appears in a dataset with prebuilt, runnable environments (the execution key needs
  them).
- R2. At least 80% of its non-test, non-vendored source lines are Python, measured with one
  fixed tool (e.g. `pygount` or `tokei`), recorded.
- R3. At least 50 non-test `.py` files at the pinned SHA.
- R4. At least K eligible tasks after the D19 filters (K proposed by Claude Code with the
  trade-off shown; e.g. 10 or 15).
- R5. It has a licence, and the licence is recorded.

**Exclude if any hold:** notebook-dominated; more than 30% generated or vendored code; a
monorepo of unrelated projects; a fork or mirror of another candidate.

None of these rules mention graph structure or any expected result. That's the point.

**Strata:** size tercile (by non-test `.py` file count) × dataset source. Domain labels come
from a fixed list decided **before** labelling — suggested: web/API, scientific/numeric,
data/ML, developer tools/testing, CLI/infrastructure, other — assigned from each repo's own
description, with Neil spot-checking.

**Draw:** Neil writes a seed number in `DECISIONS.md`. Within each stratum, sort candidates
by SHA-256 of `seed + repo_name` and take the first n. If D11 includes a SWE-bench
comparability block, those repos are included as a fixed block, not drawn.

Pilot repos (N1): the two smallest repos in the drawn sample, by rule, not by choice.

### 9.5 Machine and environment notes

- Only the execution key (Step 5) and Step 10 need Docker. Graphs, methods, and scoring do
  not.
- SWE-bench images are x86_64. Run on Ubuntu with Docker. On Windows with Docker Desktop,
  the harness docs say to raise the virtual disk limit.
- Pull images **only for sampled tasks**. Epoch AI publishes a registry of slimmed SWE-bench
  images: about 30 GiB for all 500 Verified images and 67 GiB for all 2,290
  (https://epoch.ai/latest/swebench-docker).
- Measure real disk, time per graph, and time per test run during the pilot, and report them
  before the main run.

---

## 10. Tools

Pin exact versions in the lockfile at install time. Confirm each on PyPI before use.

| Purpose | Tool | Link / note |
|---|---|---|
| Import graph (candidate 1) | grimp | https://github.com/python-grimp/grimp — needs the package importable (repo root on `sys.path`); has `exclude_type_checking_imports` |
| Import graph (candidate 2) | pydeps | confirm on PyPI |
| Import graph (candidate 3) | custom `ast` walker | stdlib; full control over Appendix A/B rules |
| Import graph (candidate 4) | tree-sitter + tree-sitter-python | tolerant of files that fail to parse |
| Graph algorithms | networkx | SCCs, condensation, topological sorts, PageRank, HITS, centralities, Louvain, transitive reduction |
| Faster graphs (optional) | python-igraph | only if networkx is too slow |
| Symbol resolution (key source 2) | jedi; alternatives: pyright, scip-python | pick one, record it |
| Execution (key source 3) | coverage.py (with per-test contexts), pytest-cov | line data must be mapped to function bodies for D20 option B |
| Git history (co-change) | PyDriller or GitPython | only commits **before** the base commit |
| Lexical retrieval | bm25s or rank_bm25 | query rule in D22 |
| Embeddings | sentence-transformers | model in D23 |
| Token counting | tiktoken with one fixed encoding | pinned; for Step 10 cost also use the provider's own counter |
| Statistics | scipy, statsmodels, scikit-posthocs | tests in D14 |
| Task harnesses | SWE-bench harness; SWE-rebench fork; SWE-bench-Live; SWE-bench Pro | links in 9.1 |
| Dataset download | huggingface_hub / datasets | public; if a dataset asks for terms, Neil accepts them |

**D23 embedding candidates** (verify names, sizes, licences on Hugging Face):
small, CPU-friendly — `jinaai/jina-embeddings-v2-base-code`;
mid — `Salesforce/SFR-Embedding-Code-400M_R`, `Qodo/Qodo-Embed-1-1.5B`;
large, needs a GPU — `nomic-ai/nomic-embed-code`, `Qodo/Qodo-Embed-1-7B`.
CoIR is the standard code-retrieval benchmark for comparing them (arXiv 2407.02883).

---

## 11. Published approaches: where the code is, and how to adapt

All four expect issue text and/or a language model. Ours may use neither (D4, D7). Each
becomes a **structure-only adaptation**, written up in the D22 spec and never described as a
reproduction.

| Approach | Code | What it does | Structure-only adaptation (to confirm in D22) |
|---|---|---|---|
| Aider repo map | https://github.com/Aider-AI/aider/blob/main/aider/repomap.py | tree-sitter definition/reference graph, personalised PageRank toward the files being edited, then fits a token budget | Closest fit: run it with the seed as the only "chat file"; read off the ranked file order. No model needed |
| RepoGraph (ICLR 2025) | https://github.com/ozyyshr/RepoGraph (`repograph/construct_graph.py`) | line-level def/ref graph; k-hop ego-graphs around a search term chosen during the run | Search terms = the seed's top-level definitions; k = 1 and 2; order files by hop, then D21 |
| LocAgent (ACL 2025) | https://github.com/gersteinlab/LocAgent (`dependency_graph/batch_build_graph.py`) | heterogeneous code graph; model-driven search tools | Build their graph; type-aware BFS from the seed's file node, no model |
| CoSIL (ASE 2025) | https://github.com/ZhonghaoJiang/CoSIL | module then function call graphs, **built by the model during search**, with a model-based pruner | Replace the model-built call graph with a static module call graph; BFS from the seed |

Also fix in D22: BM25 query = identifiers from the seed file (split on snake_case and
camelCase), corpus = every other `.py` file at the base commit; co-change window (all prior
history vs last N commits).

Worth reading in the RepoGraph paper: in their setup, the 2-hop variant fed in raw
performed below their baseline. That's one data point about "more context" — neither
support nor opposition for anything here.

---

## 12. Reading list

**Closest prior work on dependency topology and change investigation**
- Robillard, *Topology analysis of software dependencies*, ACM TOSEM 17(4), 2008 —
  https://www.cs.mcgill.ca/~martin/papers/tosem2008.pdf (specificity and reinforcement,
  Appendix D)
- Robillard, *Automatic generation of suggestions for program investigation*, ESEC/FSE 2005
  — see https://www.cs.mcgill.ca/~swevo/suade
- Zimmermann, Weißgerber, Diehl, Zeller, *Mining version histories to guide software
  changes*, IEEE TSE 31(6), 2005 — DOI 10.1109/TSE.2005.72 (co-change; IEEE)

**Order and context in code models**
- *Order Matters! An Empirical Study on LLMs' Input Order Bias in Software Fault
  Localization*, ICSE 2026 — arXiv 2412.18750
- *Hierarchical Context Pruning*, AAAI 2025 — arXiv 2406.18294 (reports on keeping files in
  dependency order in prompts)
- *Beyond More Context: How Granularity and Order Drive Code Completion Quality* —
  arXiv 2510.06606
- *DyCoder: context retrieval via partial dependency graph*, Aug 2026 — arXiv 2608.01927
- *RepoMirage* — arXiv 2605.26177 (how many files agents actually open on SWE-bench Verified)
- Liu et al., *Lost in the Middle*, TACL 2024 — arXiv 2307.03172 (not link-checked)

**Localization and repository graphs**
- LocAgent — arXiv 2503.09089 · CoSIL — arXiv 2503.22424 · RepoGraph — arXiv 2410.14684 ·
  GraphLocator — arXiv 2512.22469 · Agentless — arXiv 2407.01489 (not link-checked)

**Benchmarks**
- SWE-bench — arXiv 2310.06770 · SWE-rebench (NeurIPS 2025) — arXiv 2505.20411 ·
  SWE-bench-Live (NeurIPS 2025 D&B) — arXiv 2505.23419 · SWE-bench Pro — arXiv 2509.16941 ·
  CoIR — arXiv 2407.02883 · CodeXEmbed — arXiv 2411.12644
- OpenAI, *Why SWE-bench Verified no longer measures frontier coding capabilities*,
  23 Feb 2026 (threat to validity for Step 10)

**Statistics for SE experiments** (not link-checked; find by title)
- Demšar, *Statistical comparisons of classifiers over multiple data sets*, JMLR 2006
- Arcuri & Briand, *A hitchhiker's guide to statistical tests for assessing randomized
  algorithms in software engineering*, STVR 2014

**Disclosure policy**
- ACM publications FAQ on generative AI —
  https://www.acm.org/publications/policies/frequently-asked-questions — AI use that creates
  content (text, code, data, tables) is disclosed in the Acknowledgements; AI cannot be an
  author; authors are responsible for everything in the work.

---

## 13. What Neil must provide (Step 0 checks all of this)

- [ ] An x86_64 Ubuntu machine with Docker working (`docker run hello-world`)
- [ ] Free disk: report the real number; the SWE-bench harness recommends 120 GB
- [ ] RAM and CPU count: report them; harness recommends 16 GB and 8 cores
- [ ] A GitHub token — only needed if PR metadata beyond the datasets is fetched
      (co-change uses `git clone`, which needs none)
- [ ] Anthropic API key and a hard spend cap — only at Gate G
- [ ] OSF account — only if D24 says so
- [ ] Time for the manual audit (Gate D)

If anything is missing, Claude Code says exactly what, and continues with steps that don't
need it.

---

## 14. Easy to get wrong

1. Building the graph at the wrong commit (G1).
2. Co-change using commits after the base commit (leakage).
3. Letting files the PR creates into the key (G2).
4. Execution key built from import-time lines (N5, D20).
5. Treating `test_patch` files as source files.
6. `src/` layouts and namespace packages resolving to the wrong module names.
7. Placing our numbers next to published numbers as if comparable (N8).
8. Silently dropping anything. Every failure is logged and counted in the next report.
9. Unpinned tokenizer, library versions, or random seeds.
10. Changing a filter, metric, or rule after seeing results without `POSTHOC.md` (N3).
11. PRs linked to several issues slipping through (SWE-bench-Live: 93 of 1,888).
12. The same repo counted twice across datasets (G18).
13. Showing method comparisons during the pilot (N1).
14. Calling a DRAFT proof a theorem (G19).

---

## 15. Files this adds to the repo

```
reports/          check-ins; reports/LATEST.md is always the newest
audit/            AUDIT_SHEET.md and Neil's answers
GLOSSARY.md       plain word → paper term
DECISIONS.md      the ledger (roadmap D1–D15 plus D16–D26 here) with dates and reasons
POSTHOC.md        every change made after results existed, and every bug fix
AI_USE.md         what Claude Code did, when, with which model
results/FACTS.md  one line per reported number → the file it came from
results/pilot/    blind pilot outputs, excluded from the paper
data/datasets/    raw dataset files as downloaded, with checksums
data/candidates.csv   every candidate repo with rule outcomes
```
