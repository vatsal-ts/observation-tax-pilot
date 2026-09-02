"""Does the agent notice when the stated price is false?

In the say=5 / do=0 cell we tell the agent an observation costs 5 ticks and
then charge it 0. Every environment reply carries the tick counter, so the
discrepancy is visible in the transcript. Two readings of the null result
there hang on this:

  (a) the agent is insensitive to a stated budget
  (b) the agent detected that the quoted price was false and discounted it

(b) would be rational updating rather than a failure, and would invert what
the paper claims. This scans the model's own words for any sign of (b).

Reported per configuration and pooled, because pooling four configurations is
defensible for an existence question ("does it ever notice?") but must not be
presented as a single condition.
"""

from __future__ import annotations

import re
from collections import defaultdict

from runs_io import load_runs

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
    runs = load_runs(verbose=True)
    print()

    rows, pooled_eps, pooled_cost, pooled_notice = [], 0, 0, 0
    for run in runs:
        eps = [r for r in run["records"] if r["t_say"] == 5 and r["t_do"] == 0]
        if not eps:
            continue
        cost_eps = notices = 0
        for r in eps:
            said = False
            for turn in r.get("transcript", []):
                text = turn.get("model") or ""
                if COSTWORDS.search(text):
                    said = True
                if NOTICE.search(text):
                    notices += 1
            cost_eps += said
        label = f"{run['style']}/{run['sched']}/{run['family']}"
        rows.append((label, len(eps), cost_eps, notices))
        pooled_eps += len(eps)
        pooled_cost += cost_eps
        pooled_notice += notices

    print("Cell say=5 / do=0 : told observation costs 5, charged 0\n")
    print(f"{'configuration':<38}{'eps':>5}{'cite cost':>11}{'notice':>8}")
    print("-" * 62)
    for label, n, c, k in sorted(rows):
        print(f"{label:<38}{n:>5}{c:>11}{k:>8}")
    print("-" * 62)
    print(f"{'pooled':<38}{pooled_eps:>5}{pooled_cost:>11}{pooled_notice:>8}")
    print(f"\n{pooled_notice} turns across {pooled_eps} episodes show any sign of "
          f"noticing the quoted price is false.")
    print("Pooling four configurations is appropriate for an existence question")
    print("and must not be reported as a single condition.")


if __name__ == "__main__":
    main()
