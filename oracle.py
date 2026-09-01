"""Par-setter: the best a player can do, found by search rather than asserted.

Two quantities, and it matters that they are kept apart.

`par_staleness(T)` is the mechanical floor on how old a belief can be at the
moment an agent commits to a pick. Every policy faces it, including a perfect
one, which is exactly why raw staleness cannot be compared across costs. It is
found here by exhaustive search over short action sequences against the true
schedule, not by an analytic guess. (My analytic guess was T+1. The search
finds T, because a player can walk to the place first and observe while
standing there. That is the reason to search.)

`par_observes` is the fewest observations a *blind* player needs to finish,
searching over the same space without being told where the mover is.
"""

from __future__ import annotations

from itertools import product

from world import World, WorldConfig


def _fresh(cfg: WorldConfig) -> World:
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


def _candidate_actions(cfg: WorldConfig) -> list[tuple]:
    acts: list[tuple] = [("observe", p) for p in cfg.places]
    acts += [("goto", p) for p in cfg.places]
    acts.append(("pick", cfg.mover))
    return acts


def par_staleness(cfg: WorldConfig, max_depth: int = 4) -> int | None:
    """Minimum ticks between last observing a place and picking the mover there.

    Exhaustive over action sequences of length <= max_depth. Returns None if
    no sequence in that budget picks the mover up at all.
    """
    acts = _candidate_actions(cfg)
    best: int | None = None

    for seq in product(acts, repeat=max_depth):
        # cheap prune: a sequence that never tries to pick cannot succeed
        if ("pick", cfg.mover) not in seq:
            continue
        w = _fresh(cfg)
        last_seen: dict[str, int] = {}
        picked_stale: int | None = None
        for act in seq:
            if w.finished:
                break
            if act[0] == "observe":
                seen_tick = w.tick
                res = w.step(act)
                # only an observation that actually located the mover can
                # ground a later pick
                if cfg.mover in res.objects:
                    last_seen[act[1]] = seen_tick
            elif act[0] == "pick":
                here = w.agent_at
                t_pick = w.tick
                res = w.step(act)
                if res.ok:
                    if here in last_seen:
                        picked_stale = t_pick - last_seen[here]
                    break
            else:
                w.step(act)
        if picked_stale is not None:
            best = picked_stale if best is None else min(best, picked_stale)
    return best


def par_observes(cfg: WorldConfig, max_depth: int = 5) -> int | None:
    """Fewest observations a blind player needs to get the mover in hand.

    The player is not told where the mover is. Any sequence that succeeds is
    admissible; we report the smallest observation count among those, which is
    the blind lower bound on coverage at this cost.
    """
    acts = _candidate_actions(cfg)
    best: int | None = None
    for depth in range(2, max_depth + 1):
        for seq in product(acts, repeat=depth):
            if ("pick", cfg.mover) not in seq:
                continue
            n_obs = sum(1 for a in seq if a[0] == "observe")
            if best is not None and n_obs >= best:
                continue
            w = _fresh(cfg)
            got = False
            for act in seq:
                if w.finished:
                    break
                res = w.step(act)
                if act[0] == "pick" and getattr(res, "ok", False):
                    got = True
                    break
            if got:
                best = n_obs if best is None else min(best, n_obs)
        if best == 0:
            break
    return best
