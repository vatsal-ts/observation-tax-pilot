"""The measurement demonstration.

Claim under test, from the proposal: rho_s (the share of observations that did
not land on the mover) rises with observation cost *for arithmetic reasons*,
and therefore cannot be read as evidence that an agent reallocated attention.

The way to prove that without an LLM is to use policies whose behaviour is
fixed in code. If the policy cannot change and the number moves anyway, the
number is an artifact.

Second claim: distance from par does not have this defect. A policy that
refreshes right before committing sits at par at every cost; one that commits
on an old sighting does not, and the gap widens.

Run: python pilot/run_pilot.py
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from world import RandomSchedule, World, WorldConfig

# Two zones. The mover is only ever in the roaming zone; the target place sits
# in the fixed zone. Without that split the mover can wander onto the target by
# itself and the referee scores a success the agent did not earn. That is not a
# hypothetical: an earlier run of this file reported 25% success with zero
# successful picks.
ROAMING = ("table", "sink", "basin")
FIXED = ("counter", "shelf")
PLACES = ROAMING + FIXED
STATICS = {"bowl": "counter", "book": "shelf"}
MOVER = "cup"
TARGET = "shelf"
PERIOD = 8          # chosen from feasibility.py: period > T for every cost used
COSTS = (0, 2, 5)
N_EPISODES = 300


def make(t_do: int, seed: int) -> World:
    return World(
        WorldConfig(
            places=PLACES,
            statics=dict(STATICS),
            mover=MOVER,
            schedule=RandomSchedule(places=ROAMING, period=PERIOD, seed=seed),
            t_do=t_do,
            t_say=t_do,
            start="table",
            max_ticks=5000,
        )
    )


@dataclass
class Episode:
    n_obs: int
    n_obs_without_mover: int
    staleness: int | None      # ticks between grounding sighting and the pick
    success: bool

    @property
    def rho_s(self) -> float | None:
        if self.n_obs == 0:
            return None
        return self.n_obs_without_mover / self.n_obs


# --------------------------------------------------------------- policies
#
# Both are fixed code. Neither reads t_do. Neither changes with cost.


def policy_diligent(w: World, order: list[str]) -> Episode:
    """Sweep places until the mover is seen, then stand there, look again, pick.

    The second look is the refresh: it re-grounds the belief immediately
    before committing, which is what a careful player does.
    """
    n_obs = n_miss = 0
    staleness = None
    for _ in range(40):
        if w.finished:
            break
        for place in order:
            if w.finished:
                break
            res = w.step(("observe", place))
            n_obs += 1
            if MOVER not in getattr(res, "objects", ()):
                n_miss += 1
                continue
            w.step(("goto", place))
            seen = w.tick
            res2 = w.step(("observe", place))     # refresh in place
            n_obs += 1
            if MOVER not in getattr(res2, "objects", ()):
                n_miss += 1
                continue
            seen = res2.tick
            t_pick = w.tick
            got = w.step(("pick", MOVER))
            if getattr(got, 'ok', False):
                staleness = t_pick - seen
                w.step(("goto", TARGET))
                w.step(("place", MOVER, TARGET))
                return Episode(n_obs, n_miss, staleness, w.succeeded(MOVER, TARGET))
        if staleness is not None:
            break
    return Episode(n_obs, n_miss, staleness, w.succeeded(MOVER, TARGET))


def policy_thrifty(w: World, order: list[str]) -> Episode:
    """Sweep until the mover is seen, then commit on that sighting.

    No refresh. This is the economy the proposal predicts a cost-pressured
    agent will take: act on what you already have rather than pay to look
    again.
    """
    n_obs = n_miss = 0
    staleness = None
    for _ in range(40):
        if w.finished:
            break
        for place in order:
            if w.finished:
                break
            res = w.step(("observe", place))
            n_obs += 1
            if MOVER not in getattr(res, "objects", ()):
                n_miss += 1
                continue
            seen = res.tick
            w.step(("goto", place))
            t_pick = w.tick
            got = w.step(("pick", MOVER))
            if getattr(got, 'ok', False):
                staleness = t_pick - seen
                w.step(("goto", TARGET))
                w.step(("place", MOVER, TARGET))
                return Episode(n_obs, n_miss, staleness, w.succeeded(MOVER, TARGET))
        if staleness is not None:
            break
    return Episode(n_obs, n_miss, staleness, w.succeeded(MOVER, TARGET))


POLICIES = {"diligent": policy_diligent, "thrifty": policy_thrifty}


def run(policy_name: str, t_do: int) -> list[Episode]:
    fn = POLICIES[policy_name]
    out = []
    for seed in range(N_EPISODES):
        w = make(t_do, seed)
        order = list(ROAMING)             # fixed sweep order, identical at every cost
        out.append(fn(w, order))
    return out


def summarise(eps: list[Episode]) -> dict:
    rhos = [e.rho_s for e in eps if e.rho_s is not None]
    stales = [e.staleness for e in eps if e.staleness is not None]
    return {
        "n": len(eps),
        "success": sum(e.success for e in eps) / len(eps),
        "mean_obs": statistics.mean(e.n_obs for e in eps),
        "rho_s": statistics.mean(rhos) if rhos else float("nan"),
        "staleness": statistics.mean(stales) if stales else float("nan"),
        "n_committed": len(stales),
    }


def main() -> None:
    print(f"\nRoom: {len(PLACES)} places, 3 fixtures, 1 mover, relocation period {PERIOD}")
    print(f"{N_EPISODES} episodes per cell, fixed seeds, unpredictable schedule.")
    print("Both policies are fixed code. Neither reads the observation cost.\n")

    print("=" * 74)
    print("A. rho_s, the share of observations that did not find the mover")
    print("=" * 74)
    print(f"{'policy':<12}{'cost':>6}{'rho_s':>10}{'mean obs':>11}{'success':>10}")
    for name in POLICIES:
        for t in COSTS:
            s = summarise(run(name, t))
            print(f"{name:<12}{t:>6}{s['rho_s']:>10.3f}{s['mean_obs']:>11.2f}"
                  f"{s['success']:>10.2f}")
    print("\nThe policy code is identical across the three rows of each block.")
    print("Any movement in rho_s is therefore not a change in behaviour.\n")

    print("=" * 74)
    print("B. staleness at commitment, raw and against par")
    print("=" * 74)
    print(f"{'policy':<12}{'cost':>6}{'par':>6}{'raw':>10}{'excess':>10}{'committed':>11}")
    for name in POLICIES:
        for t in COSTS:
            s = summarise(run(name, t))
            par = t                     # measured by oracle.par_staleness for period > T
            excess = s["staleness"] - par
            print(f"{name:<12}{t:>6}{par:>6}{s['staleness']:>10.2f}{excess:>10.2f}"
                  f"{s['n_committed']:>11}")
    print("\nRaw staleness rises with cost for both policies, including the one")
    print("that plays at par. Excess over par separates them.\n")


if __name__ == "__main__":
    main()
