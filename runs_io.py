"""One loader for every analysis script, so run selection cannot drift.

Two hazards this exists to prevent, both of which bit us:

  * The 16-episode smoke test shares its configuration signature with the real
    449-episode run. Globbing on that signature silently merges them.
  * A configuration re-run twice would otherwise be double-counted.

Rule: keep only complete grids (>= MIN_EPISODES), and where a configuration
appears more than once keep the newest timestamp.
"""

from __future__ import annotations

import glob
import json
import re
from pathlib import Path

MIN_EPISODES = 100          # a complete 3x3 grid is ~450; the smoke test is 16

RUN_RE = re.compile(
    r"grid-(?P<model>.+?)-(?P<style>plain|salient)-"
    r"(?P<sched>random|periodic)-(?P<family>\S+?-target)-"
    r"(?P<stamp>\d{8}-\d{6})\.json$"
)


def load_runs(verbose: bool = False) -> list[dict]:
    """Complete grids, one per configuration, newest wins."""
    best: dict[tuple, dict] = {}
    skipped = []
    for f in sorted(glob.glob("runs/grid-*.json")):
        if f.endswith("-summary.json"):
            continue
        m = RUN_RE.search(Path(f).name)
        if not m:
            continue
        recs = json.load(open(f, encoding="utf-8"))
        if len(recs) < MIN_EPISODES:
            skipped.append((Path(f).name, len(recs)))
            continue
        key = (m["model"], m["style"], m["sched"], m["family"])
        if key not in best or m["stamp"] > best[key]["stamp"]:
            best[key] = {**m.groupdict(), "records": recs, "file": f}
    if verbose:
        for name, n in skipped:
            print(f"  skipped {name} ({n} episodes, below {MIN_EPISODES})")
        for r in best.values():
            print(f"  using   {Path(r['file']).name} ({len(r['records'])} episodes)")
    return list(best.values())
