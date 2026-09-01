# Results log

Every run, its exact configuration, its numbers, and what can and cannot be
concluded from it. Append-only. Nothing here is edited after the fact except to
add a correction, which is marked as one.

Environment for all runs unless stated: 5 places, roaming zone
`(table, sink, basin)`, fixed zone `(counter, shelf)`, statics
`bowl@counter, book@shelf`, mover `cup`, target `shelf`, relocation period 8,
unpredictable (seeded, non-inferable) schedule, seeds `0..n-1`.

---

## R0. Channel audit (no API)

**Date** 2026-09-01 · **Script** `test_channel_audit.py`

All four checks pass.

| check | result |
|---|---|
| structural, only `ObserveResult` carries objects | pass |
| invariance, 60 worlds differing only in placement give one identical transcript | pass |
| pick reveals at most one bit, per object one response per co-location bit | pass |
| clock, identical tick traces; failed pick costs what a successful one costs | pass |

**Correction made during this run.** The first version grouped pick responses
by the co-location bit alone and reported 4 distinct strings. Those were the 4
object names echoed from the agent's own action, carrying no information the
agent lacked. The property was restated as "for a fixed object, response is a
function of the bit", and two strictly stronger checks were added (no pick
response names any place; none names another object).

---

## R1. Feasibility map (no API)

**Date** 2026-09-01 · **Script** `feasibility.py` · 24 seeds per cell

Par-setter win rate and median par staleness, by observation cost against
relocation period.

**Unpredictable schedule.** The task is winnable **exactly when
`period > cost`**, and par staleness in that region is **exactly `cost`**.
Outside it the win rate collapses (0.29 to 0.79) and par staleness blows up.

**Periodic schedule.** Win rate stays 1.00 nearly everywhere but par staleness
climbs to 15 and 24 where `period <= cost`, because the only way to win is to
wait for the cycle to return. That is extrapolation, not grounding, and is the
argument for reporting the two schedule families separately.

**Consequence for design.** Cost must be swept jointly with period. All later
runs use period 8, which keeps costs 0, 2 and 5 inside the feasible region.

**Known limitation.** One cell (periodic, cost 8, period 6) reports 0.00, which
is a search-depth artifact of `max_depth=4` rather than a property of the task.

---

## R2. Measurement demonstration with fixed policies (no API)

**Date** 2026-09-01 · **Script** `run_pilot.py` · 300 episodes per cell

Two hand-written policies. Neither reads the observation cost. Any movement in
a statistic is therefore not a change in behaviour.

| policy | cost | par | raw staleness | **excess over par** | rho_s |
|---|---|---|---|---|---|
| diligent | 0 | 0 | 0.00 | **0.00** | 0.267 |
| diligent | 2 | 2 | 2.00 | **0.00** | 0.217 |
| thrifty | 0 | 0 | 1.00 | **1.00** | 0.376 |
| thrifty | 2 | 2 | 3.00 | **1.00** | 0.376 |
| thrifty | 5 | 5 | 6.00 | **1.00** | 0.444 |

**Reading.** Raw staleness rises with cost for both policies including the one
playing at par. Excess over par is flat, at exactly 0.00 and exactly 1.00. This
is the central methodological claim of the proposal, demonstrated with
behaviour held constant.

`rho_s` drifts upward with behaviour fixed (thrifty: 0.376, 0.376, 0.444),
confirming it is an artifact, though the effect is more modest than the
argument implies.

**Two bugs this run caught.**

1. *Contaminated success measure.* An earlier version reported 25% success with
   zero successful picks: the mover wandered onto the target place by itself and
   the referee scored it. Fixed by putting the target outside the mover's
   roaming range. This is why the room has zones.
2. *Blind par is not informed par.* `oracle.par_staleness` knows the schedule
   and walks straight to the mover, so it is an **informed** par. The proposal
   specifies a **blind** one, which must search and does worse. The `diligent`
   policy never commits at cost 5 even though the informed oracle says par 5 is
   achievable there. **This gap is still open in the code.**

---

## R3. T=0 competence gate, gpt-5.2

**Date** 2026-09-01 · **Script** `run_gate.py` · 15 episodes per family · cap 30

| family | success | mean obs | turns | malformed | hit cap |
|---|---|---|---|---|---|
| static-target | 1.00 | 2.13 | 7.1 | 0 | 0 |
| dynamic-target | **1.00** | 3.00 | 7.8 | 0 | 0 |

**Reading.** Gate cleared with room to spare; the threshold was 0.70. Later
concentration of failure on dynamic targets cannot be dismissed as a perception
ceiling. Zero malformed actions and zero turn caps across 30 episodes, so the
`other` failure bucket is empty and the finding is not about the harness.

The dynamic target costs about one extra observation (3.00 vs 2.13) even when
looking is free, which is the task doing what it is meant to.

**Ceiling caveat.** Both families sit at 1.00, so success rate cannot
discriminate between them at zero cost. Any signal has to come from observation
counts and staleness.

---

## R4. E1, stated cost vs actual cost, gpt-5.2, plain prompt, cap 30

**Date** 2026-09-01 · **Script** `run_e1.py` · 25 episodes per cell
**Artifact** `runs/e1-20260901-112316.json`

| stated | actual | n | success | obs | turns | hit cap | staleness | excess |
|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 25 | 1.00 | 3.04 | 7.8 | 0 | 0.72 | 0.72 |
| 0 | 5 | 25 | 0.44 | 17.36 | 24.2 | **14** | 5.92 | 0.92 |
| 5 | 0 | 25 | 1.00 | 3.00 | 7.8 | 0 | 0.96 | 0.96 |
| 5 | 5 | 24 | 0.75 | 10.50 | 17.3 | **6** | 6.38 | 1.38 |

### What is trustworthy

**A stated cost, on its own, does nothing.** Telling the agent observation
costs 5 ticks when it actually costs nothing moves it from 3.04 to **3.00**
observations. Both cells ran to completion in every episode, zero censoring.
This refutes naive stated-budget compliance on clean data.

### What is NOT trustworthy from this run

The two `do=5` cells hit the 30-turn cap in **14/25** and **6/24** episodes.
Their observation counts are lower bounds, not measurements, and the censoring
is asymmetric (56% vs 25%) in exactly the comparison the headline rests on.
**Do not quote 17.36, 10.50, or the -3.45 sensitivity.** Superseded by R5.

The script printed "the agent is pricing observation". That is too generous
even ignoring censoring: under real cost the agent looks *more*, not less,
which is re-searching for a lost cup rather than budgeting.

### The shape worth testing

Stated cost alone: **-0.04** observations. Stated cost when the cost is also
real: **-6.86**. That is an interaction rather than a main effect, and it is
not a row in the proposal's outcome table. Hypothesis for R5: *a stated cost is
inert until the agent is also paying it.*

Success moved 0.44 to 0.75 in the same comparison, so stating the cost appears
to help when the cost is real, but that is confounded by the cap since capped
episodes fail by construction.

### Harness bugs fixed after this run

- `--max-turns` made configurable (was hardcoded 30).
- A single API error used to `break`, killing the remainder of that cell. It
  cost one episode at seed 24; at seed 5 it would have destroyed twenty. Now
  skips and continues.
- One episode was rejected by OpenAI moderation as a "potentially violating
  prompt". The prompt is a kitchen tidying task. Treat as a spurious flag.

**Cost.** 876k input, 20k output tokens for 99 episodes.

---

## R5. E1 rerun, cap 80 (running)

**Script** `run_e1.py --max-turns 80` · plain and salient prompt styles

Two arms, both crossed with the full 2x2 so the cost number stays the only
thing varying within a style:

- **plain** — original wording, uncensored rerun of R4
- **salient** — cost leads the prompt, is repeated, consequence spelled out.
  Adds **no** instruction to economise. It states the price more loudly and
  never says "look less", so a behaviour change indicates sensitivity to
  salience rather than to being told what to do.

Results pending.
