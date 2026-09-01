"""Consolidate every completed grid run into clean tables.

Reads the *-summary.json files rather than parsing logs, which are UTF-16 when
written by PowerShell and awkward to scrape.

Run: python analyze.py
"""

from __future__ import annotations

import glob
import json
import re
import statistics
from pathlib import Path

RUN_RE = re.compile(r"grid-(?P<model>.+?)-(?P<style>plain|salient)-"
                    r"(?P<sched>random|periodic)-(?P<family>\S+?-target)-"
                    r"(?P<stamp>\d{8}-\d{6})-summary\.json")


def load_runs() -> list[dict]:
    runs = []
    for f in sorted(glob.glob("runs/grid-*-summary.json")):
        m = RUN_RE.search(Path(f).name)
        if not m:
            continue
        rows = json.load(open(f))
        if len(rows) < 9:          # keep only complete 3x3 grids
            continue
        runs.append({**m.groupdict(), "rows": rows, "file": f})
    # if a config was run twice, keep the newest
    best: dict[tuple, dict] = {}
    for r in runs:
        key = (r["model"], r["style"], r["sched"], r["family"])
        if key not in best or r["stamp"] > best[key]["stamp"]:
            best[key] = r
    return list(best.values())


def grid(rows, field):
    return {(r["t_say"], r["t_do"]): r[field] for r in rows}


def stated_effects(rows, costs=(0, 2, 5)):
    """Effect on observation count of stating the top cost instead of zero,
    reported separately at each level of the real cost."""
    d = grid(rows, "obs")
    lo, hi = costs[0], costs[-1]
    return {c: d[(hi, c)] - d[(lo, c)] for c in costs}


def main() -> None:
    runs = load_runs()
    if not runs:
        print("No complete grids found.")
        return

    print(f"\n{len(runs)} complete 3x3 grids\n")

    for r in runs:
        label = f"{r['model']} / {r['style']} / {r['sched']} / {r['family']}"
        print("=" * 74)
        print(label)
        print("=" * 74)
        d = grid(r["rows"], "obs")
        s = grid(r["rows"], "success")
        costs = sorted({k[0] for k in d})
        caps = sum(x["hit_cap"] for x in r["rows"])
        n = sum(x["n"] for x in r["rows"])
        mal = sum(x["malformed"] for x in r["rows"])

        print("\nmean observations      (stated down, actual across)")
        print("        " + "".join(f"{c:>9}" for c in costs))
        for a in costs:
            print(f"  say={a}" + "".join(f"{d[(a,b)]:>9.2f}" for b in costs))

        print("\nsuccess rate")
        print("        " + "".join(f"{c:>9}" for c in costs))
        for a in costs:
            print(f"  say={a}" + "".join(f"{s[(a,b)]:>9.2f}" for b in costs))

        eff = stated_effects(r["rows"], costs)
        print(f"\neffect of stating cost {costs[-1]} instead of {costs[0]}:")
        for c, v in eff.items():
            print(f"    when the real cost is {c}: {v:+7.2f} observations")

        print(f"\n  n={n}  turn-cap hits={caps}  malformed={mal}"
              f"  ({100*caps/max(n,1):.1f}% censored)")
        print()

    # cross-run comparison of the headline quantity
    print("=" * 74)
    print("HEADLINE: does telling the agent it is expensive change anything?")
    print("=" * 74)
    print(f"\n{'run':<46}{'real=0':>9}{'real=5':>9}")
    for r in sorted(runs, key=lambda x: (x["family"], x["sched"], x["model"], x["style"])):
        costs = sorted({k[0] for k in grid(r['rows'], 'obs')})
        eff = stated_effects(r["rows"], costs)
        label = f"{r['model']}/{r['style']}/{r['sched']}/{r['family']}"
        print(f"{label:<46}{eff[costs[0]]:>+9.2f}{eff[costs[-1]]:>+9.2f}")
    print("\nA stated cost that worked on its own would move the 'real=0' column.")


if __name__ == "__main__":
    main()
