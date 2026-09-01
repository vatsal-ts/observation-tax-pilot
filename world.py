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
    t_do: int                          # ticks the world charges for observe
    t_say: int                         # ticks the prompt claims observe costs
    start: str                         # where the agent begins
    max_ticks: int = 200

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
    tick: int

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
        self.tick = 0
        self.agent_at = cfg.start
        self.holding: Optional[str] = None
        self.finished = False
        # Once the mover is picked up it stops following its schedule. Without
        # this the dynamic task would be unwinnable by construction.
        self._mover_captured = False
        self._mover_placed_at: Optional[str] = None
        self.log: list[dict] = []

    # -- privileged views, never reachable through the action API -----------

    def truth_location(self, obj: str, tick: Optional[int] = None) -> Optional[str]:
        """Where `obj` really is. For the referee and the analysis only."""
        tick = self.tick if tick is None else tick
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

        if verb == "observe":
            place = action[1]
            if place not in self.cfg.places:
                self._advance(self.cfg.t_do)
                return ErrorResult(self.tick)
            seen_at = self.tick
            objects = self._objects_at(place, seen_at)
            self._advance(self.cfg.t_do)          # observe now, pay after
            self._record("observe", place, seen_at, objects)
            return ObserveResult(place, objects, seen_at)

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
            present = (
                obj != self.holding
                and self.holding is None
                and self.truth_location(obj, self.tick) == self.agent_at
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
            self._advance(1)
            return DoneResult(self.tick)

        self._advance(1)
        return ErrorResult(self.tick)

    # -- internals ---------------------------------------------------------

    def _advance(self, ticks: int) -> None:
        self.tick += ticks
        if self.tick >= self.cfg.max_ticks:
            self.finished = True

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
            t_say=cfg.t_say,
            start=cfg.start,
            max_ticks=cfg.max_ticks,
        )
    )
