"""Parse unified diffs (git format) into per-file change records.

Kept dependency-free and small so every rule is visible and unit-tested.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

_DIFF_HEADER = re.compile(r"^diff --git a/(.*) b/(.*)$")


@dataclass
class FileChange:
    old_path: str | None
    new_path: str | None
    added: int = 0
    removed: int = 0
    added_lines: list[str] = field(default_factory=list)

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
            continue
        if in_hunk:
            if line.startswith("+"):
                cur.added += 1
                cur.added_lines.append(line[1:])
            elif line.startswith("-"):
                cur.removed += 1
    return files


# Test-path rule used in RUNBOOK section 9.2. D18 may replace it; keep it named.
TEST_DIRS = {"tests", "testing"}


def is_test_path_9_2(path: str) -> bool:
    p = PurePosixPath(path)
    if any(part in TEST_DIRS for part in p.parts[:-1]):
        return True
    name = p.name
    return name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"


def is_py(path: str) -> bool:
    return path.endswith(".py")
