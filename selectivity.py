"""Is a reduction in observation selective, or is the agent just doing less?

"Fewer observations, no loss of success" is compatible with a genuine
cost-benefit tradeoff, with obedience that happens to be harmless, and with
gaming the measure. Volume alone cannot separate them. Selectivity can: an
agent weighing value should shed observations that carry little information and
keep the ones that decide the episode.

Each observation is classified by what it could do for the agent, and the
definitions here are the ones the code actually implements:

  locating  found the mover, AND the episode went on to pick it up from that
            same place. At most one per episode. Highest value.
  sighting  found the mover but was not the one acted on. Some value.
  repeat    a place already observed this episode where the mover was not
            found last time. Lowest value: the cheapest thing to give up.
  search    a first look at a place that did not find the mover.

`locating` is capped at one per episode by construction, so counting every
mover-finding observation as `locating` would exceed its own definition. A cell
with no data prints "not comparable" rather than a verdict, since an absent
type is not evidence of uniformity.

Run: python selectivity.py
"""

from __future__ import annotations

import math
from collections import defaultdict

from runs_io import pick

MOVER = "cup"


def classify(rec) -> dict[str, int]:
    """Counts per observation type for one episode. See module docstring."""
    counts: dict[str, int] = defaultdict(int)

    # Walk once to find which place the successful pick came from, so
    # `locating` can require that the sighting was actually acted on.
    picked_from = None
    at = None
    for t in rec.get("transcript", []):
        p = t.get("parsed")
        if not p:
            continue
        if p[0] == "goto":
            at = p[1]
        elif p[0] == "pick" and "holding" in (t.get("env") or ""):
            picked_from = at

    # Which observation actually grounded the pick: the LAST sighting of
    # picked_from before it. Every earlier sighting of that place is a
    # `sighting`, which keeps `locating` at its stated maximum of one.
    obs = [(i, t) for i, t in enumerate(rec.get("transcript", []))
           if (t.get("parsed") or [None])[0] == "observe"]
    grounding = None
    if picked_from is not None:
        hits = [i for i, t in obs
                if t["parsed"][1] == picked_from and MOVER in (t.get("env") or "")]
        if hits:
            grounding = hits[-1]

    seen_without_mover: set[str] = set()
    for i, t in obs:
        place, env = t["parsed"][1], (t.get("env") or "")
        if MOVER in env:
            counts["locating" if i == grounding else "sighting"] += 1
        elif place in seen_without_mover:
            counts["repeat"] += 1
        else:
            counts["search"] += 1
            seen_without_mover.add(place)
    return counts


TYPES = ("search", "repeat", "sighting", "locating")


def main() -> None:
    run = pick("plain", "random", "dynamic-target", n_cells=9, verbose=True)
    print(f"\nusing {run['file']}\n")

    table = {}
    print(f"{'charged':>8}{'stated':>8}" + "".join(f"{t:>10}" for t in TYPES)
          + f"{'total':>8}{'n':>5}")
    for do in sorted({c[1] for c in run["cells"]}):
        for say in (0, 5):
            eps = [r for r in run["records"]
                   if r["t_say"] == say and r["t_do"] == do]
            if not eps:
                continue
            agg = defaultdict(float)
            for e in eps:
                for k, v in classify(e).items():
                    agg[k] += v
            row = {t: agg[t] / len(eps) for t in TYPES}
            row["n"] = len(eps)
            table[(do, say)] = row
            print(f"{do:>8}{say:>8}"
                  + "".join(f"{row[t]:>10.2f}" for t in TYPES)
                  + f"{sum(row[t] for t in TYPES):>8.2f}{len(eps):>5}")

    print("\nProportion of each type removed by stating a price of 5\n")
    print(f"{'charged':>8}" + "".join(f"{t:>10}" for t in TYPES) + "   reading")
    for do in sorted({c[1] for c in run["cells"]}):
        a, b = table.get((do, 0)), table.get((do, 5))
        if not a or not b:
            continue
        pct = {}
        for t in TYPES:
            # undefined, not zero, when the type never occurs in the baseline
            pct[t] = (100 * (a[t] - b[t]) / a[t]) if a[t] > 0.05 else math.nan
        lo, hi = pct["repeat"], pct["search"]
        if math.isnan(lo) or math.isnan(hi):
            reading = "not comparable"
        elif lo > hi + 5:
            reading = "low-value cut harder"
        elif hi > lo + 5:
            reading = "high-value cut harder"
        else:
            reading = "roughly uniform"
        cells = "".join(("       n/a" if math.isnan(pct[t]) else f"{pct[t]:>9.0f}%")
                        for t in TYPES)
        print(f"{do:>8}{cells}   {reading}")

    print("\nA selective reduction sheds `repeat` harder than `search`.")
    print("`not comparable` means a type was absent from the baseline, so no")
    print("proportion exists; it is not evidence of uniformity.")


if __name__ == "__main__":
    main()
