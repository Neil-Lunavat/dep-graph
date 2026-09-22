"""Parse unified diffs (git format) into per-file change records.

Kept dependency-free and small so every rule is visible and unit-tested.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

_DIFF_HEADER = re.compile(r"^diff --git a/(.*) b/(.*)$")
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass
class FileChange:
    old_path: str | None
    new_path: str | None
    added: int = 0
    removed: int = 0
    added_lines: list[str] = field(default_factory=list)
    added_linenos: list[int] = field(default_factory=list)   # line numbers in the new file

    @property
    def path(self) -> str:
        return self.new_path or self.old_path  # type: ignore[return-value]

    @property
    def is_new(self) -> bool:
        return self.old_path is None

    @property
    def is_deleted(self) -> bool:
        return self.new_path is None

    @property
    def changed(self) -> int:
        return self.added + self.removed


def parse(diff: str) -> list[FileChange]:
    files: list[FileChange] = []
    cur: FileChange | None = None
    in_hunk = False
    new_no = 0
    for line in diff.splitlines():
        m = _DIFF_HEADER.match(line)
        if m:
            cur = FileChange(old_path=m.group(1), new_path=m.group(2))
            files.append(cur)
            in_hunk = False
            continue
        if cur is None:
            continue
        if not in_hunk:
            if line.startswith("--- "):
                if line[4:].strip() == "/dev/null":
                    cur.old_path = None
            elif line.startswith("+++ "):
                if line[4:].strip() == "/dev/null":
                    cur.new_path = None
            elif line.startswith("rename to "):
                cur.new_path = line[len("rename to "):]
            elif line.startswith("new file mode"):
                cur.old_path = None
            elif line.startswith("deleted file mode"):
                cur.new_path = None
        if line.startswith("@@"):
            in_hunk = True
            h = _HUNK.match(line)
            new_no = int(h.group(1)) if h else 0
            continue
        if in_hunk:
            if line.startswith("+"):
                cur.added += 1
                cur.added_lines.append(line[1:])
                cur.added_linenos.append(new_no)
                new_no += 1
            elif line.startswith("-"):
                cur.removed += 1
            elif not line.startswith("\\"):
                new_no += 1
    return files


# Test-path rule used in RUNBOOK section 9.2. D18 may replace it; keep it named.
TEST_DIRS = {"tests", "testing"}


def is_test_path_9_2(path: str) -> bool:
    p = PurePosixPath(path)
    if any(part in TEST_DIRS for part in p.parts[:-1]):
        return True
    name = p.name
    return name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"


# The study's test rule (D10b/D18): 9.2 plus directories named `test`.
STUDY_TEST_DIRS = TEST_DIRS | {"test"}


def is_test_path(path: str) -> bool:
    p = PurePosixPath(path)
    if any(part in STUDY_TEST_DIRS for part in p.parts[:-1]):
        return True
    return is_test_path_9_2(path)


def is_py(path: str) -> bool:
    return path.endswith(".py")
