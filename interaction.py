"""Does stating a price do something different when the price is charged?

The 3x3 sweep answered this by eye, comparing the say-0-vs-say-5 gap at one
charged level against the gap at another. Two contrasts whose intervals overlap
say nothing about their difference, and at 50 episodes per cell they overlapped
badly: the difference was -7.04 with an interval of [-14.50, +0.46], which
includes zero. So the sweep never established the interaction it was read as
establishing.

This tests the interaction itself, on the 2x2 run built for it at 200 episodes
per cell:

    (say5,charged5 - say0,charged5) - (say5,charged0 - say0,charged0)

with a nonparametric bootstrap resampling episodes within each of the four
cells, which is the design's actual unit of randomisation.

The number this file exists to make reproducible was previously computed by
hand and appears nowhere in the code. It is now the only place it comes from.

Run: python interaction.py
"""

from __future__ import annotations

import random
import statistics

from runs_io import pick

N_BOOT = 20000


def cells(run, metric):
    """(t_say, t_do) -> list of per-episode values."""
    out = {}
    for r in run["records"]:
        out.setdefault((r["t_say"], r["t_do"]), []).append(float(metric(r)))
    return out


def interaction(c, hi_do=5, lo_do=0, hi_say=5, lo_say=0):
    def m(say, do):
        return statistics.mean(c[(say, do)])
    return ((m(hi_say, hi_do) - m(lo_say, hi_do))
            - (m(hi_say, lo_do) - m(lo_say, lo_do)))


def boot(c, seed=0, n=N_BOOT):
    rng = random.Random(seed)
    vals = []
    keys = list(c)
    for _ in range(n):
        draw = {k: [c[k][rng.randrange(len(c[k]))] for _ in range(len(c[k]))]
                for k in keys}
        vals.append(interaction(draw))
    vals.sort()
    return vals[int(0.025 * n)], vals[int(0.975 * n)]


def report(label, run, metric, unit=""):
    c = cells(run, metric)
    need = {(0, 0), (0, 5), (5, 0), (5, 5)}
    missing = need - set(c)
    if missing:
        print(f"  {label}: missing cells {sorted(missing)}")
        return
    point = interaction(c)
    lo, hi = boot(c)
    excl = (lo > 0) == (hi > 0)
    print(f"  {label:>14}: {point:+.2f}{unit}  95% CI [{lo:+.2f}, {hi:+.2f}]"
          f"  {'excludes zero' if excl else 'INCLUDES ZERO'}")
    print(f"{'':>18}cells "
          + "  ".join(f"say{s}/do{d}={statistics.mean(c[(s, d)]):.2f}"
                      f"(n={len(c[(s, d)])})"
                      for s, d in ((0, 0), (5, 0), (0, 5), (5, 5))))


def main() -> None:
    run = pick("plain", "random", "dynamic-target", n_cells=4, verbose=True)
    print(f"\nusing {run['file']}  ({len(run['records'])} episodes)\n")
    print("Interaction of STATED price with CHARGED price")
    print("=" * 74)
    report("observations", run, lambda r: r["n_obs"])
    report("success", run, lambda r: r["success"])
    report("turns", run, lambda r: r["turns"])

    print("\nFor comparison, the same interaction on the 50-per-cell sweep,")
    print("which is where this was first read off by eye:")
    try:
        sweep = pick("plain", "random", "dynamic-target", n_cells=9)
        report("observations", sweep, lambda r: r["n_obs"])
    except LookupError as e:
        print(f"  {e}")

    print("\nA nonzero interaction means the stated price does something")
    print("different depending on the charged one, so neither can be reported")
    print("as a main effect on its own.")


if __name__ == "__main__":
    main()
