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
"""

from __future__ import annotations

import itertools
import statistics

from blind_par import play, make

ALL_PLACES = ("table", "sink", "basin", "counter", "shelf")
COSTS = (0, 2, 5)
N_SEEDS = 120

# measured agent means, plain / random / dynamic grid
AGENT = {0: (3.66, 3.32), 2: (8.69, 6.96), 5: (23.74, 16.36)}


def main() -> None:
    orders = list(itertools.permutations(ALL_PLACES))
    print(f"\nSweeping all {len(ALL_PLACES)} places, {len(orders)} orders, "
          f"{N_SEEDS} seeds, approach = commit-on-sight / walk-then-look\n")

    print(f"{'charged':>8}{'par (mean over orders)':>24}{'best order':>13}"
          f"{'agent say0':>12}{'headroom':>10}")
    for t in COSTS:
        per_order = []
        for order in orders:
            ap = "walk-then-look" if t >= 5 else "commit-on-sight"
            obs, ok = [], 0
            for seed in range(N_SEEDS):
                n, s = play(make(t, seed), order, ap)
                if s:
                    ok += 1
                    obs.append(n)
            if ok >= 0.9 * N_SEEDS:
                per_order.append(statistics.mean(obs))
        if not per_order:
            print(f"{t:>8}{'no policy solves >=90%':>24}")
            continue
        fair = statistics.mean(per_order)
        best = min(per_order)
        a0 = AGENT[t][0]
        print(f"{t:>8}{fair:>24.2f}{best:>13.2f}{a0:>12.2f}{a0 - fair:>10.2f}")

    print("\nPar as the mean over orders is what a blind agent can expect.")
    print("The best order is unattainable without knowing the cup's range.")


if __name__ == "__main__":
    main()
