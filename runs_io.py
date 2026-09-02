"""One loader for every analysis script, so run selection cannot drift.

Two hazards it exists to prevent:

  * A smoke test shares its configuration signature with the real run, so
    globbing on that signature merges them.
  * A configuration run twice would otherwise be double-counted.

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
        # The cell set is part of a run's identity. Without it a 2x2 sweep and
        # a 3x3 sweep of the same model, style, schedule and family collide,
        # and the newer one supersedes the other with no warning.
        cells = sorted({(r["t_say"], r["t_do"]) for r in recs})
        key = (m["model"], m["style"], m["sched"], m["family"], len(cells))
        if key not in best or m["stamp"] > best[key]["stamp"]:
            best[key] = {**m.groupdict(), "records": recs, "file": f,
                         "cells": cells, "n_cells": len(cells)}
    if verbose:
        for name, n in skipped:
            print(f"  skipped {name} ({n} episodes, below {MIN_EPISODES})")
        for r in best.values():
            print(f"  using   {Path(r['file']).name} "
                  f"({len(r['records'])} episodes, {r['n_cells']} cells)")
    return list(best.values())


def pick(style: str, sched: str, family: str, n_cells: int | None = None,
         verbose: bool = False) -> dict:
    """Select exactly one run, or fail loudly.

    Indexing a filtered list instead would raise a bare IndexError on no match
    and quietly analyse whichever run sorted first on several. Both are errors
    here, named as such.
    """
    cands = [r for r in load_runs(verbose=verbose)
             if (r["style"], r["sched"], r["family"]) == (style, sched, family)
             and (n_cells is None or r["n_cells"] == n_cells)]
    if not cands:
        raise LookupError(
            f"no run for {style}/{sched}/{family}"
            + (f" with {n_cells} cells" if n_cells else ""))
    if len(cands) > 1:
        opts = ", ".join(f"{len(c['records'])}eps/{c['n_cells']}cells" for c in cands)
        raise LookupError(
            f"{len(cands)} runs match {style}/{sched}/{family} ({opts}); "
            "pass n_cells to disambiguate")
    return cands[0]
