"""Blind par: the fewest observations a player can average without being told
where the mover is.

`oracle.par_staleness` searches action sequences against the true world, so it
implicitly knows where the cup is and walks straight there. That is an
*informed* par and it flatters nobody but itself. The agent is blind and has to
search, so the honest benchmark is the best a blind player can average.

Par here is the best mean over a class of blind policies, evaluated on the same
seeds the agent saw. It is therefore an upper bound on the true optimum: a
cleverer blind policy could do better, which would make the agent's excess
larger, not smaller. Reported as such.

Policy class:
  order      x  one of the 6 sweep orders over the roaming zone
  approach   x  {commit-on-sight, walk-then-look, refresh-in-place}

Run: python blind_par.py
"""

from __future__ import annotations

import itertools
import statistics

from world import RandomSchedule, World, WorldConfig

ROAMING = ("table", "sink", "basin")
FIXED = ("counter", "shelf")
PLACES = ROAMING + FIXED
STATICS = {"bowl": "counter", "book": "shelf"}
MOVER, TARGET, PERIOD = "cup", "shelf", 8
COSTS = (0, 2, 5)
N_SEEDS = 200
MAX_OBS = 120


def make(t_do: int, seed: int) -> World:
    return World(WorldConfig(
        places=PLACES, statics=dict(STATICS), mover=MOVER,
        schedule=RandomSchedule(places=ROAMING, period=PERIOD, seed=seed),
        t_do=t_do, t_say=t_do, start="table", max_ticks=4000))


def play(w: World, order, approach) -> tuple[int, bool]:
    """Returns (observations used, success). All three approaches are blind:
    none consults the schedule or the true position."""
    n_obs = 0
    while n_obs < MAX_OBS and not w.finished:
        for place in order:
            if w.finished or n_obs >= MAX_OBS:
                break

            if approach == "walk-then-look":
                # stand where you intend to pick, then look, then pick
                w.step(("goto", place))
                res = w.step(("observe", place)); n_obs += 1
                if MOVER in getattr(res, "objects", ()):
                    if getattr(w.step(("pick", MOVER)), "ok", False):
                        w.step(("place", MOVER, TARGET))
                        return n_obs, w.succeeded(MOVER, TARGET)
                continue

            res = w.step(("observe", place)); n_obs += 1
            if MOVER not in getattr(res, "objects", ()):
                continue
            w.step(("goto", place))

            if approach == "refresh-in-place":
                res2 = w.step(("observe", place)); n_obs += 1
                if MOVER not in getattr(res2, "objects", ()):
                    continue

            if getattr(w.step(("pick", MOVER)), "ok", False):
                w.step(("place", MOVER, TARGET))
                return n_obs, w.succeeded(MOVER, TARGET)
    return n_obs, w.succeeded(MOVER, TARGET)


def main() -> None:
    approaches = ("commit-on-sight", "walk-then-look", "refresh-in-place")
    print(f"\nBlind par over {N_SEEDS} seeds, period {PERIOD}, "
          f"{len(list(itertools.permutations(ROAMING)))} sweep orders x "
          f"{len(approaches)} approaches\n")

    par = {}
    for t in COSTS:
        best = None
        for order in itertools.permutations(ROAMING):
            for ap in approaches:
                obs, succ = [], 0
                for seed in range(N_SEEDS):
                    n, ok = play(make(t, seed), order, ap)
                    if ok:
                        succ += 1
                        obs.append(n)
                if succ < 0.9 * N_SEEDS:      # must actually solve the task
                    continue
                m = statistics.mean(obs)
                if best is None or m < best[0]:
                    best = (m, succ / N_SEEDS, ap, order)
        par[t] = best
        if best:
            print(f"  charged {t}:  par = {best[0]:5.2f} observations   "
                  f"(success {best[1]:.2f}, via {best[2]}, order {best[3][0][:2]}..)")
        else:
            print(f"  charged {t}:  no blind policy in the class solves >=90%")

    # the agent's measured means, from RESULTS.md R6
    agent = {(0, 0): 3.66, (0, 2): 8.69, (0, 5): 23.74,
             (5, 0): 3.32, (5, 2): 6.96, (5, 5): 16.36}

    print("\nAgent against blind par (observations per episode)\n")
    print(f"  {'charged':>8}{'par':>8}{'agent say=0':>13}{'excess':>9}"
          f"{'agent say=5':>13}{'excess':>9}")
    for t in COSTS:
        if not par[t]:
            continue
        p = par[t][0]
        a0, a5 = agent[(0, t)], agent[(5, t)]
        print(f"  {t:>8}{p:>8.2f}{a0:>13.2f}{a0 - p:>+9.2f}"
              f"{a5:>13.2f}{a5 - p:>+9.2f}")

    print("\nPar is the best mean in the policy class, so it is an upper bound")
    print("on the true blind optimum. A better blind policy would only widen")
    print("the agent's excess.")


if __name__ == "__main__":
    main()
