"""Feasibility map: which (observation cost, relocation period) cells are winnable.

The proposal claims the T=0 competence check guards a ceiling but nothing
guards the floor, and that the cost must therefore be swept jointly with the
relocation period. This measures that floor.

For each cell we ask a blind player, over many seeded scenes, whether it can
get the mover in hand at all, and what the best achievable belief age at the
moment of commitment is. A cell where the par-setter mostly fails is out of
bounds: an agent failing there tells you nothing, because nobody can win.
"""

from __future__ import annotations

import sys

from oracle import par_staleness
from world import RandomSchedule, PeriodicSchedule, WorldConfig

PLACES = ("table", "counter", "shelf", "sink", "cabinet")
COSTS = (0, 1, 2, 3, 5, 8)
PERIODS = (2, 4, 6, 8, 12, 20)
N_SEEDS = 24


def cfg(t_do: int, period: int, seed: int, periodic: bool = False) -> WorldConfig:
    if periodic:
        sched = PeriodicSchedule(order=("table", "sink", "cabinet"), period=period)
    else:
        sched = RandomSchedule(places=PLACES, period=period, seed=seed)
    return WorldConfig(
        places=PLACES,
        statics={"bowl": "counter", "book": "shelf", "pan": "sink"},
        mover="cup",
        schedule=sched,
        t_do=t_do,
        t_say=t_do,
        start="table",
    )


def cell(t_do: int, period: int, periodic: bool = False) -> tuple[float, float | None]:
    """Returns (fraction of scenes the par-setter can win, median par staleness)."""
    stalenesses = []
    wins = 0
    for seed in range(N_SEEDS):
        s = par_staleness(cfg(t_do, period, seed, periodic))
        if s is not None:
            wins += 1
            stalenesses.append(s)
    med = sorted(stalenesses)[len(stalenesses) // 2] if stalenesses else None
    return wins / N_SEEDS, med


def main() -> None:
    for periodic in (False, True):
        label = "periodic" if periodic else "unpredictable"
        print(f"\n=== schedule: {label} ===")
        print("par-setter win rate (and median par staleness)\n")
        print("cost \\ period " + "".join(f"{p:>12}" for p in PERIODS))
        for t in COSTS:
            row = f"T={t:<11}"
            for p in PERIODS:
                rate, med = cell(t, p, periodic)
                cellstr = f"{rate:.2f}" + (f"/{med}" if med is not None else "/-")
                row += f"{cellstr:>12}"
            print(row)
        print("\nA cell is usable only where the win rate is high. Where it is")
        print("low, failure is a floor artifact and says nothing about an agent.")


if __name__ == "__main__":
    main()
