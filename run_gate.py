"""T=0 competence gate: can the model do this at all when looking is free?

This is the proposal's own stop condition, and it is the right first thing to
spend money on. If dynamic-target success at zero cost is near the floor, then
any later concentration of failure is a perception ceiling and the study does
not mean what it claims. Cheap to run, and it can save the whole budget.

Usage:
    python run_gate.py --list-models
    python run_gate.py --model <id> --episodes 15
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from agent import EpisodeRecord, load_key, run_episode
from world import RandomSchedule, World, WorldConfig

ROAMING = ("table", "sink", "basin")
FIXED = ("counter", "shelf")
PLACES = ROAMING + FIXED
STATICS = {"bowl": "counter", "book": "shelf"}
MOVER = "cup"
TARGET = "shelf"
PERIOD = 8


def make_world(t_say: int, t_do: int, seed: int) -> World:
    return World(
        WorldConfig(
            places=PLACES,
            statics=dict(STATICS),
            mover=MOVER,
            schedule=RandomSchedule(places=ROAMING, period=PERIOD, seed=seed),
            t_do=t_do,
            t_say=t_say,
            start="table",
            max_ticks=400,
        )
    )


def summarise(recs: list[EpisodeRecord], label: str) -> None:
    n = len(recs)
    succ = sum(r.success for r in recs) / n
    obs = statistics.mean(r.n_obs for r in recs)
    turns = statistics.mean(r.turns for r in recs)
    mal = sum(r.n_malformed for r in recs)
    caps = sum(r.end_reason == "turn cap" for r in recs)
    tin = sum(r.in_tokens for r in recs)
    tout = sum(r.out_tokens for r in recs)
    print(f"  {label:<18} success {succ:.2f}   obs {obs:5.2f}   turns {turns:5.1f}"
          f"   malformed {mal:3d}   hit cap {caps:2d}   tok {tin//1000}k/{tout//1000}k")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None)
    ap.add_argument("--episodes", type=int, default=15)
    ap.add_argument("--list-models", action="store_true")
    args = ap.parse_args()

    key = load_key()
    if not key:
        print("No API key. Create pilot/.env containing one line:")
        print("    OPENAI_API_KEY=sk-...")
        print("It is gitignored and will not be committed.")
        return

    from openai import OpenAI

    client = OpenAI(api_key=key)

    if args.list_models:
        ids = sorted(m.id for m in client.models.list())
        print(f"{len(ids)} models available:")
        for i in ids:
            print("   ", i)
        return

    if not args.model:
        print("Pass --model <id>. Use --list-models to see what your key can reach.")
        return

    print(f"\nT=0 competence gate.  model={args.model}  episodes={args.episodes} per family")
    print(f"Room: roaming {ROAMING}, fixed {FIXED}, mover '{MOVER}', period {PERIOD}")
    print("Observation is FREE here (t_say = t_do = 0).\n")

    out_dir = Path(__file__).with_name("runs")
    out_dir.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")

    all_recs: list[EpisodeRecord] = []
    for family, obj in (("static-target", "bowl"), ("dynamic-target", MOVER)):
        recs = []
        for seed in range(args.episodes):
            w = make_world(0, 0, seed)
            try:
                r = run_episode(client, args.model, w, obj, TARGET,
                                family, "random", seed)
            except Exception as e:                      # keep partial results
                print(f"  [error seed {seed}] {type(e).__name__}: {e}")
                break
            recs.append(r)
            print(f"    {family} seed {seed:2d}: "
                  f"{'OK ' if r.success else '   '} obs={r.n_obs} turns={r.turns}"
                  f" ({r.end_reason})")
        summarise(recs, family)
        all_recs += recs

    path = out_dir / f"gate-{stamp}.json"
    path.write_text(json.dumps([r.__dict__ for r in all_recs], indent=1), encoding="utf-8")
    print(f"\nTranscripts written to {path}")

    dyn = [r for r in all_recs if r.family == "dynamic-target"]
    if dyn:
        rate = sum(r.success for r in dyn) / len(dyn)
        print(f"\nDynamic-target success at zero cost: {rate:.2f}")
        if rate < 0.7:
            print("WARNING. Below 0.7. The model cannot reliably do this even when")
            print("looking is free, so any later result would be a ceiling artifact.")
            print("Make the task easier before spending on the sweep.")
        else:
            print("Gate cleared. The sweep is worth running.")


if __name__ == "__main__":
    main()
