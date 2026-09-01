"""ReAct agent over the room simulator, driven by an OpenAI model.

The prompt is identical across every condition except the single number it
states for the observation cost. That number is T_say. The world charges
T_do. Holding those apart is the point of the headline experiment, so nothing
else in the prompt may vary with condition.

The key is read from OPENAI_API_KEY, or from pilot/.env if that file exists.
.env is gitignored and must never be committed.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from world import World


def load_key() -> str | None:
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    env = Path(__file__).with_name(".env")
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


SYSTEM = """You are an agent acting in a room. You cannot see the room. The \
only way to learn anything about it is to use the observe action.

Places in the room: {places}

Objects in the room: {objects}

The room runs on a tick clock. Your actions cost time:

  observe(<place>)        tells you which objects are at that place RIGHT NOW.
                          Costs {t_say} tick(s).
  goto(<place>)           moves you there. Costs 1 tick.
                          It tells you NOTHING about what is there.
  pick(<object>)          picks it up, and only works if you are already at
                          the same place as it. Costs 1 tick.
  place(<object>,<place>) puts down what you are holding. Costs 1 tick.
  done()                  ends the episode.

Important: {mover} does not stay still. It moves to a new place every so \
often, and it keeps moving while you are observing. An observation tells you \
where things were at the moment you looked, and the clock has advanced by the \
time you can act on it. The other objects never move.

Your task: {task}

Reply with exactly one action per turn, on its own line, in the form

ACTION: observe(sink)

You may write one short line of reasoning before it. Do not write anything \
after the ACTION line."""

ACTION_RE = re.compile(
    r"ACTION:\s*(observe|goto|pick|place|done)\s*\(([^)]*)\)", re.IGNORECASE
)


def parse_action(text: str) -> tuple | None:
    m = ACTION_RE.search(text or "")
    if not m:
        return None
    verb = m.group(1).lower()
    args = [a.strip() for a in m.group(2).split(",") if a.strip()]
    if verb == "done":
        return ("done",)
    if verb in ("observe", "goto") and len(args) == 1:
        return (verb, args[0])
    if verb == "pick" and len(args) == 1:
        return ("pick", args[0])
    if verb == "place" and len(args) == 2:
        return ("place", args[0], args[1])
    return None


@dataclass
class EpisodeRecord:
    t_say: int
    t_do: int
    schedule: str
    family: str
    seed: int
    model: str
    success: bool = False
    n_obs: int = 0
    n_obs_without_mover: int = 0
    n_malformed: int = 0
    turns: int = 0
    in_tokens: int = 0
    out_tokens: int = 0
    staleness: int | None = None
    end_reason: str = ""
    transcript: list[dict] = field(default_factory=list)

    @property
    def rho_s(self) -> float | None:
        return None if self.n_obs == 0 else self.n_obs_without_mover / self.n_obs


def run_episode(
    client,
    model: str,
    w: World,
    task_obj: str,
    task_place: str,
    family: str,
    schedule: str,
    seed: int,
    max_turns: int = 30,
) -> EpisodeRecord:
    cfg = w.cfg
    objects = sorted(list(cfg.statics.keys()) + [cfg.mover])
    system = SYSTEM.format(
        places=", ".join(cfg.places),
        objects=", ".join(objects),
        t_say=cfg.t_say,
        mover=cfg.mover,
        task=f"put {task_obj} on the {task_place}.",
    )
    rec = EpisodeRecord(
        t_say=cfg.t_say, t_do=cfg.t_do, schedule=schedule, family=family,
        seed=seed, model=model,
    )
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": "Begin. What is your first action?"}]

    last_seen: dict[str, int] = {}   # place -> tick the mover was last seen there

    for _ in range(max_turns):
        if w.finished:
            rec.end_reason = "world finished"
            break
        resp = client.chat.completions.create(
            model=model, messages=messages, max_completion_tokens=200,
        )
        text = resp.choices[0].message.content or ""
        if getattr(resp, "usage", None):
            rec.in_tokens += resp.usage.prompt_tokens or 0
            rec.out_tokens += resp.usage.completion_tokens or 0
        rec.turns += 1
        messages.append({"role": "assistant", "content": text})

        act = parse_action(text)
        if act is None:
            rec.n_malformed += 1
            w.step(("__malformed__",))
            messages.append({"role": "user",
                             "content": "That was not a valid action. "
                                        "Reply with one ACTION: line."})
            rec.transcript.append({"model": text, "parsed": None})
            continue

        if act[0] == "pick" and act[1] == cfg.mover:
            here = w.agent_at
            if here in last_seen:
                rec.staleness = w.tick - last_seen[here]

        res = w.step(act)

        if act[0] == "observe":
            rec.n_obs += 1
            found = cfg.mover in getattr(res, "objects", ())
            if found:
                last_seen[act[1]] = res.tick
            else:
                rec.n_obs_without_mover += 1

        obs_text = res.render()
        messages.append({"role": "user", "content": obs_text})
        rec.transcript.append({"model": text, "parsed": list(act), "env": obs_text})

        if act[0] == "done":
            rec.end_reason = "agent called done"
            break
    else:
        rec.end_reason = "turn cap"

    rec.success = w.succeeded(task_obj, task_place)
    return rec
