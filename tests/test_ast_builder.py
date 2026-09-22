"""G13: toy repos whose graphs are known by hand."""
from pathlib import Path

import pytest

from depgraphs.graph.ast_builder import Options, build
from depgraphs.graph.cycles import condense, to_nx


def make(root: Path, files: dict[str, str]) -> Path:
    for rel, src in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src)
    return root


@pytest.fixture
def flat(tmp_path):
    return make(tmp_path, {
        "pkg/__init__.py": "from .core import Engine\nfrom .util import *\n__all__ = ['Engine']\n",
        "pkg/core.py": "import os\nimport numpy\nfrom . import util\nfrom .sub.deep import thing\n",
        "pkg/util.py": "from pkg.core import Engine\n",   # loop: core <-> util
        "pkg/sub/__init__.py": "",
        "pkg/sub/deep.py": (
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n    from pkg.core import Engine\n"
            "try:\n    import pkg.fast\nexcept ImportError:\n    pkg_fast = None\n"
            "def f():\n    import pkg.util\n"
            "import importlib\nm = importlib.import_module('pkg.util')\n"
            "thing = 1\n"),
        "pkg/fast.py": "",
        "pkg/broken.py": "def (:\n",
        "app.py": "import pkg.sub.deep\nfrom pkg import Engine\nimport pkg.missing\n",
        "tests/test_app.py": "import app\n",
    })


def E(g):
    return set(g.edges)


def test_default_edges(flat):
    g = build(flat)
    assert E(g) == {
        ("pkg/__init__.py", "pkg/core.py"),
        ("pkg/__init__.py", "pkg/util.py"),
        ("pkg/core.py", "pkg/util.py"),
        ("pkg/core.py", "pkg/sub/deep.py"),
        ("pkg/util.py", "pkg/core.py"),
        ("pkg/sub/deep.py", "pkg/core.py"),       # TYPE_CHECKING kept by default
        ("pkg/sub/deep.py", "pkg/fast.py"),       # try/except ImportError
        ("pkg/sub/deep.py", "pkg/util.py"),       # function-level
        ("app.py", "pkg/sub/deep.py"),
        ("app.py", "pkg/__init__.py"),            # `from pkg import Engine` -> package init
        ("tests/test_app.py", "app.py"),
    }


def test_counts_and_unresolved(flat):
    g = build(flat)
    assert g.counts["external_stdlib"] == 3          # os, typing, importlib
    assert g.counts["external_thirdparty"] == 1      # numpy
    assert g.counts["star"] == 1
    assert g.counts["relative"] == 4
    assert g.counts["importlib_import_module"] == 1
    assert g.counts["parse_failure"] == 1 and g.parse_failures == ["pkg/broken.py: SyntaxError"]
    assert g.counts["dunder_all"] == 1
    # `import pkg.missing` resolves only to its parent: partial, and logged
    assert g.counts["import_partially_resolved"] == 1
    rec = {r.lineno: r for r in g.records if r.src == "pkg/sub/deep.py"}
    assert rec[3].in_type_checking and rec[5].in_try_importerror and rec[9].in_function


def test_switches(flat):
    base = E(build(flat))
    no_tc = E(build(flat, Options(type_checking=False)))
    assert base - no_tc == {("pkg/sub/deep.py", "pkg/core.py")}
    no_fn = E(build(flat, Options(function_level=False)))
    assert base - no_fn == {("pkg/sub/deep.py", "pkg/util.py")}
    no_tests = build(flat, Options(include_tests=False))
    assert "tests/test_app.py" not in no_tests.nodes
    parents = E(build(flat, Options(parent_inits=True)))
    assert parents - base == {("app.py", "pkg/sub/__init__.py"),        # import pkg.sub.deep
                              ("pkg/sub/deep.py", "pkg/__init__.py"),   # import pkg.fast
                              ("pkg/core.py", "pkg/__init__.py"),       # from . import util
                              ("pkg/core.py", "pkg/sub/__init__.py"),   # from .sub.deep import
                              ("pkg/util.py", "pkg/__init__.py")}       # from pkg.core import
    # pkg/__init__ doing `from .core import` would point at itself: no self-edge.
    defining = E(build(flat, Options(from_target="defining")))
    # `from pkg import Engine` now points at core.py; app -> pkg/__init__ remains because
    # `import pkg.missing` partially resolves to the package.
    assert defining - base == {("app.py", "pkg/core.py")}
    assert base - defining == set()


def test_weighted(tmp_path):
    r = make(tmp_path, {"a.py": "import b\nimport b\ndef f():\n    import b\n", "b.py": ""})
    assert build(r).edges == {("a.py", "b.py"): 1}
    assert build(r, Options(weighted=True)).edges == {("a.py", "b.py"): 3}


def test_src_layout_and_namespace_package(tmp_path):
    r = make(tmp_path, {
        "src/lib/__init__.py": "",
        "src/lib/a.py": "from lib.ns.b import x\n",
        "src/lib/ns/b.py": "x = 1\nfrom ..a import *\n",   # ns has no __init__ (PEP 420)
        "tests/test_a.py": "from lib import a\n",
    })
    g = build(r)
    assert E(g) == {("src/lib/a.py", "src/lib/ns/b.py"), ("src/lib/ns/b.py", "src/lib/a.py"),
                    ("tests/test_a.py", "src/lib/a.py")}


def test_relative_beyond_top_is_logged(tmp_path):
    r = make(tmp_path, {"a.py": "from ... import x\n"})
    g = build(r)
    assert g.edges == {} and g.unresolved[0]["reason"] == "relative beyond top"


def test_condense(flat):
    g = build(flat)
    dag, clumps, member = condense(to_nx(g.nodes, g.edges))
    loops = [c for c in clumps.values() if len(c) > 1]
    assert loops == [["pkg/core.py", "pkg/sub/deep.py", "pkg/util.py"]]
    import networkx as nx
    assert nx.is_directed_acyclic_graph(dag)
    assert member["pkg/core.py"] == member["pkg/util.py"]


def test_treesitter_matches_ast_on_parseable_files(flat):
    a = build(flat)
    t = build(flat, parser="treesitter")
    assert set(t.edges) == set(a.edges)
    ra = {(r.src, r.lineno, r.module, r.names, r.level, r.in_function, r.in_type_checking,
           r.in_try_importerror) for r in a.records}
    rt = {(r.src, r.lineno, r.module, r.names, r.level, r.in_function, r.in_type_checking,
           r.in_try_importerror) for r in t.records}
    assert ra == rt


def test_treesitter_keeps_imports_from_broken_file(tmp_path):
    r = make(tmp_path, {"a.py": "import b\ndef (:\n", "b.py": ""})
    assert build(r).edges == {}
    assert build(r, parser="treesitter").edges == {("a.py", "b.py"): 1}


def test_unreadable_file_is_counted_not_fatal(tmp_path, monkeypatch):
    r = make(tmp_path, {"a.py": "import b\n", "b.py": ""})
    real = Path.read_text

    def fake(self, *a, **k):
        if self.name == "a.py":
            raise PermissionError("denied")
        return real(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", fake)
    g = build(r)
    assert g.counts["read_failure"] == 1 and g.parse_failures == ["a.py: unreadable (PermissionError)"]


def test_directory_named_like_py_file_is_not_a_node(tmp_path):
    r = make(tmp_path, {"a.py": "import b\n", "b.py": "", "weird.py/inner.txt": "x"})
    assert build(r).nodes == ["a.py", "b.py"]


def test_skipped_files_are_counted(tmp_path):
    r = make(tmp_path, {"a.py": "", "docs/my-example/x.py": "", ".hidden/y.py": "",
                        "tests/test_a.py": ""})
    g = build(r, Options(include_tests=False))
    assert g.nodes == ["a.py"]
    assert (g.counts["skipped_non_identifier_path"], g.counts["skipped_hidden_path"],
            g.counts["skipped_test_file"]) == (1, 1, 1)
