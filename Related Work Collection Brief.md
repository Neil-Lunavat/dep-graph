# Related Work Collection Brief

Sep 23, 2026 · @Someone

## Why I need these

Our paper's whole argument rests on one sentence: **the field grades code localization against the files that were edited, and that is the key on which import-graph structure performs worst.**

Four examples is an anecdote. Thirty is a finding. That is the only reason this list exists.

The paper's prior-work table currently has **4 verified entries** (LocAgent, CoSIL, RepoGraph, Agentless). A reviewer will say *"you checked four papers and drew a conclusion about a whole field"* — and they would be right.

**Target: 25–30 papers. 20 is enough. Below 15 the claim has to be softened** to "the systems we examined," which costs us the sharpest paragraph in the paper.

One thing that should make this easier: **you do not need to read them.** I need the PDFs. I extract what matters. Find and download is the whole job.

## What I pull out of each one

Just so you know what makes a paper useful or useless to us. **The single field that matters is the ground-truth key** — what the paper counts as a correct answer.

| Field | What it means | Where it usually hides |
| --- | --- | --- |
| Ground-truth key | What counts as a file you should have retrieved | Evaluation / Experimental Setup section |
| Granularity | File, class, function, or line | Same place |
| Signal used | Import graph, call graph, embeddings, BM25, LLM agent, hybrid | Method section |
| Benchmark | SWE-bench, Verified, Lite, Loc-Bench, own dataset | Setup |
| Cost reported | Top-k files, tokens, dollars, or nothing | Results tables |

The answer to "ground-truth key" is nearly always **"the files modified by the gold patch."** That *is* our finding. Every paper where that is true is one more row supporting the argument.

**A paper that does something different is worth more, not less.** If one grades against files a developer *read*, or an execution trace, or a manually-labelled set — flag it. Those are the interesting exceptions and I want them called out by name in the paper.

One warning: papers often state this only in a half-sentence, or only implicitly by citing the benchmark. So a paper that looks unhelpful on a skim may still be fine. **When unsure, keep it.** A wrong include costs me two minutes; a wrong exclude costs us a row.

## Tier 1 — graph-based localization (highest value)

These are systems that build a code graph and use it to find files. **They are the ones our finding is actually about.** If you only have time for one tier, make it this one. Aim for 10–12.

I have the first four already — listed so you don't re-fetch them.

| Paper | Status | Search hint |
| --- | --- | --- |
| LocAgent | have it | arXiv 2503.09089 |
| CoSIL | have it | arXiv 2503.22424 |
| RepoGraph | have it | arXiv 2410.14684, ICLR 2025 |
| Agentless | have it | arXiv 2407.01489 |
| **Orcaloca** | need | search `OrcaLoca LLM agent code localization` |
| **RepoUnderstander** | need | search `repository knowledge graph SWE-bench agent` |
| **CodexGraph** | need | search `CodexGraph code graph database LLM` |
| **GraphCoder** | need | search `GraphCoder code completion context graph` |
| **RepoHyper** | need | search `RepoHyper repo-level code completion graph` |
| **KGCompass** | need | search `knowledge graph repository issue resolution` |
| **SWE-Search / SWE-Exp** | need | search `Monte Carlo tree search software engineering agent` |
| **DeepSeek / Moatless tools** | need | search `Moatless tools semantic search SWE-bench` |

The best way to find the rest: **open the LocAgent and CoSIL PDFs, go to their related-work sections, and take whatever they cite.** That is faster than searching blind and it guarantees relevance. Same trick on RepoGraph.

Second-best: search Google Scholar for **papers that cite LocAgent**, sort by date. Anything from 2025–2026 doing localization will be in there.

Titles marked with a search hint rather than an exact reference are from my memory and **the title may be slightly wrong** — search the phrase, not the name, and trust what you find over what I wrote.

## Tier 2 — agents that localize before fixing

These don't sell themselves as localization papers, but every one has a step that decides which files go into the model's context. **That step is the thing our paper is about, and they all evaluate it against the gold patch.** Aim for 8–10.

| Paper | Search hint |
| --- | --- |
| SWE-agent | search `SWE-agent agent computer interface` — NeurIPS 2024 |
| AutoCodeRover | search `AutoCodeRover program repair autonomous` |
| SpecRover | search `SpecRover specification inference repair` |
| OpenHands / OpenDevin | search `OpenHands generalist AI software developers` |
| CodeR | search `CodeR multi-agent task graph issue resolution` |
| MASAI | search `MASAI modular architecture software engineering AI` |
| MAGIS | search `MAGIS LLM multi-agent GitHub issue resolution` |
| Aider | the repo-map docs page, `aider.chat/docs/repomap.html` — I cite this already but a paper-shaped source would be better |
| Devlo / Amazon Q / Factory | any vendor SWE-bench technical report you can find |

For this tier the fastest route is the **SWE-bench leaderboard** at `swebench.com` — most entries link a paper or a report. Grab whichever have real write-ups.

These are lower value per paper than Tier 1, because a reviewer expects an agent paper to use the benchmark's own key. **Tier 1 is where the argument bites** — those are papers that specifically claim graph structure helps, and grade that claim on the key where it helps least.

## Tier 3 — retrieval and context selection for code

This tier supports the *other* half of the paper: that cost should be counted in tokens, and that lexical matching is a serious baseline rather than a straw man. Aim for 5–6.

| Topic | Search hint |
| --- | --- |
| Repo-level code completion with retrieval | search `RepoCoder iterative retrieval repository code completion` |
| Long-context vs retrieval for code | search `repository level code context long context LLM` |
| Lost in the middle | search `Lost in the Middle how language models use long contexts` — Liu et al., TACL |
| Code search with BM25 vs neural | search `BM25 strong baseline neural code search` |
| Context compression / pruning for code agents | search `context pruning code agent token budget` |
| RAG for software engineering (survey) | search `retrieval augmented generation software engineering survey` |

**Lost in the Middle is the one I most want.** You raised the position question yourself — whether order inside a prompt matters. That paper is the standard citation for it, and it lets me answer the point properly in the discussion instead of waving at it.

A survey here is worth three individual papers, because I can cite it once for the background and spend the space on our own argument.

## Tier 4 — classical background (low effort, don't overdo it)

Old software-engineering work on the same questions, from before LLMs. It matters for one reason: **our two evidence keys are not something we invented.** Co-edited files are change coupling, from the 2000s mining literature. Symbol references are static impact analysis, older still. Showing that lineage makes us look grounded rather than ad hoc.

I already cite six of these from memory and they need verifying anyway (next section), so fetching them does double duty.

| Paper | Search hint |
| --- | --- |
| Zimmermann et al., mining version histories | search `Mining Version Histories to Guide Software Changes` |
| Ying et al., predicting source code changes | search `Predicting Source Code Changes by Mining Change History` |
| Robillard, topology of software dependencies | search `Topology Analysis of Software Dependencies Robillard` |
| Ko et al., how developers seek information | search `exploratory study developers seek relate collect information maintenance` |
| Dit et al., feature location survey | search `Feature Location in Source Code Taxonomy and Survey` |
| Bohner & Arnold, impact analysis | it's a 1996 book — a scan or the citation page is fine |

**Six is plenty here.** Do not go hunting for more classical work; the paper is about the modern systems and this section is one paragraph. If these six are hard to get, skip them and tell me — I can cite them without the PDFs, they just stay unverified.

## Benchmarks (we build on their data, so we must cite them right)

Our corpus is assembled from these. Getting their citations wrong is the kind of error a reviewer treats as carelessness, so these need to be exact.

| Benchmark | Our use | Status |
| --- | --- | --- |
| SWE-bench | 82 of our scored instances | need to verify the citation |
| SWE-bench Verified | 15 instances | it's an OpenAI blog post, not a paper — find the canonical URL |
| SWE-bench Lite | 3 instances | usually cited via SWE-bench itself |
| SWE-bench-Live | 314 instances | have it, verified |
| SWE-rebench | **784 instances — our largest source** | have it, verified |
| SWE-Gym | 2 instances | need |
| Loc-Bench | 4 instances, and it's LocAgent's benchmark | need — worth having for Tier 1 too |
| SWE-bench Pro | 0 instances | skip, we don't use it |

SWE-rebench is the one that matters most — it supplies two thirds of our scored corpus and it is also the paper that makes the decontamination argument we lean on.

**Loc-Bench is worth real effort.** It is a localization benchmark built specifically because its authors thought existing ground truth was inadequate. If their reasoning overlaps with ours, that is either strong support or the closest thing to a competing claim — and I need to know which before we submit, not after a reviewer tells us.

## The 14 I wrote from memory

Being straight with you: our bibliography has 20 entries and **only 6 are verified.** The other 14 I wrote from memory — authors, titles, venues, years. They are marked `VERIFY` in `references.bib`.

Memory is not a source. I have already been wrong once on this paper: I had LocAgent's author list and page range wrong until I checked. **Assume some of the remaining 14 are wrong too.**

Six of them are the Tier 4 classics above. The other eight are statistics and methods references:

- Robertson & Zaragoza — BM25 / probabilistic relevance framework
- Blondel et al. — Louvain community detection
- Vargha & Delaney — the A12 effect size
- Holm — sequential rejective multiple test procedure
- Demšar — statistical comparisons of classifiers
- Benjamini & Hochberg — false discovery rate
- SWE-bench — the ICLR 2024 paper
- Aider repo-map — a docs page, needs an access date

**These eight are low priority for you.** They are famous and I can verify them myself against publisher listings without a PDF. I'm listing them only so you know what state the bibliography is in — don't spend time here unless everything else is done.

## Where to put them

Drop everything in `papers/` at the top of the repo. I'll add it to `.gitignore` so the PDFs don't bloat the history.

Naming: `firstauthor-year-shortname.pdf`, lowercase, e.g. `chen-2025-locagent.pdf`. If you can't tell the author, `unknown-2025-whatever.pdf` is fine — I'd rather have a badly named PDF than no PDF.

**arXiv is usually enough.** Almost everything in Tiers 1–3 is on arXiv, free, no login. Prefer the arXiv version even when a published one exists — the content is nearly always the same and I'll cite the published venue regardless.

When something is paywalled (mostly Tier 4 and older IEEE/ACM work): **don't fight it.** Try your college library access once, and if that fails just note the title in a text file in `papers/`. For the old classics I only need the citation details, which are on the publisher's landing page without a subscription.

One small thing that saves me time: if you notice a paper's evaluation section while you're downloading, jot the ground-truth key in a line of `papers/notes.txt`. Entirely optional — skip it if it slows you down.

## Don't bother with

Saying this explicitly because the surrounding literature is enormous and it is easy to spend a day on things I cannot use.

- **Code generation benchmarks** — HumanEval, MBPP, anything where the task is writing a function from a description. No repository, no retrieval, nothing for us.
- **Bug prediction / defect prediction** — predicting which files are buggy in general. Different question, and it would blur our argument.
- **Pure LLM training or architecture papers.** We cite no model papers.
- **Non-Python work**, unless it is a Tier 1 graph localization system. Our study is Python-only and we say so in Threats.
- **Anything before 2000** other than the Bohner & Arnold book.

A rough stopping rule: **20 papers total, weighted toward Tier 1.** Once Tier 1 has 10 entries the argument holds, and more papers past that point improve the table's look rather than its force.

If you get bored or stuck, stop and hand me what you have. A short list I can actually verify beats a long one where half the entries are wrong — and the paper is not blocked on this: I'll be writing the rest of it while you collect.
