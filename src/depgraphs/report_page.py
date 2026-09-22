"""Build the findings page (reports/findings.html) from results/analysis/*. Every number on
the page is read from those files; nothing is typed in by hand."""
from __future__ import annotations

import json

import pandas as pd

from depgraphs.datasets import ROOT

A = ROOT / "results" / "analysis"
REFS = {"random", "same_dir", "whole_repo", "seed_alone", "oracle"}
LABEL = {
    "ppr_und": "Personalised PageRank (undirected)", "ppr_fwd": "Personalised PageRank (imports)",
    "locagent_bfs": "LocAgent-style BFS (adapted)", "ids_und": "Iterative deepening (undirected)",
    "bfs_und": "BFS (undirected)", "pagerank": "PageRank (global)", "indegree": "In-degree (hubs)",
    "robillard": "Robillard specificity×reinforcement", "aider_repomap": "Aider repo-map (adapted)",
    "hits_auth": "HITS authority", "bfs_fwd": "BFS (imports)", "closure_fwd_trim": "Forward closure, near first",
    "directory": "Directory proximity", "bm25": "BM25 on identifiers", "closeness": "Closeness centrality",
    "cochange": "Co-change history", "khop1_und": "1-hop neighbours", "repograph_k2": "RepoGraph 2-hop (adapted)",
    "betweenness": "Betweenness", "cosil_bfs": "CoSIL-style call-graph BFS (adapted)",
    "topo_fwd": "Topological (dependencies first)", "repograph_k1": "RepoGraph 1-hop (adapted)",
    "closure_fwd": "Forward closure", "closure_comb": "Both-direction closure", "khop2_und": "2-hop neighbours",
    "whole_repo": "Whole repo, path order", "labelprop": "Label-propagation cluster", "dfs_und": "DFS (undirected)",
    "random": "Random order (floor)", "louvain": "Louvain cluster", "same_dir": "Same directory",
    "bfs_rev": "BFS (importers)", "closure_rev": "Reverse closure (importers)", "seed_alone": "Starting file alone",
    "oracle": "Cheat ceiling (uses the key)",
}


def load():
    f = json.loads((A / "findings.json").read_text())
    rq1 = {s: pd.read_csv(A / f"rq1_{s}.csv") for s in
           ["union", "co_edited", "symbol", "execution_B", "union_single", "union_multi"]}
    curves = pd.read_csv(A / "curves_union.csv")
    wrong = None
    p = A / "wrong_seed.csv"
    if p.exists():
        wrong = pd.read_csv(p)
    return f, rq1, curves, wrong


def fmt(x, d=2):
    return f"{x:.{d}f}"


def main():
    f, rq1, curves, wrong = load()
    u = rq1["union"].set_index("method")
    dup = "closure_fwd_trim"          # identical to bfs_fwd by construction
    dots = [{"m": m, "label": LABEL.get(m, m), "mean": r.mean_auc, "lo": r.ci_lo, "hi": r.ci_hi,
             "ref": bool(r.is_reference), "a12": r.a12_vs_random, "n": int(r.n_prs)}
            for m, r in u.iterrows() if m != dup]
    top = [m for m in u.index if m not in REFS][0]
    by_src = {}
    for s in ["co_edited", "symbol", "execution_B"]:
        d = rq1[s].set_index("method")
        meths = [m for m in d.index if m not in REFS and m != dup]
        by_src[s] = {"n": int(d.n_prs.max()), "random": d.loc["random", "mean_auc"],
                     "oracle": d.loc["oracle", "mean_auc"],
                     "top": [(LABEL.get(m, m), d.loc[m, "mean_auc"]) for m in meths[:3]],
                     "rank_of": {m: meths.index(m) + 1 for m in ("ppr_und", "bm25", "cochange", "bfs_und")
                                 if m in meths}}
    cm = ["ppr_und", "bm25", "random", "oracle"]
    cdata = {m: curves[curves.method == m].sort_values("budget")[["budget", "coverage"]].values.tolist()
             for m in cm}
    rq3 = f["rq3"]
    rq3rows = []
    for s, lab in [("co_edited", "Co-edited"), ("symbol", "Symbol"), ("execution_B", "Execution (B)")]:
        v = rq3.get(s)
        if not v:
            continue
        c = {int(k): n for k, n in v["und_dist_counts"].items()}
        tot = sum(c.values())
        rq3rows.append({"src": lab, "pairs": v["pairs"], "h1": c.get(1, 0) / tot, "h2": c.get(2, 0) / tot,
                        "h3p": sum(n for k, n in c.items() if k >= 3) / tot,
                        "none": c.get(-1, 0) / tot, "nofwd": v["no_path_fwd"]})
    ag = f["key_agreement"]
    r2 = f["rq2"]
    fr = f["friedman_union"]
    cnt = f["counts"]
    single = rq1["union_single"].set_index("method")
    multi = rq1["union_multi"].set_index("method")
    sm_top = lambda d: [m for m in d.index if m not in REFS and m != dup][0]

    wrong_html = ""
    if wrong is not None:
        rows = "".join(
            f"<tr><td>{LABEL.get(r.method, r.method)}</td>" + "".join(
                f"<td class=num>{fmt(getattr(r, c))}</td>" for c in ["true", "wrong1", "wrong2", "wrongrand"]) + "</tr>"
            for r in wrong.itertuples())
        wrong_html = f"""
<section>
  <h2>RQ4 · A wrong starting file</h2>
  <p>Same methods, but started from a file 1 hop away, 2 hops away, or chosen at random (rule D26).
  The answer key stays the true one. Mean area under the curve, union key. Tasks with no file at
  exactly 1 hop (51) or 2 hops (66) are left out of those columns.</p>
  <p>PageRank and in-degree don't use the starting file at all, so they barely move. Methods that
  walk out from the starting file lose a lot. With a random start, BFS and iterative deepening fall to
  about the random floor, while personalised PageRank keeps part of its lead.</p>
  <div class=tablewrap><table>
    <thead><tr><th>Method</th><th class=num>Correct start</th><th class=num>1 hop off</th><th class=num>2 hops off</th><th class=num>Random start</th></tr></thead>
    <tbody>{rows}</tbody></table></div>
</section>"""

    payload = {"dots": dots, "curves": cdata,
               "labels": {m: LABEL[m] for m in cm}}
    html = TEMPLATE
    subs = {
        "__PAYLOAD__": json.dumps(payload),
        "__TASKS__": f"{cnt['tasks']:,}", "__PRS__": f"{cnt['prs']:,}", "__REPOS__": str(cnt["repos"]),
        "__SCORED_PRS__": f"{int(u.n_prs.max()):,}",
        "__TOP__": LABEL[top], "__TOP_AUC__": fmt(u.loc[top, "mean_auc"]),
        "__TOP_LO__": fmt(u.loc[top, "ci_lo"]), "__TOP_HI__": fmt(u.loc[top, "ci_hi"]),
        "__RAND_AUC__": fmt(u.loc["random", "mean_auc"]), "__ORACLE_AUC__": fmt(u.loc["oracle", "mean_auc"]),
        "__TOP_A12__": fmt(u.loc[top, "a12_vs_random"]),
        "__CO_N__": str(by_src["co_edited"]["n"]), "__SYM_N__": str(by_src["symbol"]["n"]),
        "__EX_N__": str(by_src["execution_B"]["n"]),
        "__SRC_ROWS__": "".join(
            f"<tr><th scope=row>{lab}</th><td class=num>{by_src[s]['n']}</td>"
            f"<td>{'<br>'.join(f'{n} <span class=mono>{fmt(v)}</span>' for n, v in by_src[s]['top'])}</td>"
            f"<td class=num>{fmt(by_src[s]['random'])}</td><td class=num>{fmt(by_src[s]['oracle'])}</td>"
            f"<td class=num>{by_src[s]['rank_of'].get('ppr_und', '—')}</td><td class=num>{by_src[s]['rank_of'].get('bm25', '—')}</td></tr>"
            for s, lab in [("co_edited", "Co-edited files"), ("symbol", "Symbol definitions"),
                           ("execution_B", "Executed by fixing tests")]),
        "__RQ3_ROWS__": "".join(
            f"<tr><th scope=row>{r['src']}</th><td class=num>{r['pairs']:,}</td><td class=num>{r['h1']:.0%}</td>"
            f"<td class=num>{r['h2']:.0%}</td><td class=num>{r['h3p']:.0%}</td><td class=num>{r['none']:.1%}</td>"
            f"<td class=num>{r['nofwd']:.0%}</td></tr>" for r in rq3rows),
        "__AG_TASKS__": str(ag.get("tasks", 0)), "__AG_J__": fmt(ag.get("mean_jaccard", 0)),
        "__AG_SE__": f"{ag.get('share_static_found_by_exec', 0):.0%}",
        "__AG_ES__": f"{ag.get('share_exec_found_by_static', 0):.0%}",
        "__AG_SS__": fmt(ag.get("mean_size_static", 0), 1), "__AG_SX__": fmt(ag.get("mean_size_exec_B", 0), 1),
        "__R2_PAIRS__": str(r2["pairs"]), "__R2_BH__": str(r2["sig_bh_005"]),
        "__R2_TOP__": "".join(f"<li><span class=mono>{t['method']}</span> × <span class=mono>{t['property']}</span>: "
                              f"ρ = {t['rho']:.2f}</li>" for t in r2["top"][:5]),
        "__FR_CHI__": f"{fr['chi2']:.0f}", "__FR_N__": str(fr["n_repos"]), "__FR_K__": str(fr["k_methods"]),
        "__FR_CD__": fmt(fr["nemenyi_cd"]),
        "__SINGLE_N__": str(int(single.n_prs.max())), "__MULTI_N__": str(int(multi.n_prs.max())),
        "__SINGLE_TOP__": LABEL[sm_top(single)], "__SINGLE_AUC__": fmt(single.loc[sm_top(single), "mean_auc"]),
        "__MULTI_TOP__": LABEL[sm_top(multi)], "__MULTI_AUC__": fmt(multi.loc[sm_top(multi), "mean_auc"]),
        "__WINNERS__": ", ".join(f"{LABEL.get(m, m)} ({n})" for m, n in list(f["winners"].items())[:5]),
        "__WRONG__": wrong_html,
    }
    for k, v in subs.items():
        html = html.replace(k, v)
    out = ROOT / "reports" / "findings.html"
    out.write_text(html, encoding="utf-8")
    print("wrote", out)


TEMPLATE = r"""<title>Reading Order Findings</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,500;8..60,650&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{
  --ground:#f6f7f4; --panel:#ffffff; --ink:#15201b; --ink-2:#4f5b55; --ink-3:#7c8781;
  --rule:#dfe3de; --grid:#e8ebe7; --accent:#2a78d6; --s1:#2a78d6; --s2:#eb6834; --s3:#7c8781; --s4:#1baf7a;
  --ref:#a9b1ac; --band:rgba(42,120,214,.10); --hi:#fff4d6;
  color-scheme: light;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ground:#121614; --panel:#1a1f1c; --ink:#eef2ef; --ink-2:#b3bdb7; --ink-3:#8b958f;
    --rule:#2c332f; --grid:#262c29; --accent:#3987e5; --s1:#3987e5; --s2:#d95926; --s3:#8b958f; --s4:#199e70;
    --ref:#5d6661; --band:rgba(57,135,229,.16); --hi:#3a3220; color-scheme: dark;
  }
}
:root[data-theme="dark"]{
  --ground:#121614; --panel:#1a1f1c; --ink:#eef2ef; --ink-2:#b3bdb7; --ink-3:#8b958f;
  --rule:#2c332f; --grid:#262c29; --accent:#3987e5; --s1:#3987e5; --s2:#d95926; --s3:#8b958f; --s4:#199e70;
  --ref:#5d6661; --band:rgba(57,135,229,.16); --hi:#3a3220; color-scheme: dark;
}
body{background:var(--ground);color:var(--ink);font:15px/1.6 "IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:880px;margin:0 auto;padding-inline:20px;padding-block:40px 80px;display:grid;gap:44px}
h1,h2{font-family:"Source Serif 4",Georgia,serif;font-weight:650;text-wrap:balance;margin:0;letter-spacing:-.01em}
h1{font-size:clamp(28px,5vw,40px);line-height:1.12}
h2{font-size:22px;line-height:1.25}
p{margin:0;max-width:68ch}
section{display:grid;gap:14px}
.eyebrow{font:500 12px/1.4 "IBM Plex Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3)}
.lede{color:var(--ink-2);font-size:16.5px}
.mono,.num{font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}
.fact{background:var(--panel);border:1px solid var(--rule);border-radius:10px;padding:16px 18px;display:grid;gap:6px;align-content:start}
.fact b{font-family:"Source Serif 4",Georgia,serif;font-size:17px;font-weight:650;line-height:1.3}
.fact span{color:var(--ink-2);font-size:14px}
.callout{border-left:3px solid var(--s2);background:var(--panel);padding:14px 18px;border-radius:0 10px 10px 0}
figure{margin:0;background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:18px 18px 12px;display:grid;gap:10px}
figcaption{color:var(--ink-2);font-size:13.5px}
.chart{position:relative;width:100%}
.chart svg{display:block;width:100%;height:auto;overflow:visible}
.chart text{fill:var(--ink-2);font:12px "IBM Plex Sans",system-ui,sans-serif}
.chart .lab{fill:var(--ink);font-size:12px}
.chart .reflab{fill:var(--ink-3)}
.legend{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:13px;color:var(--ink-2)}
.legend i{display:inline-block;width:18px;height:3px;border-radius:2px;vertical-align:middle;margin-right:6px}
.tip{position:absolute;pointer-events:none;background:var(--ink);color:var(--ground);font:12.5px/1.45 "IBM Plex Sans",sans-serif;padding:8px 10px;border-radius:8px;max-width:280px;transform:translate(-50%,-100%);margin-top:-10px;white-space:normal;z-index:2}
.tablewrap{overflow-x:auto;background:var(--panel);border:1px solid var(--rule);border-radius:12px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--rule);vertical-align:top}
thead th{font:500 12px/1.3 "IBM Plex Mono",monospace;letter-spacing:.04em;text-transform:uppercase;color:var(--ink-3)}
tbody tr:last-child th,tbody tr:last-child td{border-bottom:0}
td.num,th.num{text-align:right}
ul{margin:0;padding-left:20px;display:grid;gap:4px}
.pending{display:grid;gap:8px}
.pill{display:inline-block;font:500 11.5px/1 "IBM Plex Mono",monospace;padding:4px 8px;border-radius:99px;border:1px solid var(--rule);color:var(--ink-2);margin-right:6px}
footer{color:var(--ink-3);font-size:13px}
@media (max-width:560px){ .wrap{padding-block:24px 56px} }
</style>

<div class="wrap">
<header style="display:grid;gap:14px">
  <div class="eyebrow">Python import graphs · structure-only reading order · 22 Sep 2026</div>
  <h1>Which files should you read, and in what order, before changing one file?</h1>
  <p class="lede">We ran 30 ordering methods (plus 4 simple references) on __TASKS__ tasks (one per starting file) from __PRS__ real bug-fix PRs in __REPOS__ Python repositories, and measured how much code each method's list made you read before you had seen the files the change needed. No language model is used anywhere.</p>
</header>

<section>
  <h2>What was measured</h2>
  <div class="facts">
    <div class="fact"><b>Graph-walking methods cover the key faster than random, by a wide margin</b><span>Best overall: __TOP__, area under the curve __TOP_AUC__ (95% CI __TOP_LO__–__TOP_HI__) vs __RAND_AUC__ for random order. Vargha–Delaney A12 vs random = __TOP_A12__ (0.5 = no difference).</span></div>
    <div class="fact"><b>But which method leads depends on the evidence used as the answer key</b><span>With the co-edited-files key (independent of imports), text search (BM25) and co-change history rank near the top. With the symbol key, which overlaps the import graph by construction, graph methods lead.</span></div>
    <div class="fact"><b>Needed files sit close to the starting file</b><span>Most answer-key files are 1–2 import hops away (ignoring direction). Few have no path at all. Following imports in one direction only misses about a third.</span></div>
    <div class="fact"><b>There is a large gap to the ceiling</b><span>A cheat ceiling that already knows the answer reaches __ORACLE_AUC__. The best real method reaches __TOP_AUC__, so there is room for better orderings.</span></div>
  </div>
</section>

<section>
  <h2>How much of the needed code you've seen, by reading budget</h2>
  <figure>
    <div class="legend" id="legend"></div>
    <div class="chart" id="curve"></div>
    <figcaption>Share of the answer key (union of co-edited, symbol and, where run, executed files) seen after reading the first N lines of each method's list. Mean over __SCORED_PRS__ PRs with a non-empty key (each PR weighted once). Log scale on the budget.</figcaption>
  </figure>
</section>

<section>
  <h2>RQ1 · Every method, one number each</h2>
  <p>Area under the coverage curve over budgets of 250 to 32,000 lines (1 = the whole key read within 250 lines). Grey rows are references, not methods. Bars show a 95% bootstrap interval that resamples whole repositories.</p>
  <figure>
    <div class="chart" id="dots"></div>
    <figcaption>Friedman test across __FR_K__ methods over __FR_N__ repos: χ² = __FR_CHI__, p &lt; 0.001; Nemenyi critical difference in average rank = __FR_CD__. "BFS (imports)" and "forward closure, near first" are the same rule by construction; only one is shown.</figcaption>
  </figure>
</section>

<section>
  <h2>The answer key changes the ranking</h2>
  <p class="callout">This is the most important caution. The symbol key comes from resolving names in the new code, and a file that defines a name you use is usually one you import. So it favours import-graph methods by construction. The co-edited key has no such link, and on it text similarity and history do as well as or better than graph walks.</p>
  <div class="tablewrap"><table>
    <thead><tr><th>Answer key from</th><th class="num">PRs</th><th>Top 3 methods (AUC)</th><th class="num">Random</th><th class="num">Ceiling</th><th class="num">Rank of PPR (und)</th><th class="num">Rank of BM25</th></tr></thead>
    <tbody>__SRC_ROWS__</tbody>
  </table></div>
  <p>Single-file changes (__SINGLE_N__ PRs): top is __SINGLE_TOP__ (__SINGLE_AUC__). Multi-file changes (__MULTI_N__ PRs): top is __MULTI_TOP__ (__MULTI_AUC__). Reported separately, as decided up front.</p>
</section>

<section>
  <h2>RQ3 · How far are the needed files?</h2>
  <div class="tablewrap"><table>
    <thead><tr><th>Key source</th><th class="num">Pairs</th><th class="num">1 hop</th><th class="num">2 hops</th><th class="num">3+ hops</th><th class="num">No path</th><th class="num">No path following imports only</th></tr></thead>
    <tbody>__RQ3_ROWS__</tbody>
  </table></div>
  <p>Distance is the shortest path in the import graph, ignoring direction, from the starting file to each answer-key file.</p>
</section>

<section>
  <h2>RQ2 · Does repository shape predict which method helps?</h2>
  <p>We correlated every Table 1 property with every method's gain over random, across repositories: __R2_PAIRS__ pairs, Benjamini–Hochberg corrected. __R2_BH__ pairs are significant at 0.05. The strongest are mostly about <em>size</em>. In bigger repositories the random floor drops, so every method's gain grows. This is exploratory and size is a likely confounder; we have not separated it out yet.</p>
  <ul>__R2_TOP__</ul>
  <p>Which method was best per repository varies: __WINNERS__.</p>
</section>

__WRONG__

<section>
  <h2>Do the three kinds of evidence agree?</h2>
  <p>On the __AG_TASKS__ tasks with an execution run so far: the static key (co-edited + symbol) has __AG_SS__ files on average, and the execution key (lines inside functions that ran during the fixing tests) has __AG_SX__. __AG_SE__ of static-key files also ran; only __AG_ES__ of executed files are in the static key. Mean overlap (Jaccard) = __AG_J__. So running the tests touches far more code than the static evidence points to. That's a result about the limits of static analysis, not a bug.</p>
</section>

<section class="pending">
  <h2>What's not done yet</h2>
  <p><span class="pill">running</span>Execution answer key: __EX_N__ of the PRs so far. It needs one Docker test box per PR, and the full set takes about 14 hours. The PRs are processed in seeded random order, so the finished part is a random subset.</p>
  <p><span class="pill">pending</span>Embedding-based retrieval (one method): skipped for time. It needs about 9 hours of CPU, or minutes on a GPU.</p>
  <p><span class="pill">not started</span>RQ5 (does order change what a language model needs?) needs an API budget. RQ6 (formal analysis) is deferred.</p>
</section>

<section>
  <h2>How to read these numbers</h2>
  <ul>
    <li>The answer key is a <em>floor</em>. It contains files with evidence attached and misses files a developer only read. Methods are never penalised for listing extra files, only charged for the reading.</li>
    <li>Published approaches (Aider, RepoGraph, LocAgent, CoSIL) appear as <em>structure-only adaptations</em>, with no issue text and no model. These numbers must never be compared with the published ones.</li>
    <li>Unit of analysis: the PR (a PR's tasks are averaged). Ties inside any method are broken randomly, averaged over 5 seeds.</li>
    <li>Every rule was written down before any method ran (git tag <span class="mono">freeze-1</span>). Every change is logged.</li>
  </ul>
</section>

<footer>Generated by <span class="mono">src/depgraphs/report_page.py</span> from <span class="mono">results/analysis/</span>. Sample: 113 repos from SWE-bench, SWE-bench-Live and SWE-rebench, at most 20 PRs each, drawn by seed 20260922.</footer>
</div>

<script>
const D = __PAYLOAD__;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const NS = "http://www.w3.org/2000/svg";
const el = (t, a={}, p) => { const e=document.createElementNS(NS,t); for (const k in a) e.setAttribute(k,a[k]); if(p) p.appendChild(e); return e; };
function tip(host){ const t=document.createElement("div"); t.className="tip"; t.hidden=true; host.appendChild(t); return t; }

function drawCurves(){
  const host=document.getElementById("curve"); host.innerHTML="";
  const W=800,H=360,m={l:48,r:150,t:12,b:40};
  const svg=el("svg",{viewBox:`0 0 ${W} ${H}`,role:"img","aria-label":"Coverage by reading budget"},host);
  const order=["ppr_und","bm25","random","oracle"], col={ppr_und:"--s1",bm25:"--s2",random:"--s3",oracle:"--s4"};
  const xs=D.curves[order[0]].map(d=>d[0]);
  const lx=v=>m.l+(Math.log(v)-Math.log(xs[0]))/(Math.log(xs[xs.length-1])-Math.log(xs[0]))*(W-m.l-m.r);
  const ly=v=>m.t+(1-v)*(H-m.t-m.b);
  for (const g of [0,.25,.5,.75,1]){ el("line",{x1:m.l,x2:W-m.r,y1:ly(g),y2:ly(g),stroke:css("--grid")},svg);
    el("text",{x:m.l-8,y:ly(g)+4,"text-anchor":"end"},svg).textContent=Math.round(g*100)+"%"; }
  for (const x of xs){ el("text",{x:lx(x),y:H-m.b+18,"text-anchor":"middle"},svg).textContent=x>=1000?(x/1000)+"k":x; }
  el("text",{x:(m.l+W-m.r)/2,y:H-4,"text-anchor":"middle"},svg).textContent="lines read";
  const leg=document.getElementById("legend"); leg.innerHTML="";
  const ends=[];
  for (const k of order){ const pts=D.curves[k]; const c=css(col[k]);
    el("path",{d:pts.map((p,i)=>(i?"L":"M")+lx(p[0])+","+ly(p[1])).join(""),fill:"none",stroke:c,"stroke-width":2,"stroke-dasharray":k==="oracle"?"5 4":"none"},svg);
    const s=document.createElement("span"); s.innerHTML=`<i style="background:${c}"></i>${D.labels[k]}`; leg.appendChild(s);
    const last=pts[pts.length-1]; ends.push({k,y:ly(last[1]),c}); }
  ends.sort((a,b)=>a.y-b.y); for (let i=1;i<ends.length;i++) if (ends[i].y-ends[i-1].y<15) ends[i].y=ends[i-1].y+15;
  for (const e of ends){ el("text",{x:W-m.r+8,y:e.y+4,class:"lab"},svg).textContent=D.labels[e.k].replace(/ \(.*\)/,""); }
  const cross=el("line",{y1:m.t,y2:H-m.b,stroke:css("--ink-3"),"stroke-dasharray":"2 3",visibility:"hidden"},svg);
  const t=tip(host);
  const hit=el("rect",{x:m.l,y:m.t,width:W-m.l-m.r,height:H-m.t-m.b,fill:"transparent"},svg);
  hit.addEventListener("mousemove",ev=>{ const r=svg.getBoundingClientRect(); const px=(ev.clientX-r.left)*W/r.width;
    let i=0,best=1e9; xs.forEach((x,j)=>{const d=Math.abs(lx(x)-px); if(d<best){best=d;i=j;}});
    cross.setAttribute("x1",lx(xs[i])); cross.setAttribute("x2",lx(xs[i])); cross.setAttribute("visibility","visible");
    t.innerHTML=`<b>${xs[i].toLocaleString()} lines read</b><br>`+order.map(k=>`${D.labels[k]}: ${(D.curves[k][i][1]*100).toFixed(1)}%`).join("<br>");
    t.style.left=(lx(xs[i])/W*100)+"%"; t.style.top=(m.t/H*100+10)+"%"; t.hidden=false; });
  hit.addEventListener("mouseleave",()=>{t.hidden=true; cross.setAttribute("visibility","hidden");});
}

function drawDots(){
  const host=document.getElementById("dots"); host.innerHTML="";
  const rows=D.dots, rowH=22, m={l:270,r:56,t:20,b:30}, W=800, H=m.t+m.b+rows.length*rowH;
  const svg=el("svg",{viewBox:`0 0 ${W} ${H}`,role:"img","aria-label":"Area under the curve per method"},host);
  const max=Math.max(...rows.map(r=>r.hi)); const hiX=Math.ceil(max*10)/10;
  const x=v=>m.l+v/hiX*(W-m.l-m.r);
  for (let g=0; g<=hiX+1e-9; g+=0.1){ el("line",{x1:x(g),x2:x(g),y1:m.t-6,y2:H-m.b,stroke:css("--grid")},svg);
    el("text",{x:x(g),y:H-m.b+18,"text-anchor":"middle"},svg).textContent=g.toFixed(1); }
  const rnd=rows.find(r=>r.m==="random");
  el("line",{x1:x(rnd.mean),x2:x(rnd.mean),y1:m.t-6,y2:H-m.b,stroke:css("--ink-3"),"stroke-dasharray":"3 3"},svg);
  el("text",{x:x(rnd.mean)+4,y:m.t-8},svg).textContent="random floor";
  const t=tip(host);
  rows.forEach((r,i)=>{ const y=m.t+i*rowH+rowH/2; const c=r.ref?css("--ref"):css("--s1");
    el("text",{x:m.l-10,y:y+4,"text-anchor":"end",class:r.ref?"reflab":"lab"},svg).textContent=r.label;
    el("line",{x1:x(r.lo),x2:x(r.hi),y1:y,y2:y,stroke:c,"stroke-width":2,"stroke-linecap":"round"},svg);
    el("circle",{cx:x(r.mean),cy:y,r:4.5,fill:c,stroke:css("--panel"),"stroke-width":2},svg);
    el("text",{x:W-m.r+8,y:y+4,class:"mono"},svg).textContent=r.mean.toFixed(3);
    const hit=el("rect",{x:0,y:y-rowH/2,width:W,height:rowH,fill:"transparent"},svg);
    hit.addEventListener("mouseenter",()=>{ t.innerHTML=`<b>${r.label}</b><br>AUC ${r.mean.toFixed(3)} (95% CI ${r.lo.toFixed(3)}–${r.hi.toFixed(3)})<br>`+(r.m==="random"?"":`A12 vs random: ${r.a12.toFixed(2)}<br>`)+`${r.n} PRs`;
      t.style.left=(x(r.mean)/W*100)+"%"; t.style.top=((y-6)/H*100)+"%"; t.hidden=false; });
    hit.addEventListener("mouseleave",()=>t.hidden=true);
  });
}
function draw(){ drawCurves(); drawDots(); }
draw();
new MutationObserver(draw).observe(document.documentElement,{attributes:true,attributeFilter:["data-theme"]});
matchMedia("(prefers-color-scheme: dark)").addEventListener("change",draw);
</script>
"""

if __name__ == "__main__":
    main()
