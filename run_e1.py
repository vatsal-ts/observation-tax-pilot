"""E1: stated cost versus actual cost. The headline experiment.

Cross the cost the prompt names (T_say) with the cost the world charges
(T_do) over {0,5}^2. The diagonal is what every existing efficiency result
measures. The two off-diagonal cells are the experiment:

    T_say=5, T_do=0   told looking is expensive, it is actually free
    T_say=0, T_do=5   told it is free, it is actually expensive

If behaviour tracks T_say and barely moves with T_do, the agent is complying
with an instruction rather than pricing what it pays. If it tracks T_do, it is
adapting to the cost it experiences.

The prompt is byte-identical across cells except for the single number.

Usage: python run_e1.py --model gpt-5.2 --episodes 25
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from agent import EpisodeRecord, STYLES, load_key, run_episode
from world import RandomSchedule, World, WorldConfig

ROAMING = ("table", "sink", "basin")
FIXED = ("counter", "shelf")
PLACES = ROAMING + FIXED
STATICS = {"bowl": "counter", "book": "shelf"}
MOVER = "cup"
TARGET = "shelf"
PERIOD = 8          # feasibility.py: winnable while period > cost
CELLS = [(0, 0), (0, 5), (5, 0), (5, 5)]     # (t_say, t_do)


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
            max_ticks=600,
        )
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-5.2")
    ap.add_argument("--episodes", type=int, default=25)
    ap.add_argument("--max-turns", type=int, default=30)
    ap.add_argument("--prompt-style", default="plain",
                    choices=sorted(STYLES))   # never hand-listed again
    args = ap.parse_args()

    key = load_key()
    if not key:
        print("No API key found in env or pilot/.env")
        return
    from openai import OpenAI

    client = OpenAI(api_key=key)

    out_dir = Path(__file__).with_name("runs")
    out_dir.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")

    print(f"\nE1: stated vs actual observation cost.  model={args.model}")
    print(f"{args.episodes} episodes per cell, dynamic target, period {PERIOD}\n")

    all_recs: list[EpisodeRecord] = []
    rows = []
    for t_say, t_do in CELLS:
        recs = []
        for seed in range(args.episodes):
            w = make_world(t_say, t_do, seed)
            try:
                r = run_episode(client, args.model, w, MOVER, TARGET,
                                "dynamic-target", "random", seed,
                                max_turns=args.max_turns,
                                prompt_style=args.prompt_style)
            except Exception as e:
                print(f"  [skip {t_say}/{t_do} seed {seed}] {type(e).__name__}")
                continue
            recs.append(r)
        all_recs += recs
        if not recs:
            continue
        obs = statistics.mean(r.n_obs for r in recs)
        succ = sum(r.success for r in recs) / len(recs)
        stales = [r.staleness for r in recs if r.staleness is not None]
        stale = statistics.mean(stales) if stales else float("nan")
        mal = sum(r.n_malformed for r in recs)
        rows.append((t_say, t_do, obs, succ, stale, mal, len(recs)))
        print(f"  say={t_say} do={t_do}: obs {obs:5.2f}  success {succ:.2f}  "
              f"staleness {stale:6.2f}  malformed {mal}  n={len(recs)}")

    path = out_dir / f"e1-{args.prompt_style}-{stamp}.json"
    path.write_text(json.dumps([r.__dict__ for r in all_recs], indent=1), encoding="utf-8")

    print("\n" + "=" * 62)
    print("Sensitivity of observation count")
    print("=" * 62)
    d = {(s, o): obs for s, o, obs, *_ in rows}
    if len(d) == 4:
        # how much does behaviour move when only the stated number changes,
        # holding the real cost fixed, and vice versa
        say_effect = ((d[(5, 0)] - d[(0, 0)]) + (d[(5, 5)] - d[(0, 5)])) / 2
        do_effect = ((d[(0, 5)] - d[(0, 0)]) + (d[(5, 5)] - d[(5, 0)])) / 2
        print(f"  effect of the STATED cost (T_do held fixed):  {say_effect:+.2f} observations")
        print(f"  effect of the ACTUAL cost (T_say held fixed): {do_effect:+.2f} observations")
        print()
        if abs(say_effect) > abs(do_effect):
            print("  Behaviour moves more with the stated number than with the")
            print("  experienced cost. That is stated-budget compliance.")
        else:
            print("  Behaviour moves more with the experienced cost than with the")
            print("  stated number. The agent is pricing observation.")
    print(f"\nTranscripts written to {path}")

    tin = sum(r.in_tokens for r in all_recs)
    tout = sum(r.out_tokens for r in all_recs)
    print(f"Tokens: {tin/1000:.0f}k in, {tout/1000:.0f}k out over {len(all_recs)} episodes")


if __name__ == "__main__":
    main()
