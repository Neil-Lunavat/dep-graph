"""logs/progress.json: one entry per stage, merged so parallel jobs don't overwrite each other."""
from __future__ import annotations

import json
import os
import time

from depgraphs.datasets import ROOT

PATH = ROOT / "logs" / "progress.json"


def update(stage: str, **fields) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(PATH.read_text())
        if "stage" in data:            # old single-stage format
            data = {data.pop("stage"): data}
    except (OSError, ValueError):
        data = {}
    data[stage] = {**fields, "updated": time.strftime("%Y-%m-%d %H:%M:%S")}
    tmp = PATH.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=1))
    os.replace(tmp, PATH)
