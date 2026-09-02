"""Is the stated-price effect at charged 0 real, and is it small because there
is nothing left to cut?

Two questions the raw means cannot answer.

1. With blind par at 1.94 and the agent at 3.66, there ARE 1.72 observations of
   headroom at charged 0. So "no room to economise" is not automatically true.
   The right normaliser is the reduction achieved as a share of the reduction
   available, which controls for the floor exactly.

2. Is -0.34 distinguishable from zero at all? Reported as a bootstrap CI and a
   Welch t-test on the per-episode counts, not on the means.
"""

from __future__ import annotations

import random
import statistics
from collections import defaultdict

from runs_io import load_runs

PAR = {0: 1.94, 2: 1.94, 5: 8.01}


def load_plain_moving() -> dict:
    """Per-episode observation counts for the plain / random / dynamic grid."""
    for run in load_runs():
        if (run['style'], run['sched'], run['family']) == ('plain', 'random', 'dynamic-target'):
            print(f"using {run['file']}")
            cells = defaultdict(list)
            for r in run['records']:
                cells[(r['t_say'], r['t_do'])].append(r['n_obs'])
            return cells
    return {}


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
    print("=" * 74)
    print(f"{'charged':>8}{'par':>7}{'say0':>8}{'say5':>8}{'cut':>8}"
          f"{'headroom':>10}{'cut/headroom':>14}{'95% CI':>18}")
    for do in (0, 2, 5):
        a, b = cells[(0, do)], cells[(5, do)]
        if not a or not b:
            continue
        ma, mb = statistics.mean(a), statistics.mean(b)
        cut = ma - mb
        head = ma - PAR[do]
        lo, hi = boot_ci(a, b)
        print(f"{do:>8}{PAR[do]:>7.2f}{ma:>8.2f}{mb:>8.2f}{cut:>8.2f}"
              f"{head:>10.2f}{100*cut/head:>13.0f}%"
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
