"""Decouple economic cost from information staleness.

The pilot's `t_do` did two jobs at once. It consumed world time, and it let the
target drift while the agent looked. Since nothing else in that world depended
on time, those were not merely correlated, they were the same quantity. So the
headline result could not distinguish

    "observing is expensive, so I should do less of it"          (economic)

from

    "observing makes my information stale, so it is worth less"  (informational)

This runs the 2x2x2 that separates them:

    charged   C in {0,5}   budget an observation consumes, against a stated
                           deadline the agent can actually run out of
    drift     D in {0,5}   how far the target moves during an observation
    stated    S in {0,5}   the figure named in the prompt

C=5,D=0 is expensive but informative; C=0,D=5 is free but stale. If behaviour
tracks D and ignores C, the earlier result was about staleness, not price.

Usage: python run_factorial.py --model gpt-5.2 --episodes 40 --workers 10
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from agent import load_key, run_episode
from world import RandomSchedule, World, WorldConfig

ROAMING = ("table", "sink", "basin")
PLACES = ROAMING + ("counter", "shelf")
STATICS = {"bowl": "counter", "book": "shelf"}
MOVER, TARGET, PERIOD = "cup", "shelf", 8
DEADLINE = 60           # binds a profligate agent, ample for an efficient one


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
    r.__dict__["charged"] = c
    r.__dict__["drift"] = d
    r.__dict__["ticks_used"] = w.tick
    return r


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-5.2")
    ap.add_argument("--episodes", type=int, default=40)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--max-turns", type=int, default=60)
    ap.add_argument("--stated", type=int, nargs="+", default=[0, 5],
                    help="restrict the stated-price levels, e.g. --stated 0")
    args = ap.parse_args()

    key = load_key()
    if not key:
        print("no API key")
        return
    from openai import OpenAI
    client = OpenAI(api_key=key, max_retries=0)

    cells = [(s, c, d) for s in args.stated for c in (0, 5) for d in (0, 5)]
    print(f"\nDecoupled factorial, model={args.model}, deadline={DEADLINE}")
    print(f"{len(cells)} cells x {args.episodes} episodes\n")
    print(f"{'stated':>7}{'charged':>9}{'drift':>7}{'obs':>8}{'ticks':>8}"
          f"{'success':>9}{'n':>5}")

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
        row = {
            "t_say": s, "charged": c, "drift": d, "n": len(recs),
            "obs": statistics.mean(r.n_obs for r in recs),
            "ticks": statistics.mean(r.__dict__["ticks_used"] for r in recs),
            "success": sum(r.success for r in recs) / len(recs),
        }
        rows.append(row)
        all_recs += recs
        print(f"{s:>7}{c:>9}{d:>7}{row['obs']:>8.2f}{row['ticks']:>8.1f}"
              f"{row['success']:>9.2f}{row['n']:>5}")

    out = Path(__file__).with_name("runs")
    out.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (out / f"factorial-{args.model}-{stamp}.json").write_text(
        json.dumps([r.__dict__ for r in all_recs], indent=1), encoding="utf-8")
    (out / f"factorial-{args.model}-{stamp}-summary.json").write_text(
        json.dumps(rows, indent=1), encoding="utf-8")

    # main effects on observation count, averaged over the other two factors
    def eff(key):
        """None when a factor was not varied, e.g. --stated 0 fixes t_say.

        This previously raised StatisticsError on an empty sequence, killing the
        summary *after* every episode had been written. An 800-episode run that
        had completed fine exited non-zero and looked like a failed run.
        """
        hi = [r["obs"] for r in rows if r[key] == 5]
        lo = [r["obs"] for r in rows if r[key] == 0]
        if not hi or not lo:
            return None
        return statistics.mean(hi) - statistics.mean(lo)

    print("\n" + "=" * 58)
    for label, key in (("STATED price 0->5", "t_say"),
                       ("CHARGED budget   ", "charged"),
                       ("DRIFT (staleness)", "drift")):
        e = eff(key)
        print(f"  effect of {label} : "
              + (f"{e:+.2f} observations" if e is not None else "not varied"))
    print("\nIf drift dominates charged, the earlier headline was about")
    print("information going stale, not about price.")
    print(f"\n{len(all_recs)} episodes in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
