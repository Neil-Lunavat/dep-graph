"""Custom `ast` import-graph builder (builder candidate 3, ROADMAP Step 3).

Every open Appendix A rule is a switch in `Options`, so D9 can be decided by looking at
what each switch does rather than by a default baked into code.

Nodes are repository files (POSIX relative paths). An edge X -> Y means X imports Y.
Every import statement is logged with the context it appeared in (Appendix B), and every
statement that could not be resolved to a repository file is kept in `unresolved`.
"""
from __future__ import annotations

import ast
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from depgraphs.patches import is_test_path_9_2

STDLIB = set(sys.stdlib_module_names)


@dataclass(frozen=True)
class Options:
    parent_inits: bool = False        # `import a.b.c` also adds edges to a/__init__, a/b/__init__
    from_target: str = "module"       # "module": `from pkg import name` -> pkg/__init__ if name is not a submodule
                                      # "defining": follow __init__ re-exports to the defining file
    weighted: bool = False            # edges carry the number of import statements (else weight 1)
    include_tests: bool = True        # test files (9.2 path rule) are nodes
    type_checking: bool = True        # keep imports under `if TYPE_CHECKING:`
    function_level: bool = True       # keep imports inside functions/methods


@dataclass
class ImportRecord:
    src: str                 # importing file
    lineno: int
    module: str              # absolute dotted target as written/resolved (may be "")
    names: tuple[str, ...]   # imported names for from-imports
    level: int               # relative level (0 = absolute)
    in_function: bool = False
    in_type_checking: bool = False
    in_try_importerror: bool = False
    in_conditional: bool = False
    star: bool = False


@dataclass
class Graph:
    nodes: list[str]
    edges: dict[tuple[str, str], int]
    module_of: dict[str, str]
    records: list[ImportRecord] = field(default_factory=list)
    unresolved: list[dict] = field(default_factory=list)
    counts: Counter = field(default_factory=Counter)   # Appendix B construct frequencies
    parse_failures: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- module discovery

def source_roots(repo: Path) -> list[Path]:
    """Directories whose children are top-level importable names.

    src/ layout if `src/` holds at least one package or module; always the repo root too
    (tests, scripts and flat-layout packages live there).
    """
    roots = []
    src = repo / "src"
    if src.is_dir() and any((p.is_dir() and not p.name.startswith(".")) or p.suffix == ".py"
                            for p in src.iterdir()):
        roots.append(src)
    roots.append(repo)
    return roots


def discover(repo: Path, include_tests: bool = True) -> dict[str, str]:
    """Map dotted module name -> file path (relative, POSIX)."""
    mods: dict[str, str] = {}
    roots = source_roots(repo)
    for p in sorted(repo.rglob("*.py")):
        rel = PurePosixPath(p.relative_to(repo).as_posix())
        if any(part.startswith(".") for part in rel.parts) or ".git" in rel.parts:
            continue
        if not include_tests and is_test_path_9_2(str(rel)):
            continue
        root = next(r for r in roots if p.is_relative_to(r))
        parts = list(PurePosixPath(p.relative_to(root).as_posix()).with_suffix("").parts)
        if not all(x.isidentifier() for x in parts):
            continue  # not importable by name (e.g. `my-script.py`); still counted below
        if parts[-1] == "__init__":
            parts = parts[:-1]
            if not parts:
                continue
        name = ".".join(parts)
        # Inner root (src/) wins over the repo root for the same name.
        mods.setdefault(name, str(rel))
    return mods


# ---------------------------------------------------------------- statement collection

def _is_type_checking(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")


def _catches_importerror(h: ast.ExceptHandler) -> bool:
    names = []
    t = h.type
    if t is None:
        return True
    for e in (t.elts if isinstance(t, ast.Tuple) else [t]):
        if isinstance(e, ast.Name):
            names.append(e.id)
        elif isinstance(e, ast.Attribute):
            names.append(e.attr)
    return any(n in ("ImportError", "ModuleNotFoundError", "Exception", "BaseException")
               for n in names)


class _Collector(ast.NodeVisitor):
    def __init__(self, src: str, counts: Counter):
        self.src, self.counts = src, counts
        self.records: list[ImportRecord] = []
        self.fn = self.tc = self.tryie = self.cond = 0

    def _ctx(self, **kw):
        return dict(in_function=self.fn > 0, in_type_checking=self.tc > 0,
                    in_try_importerror=self.tryie > 0, in_conditional=self.cond > 0, **kw)

    def visit_FunctionDef(self, node):
        self.fn += 1
        self.generic_visit(node)
        self.fn -= 1
        if node.name == "__getattr__" and self.fn == 0:
            self.counts["module_getattr"] += 1

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_If(self, node):
        tc = _is_type_checking(node.test)
        self.tc += tc
        self.cond += not tc
        for n in node.body:
            self.visit(n)
        self.tc -= tc
        self.cond -= not tc
        self.cond += 1
        for n in node.orelse:
            self.visit(n)
        self.cond -= 1
        self.visit(node.test)

    def visit_Try(self, node):
        ie = any(_catches_importerror(h) for h in node.handlers)
        self.tryie += ie
        for n in node.body:
            self.visit(n)
        self.tryie -= ie
        for part in (node.handlers, node.orelse, node.finalbody):
            for n in part:
                self.visit(n)

    visit_TryStar = visit_Try

    def visit_Import(self, node):
        for a in node.names:
            self.counts["import"] += 1
            if a.asname:
                self.counts["aliased"] += 1
            self.records.append(ImportRecord(self.src, node.lineno, a.name, (), 0, **self._ctx()))

    def visit_ImportFrom(self, node):
        self.counts["from_import"] += 1
        if node.level:
            self.counts["relative"] += 1
        star = any(a.name == "*" for a in node.names)
        if star:
            self.counts["star"] += 1
        if any(a.asname for a in node.names):
            self.counts["aliased"] += 1
        self.records.append(ImportRecord(self.src, node.lineno, node.module or "",
                                         tuple(a.name for a in node.names), node.level,
                                         star=star, **self._ctx()))

    def visit_Call(self, node):
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
        if name == "import_module":
            self.counts["importlib_import_module"] += 1
        elif name == "__import__":
            self.counts["dunder_import"] += 1
        if isinstance(f, ast.Attribute) and f.attr in ("insert", "append", "extend") and \
                isinstance(f.value, ast.Attribute) and f.value.attr == "path" and \
                getattr(f.value.value, "id", None) == "sys":
            self.counts["sys_path_edit"] += 1
        self.generic_visit(node)

    def visit_Assign(self, node):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == "__all__" and self.fn == 0:
                self.counts["dunder_all"] += 1
        self.generic_visit(node)


# ---------------------------------------------------------------- resolution

def _package_of(module: str, is_init: bool) -> str:
    return module if is_init else module.rpartition(".")[0]


def _absolute(rec: ImportRecord, module: str, is_init: bool) -> str | None:
    if rec.level == 0:
        return rec.module
    pkg = _package_of(module, is_init).split(".") if module else []
    up = rec.level - 1
    if up > len(pkg):
        return None
    base = pkg[: len(pkg) - up] if up else pkg
    return ".".join([*base, *( [rec.module] if rec.module else [])])


def build(repo: str | Path, opts: Options = Options()) -> Graph:
    repo = Path(repo)
    mods = discover(repo, include_tests=opts.include_tests)
    file_to_mod = {f: m for m, f in mods.items()}
    tops = {m.split(".")[0] for m in mods}
    counts: Counter = Counter()
    records: list[ImportRecord] = []
    parse_failures = []
    trees: dict[str, ast.Module] = {}
    for f in sorted(set(mods.values())):
        try:
            src = (repo / f).read_text(encoding="utf-8", errors="replace")
            trees[f] = ast.parse(src, filename=f)
        except (SyntaxError, ValueError) as e:
            parse_failures.append(f"{f}: {type(e).__name__}")
            counts["parse_failure"] += 1
            continue
        c = _Collector(f, counts)
        c.visit(trees[f])
        records += c.records

    reexports = _reexport_table(mods, trees) if opts.from_target == "defining" else {}

    edges: Counter = Counter()
    unresolved = []

    def add(src: str, mod: str):
        dst = mods.get(mod)
        if dst and dst != src:
            edges[(src, dst)] += 1
            return True
        return False

    for r in records:
        if r.in_type_checking and not opts.type_checking:
            counts["dropped_type_checking"] += 1
            continue
        if r.in_function and not opts.function_level:
            counts["dropped_function_level"] += 1
            continue
        me = file_to_mod[r.src]
        target = _absolute(r, me, r.src.endswith("__init__.py"))
        if target is None:
            unresolved.append({"file": r.src, "line": r.lineno, "reason": "relative beyond top"})
            continue
        top = target.split(".")[0] if target else ""
        if r.level == 0 and top not in tops:
            counts["external_stdlib" if top in STDLIB else "external_thirdparty"] += 1
            continue

        targets: list[str] = []
        if r.names and not r.star:
            for n in r.names:
                sub = f"{target}.{n}" if target else n
                if sub in mods:
                    targets.append(sub)
                elif target in mods:
                    targets.append(reexports.get((target, n), target))
                else:
                    targets.append("")
        elif r.star:
            targets.append(target)
        else:
            # `import a.b.c`: deepest existing module; parents optional.
            parts = target.split(".")
            found = next((".".join(parts[:i]) for i in range(len(parts), 0, -1)
                          if ".".join(parts[:i]) in mods), None)
            targets.append(found or "")
            if found and found != target:
                counts["import_partially_resolved"] += 1
            if opts.parent_inits and found:
                fp = found.split(".")
                targets += [".".join(fp[:i]) for i in range(1, len(fp))]

        for t in targets:
            if not t or not add(r.src, t):
                if not t or t not in mods:
                    unresolved.append({"file": r.src, "line": r.lineno,
                                       "target": target, "names": ",".join(r.names),
                                       "reason": "internal name not found"})
                    counts["unresolved_internal"] += 1
                else:
                    counts["self_import"] += 1

    if not opts.weighted:
        edges = Counter({e: 1 for e in edges})
    return Graph(nodes=sorted(set(mods.values())), edges=dict(edges), module_of=file_to_mod,
                 records=records, unresolved=unresolved, counts=counts,
                 parse_failures=parse_failures)


def _reexport_table(mods: dict[str, str], trees: dict[str, ast.Module]) -> dict:
    """(package module, name) -> defining module, following `from .x import name` chains
    written at the top level of __init__.py files."""
    direct: dict[tuple[str, str], str] = {}
    for m, f in mods.items():
        if not f.endswith("__init__.py") or f not in trees:
            continue
        for node in trees[f].body:
            if isinstance(node, ast.ImportFrom):
                rec = ImportRecord(f, node.lineno, node.module or "", (), node.level)
                tgt = _absolute(rec, m, True)
                if not tgt or tgt not in mods:
                    continue
                for a in node.names:
                    if a.name != "*":
                        direct[(m, a.asname or a.name)] = (
                            f"{tgt}.{a.name}" if f"{tgt}.{a.name}" in mods else tgt)

    def follow(key, seen=()):
        tgt = direct[key]
        nxt = (tgt, key[1])
        if nxt in direct and nxt not in seen and mods.get(tgt, "").endswith("__init__.py"):
            return follow(nxt, (*seen, key))
        return tgt

    return {k: follow(k) for k in direct}
