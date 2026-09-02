"""Decouple elapsed time from information staleness.

The pilot's `t_do` did two jobs at once. It consumed world time, and it let the
target drift while the agent looked. Since nothing else in that world depended
on time, those were not merely correlated, they were the same quantity. So the
headline result could not distinguish

    "observing takes time I do not have"                 (latency)

from

    "observing makes my information stale, so it is worth less"  (staleness)

This runs the 2x2x2 that separates them:

    charged   C in {0,5}   ticks an observation consumes against a deadline
    drift     D in {0,5}   how far the target moves during an observation
    stated    S in {0,5}   the figure named in the prompt

C=5,D=0 is slow but informative; C=0,D=5 is instant but stale. If behaviour
tracks D and ignores C, the earlier result was about the world moving on, not
about time spent.

Usage: python run_factorial.py --model gpt-5.2 --episodes 40 --workers 10
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from agent import load_key, run_episode
from world import RandomSchedule, World, WorldConfig

ROAMING = ("table", "sink", "basin")
PLACES = ROAMING + ("counter", "shelf")
STATICS = {"bowl": "counter", "book": "shelf"}
MOVER, TARGET, PERIOD = "cup", "shelf", 8
DEADLINE = 60           # binds a profligate agent, ample for an efficient one

# End reasons that mean the episode was cut off rather than concluded. Turn-cap
# censoring at 30 turns once fell 14/25 against 6/24 across two arms, which on
# its own can manufacture a difference in observation counts.
CENSORED = ("turn cap", "max_ticks exhausted")


def make_world(t_say: int, charged: int, drift: int, seed: int) -> World:
    return World(WorldConfig(
        places=PLACES, statics=dict(STATICS), mover=MOVER,
        schedule=RandomSchedule(places=ROAMING, period=PERIOD, seed=seed),
        t_do=charged, t_say=t_say, t_drift=drift,
        start="table", max_ticks=4000, deadline=DEADLINE,
    ))


def one(client, args, s, c, d, seed):
    w = make_world(s, c, d, seed)
    r = run_episode(client, args.model, w, MOVER, TARGET,
                    "dynamic-target", "random", seed,
                    max_turns=args.max_turns, prompt_style="budget")
    # t_do / t_drift / ticks_used are recorded by run_episode itself now. These
    # aliases stay only because the saved records and the analysis scripts read
    # them by these names; they are checked against the world, not re-derived.
    assert r.t_do == c and r.t_drift == d and r.ticks_used == w.tick
    r.__dict__["charged"] = c
    r.__dict__["drift"] = d
    return r


def contrast(recs, key, lo, hi, metric):
    """Unweighted marginal effect of `key`, hi minus lo, with a bootstrap CI.

    Two things this gets right that the previous version did not.

    First, it averages over EPISODES within each cell and then over CELLS with
    equal weight. Averaging the per-cell means directly was fine only while
    every cell held the same number of episodes; cells lose episodes to API
    errors, and one cell finishing 31 of 40 silently reweighted the design.
    Cells are now weighted equally by construction and the imbalance is
    printed, so a lopsided run is visible instead of absorbed.

    Second, it returns an interval. The project has twice been embarrassed by a
    point estimate whose interval straddled zero, so no contrast is reported
    without one.
    """
    other = [k for k in ("t_say", "charged", "drift") if k != key]

    def marginal(sample):
        cells: dict[tuple, list[float]] = {}
        for r in sample:
            cells.setdefault(tuple(r.__dict__[k] for k in other), []).append(
                metric(r))
        return cells

    def diff(sample):
        hi_cells = marginal([r for r in sample if r.__dict__[key] == hi])
        lo_cells = marginal([r for r in sample if r.__dict__[key] == lo])
        shared = set(hi_cells) & set(lo_cells)
        if not shared:
            return None
        # per-cell difference first, then the mean over cells: the paired form,
        # so the other factors cannot shift between the two arms
        return statistics.mean(
            statistics.mean(hi_cells[c]) - statistics.mean(lo_cells[c])
            for c in shared)

    point = diff(recs)
    if point is None:
        return None
    rng = random.Random(0)
    boots = []
    for _ in range(2000):
        draw = [recs[rng.randrange(len(recs))] for _ in range(len(recs))]
        d = diff(draw)
        if d is not None:
            boots.append(d)
    boots.sort()
    if len(boots) < 100:
        return point, None, None
    return point, boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-5.2")
    ap.add_argument("--episodes", type=int, default=40)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--max-turns", type=int, default=60)
    # All three factors are configurable, and the analysis reads its levels
    # back off these lists. `charged` and `drift` used to be hardcoded (0, 5)
    # in the cell loop while `eff()` separately hardcoded `== 5` and `== 0`, so
    # restricting a factor produced a table that no longer matched the summary.
    ap.add_argument("--stated", type=int, nargs="+", default=[0, 5])
    ap.add_argument("--charged", type=int, nargs="+", default=[0, 5])
    ap.add_argument("--drift", type=int, nargs="+", default=[0, 5])
    args = ap.parse_args()

    key = load_key()
    if not key:
        print("no API key")
        return
    from openai import OpenAI
    client = OpenAI(api_key=key, max_retries=0)

    levels = {"t_say": sorted(set(args.stated)),
              "charged": sorted(set(args.charged)),
              "drift": sorted(set(args.drift))}
    cells = [(s, c, d) for s in levels["t_say"]
             for c in levels["charged"] for d in levels["drift"]]
    print(f"\nDecoupled factorial, model={args.model}, deadline={DEADLINE}")
    print(f"{len(cells)} cells x {args.episodes} episodes")
    print("levels: " + ", ".join(f"{k}={v}" for k, v in levels.items()) + "\n")
    print(f"{'stated':>7}{'charged':>9}{'drift':>7}{'obs':>8}{'ticks':>8}"
          f"{'success':>9}{'cens':>6}{'n':>5}")

    t0, all_recs, rows = time.time(), [], []
    for s, c, d in cells:
        recs = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(one, client, args, s, c, d, seed): seed
                    for seed in range(args.episodes)}
            for f in as_completed(futs):
                try:
                    recs.append(f.result())
                except Exception as e:
                    print(f"    [skip {s}/{c}/{d}] {type(e).__name__}")
        if not recs:
            continue
        cens = sum(r.end_reason in CENSORED for r in recs)
        row = {
            "t_say": s, "charged": c, "drift": d,
            "n": len(recs), "requested": args.episodes,
            "obs": statistics.mean(r.n_obs for r in recs),
            "ticks": statistics.mean(r.ticks_used for r in recs),
            "success": sum(r.success for r in recs) / len(recs),
            "censored": cens,
            "end_reasons": dict(Counter(r.end_reason for r in recs)),
            "over_deadline": sum(r.ticks_used > DEADLINE for r in recs),
        }
        rows.append(row)
        all_recs += recs
        print(f"{s:>7}{c:>9}{d:>7}{row['obs']:>8.2f}{row['ticks']:>8.1f}"
              f"{row['success']:>9.2f}{cens:>6}{row['n']:>5}")

    out = Path(__file__).with_name("runs")
    out.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (out / f"factorial-{args.model}-{stamp}.json").write_text(
        json.dumps([r.__dict__ for r in all_recs], indent=1), encoding="utf-8")
    (out / f"factorial-{args.model}-{stamp}-summary.json").write_text(
        json.dumps({"levels": levels, "deadline": DEADLINE, "cells": rows},
                   indent=1), encoding="utf-8")

    # -- integrity of the design, before any effect is quoted ---------------
    print("\n" + "=" * 62)
    short = [(r["t_say"], r["charged"], r["drift"], r["n"])
             for r in rows if r["n"] < r["requested"]]
    if short:
        print(f"  UNBALANCED: {len(short)} of {len(rows)} cells short of "
              f"{args.episodes}: {short}")
        print("  contrasts below weight cells equally, so this shifts the CI,")
        print("  not the point estimate.")
    else:
        print(f"  balanced: every cell has {args.episodes} episodes")
    tot_cens = sum(r["censored"] for r in rows)
    if tot_cens:
        worst = max(rows, key=lambda r: r["censored"])
        print(f"  CENSORED: {tot_cens} episodes cut off at the turn cap; "
              f"worst cell {worst['censored']}/{worst['n']}")
        print("  asymmetric censoring can manufacture an effect on its own.")
    over = sum(r["over_deadline"] for r in rows)
    print(f"  over deadline: {over} episodes"
          + ("  <-- the deadline is not binding" if over else ""))

    # -- main effects -------------------------------------------------------
    print()
    metrics = (("observations", lambda r: float(r.n_obs)),
               ("ticks used  ", lambda r: float(r.ticks_used)),
               ("success     ", lambda r: float(r.success)))
    for label, key in (("STATED price ", "t_say"),
                       ("CHARGED ticks", "charged"),
                       ("DRIFT        ", "drift")):
        lv = levels[key if key != "t_say" else "t_say"]
        if len(lv) < 2:
            print(f"  {label} {lv[0]} fixed: not varied")
            continue
        lo, hi = lv[0], lv[-1]
        print(f"  {label} {lo} -> {hi}")
        for mlabel, metric in metrics:
            res = contrast(all_recs, key, lo, hi, metric)
            if res is None:
                print(f"      {mlabel}: no cell varies this factor")
                continue
            point, ci_lo, ci_hi = res
            ci = ("" if ci_lo is None
                  else f"  [{ci_lo:+.2f}, {ci_hi:+.2f}]")
            zero = ("" if ci_lo is None or (ci_lo > 0) == (ci_hi > 0)
                    else "   includes zero")
            print(f"      {mlabel}: {point:+.2f}{ci}{zero}")

    print("\nIf drift moves behaviour and charged does not, the effect is")
    print("information going stale, not time being spent.")
    print(f"\n{len(all_recs)} episodes in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
