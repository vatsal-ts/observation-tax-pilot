"""Room simulator for the observation-tax pilot.

The one correctness property that matters: no action other than `observe`
may reveal anything about where objects are. `test_channel_audit.py` proves
it. If that test fails, the observation cost stops binding and no downstream
result means anything.

Semantics worth stating explicitly:

* `observe(place)` reports the scene as it is at the tick the call is made,
  and *then* advances the clock by T. So the information the agent receives
  is already T ticks stale by the time it can act on it. That staleness is
  the whole mechanic.
* Every action costs its ticks whether or not it succeeds. A failed `pick`
  costs the same as a successful one. Otherwise the tick counter itself
  becomes a side channel telling the agent whether the object was there.
* T_say (the cost named in the prompt) and T_do (the cost the world charges)
  are separate. Every existing efficiency result holds them equal.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------- schedules


class Schedule:
    """Where the moving object is at a given tick, before anyone picks it up."""

    def location_at(self, tick: int) -> str:
        raise NotImplementedError


@dataclass(frozen=True)
class PeriodicSchedule:
    """Cycles a fixed order of places, one hop every `period` ticks.

    Inferable in principle from two observations, which is why results are
    reported separately for this and for `RandomSchedule`.
    """

    order: tuple[str, ...]
    period: int

    def location_at(self, tick: int) -> str:
        return self.order[(tick // self.period) % len(self.order)]


@dataclass(frozen=True)
class RandomSchedule:
    """Seeded, but not inferable from any prefix.

    The hop sequence is drawn up front from `seed`, and consecutive places
    always differ, so every hop is a real move.
    """

    places: tuple[str, ...]
    period: int
    seed: int
    horizon_hops: int = 512
    _hops: tuple[str, ...] = field(default=(), compare=False)

    def __post_init__(self) -> None:
        rng = random.Random(self.seed)
        hops: list[str] = [rng.choice(self.places)]
        for _ in range(self.horizon_hops - 1):
            nxt = rng.choice([p for p in self.places if p != hops[-1]])
            hops.append(nxt)
        object.__setattr__(self, "_hops", tuple(hops))

    def location_at(self, tick: int) -> str:
        return self._hops[(tick // self.period) % len(self._hops)]


# ------------------------------------------------------------------- config


@dataclass(frozen=True)
class WorldConfig:
    places: tuple[str, ...]
    statics: dict[str, str]            # object name -> fixed place
    mover: str                         # name of the single moving object
    schedule: Schedule
    t_do: int                          # ticks of BUDGET an observe consumes
    t_say: int                         # ticks the prompt claims observe costs
    start: str                         # where the agent begins
    max_ticks: int = 200
    # t_do is latency: the world time an observation consumes. t_drift is how
    # far the mover's schedule advances during that observation. Held equal,
    # the two are indistinguishable, since nothing else here depends on time.
    # Setting them apart is what separates the cost of looking from the decay
    # of what it returns. Defaults to t_do.
    t_drift: int | None = None
    # A budget only bites if exceeding it can lose the episode.
    deadline: int | None = None

    def __post_init__(self) -> None:
        for obj, place in self.statics.items():
            assert place in self.places, f"static {obj} at unknown place {place}"
        assert self.start in self.places
        assert self.mover not in self.statics


# ------------------------------------------------------------------ results
#
# Only ObserveResult carries object information. The audit checks this
# structurally as well as behaviourally.


@dataclass(frozen=True)
class ObserveResult:
    place: str
    objects: tuple[str, ...]
    tick: int                # elapsed time, the clock the agent is shown
    resolved_at: int = -1    # drift clock the objects were resolved against

    def render(self) -> str:
        if self.objects:
            return f"[tick {self.tick}] At {self.place}: " + ", ".join(self.objects) + "."
        return f"[tick {self.tick}] At {self.place}: nothing."


@dataclass(frozen=True)
class MoveResult:
    place: str
    tick: int

    def render(self) -> str:
        return f"[tick {self.tick}] You are at {self.place}."


@dataclass(frozen=True)
class PickResult:
    ok: bool
    obj: str
    tick: int

    def render(self) -> str:
        if self.ok:
            return f"[tick {self.tick}] You are holding {self.obj}."
        return f"[tick {self.tick}] Nothing to pick up here."


@dataclass(frozen=True)
class PlaceResult:
    ok: bool
    obj: str
    place: str
    tick: int

    def render(self) -> str:
        if self.ok:
            return f"[tick {self.tick}] You put down {self.obj}."
        return f"[tick {self.tick}] You are not holding that."


@dataclass(frozen=True)
class ErrorResult:
    tick: int

    def render(self) -> str:
        return f"[tick {self.tick}] That is not a valid action."


@dataclass(frozen=True)
class DoneResult:
    tick: int

    def render(self) -> str:
        return f"[tick {self.tick}] Episode over."


# ------------------------------------------------------------------- world


class World:
    """The simulator. Agents may only reach it through `step`."""

    def __init__(self, cfg: WorldConfig) -> None:
        self.cfg = cfg
        self.tick = 0          # budget consumed
        self.drift = 0         # how far the mover's schedule has run
        self.agent_at = cfg.start
        self.holding: Optional[str] = None
        self.finished = False
        # Why the episode stopped. "world finished" told the analysis nothing:
        # running out of deadline, exhausting max_ticks and the agent choosing
        # to stop are three different outcomes, and only the first two are
        # censoring. Distinguishing them is what makes a censoring count
        # possible at all.
        self.finish_reason: str = ""
        # Once the mover is picked up it stops following its schedule. Without
        # this the dynamic task would be unwinnable by construction.
        self._mover_captured = False
        self._mover_placed_at: Optional[str] = None
        self.log: list[dict] = []

    # -- privileged views, never reachable through the action API -----------

    def truth_location(self, obj: str, tick: Optional[int] = None) -> Optional[str]:
        """Where `obj` really is. For the referee and the analysis only."""
        tick = self.drift if tick is None else tick
        if obj == self.cfg.mover:
            if self.holding == obj:
                return None                     # in hand
            if self._mover_captured:
                return self._mover_placed_at
            return self.cfg.schedule.location_at(tick)
        if self.holding == obj:
            return None
        return self.cfg.statics.get(obj)

    def _objects_at(self, place: str, tick: int) -> tuple[str, ...]:
        here = [o for o, p in self.cfg.statics.items() if p == place and self.holding != o]
        if self.truth_location(self.cfg.mover, tick) == place:
            here.append(self.cfg.mover)
        return tuple(sorted(here))

    # -- the action API ----------------------------------------------------

    def step(self, action: tuple):
        """`action` is a parsed tuple. Returns a typed result.

        Every branch advances the clock by a fixed amount for that verb,
        regardless of outcome, so the tick counter leaks nothing.
        """
        if self.finished:
            return DoneResult(self.tick)

        verb = action[0]

        # Affordability is checked BEFORE the action applies. Checking after
        # the effect would let an agent with 2 ticks left buy a 5-tick observe,
        # receive the answer and act on it, finishing past a deadline the
        # prompt describes as fatal.
        if self.cfg.deadline is not None:
            cost = self.cfg.t_do if verb == "observe" else 1
            if self.tick + cost > self.cfg.deadline:
                self.finished = True
                self.finish_reason = "deadline: next action unaffordable"
                return DoneResult(self.tick)

        if verb == "observe":
            place = action[1]
            if place not in self.cfg.places:
                self._advance(self.cfg.t_do, self._drift())
                return ErrorResult(self.tick)
            # Two different clocks, for two different jobs. Objects resolve
            # against drift, because that is what governs where the mover is.
            # The tick SHOWN to the agent is elapsed time, so that every reply
            # it ever sees reports the same counter. Rendering drift here while
            # every other result rendered elapsed time gave the agent a clock
            # that jumped back and forth between actions.
            resolve_at = self.drift
            objects = self._objects_at(place, resolve_at)
            shown = self.tick
            self._advance(self.cfg.t_do, self._drift())   # observe now, pay after
            self._record("observe", place, resolve_at, objects)
            return ObserveResult(place, objects, shown, resolve_at)

        if verb == "goto":
            place = action[1]
            if place not in self.cfg.places:
                self._advance(1)
                return ErrorResult(self.tick)
            self.agent_at = place
            self._advance(1)
            self._record("goto", place, self.tick, None)
            return MoveResult(place, self.tick)

        if verb == "pick":
            obj = action[1]
            # The only thing this may reveal is whether obj is here, which the
            # spec allows. It must reveal nothing more.
            # Resolve against the drift clock, the same one `observe` and the
            # referee use. All three must agree, or the world can report the
            # mover somewhere it then refuses to hand it over. The clocks
            # coincide while t_drift equals t_do and diverge once it does not,
            # which is exactly the comparison the split exists to make.
            present = (
                obj != self.holding
                and self.holding is None
                and self.truth_location(obj, self.drift) == self.agent_at
            )
            if present:
                if obj == self.cfg.mover:
                    self._mover_captured = True
                    self._mover_placed_at = None
                self.holding = obj
            self._advance(1)
            self._record("pick", obj, self.tick, None, ok=present)
            return PickResult(present, obj, self.tick)

        if verb == "place":
            obj, place = action[1], action[2]
            ok = self.holding == obj and place in self.cfg.places
            if ok:
                self.holding = None
                if obj == self.cfg.mover:
                    self._mover_placed_at = place
                else:
                    self.cfg.statics[obj] = place
                self.agent_at = place
            self._advance(1)
            self._record("place", f"{obj}->{place}", self.tick, None, ok=ok)
            return PlaceResult(ok, obj, place, self.tick)

        if verb == "done":
            self.finished = True
            self.finish_reason = "agent called done"
            self._advance(1)
            return DoneResult(self.tick)

        self._advance(1)
        return ErrorResult(self.tick)

    # -- internals ---------------------------------------------------------

    def _advance(self, ticks: int, drift: int | None = None) -> None:
        self.tick += ticks
        self.drift += ticks if drift is None else drift
        if self.tick >= self.cfg.max_ticks and not self.finished:
            self.finished = True
            self.finish_reason = "max_ticks exhausted"
        if (self.cfg.deadline is not None and self.tick >= self.cfg.deadline
                and not self.finished):
            self.finished = True
            self.finish_reason = "deadline reached"

    def drift_step(self) -> int:
        """Ticks the mover's schedule advances during one observation."""
        c = self.cfg
        return c.t_do if c.t_drift is None else c.t_drift

    # kept as the internal name used by `step`
    _drift = drift_step

    def _record(self, verb, arg, tick, objects, ok=None) -> None:
        self.log.append(
            {"verb": verb, "arg": arg, "tick": tick, "objects": objects, "ok": ok}
        )

    # -- referee -----------------------------------------------------------

    def succeeded(self, target_obj: str, target_place: str) -> bool:
        """Ground truth. Never ask the agent whether it succeeded."""
        return self.truth_location(target_obj) == target_place


def make_world(cfg: WorldConfig) -> World:
    # statics is mutated by `place`, so each world gets its own copy
    return World(
        WorldConfig(
            places=cfg.places,
            statics=dict(cfg.statics),
            mover=cfg.mover,
            schedule=cfg.schedule,
            t_do=cfg.t_do,
            t_drift=cfg.t_drift,
            deadline=cfg.deadline,
            t_say=cfg.t_say,
            start=cfg.start,
            max_ticks=cfg.max_ticks,
        )
    )
