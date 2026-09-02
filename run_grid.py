"""Full cost grid, run in parallel.

Crosses the cost we STATE with the cost we CHARGE over a grid, rather than
just the {0,5}^2 corners. The corners tell you whether a stated cost does
anything; the grid tells you the shape of the response, including whether the
agent is sensitive to the size of the number or only to its presence.

Episodes inside a cell are independent, so they run on a thread pool. That is
the difference between an afternoon and a few minutes.

Usage:
  python run_grid.py --model gpt-5.2 --episodes 25 --workers 8
  python run_grid.py --model gpt-5.2 --prompt-style salient --costs 0 2 5
"""

from __future__ import annotations

import argparse
import json
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from agent import EpisodeRecord, STYLES, load_key, run_episode
from world import PeriodicSchedule, RandomSchedule, World, WorldConfig

ROAMING = ("table", "sink", "basin")
FIXED = ("counter", "shelf")
PLACES = ROAMING + FIXED
STATICS = {"bowl": "counter", "book": "shelf"}
MOVER = "cup"
TARGET = "shelf"
PERIOD = 8

_print_lock = threading.Lock()


def make_world(t_say: int, t_do: int, seed: int, schedule: str) -> World:
    if schedule == "periodic":
        sched = PeriodicSchedule(order=ROAMING, period=PERIOD)
    else:
        sched = RandomSchedule(places=ROAMING, period=PERIOD, seed=seed)
    return World(
        WorldConfig(
            places=PLACES, statics=dict(STATICS), mover=MOVER, schedule=sched,
            t_do=t_do, t_say=t_say, start="table", max_ticks=2000,
        )
    )


def one_episode(client, args, t_say, t_do, seed, family, schedule):
    obj = MOVER if family == "dynamic-target" else "bowl"
    w = make_world(t_say, t_do, seed, schedule)
    return run_episode(
        client, args.model, w, obj, TARGET, family, schedule, seed,
        max_turns=args.max_turns, prompt_style=args.prompt_style,
    )


def summarise(recs: list[EpisodeRecord], t_say: int, t_do: int) -> dict:
    n = len(recs)
    stales = [r.staleness for r in recs if r.staleness is not None]
    caps = sum(1 for r in recs if r.end_reason == "turn cap")
    stale = statistics.mean(stales) if stales else float("nan")
    return {
        "t_say": t_say, "t_do": t_do, "n": n,
        "success": sum(r.success for r in recs) / n,
        "obs": statistics.mean(r.n_obs for r in recs),
        "turns": statistics.mean(r.turns for r in recs),
        "hit_cap": caps,
        "malformed": sum(r.n_malformed for r in recs),
        "staleness": stale,
        "excess": stale - t_do,          # par staleness is t_do while period > cost
        "committed": len(stales),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-5.2")
    ap.add_argument("--episodes", type=int, default=25)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-turns", type=int, default=80)
    ap.add_argument("--prompt-style", default="plain",
                    choices=sorted(STYLES))   # never hand-listed again
    ap.add_argument("--costs", type=int, nargs="+", default=[0, 2, 5])
    ap.add_argument("--schedule", default="random", choices=["random", "periodic"])
    ap.add_argument("--family", default="dynamic-target",
                    choices=["dynamic-target", "static-target"])
    args = ap.parse_args()

    key = load_key()
    if not key:
        print("No API key in env or pilot/.env")
        return
    from openai import OpenAI

    client = OpenAI(api_key=key, max_retries=0)   # we do our own backoff

    cells = [(s, d) for s in args.costs for d in args.costs]
    total = len(cells) * args.episodes
    print(f"\nGrid: model={args.model} prompt={args.prompt_style} "
          f"schedule={args.schedule} family={args.family}")
    print(f"{len(cells)} cells x {args.episodes} episodes = {total} episodes, "
          f"{args.workers} workers, turn cap {args.max_turns}\n")

    t0 = time.time()
    all_recs: list[EpisodeRecord] = []
    rows = []
    skipped = 0

    for t_say, t_do in cells:
        recs: list[EpisodeRecord] = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = {
                pool.submit(one_episode, client, args, t_say, t_do, seed,
                            args.family, args.schedule): seed
                for seed in range(args.episodes)
            }
            for fut in as_completed(futs):
                try:
                    recs.append(fut.result())
                except Exception as e:
                    skipped += 1
                    with _print_lock:
                        print(f"    [skip say={t_say} do={t_do} "
                              f"seed={futs[fut]}] {type(e).__name__}")
        if not recs:
            continue
        s = summarise(recs, t_say, t_do)
        rows.append(s)
        all_recs += recs
        print(f"  say={t_say} do={t_do}: obs {s['obs']:6.2f}  succ {s['success']:.2f}  "
              f"stale {s['staleness']:6.2f}  excess {s['excess']:+5.2f}  "
              f"cap {s['hit_cap']:2d}/{s['n']}  malformed {s['malformed']}")

    out_dir = Path(__file__).with_name("runs")
    out_dir.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    tag = f"{args.model}-{args.prompt_style}-{args.schedule}-{args.family}"
    (out_dir / f"grid-{tag}-{stamp}.json").write_text(
        json.dumps([r.__dict__ for r in all_recs], indent=1), encoding="utf-8")
    (out_dir / f"grid-{tag}-{stamp}-summary.json").write_text(
        json.dumps(rows, indent=1), encoding="utf-8")

    # main effects, averaged over the other factor
    print("\n" + "=" * 66)
    d = {(r["t_say"], r["t_do"]): r["obs"] for r in rows}
    costs = args.costs
    if len(d) == len(cells):
        lo, hi = costs[0], costs[-1]
        say_eff = statistics.mean(d[(hi, x)] - d[(lo, x)] for x in costs)
        do_eff = statistics.mean(d[(x, hi)] - d[(x, lo)] for x in costs)
        print(f"effect of STATED cost {lo}->{hi} (averaged over actual): "
              f"{say_eff:+.2f} observations")
        print(f"effect of ACTUAL cost {lo}->{hi} (averaged over stated): "
              f"{do_eff:+.2f} observations")
        print()
        print(f"stated-cost effect when actual cost is {lo}: "
              f"{d[(hi, lo)] - d[(lo, lo)]:+.2f}")
        print(f"stated-cost effect when actual cost is {hi}: "
              f"{d[(hi, hi)] - d[(lo, hi)]:+.2f}")
        print("(if these differ, the stated cost only bites when the agent pays)")

    tin = sum(r.in_tokens for r in all_recs)
    tout = sum(r.out_tokens for r in all_recs)
    print(f"\n{len(all_recs)} episodes, {skipped} skipped, "
          f"{time.time()-t0:.0f}s, {tin/1000:.0f}k in / {tout/1000:.0f}k out")


if __name__ == "__main__":
    main()
