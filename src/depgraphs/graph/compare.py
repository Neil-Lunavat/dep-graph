"""Gate B prep: compare import-graph builders on the same repository (ROADMAP Step 3, D9).

Scope: files inside the repo's top-level packages (so grimp and pydeps, which work per
package, see the same node set as the file-walking builders). Each builder's output is mapped
to file-level edges (POSIX paths relative to the repo) and compared pairwise.

Writes results/step3_prep/builders/<repo>.json and results/step3_prep/builders_summary.csv
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from depgraphs.datasets import ROOT
from depgraphs.graph.ast_builder import Options, build, discover, source_roots

OUT = ROOT / "results" / "step3_prep"
NOT_PACKAGES = {"tests", "test", "testing", "docs", "doc", "examples", "example",
                "benchmarks", "bench", "scripts", "tools", "ci", "build", "dist"}


def top_packages(repo: Path) -> list[tuple[Path, str]]:
    """(source root, package name) for every top-level regular package."""
    out = []
    for root in source_roots(repo):
        for d in sorted(root.iterdir()):
            if d.is_dir() and (d / "__init__.py").exists() and d.name.isidentifier() \
                    and d.name not in NOT_PACKAGES and not any(d.name == r.name for r, _ in out):
                out.append((root, d.name))
    return out


def _grimp(repo: Path, pkgs, mods) -> set:
    code = r"""
import json, sys
roots, names = json.loads(sys.argv[1]), json.loads(sys.argv[2])
sys.path[:0] = roots
import grimp
g = grimp.build_graph(*names, include_external_packages=False,
                      exclude_type_checking_imports=False, cache_dir=None)
print(json.dumps([[m, i] for m in g.modules for i in g.find_modules_directly_imported_by(m)]))
"""
    roots = sorted({str(r.resolve()) for r, _ in pkgs})
    names = [n for _, n in pkgs]
    r = subprocess.run([sys.executable, "-c", code, json.dumps(roots), json.dumps(names)],
                       capture_output=True, text=True, timeout=1800, check=True)
    pairs = json.loads(r.stdout)
    return {(mods[a], mods[b]) for a, b in pairs if a in mods and b in mods and mods[a] != mods[b]}


def _pydeps(repo: Path, pkgs, mods) -> tuple[set, list[str]]:
    exe = Path(sys.executable).with_name("pydeps.exe" if sys.platform == "win32" else "pydeps")
    edges, errors = set(), []
    by_path = {str((repo / f).resolve()).lower(): f for f in mods.values()}
    for root, name in pkgs:
        r = subprocess.run([str(exe), name, "--show-deps", "--no-output", "--max-bacon", "0",
                            "--no-config"], cwd=root, capture_output=True, text=True,
                           timeout=1800)
        if r.returncode != 0:
            errors.append(f"{name}: {r.stderr.strip()[-300:]}")
            continue
        deps = json.loads(r.stdout)
        path_of = {k: v.get("path") for k, v in deps.items()}
        for k, v in deps.items():
            a = by_path.get(str(Path(path_of[k]).resolve()).lower()) if path_of[k] else None
            for imp in v.get("imports", []):
                p = path_of.get(imp)
                b = by_path.get(str(Path(p).resolve()).lower()) if p else None
                if a and b and a != b:
                    edges.add((a, b))
    return edges, errors


def compare(repo: str | Path) -> dict:
    repo = Path(repo)
    pkgs = top_packages(repo)
    mods = discover(repo)
    prefixes = []
    for root, name in pkgs:
        rel = (root / name).relative_to(repo).as_posix()
        prefixes.append(rel + "/")
    in_scope = lambda f: any(f.startswith(p) for p in prefixes)
    scope_mods = {m: f for m, f in mods.items() if in_scope(f)}
    nodes = sorted(set(scope_mods.values()))

    def restrict(edges):
        return {(a, b) for a, b in edges if in_scope(a) and in_scope(b)}

    results, timings, errors = {}, {}, {}
    variants = {
        "ast": Options(),
        "ast_parent_inits": Options(parent_inits=True),
        "ast_defining": Options(from_target="defining"),
        "ast_no_type_checking": Options(type_checking=False),
        "ast_no_function_level": Options(function_level=False),
    }
    ast_graph = None
    for name, opts in variants.items():
        t0 = time.time()
        g = build(repo, opts)
        timings[name] = round(time.time() - t0, 2)
        results[name] = restrict(g.edges)
        if name == "ast":
            ast_graph = g
    t0 = time.time()
    results["treesitter"] = restrict(build(repo, parser="treesitter").edges)
    timings["treesitter"] = round(time.time() - t0, 2)
    for name, fn in (("grimp", _grimp), ("pydeps", _pydeps)):
        t0 = time.time()
        try:
            out = fn(repo, pkgs, scope_mods)
            if isinstance(out, tuple):
                out, errs = out
                if errs:
                    errors[name] = errs
            results[name] = restrict(out)
        except Exception as e:
            errors[name] = [f"{type(e).__name__}: {getattr(e, 'stderr', '') or e}"[-500:]]
        timings[name] = round(time.time() - t0, 2)

    # Where each ast edge came from, for explaining disagreements.
    why = {}
    for r in ast_graph.records:
        why.setdefault(r.src, []).append(asdict(r))

    pair_rows = []
    names = list(results)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            A, B = results[a], results[b]
            pair_rows.append({"a": a, "b": b, "a_edges": len(A), "b_edges": len(B),
                              "both": len(A & B), "only_a": len(A - B), "only_b": len(B - A),
                              "jaccard": round(len(A & B) / max(len(A | B), 1), 4)})
    examples = {}
    for other in names:
        if other == "ast":
            continue
        examples[other] = {"only_ast": sorted(results["ast"] - results[other])[:15],
                           "only_" + other: sorted(results[other] - results["ast"])[:15]}
    return {"repo": repo.name, "packages": [n for _, n in pkgs], "nodes": len(nodes),
            "edges": {k: len(v) for k, v in results.items()}, "timings_s": timings,
            "errors": errors, "pairs": pair_rows, "examples": examples,
            "ast_counts": dict(ast_graph.counts),
            "ast_unresolved": len([u for u in ast_graph.unresolved if in_scope(u["file"])]),
            "ast_parse_failures": ast_graph.parse_failures,
            "edge_lists": {k: sorted(v) for k, v in results.items()}}


# Run by mistake before the rule was applied (see DECISIONS.md); kept and labelled, not hidden.
EXTRA_REPOS = ["mwaskom/seaborn", "django-json-api/django-rest-framework-json-api"]


def rule_repos() -> list[str]:
    """The passing repo with fewest non-test .py files from SWE-bench, and from the rest
    (ties by name)."""
    r = pd.read_csv(ROOT / "results" / "step2" / "gate_a_repos.csv")
    r = r[r.passes_R2_R3_R5_X].sort_values(["nontest_py_files", "repo_key"])
    sb = r.datasets.str.contains("swebench_full")
    return [r[sb].repo_key.iloc[0], r[~sb].repo_key.iloc[0]]


def main(repos: list[str]):
    (OUT / "builders").mkdir(parents=True, exist_ok=True)
    rows = []
    for r in repos:
        res = compare(ROOT / "data" / "repos" / r.replace("/", "__"))
        (OUT / "builders" / f"{r.replace('/', '__')}.json").write_text(json.dumps(res, indent=1))
        for p in res["pairs"]:
            rows.append({"repo": r, "chosen_by": "extra" if r in EXTRA_REPOS else "rule", **p})
    pd.DataFrame(rows).to_csv(OUT / "builders_summary.csv", index=False)


if __name__ == "__main__":
    main(sys.argv[1:])
