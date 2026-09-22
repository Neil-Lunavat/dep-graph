"""R2 under an alternative definition, for Neil to compare at Gate A (D10). Not applied.

Variant "b" differs from the measured rule "a" in three places only:
  1. .pyi, .pyx, .pxd, .pxi count as Python (stubs and Cython) instead of other languages;
  2. a directory named `test` counts as a test directory (9.2 lists only tests/ and testing/);
  3. `cextern` is added to the vendored-directory names.
Writes results/step2/r2_variants.csv
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path, PurePosixPath

import pandas as pd

from depgraphs.candidates import CLONES, CODE_EXT, MAX_FILE_BYTES, VENDOR_DIRS, _analyse
from depgraphs.datasets import ROOT
from depgraphs.patches import is_test_path_9_2

PY_B = {".py", ".pyi", ".pyx", ".pxd", ".pxi"}
VENDOR_B = VENDOR_DIRS | {"cextern"}


def is_test_b(rel: PurePosixPath) -> bool:
    return is_test_path_9_2(str(rel)) or "test" in rel.parts[:-1]


def share_b(repo_dir: Path, pool) -> dict:
    files = [p for p in repo_dir.rglob("*") if p.is_file() and ".git" not in p.parts
             and p.suffix.lower() in CODE_EXT and p.stat().st_size <= MAX_FILE_BYTES]
    keep = []
    for p in files:
        rel = PurePosixPath(p.relative_to(repo_dir).as_posix())
        if is_test_b(rel) or any(x in VENDOR_B for x in rel.parts[:-1]):
            continue
        keep.append((p, rel))
    res = dict((r, n or 0) for r, n, _ in
               pool.map(_analyse, [(str(p), str(r)) for p, r in keep], chunksize=32))
    total = sum(res.values())
    py = sum(res[str(r)] for p, r in keep if p.suffix.lower() in PY_B)
    nontest_py = sum(1 for p, r in keep if p.suffix == ".py")
    return {"python_share_b": round(py / max(total, 1), 4), "nontest_py_files_b": nontest_py}


def main():
    c = pd.read_csv(ROOT / "data" / "candidates.csv")
    c = c[c.nontest_py_files.notna()]
    rows = []
    with ProcessPoolExecutor(8) as pool:
        for rk in c.repo_key:
            rows.append({"repo_key": rk, **share_b(CLONES / rk.replace("/", "__"), pool)})
    out = c[["repo_key", "python_share", "nontest_py_files"]].merge(pd.DataFrame(rows))
    out["R2_a"] = out.python_share >= 0.80
    out["R2_b"] = out.python_share_b >= 0.80
    out["R3_a"] = out.nontest_py_files >= 50
    out["R3_b"] = out.nontest_py_files_b >= 50
    out.to_csv(ROOT / "results" / "step2" / "r2_variants.csv", index=False)
    flips = out[(out.R2_a != out.R2_b) | (out.R3_a != out.R3_b)]
    print(flips.to_string())


if __name__ == "__main__":
    main()
