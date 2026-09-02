"""Is the reduction selective, or is the agent just doing less?

"Fewer observations, no loss of success" is compatible with three stories:
a genuine cost-benefit tradeoff, obedience that happens to be harmless because
the task has slack, and gaming the measure. The headline number cannot
distinguish them.

Selectivity can. A cost-sensitive agent should shed observations that carry
little information and keep the ones that decide the episode. An agent merely
complying should shed them roughly uniformly.

Each observation is classified by what it could do for the agent:

  repeat   a place already observed this episode, and the mover was not
           found there last time. Low value: cheapest thing to give up.
  search   a first look at a place. This is how the mover gets found.
  locating the observation that found the mover and was followed by a pick.
           Highest value; giving these up should hurt.

If the stated price cuts `repeat` harder than `search`, the reduction is
selective. If it cuts them in the same proportion, it is suppression.
"""

from __future__ import annotations

from collections import defaultdict

from runs_io import load_runs

MOVER = "cup"


def classify(rec) -> dict:
    """Counts of each observation type in one episode."""
    seen, found_at, counts = set(), None, defaultdict(int)
    for t in rec.get("transcript", []):
        p = t.get("parsed")
        if not p or p[0] != "observe":
            continue
        place, env = p[1], (t.get("env") or "")
        located = MOVER in env
        if located:
            counts["locating"] += 1
            found_at = place
        elif place in seen:
            counts["repeat"] += 1
        else:
            counts["search"] += 1
        seen.add(place)
    return counts


def main() -> None:
    run = [r for r in load_runs()
           if (r["style"], r["sched"], r["family"])
           == ("plain", "random", "dynamic-target")][0]

    print("\nObservation types per episode, moving target\n")
    print(f"{'charged':>8}{'stated':>8}{'search':>9}{'repeat':>9}"
          f"{'locating':>10}{'total':>8}")
    table = {}
    for do in (0, 2, 5):
        for say in (0, 5):
            eps = [r for r in run["records"]
                   if r["t_say"] == say and r["t_do"] == do]
            if not eps:
                continue
            agg = defaultdict(float)
            for e in eps:
                for k, v in classify(e).items():
                    agg[k] += v
            n = len(eps)
            row = {k: agg[k] / n for k in ("search", "repeat", "locating")}
            row["total"] = sum(row.values())
            table[(do, say)] = row
            print(f"{do:>8}{say:>8}{row['search']:>9.2f}{row['repeat']:>9.2f}"
                  f"{row['locating']:>10.2f}{row['total']:>8.2f}")

    print("\nWhat stating a price of 5 removes, by type\n")
    print(f"{'charged':>8}{'search':>12}{'repeat':>12}{'locating':>12}"
          f"{'  selective?':>14}")
    for do in (0, 2, 5):
        a, b = table.get((do, 0)), table.get((do, 5))
        if not a or not b:
            continue
        d = {k: b[k] - a[k] for k in ("search", "repeat", "locating")}
        # share of each type removed, so types with different bases compare
        pct = {k: (100 * -d[k] / a[k]) if a[k] > 0.05 else float("nan")
               for k in d}
        verdict = ("repeat cut harder" if pct["repeat"] > pct["search"] + 5
                   else "search cut harder" if pct["search"] > pct["repeat"] + 5
                   else "roughly uniform")
        print(f"{do:>8}{pct['search']:>11.0f}%{pct['repeat']:>11.0f}%"
              f"{pct['locating']:>11.0f}%{verdict:>16}")

    print("\nSelective reduction sheds low-value observations preferentially.")
    print("Uniform reduction is consistent with compliance rather than pricing.")


if __name__ == "__main__":
    main()
