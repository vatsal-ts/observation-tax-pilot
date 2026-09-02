"""Par computed under the agent's actual information, not more.

`blind_par.py` swept only the roaming zone (table, sink, basin). The prompt
never tells the agent the cup is confined there; it lists all five places. So
that par knew something the agent did not, and the headroom it implied was too
large.

Two further corrections here:

  * the sweep covers all five places, as the agent must;
  * par is the MEAN over sweep orders, not the minimum. A blind agent cannot
    know which order happens to be lucky, so taking the best order would again
    grant knowledge it lacks. The min is reported alongside only as a bound.

This is also the single source of par for every other script. `effect_size.py`
carried its own hardcoded `PAR = {0: 1.94, 2: 1.94, 5: 8.01}`, which is the
superseded range-privileged par, so it kept printing the 1.72 headroom that
R12 had already retracted. Numbers that are recorded as corrected in one place
and still hardcoded in another are how a retracted claim comes back.
"""

from __future__ import annotations

import itertools
import statistics
from functools import lru_cache

from blind_par import play, make

ALL_PLACES = ("table", "sink", "basin", "counter", "shelf")
COSTS = (0, 2, 5)
N_SEEDS = 120


@lru_cache(maxsize=None)
def par(cost: int, n_seeds: int = N_SEEDS) -> tuple[float, float] | None:
    """(mean over all sweep orders, best single order) for one charged price.

    None when no order in the policy class solves at least 90% of seeds, which
    is the honest answer when the task is not reliably winnable at that price.
    """
    per_order = []
    approach = "walk-then-look" if cost >= 5 else "commit-on-sight"
    for order in itertools.permutations(ALL_PLACES):
        obs, ok = [], 0
        for seed in range(n_seeds):
            n, s = play(make(cost, seed), order, approach)
            if s:
                ok += 1
                obs.append(n)
        if ok >= 0.9 * n_seeds:
            per_order.append(statistics.mean(obs))
    if not per_order:
        return None
    return statistics.mean(per_order), min(per_order)


def agent_means() -> dict[int, tuple[float, float]]:
    """Measured (say0, say5) observation means, read from the run itself.

    These were a hardcoded dict copied out of an earlier analysis run. Reading
    them keeps par and the agent numbers describing the same episodes.
    """
    import statistics as st

    from runs_io import pick
    run = pick("plain", "random", "dynamic-target", n_cells=9)
    out = {}
    for do in COSTS:
        row = []
        for say in (0, 5):
            eps = [r["n_obs"] for r in run["records"]
                   if r["t_say"] == say and r["t_do"] == do]
            row.append(st.mean(eps) if eps else float("nan"))
        out[do] = tuple(row)
    return out


def main() -> None:
    n_orders = len(list(itertools.permutations(ALL_PLACES)))
    print(f"\nSweeping all {len(ALL_PLACES)} places, {n_orders} orders, "
          f"{N_SEEDS} seeds, approach = commit-on-sight / walk-then-look\n")

    agent = agent_means()
    print(f"{'charged':>8}{'par (mean over orders)':>24}{'best order':>13}"
          f"{'agent say0':>12}{'headroom':>10}")
    for t in COSTS:
        p = par(t)
        if p is None:
            print(f"{t:>8}{'no policy solves >=90%':>24}")
            continue
        fair, best = p
        a0 = agent[t][0]
        print(f"{t:>8}{fair:>24.2f}{best:>13.2f}{a0:>12.2f}{a0 - fair:>10.2f}")

    print("\nPar as the mean over orders is what a blind agent can expect.")
    print("The best order is unattainable without knowing the cup's range.")


if __name__ == "__main__":
    main()
