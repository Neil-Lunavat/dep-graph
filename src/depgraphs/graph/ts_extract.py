"""Import extraction with tree-sitter (builder candidate 4).

Produces the same ImportRecord objects as the ast collector, so resolution is shared and
any disagreement comes from parsing. Keeps going past syntax errors.
Construct counts (star, dynamic imports, ...) are left to the ast collector.
"""
from __future__ import annotations

import tree_sitter_python
from tree_sitter import Language, Parser

from depgraphs.graph.ast_builder import ImportRecord

_LANG = Language(tree_sitter_python.language())
_PARSER = Parser(_LANG)
_FUNC = {"function_definition", "lambda"}


def _text(n) -> str:
    return n.text.decode("utf-8", errors="replace")


def _context(node):
    fn = tc = tryie = cond = False
    child, p = node, node.parent
    while p is not None:
        if p.type in _FUNC:
            fn = True
        elif p.type == "if_statement":
            test = p.child_by_field_name("condition")
            in_body = p.child_by_field_name("consequence")
            is_tc = test is not None and _text(test).split(".")[-1].strip() == "TYPE_CHECKING"
            if is_tc and in_body is not None and in_body.id == child.id:
                tc = True
            else:
                cond = True
        elif p.type in ("elif_clause", "else_clause"):
            cond = True
        elif p.type == "try_statement":
            body = p.child_by_field_name("body")
            if body is not None and body.id == child.id:
                for h in p.children:
                    if h.type == "except_clause":
                        t = _text(h)
                        if any(x in t for x in ("ImportError", "ModuleNotFoundError", "Exception")) \
                                or t.split(":")[0].strip() == "except":
                            tryie = True
        child, p = p, p.parent
    return dict(in_function=fn, in_type_checking=tc, in_try_importerror=tryie, in_conditional=cond)


def extract(path: str, src: str) -> tuple[list[ImportRecord], bool]:
    tree = _PARSER.parse(src.encode("utf-8"))
    out: list[ImportRecord] = []
    stack = [tree.root_node]
    while stack:
        n = stack.pop()
        if n.type == "import_statement":
            for c in n.named_children:
                name = c.child_by_field_name("name") if c.type == "aliased_import" else c
                if name is not None and name.type == "dotted_name":
                    out.append(ImportRecord(path, n.start_point[0] + 1, _text(name), (), 0,
                                            **_context(n)))
        elif n.type == "import_from_statement":
            mod = n.child_by_field_name("module_name")
            level, module = 0, ""
            if mod is not None:
                t = _text(mod)
                level = len(t) - len(t.lstrip("."))
                module = t.lstrip(".")
            names, star = [], False
            for c in n.children_by_field_name("name"):
                nm = c.child_by_field_name("name") if c.type == "aliased_import" else c
                names.append(_text(nm))
            if any(c.type == "wildcard_import" for c in n.children):
                star, names = True, ["*"]
            out.append(ImportRecord(path, n.start_point[0] + 1, module, tuple(names), level,
                                    star=star, **_context(n)))
        stack.extend(reversed(n.children))
    out.sort(key=lambda r: r.lineno)
    return out, tree.root_node.has_error
