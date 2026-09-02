"""Is the stated-price effect at charged 0 real, and is it small because there
is nothing left to cut?

Two questions the raw means cannot answer.

1. Headroom. If par sits close to the agent's count there is little to cut and
   a small effect means nothing. The normaliser is the reduction achieved as a
   share of the reduction available. Par comes from `fair_par.par`, computed
   under the agent's own information. This file used to hardcode
   `PAR = {0: 1.94, 2: 1.94, 5: 8.01}`, the superseded par that swept only the
   cup's roaming zone, and so kept printing a headroom of 1.72 at charged 0
   long after R12 corrected it to 0.66. The real headroom is small, which
   weakens rather than supports the claim this script was written to defend.

2. Is the effect distinguishable from zero at all? Reported as a bootstrap CI
   and a Welch t-test on the per-episode counts, not on the means.
"""

from __future__ import annotations

import random
import statistics
from collections import defaultdict

from fair_par import par
from runs_io import pick


def load_plain_moving() -> dict:
    """Per-episode observation counts for the plain / random / dynamic grid.

    This looped over `load_runs()` and took the first match, so it silently
    accepted whichever of the 9-cell sweep and the 4-cell powered run happened
    to come first. `pick` demands the cell count and fails loudly otherwise.
    """
    run = pick("plain", "random", "dynamic-target", n_cells=9)
    print(f"using {run['file']}")
    cells = defaultdict(list)
    for r in run["records"]:
        cells[(r["t_say"], r["t_do"])].append(r["n_obs"])
    return cells


def boot_ci(a, b, n=20000, seed=0):
    """bootstrap CI on mean(b) - mean(a)"""
    rng = random.Random(seed)
    diffs = []
    for _ in range(n):
        ra = [a[rng.randrange(len(a))] for _ in range(len(a))]
        rb = [b[rng.randrange(len(b))] for _ in range(len(b))]
        diffs.append(statistics.mean(rb) - statistics.mean(ra))
    diffs.sort()
    return diffs[int(0.025 * n)], diffs[int(0.975 * n)]


def welch(a, b):
    ma, mb = statistics.mean(a), statistics.mean(b)
    va, vb = statistics.variance(a), statistics.variance(b)
    se = (va / len(a) + vb / len(b)) ** 0.5
    return (mb - ma) / se if se else float("nan")


def main() -> None:
    cells = load_plain_moving()
    if not cells:
        print("no plain/random/dynamic grid found")
        return

    print("\nEffect of stating 5 rather than 0, per charged price")
    print("(par from fair_par, computed under the agent's own information)")
    print("=" * 74)
    print(f"{'charged':>8}{'par':>7}{'say0':>8}{'say5':>8}{'cut':>8}"
          f"{'headroom':>10}{'cut/headroom':>14}{'95% CI':>18}")
    for do in (0, 2, 5):
        a, b = cells[(0, do)], cells[(5, do)]
        if not a or not b:
            continue
        ma, mb = statistics.mean(a), statistics.mean(b)
        cut = ma - mb
        p = par(do)
        lo, hi = boot_ci(a, b)
        if p is None:
            print(f"{do:>8}{'n/a':>7}{ma:>8.2f}{mb:>8.2f}{cut:>8.2f}")
            continue
        head = ma - p[0]
        share = f"{100*cut/head:>13.0f}%" if head > 0.05 else f"{'n/a':>14}"
        print(f"{do:>8}{p[0]:>7.2f}{ma:>8.2f}{mb:>8.2f}{cut:>8.2f}"
              f"{head:>10.2f}{share}"
              f"{f'[{lo:+.2f},{hi:+.2f}]':>18}")

    print("\nIs the charged-0 effect distinguishable from zero?")
    print("=" * 74)
    a, b = cells[(0, 0)], cells[(5, 0)]
    lo, hi = boot_ci(a, b)
    t = welch(a, b)
    print(f"  n = {len(a)} vs {len(b)} episodes")
    print(f"  means {statistics.mean(a):.2f} vs {statistics.mean(b):.2f}, "
          f"sd {statistics.stdev(a):.2f} vs {statistics.stdev(b):.2f}")
    print(f"  difference {statistics.mean(b)-statistics.mean(a):+.2f}, "
          f"95% CI [{lo:+.2f}, {hi:+.2f}], Welch t = {t:.2f}")
    print("  CI excludes zero." if (lo > 0 or hi < 0) else
          "  CI INCLUDES zero: the effect is not distinguishable from none.")


if __name__ == "__main__":
    main()
