"""Channel audit: prove that only `observe` reveals object locations.

This is the precondition for the whole project. If any other action leaks
where things are, the agent gets free observations, the observation cost
stops binding, and no downstream number means anything.

Six independent checks, because one is easy to fool:

  A. Structural.   Only ObserveResult carries an `objects` field.
  B. Invariance.   For goto / place / done / malformed actions, the exact
                   bytes the agent sees are identical across worlds that
                   differ only in where objects are.
  C. Pick channel. `pick` may reveal one bit, whether the named object is
                   here. It must reveal nothing more: responses grouped by
                   that bit must each collapse to a single distinct string.
  D. Clock.        Tick counts after a fixed action sequence are identical
                   across those same worlds, so the clock is not a side
                   channel either.
  E. Staleness.    An observation reports the scene before its cost is charged.
  F. Consistency.  observe, pick and the referee resolve against the SAME
                   clock, the rendered clock is monotone, and a deadline is
                   never overshot. A. to E. exercise only the default
                   configuration, where the latency and drift clocks coincide;
                   this section sets them apart, which is the only setting in
                   which they can disagree.

Run: python pilot/test_channel_audit.py
"""

from __future__ import annotations

import dataclasses
import itertools
import random
import sys

from world import (
    DoneResult,
    ErrorResult,
    MoveResult,
    ObserveResult,
    PickResult,
    PlaceResult,
    PeriodicSchedule,
    RandomSchedule,
    World,
    WorldConfig,
)

PLACES = ("table", "counter", "shelf", "sink", "cabinet")
STATIC_NAMES = ("bowl", "book", "pan")
MOVER = "cup"

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def build_world(seed: int, t_do: int = 5, periodic: bool = False) -> World:
    """A world whose object placement is entirely determined by `seed`."""
    rng = random.Random(seed)
    statics = {name: rng.choice(PLACES) for name in STATIC_NAMES}
    if periodic:
        order = tuple(rng.sample(PLACES, 3))
        schedule = PeriodicSchedule(order=order, period=3)
    else:
        schedule = RandomSchedule(places=PLACES, period=3, seed=seed)
    cfg = WorldConfig(
        places=PLACES,
        statics=statics,
        mover=MOVER,
        schedule=schedule,
        t_do=t_do,
        t_say=t_do,
        start="table",
    )
    return World(cfg)


# --------------------------------------------------------------- A. structural

print("\nA. Structural: only ObserveResult exposes object identity")

observe_fields = {f.name for f in dataclasses.fields(ObserveResult)}
check("ObserveResult has an `objects` field", "objects" in observe_fields)

leaky = []
for rt in (MoveResult, PickResult, PlaceResult, ErrorResult, DoneResult):
    names = {f.name for f in dataclasses.fields(rt)}
    if "objects" in names or "location" in names:
        leaky.append(rt.__name__)
check("no other result type carries objects/location", not leaky, str(leaky))


# --------------------------------------------------------------- B. invariance

print("\nB. Invariance: non-observe responses do not vary with object placement")

# The same action script, run against many differently-populated worlds.
SCRIPT = [
    ("goto", "counter"),
    ("goto", "shelf"),
    ("place", "bowl", "shelf"),   # fails, agent holds nothing
    ("goto", "sink"),
    ("frobnicate",),              # malformed
    ("goto", "nowhere"),          # invalid place
    ("goto", "cabinet"),
    ("done",),
]

transcripts = set()
tick_traces = set()
for seed in range(60):
    w = build_world(seed)
    rendered, ticks = [], []
    for act in SCRIPT:
        r = w.step(act)
        rendered.append(r.render())
        ticks.append(w.tick)
    transcripts.add(tuple(rendered))
    tick_traces.add(tuple(ticks))

check(
    "60 differently-populated worlds give one identical transcript",
    len(transcripts) == 1,
    f"distinct transcripts = {len(transcripts)}",
)


# ------------------------------------------------------------- C. pick channel

print("\nC. Pick reveals at most one bit (is the object here)")

# `pick` legitimately echoes the object name the agent itself supplied, so the
# property is not "all picks render identically". It is: for a FIXED object
# name, the response is a function of the co-location bit and nothing else.
# Grouping by bit alone would fail merely because "You are holding cup" and
# "You are holding pan" differ, which carries no information the agent lacked.
by_obj_bit: dict[tuple[str, bool], set[str]] = {}
for seed in range(400):
    for place in PLACES:
        for obj in STATIC_NAMES + (MOVER,):
            probe = build_world(seed)
            probe.step(("goto", place))
            truth = probe.truth_location(obj, probe.tick) == place
            res = probe.step(("pick", obj))
            by_obj_bit.setdefault((obj, truth), set()).add(res.render())

worst = max(len(v) for v in by_obj_bit.values())
check(
    "per (object, co-located) group, one distinct response",
    worst == 1,
    f"largest group = {worst} distinct strings over {len(by_obj_bit)} groups",
)

# Strictly stronger than the old check: no pick response may name any place,
# nor any object other than the one the agent asked for.
named_place = [s for v in by_obj_bit.values() for s in v if any(p in s for p in PLACES)]
check("no pick response names any place", not named_place, str(named_place[:2]))

wrong_obj = [
    s
    for (obj, _), v in by_obj_bit.items()
    for s in v
    if any(o in s for o in STATIC_NAMES + (MOVER,) if o != obj)
]
check("no pick response names another object", not wrong_obj, str(wrong_obj[:2]))


# -------------------------------------------------------------------- D. clock

print("\nD. Clock: tick counts do not depend on object placement")

check(
    "60 worlds give one identical tick trace",
    len(tick_traces) == 1,
    f"distinct traces = {len(tick_traces)}",
)

# Success and failure of the same verb must cost the same.
w_hit = build_world(0)
w_hit.step(("goto", w_hit.truth_location(MOVER, w_hit.tick)))
t0 = w_hit.tick
w_hit.step(("pick", MOVER))
cost_hit = w_hit.tick - t0

w_miss = build_world(0)
elsewhere = [p for p in PLACES if p != w_miss.truth_location(MOVER, w_miss.tick)][0]
w_miss.step(("goto", elsewhere))
t1 = w_miss.tick
w_miss.step(("pick", MOVER))
cost_miss = w_miss.tick - t1

check("successful and failed pick cost the same", cost_hit == cost_miss,
      f"{cost_hit} vs {cost_miss}")


# --------------------------------------------------------- E. observe is stale

print("\nE. Sanity: observe reports the tick it was made, then charges T")

w = build_world(7, t_do=5)
r = w.step(("observe", "table"))
check("observation is timestamped before the cost is charged",
      isinstance(r, ObserveResult) and r.tick == 0 and w.tick == 5,
      f"obs.tick={r.tick} clock={w.tick}")



# --------------------------------------------------- F. clock consistency

print("\nF. Clocks: observe, pick and the referee must agree")

# build_world leaves t_drift at None, where drift and tick are identical by
# construction, so no check above can detect a verb resolving against the wrong
# one. This section sets the two clocks apart, where they can disagree.
def split_world(seed: int, t_do: int, t_drift: int) -> World:
    rng = random.Random(seed)
    statics = {name: rng.choice(PLACES) for name in STATIC_NAMES}
    cfg = WorldConfig(
        places=PLACES, statics=statics, mover=MOVER,
        schedule=RandomSchedule(places=PLACES, period=3, seed=seed),
        t_do=t_do, t_say=t_do, t_drift=t_drift, start="table", max_ticks=9999,
    )
    return World(cfg)

mismatch = 0
for seed in range(60):
    w = split_world(seed, t_do=5, t_drift=0)
    for place in PLACES:
        res = w.step(("observe", place))
        if MOVER in res.objects:
            w.step(("goto", place))
            if not w.step(("pick", MOVER)).ok:
                mismatch += 1
            break
check("observe and pick agree when drift is split from cost", mismatch == 0,
      f"{mismatch}/60 seeds where observe found the mover but pick failed")

# the agent must see one monotone clock, whatever the split
w = split_world(0, t_do=5, t_drift=0)
shown = [w.step(("observe", "table")).tick for _ in range(3)]
shown.append(w.step(("goto", "sink")).tick)
check("the rendered clock is monotone under a split", shown == sorted(shown),
      str(shown))

# a deadline must not be overshot by an action the agent cannot afford
w2 = World(WorldConfig(places=PLACES, statics={"bowl": "counter"}, mover=MOVER,
                       schedule=RandomSchedule(places=PLACES, period=3, seed=1),
                       t_do=5, t_say=5, start="table", max_ticks=9999,
                       deadline=12))
for _ in range(6):
    w2.step(("observe", "table"))
check("a deadline is never overshot", w2.tick <= 12, f"tick={w2.tick} deadline=12")

# -------------------------------------------------------------------- verdict

print()
if failures:
    print(f"CHANNEL AUDIT FAILED: {len(failures)} check(s): {failures}")
    sys.exit(1)
print("CHANNEL AUDIT PASSED. Only `observe` reveals object locations.")
