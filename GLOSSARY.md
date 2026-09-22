# GLOSSARY — plain word → paper term

Neil voice uses the left column, always the same word. Paper voice uses the right column.

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
| task | instance (one PR / issue fix from a benchmark) |
| usable task | eligible instance (passes the fixed task filters) |
| fixing test | fail-to-pass (F2P) test |
| ready-made test box | prebuilt Docker execution environment |
| line cap | maximum changed lines in the source diff |
| candidate repo | repository passing the inclusion rules, before sampling |
| snapshot | pinned commit SHA |
| duplicate task | the same PR appearing in two benchmarks |
| group (for sampling) | stratum |
| how much the RQ2 test can see | statistical power; minimum detectable effect |
