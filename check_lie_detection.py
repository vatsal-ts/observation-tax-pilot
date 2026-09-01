"""Does the agent notice when the stated price is false?

In the say=5 / do=0 cell we tell the agent an observation costs 5 ticks and
then charge it 0. Every environment reply carries the tick counter, so the
discrepancy is visible in the transcript. Two readings of the null result
there hang on this:

  (a) the agent is insensitive to a stated budget
  (b) the agent detected that the quoted price was false and discounted it

(b) would be rational updating rather than a failure, and would invert what
the paper claims. This scans the model's own words for any sign of (b).
"""

from __future__ import annotations

import glob
import json
import re
from collections import defaultdict

# phrases that would indicate the model reasoning about the price it was
# quoted versus the price it is observing
NOTICE = re.compile(
    r"actually free|no time|didn't cost|did not cost|costs? nothing|"
    r"no tick|zero tick|0 tick|free to (?:look|observe)|"
    r"clock (?:has ?n[o']t|did ?n[o']t|didn't)|"
    r"cheaper than|not.{0,15}expensive as|contrary to|despite (?:the )?(?:stated|claim)|"
    r"said to cost|supposed to cost|claimed to cost|stated cost",
    re.I,
)
COSTWORDS = re.compile(r"\bcost|\btick|\bexpensive|\bbudget|\bcheap", re.I)


def main() -> None:
    cells = defaultdict(lambda: {"eps": 0, "cost_mentions": 0, "notices": 0,
                                 "examples": []})

    for f in glob.glob("runs/grid-*.json"):
        if f.endswith("-summary.json"):
            continue
        try:
            recs = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        for r in recs:
            if not isinstance(r, dict) or "transcript" not in r:
                continue
            key = (r["t_say"], r["t_do"])
            c = cells[key]
            c["eps"] += 1
            said_cost = False
            for turn in r["transcript"]:
                text = turn.get("model") or ""
                if COSTWORDS.search(text):
                    said_cost = True
                m = NOTICE.search(text)
                if m and len(c["examples"]) < 4:
                    c["examples"].append(text.strip().replace("\n", " ")[:180])
                if m:
                    c["notices"] += 1
            if said_cost:
                c["cost_mentions"] += 1

    print(f"\n{'say/do':<9}{'eps':>5}{'eps citing cost':>17}{'turns noticing':>16}")
    print("-" * 48)
    for k in sorted(cells):
        c = cells[k]
        print(f"{k[0]}/{k[1]:<7}{c['eps']:>5}{c['cost_mentions']:>17}"
              f"{c['notices']:>16}")

    print("\nThe cell that matters is say=5 / do=0: told expensive, charged nothing.")
    key = (5, 0)
    if key in cells:
        c = cells[key]
        pct = 100 * c["cost_mentions"] / max(c["eps"], 1)
        print(f"  {c['eps']} episodes, {c['cost_mentions']} ({pct:.0f}%) mention cost at all,"
              f" {c['notices']} turns show any sign of noticing the discrepancy.")
        for e in c["examples"]:
            print("   ex:", e)


if __name__ == "__main__":
    main()
