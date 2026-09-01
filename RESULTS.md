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

## R5. T=0 competence gate across a model ladder

**Date** 2026-09-01 · **Script** `run_gate.py` · 12 episodes per family · cap 30

| model | dynamic success | obs | turns | malformed | hit cap |
|---|---|---|---|---|---|
| gpt-5.2 | 1.00 | 3.00 | 7.8 | 0 | 0 |
| gpt-4.1 | 1.00 | 4.08 | 9.1 | 0 | 0 |
| gpt-4o-mini | 0.92 | 4.58 | 9.5 | 0 | 1 |
| gpt-3.5-turbo | **0.75** | **8.33** | 15.6 | **1** | **2** |

All four clear the 0.70 threshold, so all are eligible for the sweep, but the
gradient is monotonic in both success and effort: the weakest model needs 2.8x
the observations of the strongest to do the same job with looking free.

**This is the first evidence the harness is sound rather than lucky.** The
`other` failure bucket sat at exactly zero for every strong model. It moves
only on gpt-3.5-turbo (1 malformed action, 2 turn caps). A harness that
produced parse failures everywhere, or nowhere regardless of model, would be
suspect. This is the pattern a working one produces.

---

## R6. Full cost grid, gpt-5.2, plain prompt

**Date** 2026-09-01 · **Script** `run_grid.py` · 50 episodes per cell · cap 120
**Artifact** `runs/grid-gpt-5.2-plain-random-dynamic-target-*.json`
449 episodes (1 skipped by a spurious moderation flag), 1235s, 10 workers.

Mean observations, stated cost down the side, actual cost across:

| stated \ actual | 0 | 2 | 5 |
|---|---|---|---|
| **0** | 3.66 | 8.69 | 23.74 |
| **2** | 3.44 | 9.12 | 20.70 |
| **5** | 3.32 | 6.96 | 16.36 |

**Censoring is not a problem here.** 2 turn-cap hits across 449 episodes, and
zero malformed actions. Unlike R4, these numbers are quotable.

### The main result

Effect of raising the **stated** cost from 0 to 5, at each level of real cost:

| real cost | effect of stating 5 instead of 0 |
|---|---|
| 0 | **-0.34** observations |
| 2 | **-1.73** |
| 5 | **-7.38** |

Monotonic across three levels. Averaged over actual cost the stated effect is
-3.15 observations; the actual-cost effect is **+16.79**, five times larger.

**Reading.** A stated cost is close to inert on its own. Telling the agent
observation costs 5 ticks when it costs nothing changes behaviour by a third of
one observation, from 3.66 to 3.32, on 50 episodes per cell. The statement's
bite grows in proportion to what the agent is actually paying. This is an
interaction, not a main effect, and it replicates the R4 corners at higher
power with three levels instead of two.

The rise in observations with real cost (+16.79) is **not** economising. The
agent looks *more* when looking is expensive, because it keeps losing the mover
and has to re-search. Cost drives effort up, not down.

### Success and staleness

Success stays high (1.00 everywhere except 0.86, 0.94, 0.94 at real cost 5), so
success rate is near ceiling and cannot carry the analysis. Observation count
and staleness are the informative measures, as anticipated in R3.

Excess staleness over par by cell: 0.58, 1.06, 1.04, 0.84, 1.38, **10.16**,
0.98, 0.94, 4.00.

**Open anomaly.** The `say=2 do=5` cell shows excess 10.16 against 1.04 at
`say=0 do=5` and 4.00 at `say=5 do=5`. That is non-monotonic and unexplained at
n=50. It should be checked against the transcripts before any claim rests on
staleness. Do not build the story on the staleness column until this is
understood.

**Cost.** 7,039k input, 117k output, about $14 at gpt-5.2 rates.

---

## R7. Remaining grids: salience, predictability, and the matched control

**Date** 2026-09-01 · **Script** `run_grid.py` via `queue.ps1` · 50 per cell · cap 120
**Consolidated by** `analyze.py`, which reads the `*-summary.json` files.

Change in mean observations from stating a price of 5 rather than 0:

| condition | charged 0 | charged 5 |
|---|---|---|
| moving target, unpredictable (R6) | **-0.34** | -7.38 |
| moving target, unpredictable, salient prompt | **-0.74** | -8.64 |
| moving target, periodic relocation | **+0.34** | -14.27 |
| **fixed target, matched control** | **-0.08** | **-0.04** |

1798 episodes across four grids. 6 turn-cap hits total (0.3%), 1 malformed
response. Censoring is not a concern at cap 120.

**The headline replicates in every condition.** Every entry in the
charged-0 column falls within +/-0.75 observations. A stated price does
essentially nothing on its own whether the warning is loud or quiet, and
whether the world is predictable or not.

**The matched control is flat, which is the most important row.** Mean
observations sit at ~2.0 in all nine cells with success 1.00 throughout, and
neither parameter moves anything. Whatever the price does in the moving-target
family, it is specific to needing current information rather than a generic
reaction to being charged. Without this row the result would be far weaker.

**Salience is not the missing ingredient.** Making the warning prominent takes
the charged-0 effect from -0.34 to -0.74, which is twice a very small number.

**Predictability changes magnitude, not shape.** Periodic relocation leaves the
charged-0 effect at +0.34 and gives the largest charged-5 effect (-14.27).
Under free or cheap observation the agent exploits the cycle and uses only
~1.1-1.6 observations, against 3.4-9 under an unpredictable schedule.

### Confound found in our own salient prompt

The salient arm uses fewer observations overall (15.86 vs 23.74 at say=0,
do=5). The prompt asserts "observing is by far the most expensive thing you can
do" regardless of the stated number, which is false when that number is 0 and
amounts to a frugality instruction. It was introduced on the explicit claim
that it added no such instruction. **Within-arm comparisons hold; absolute
levels are not comparable to the plain arm.** Fixing this requires rewording
and rerunning that arm.

---

## R8. Capability ladder: abandoned

gpt-4.1 was launched over the full grid and hit sustained rate limiting,
skipping large numbers of episodes rather than completing cells. gpt-4o-mini
and gpt-3.5-turbo were never started. The partial gpt-4.1 data is not used.

All agent-facing claims therefore rest on gpt-5.2 alone. The T=0 gate in R5
remains valid for all four models, since those runs completed, but no grid
exists for any model other than gpt-5.2.

---

## R9. Blind par, and a correction to R6's reading

**Date** 2026-09-01 · **Script** `blind_par.py` · 200 seeds per policy

Closes the open item from R2. `oracle.par_staleness` is *informed*: it searches
against the true world and so walks straight to the mover. `blind_par.py`
instead takes the best mean over a class of 18 blind policies (6 sweep orders x
{commit-on-sight, walk-then-look, refresh-in-place}) on the same seeds the
agent saw. That is a policy-class best, not a proven optimum, so it
**upper-bounds** the true blind optimum and the excesses below are **lower
bounds**.

| charged | blind par | slack | agent excess, stated 0 | stated 5 |
|---|---|---|---|---|
| 0 | 1.94 | +7 | +1.73 | +1.38 |
| 2 | 1.94 | +1 | +6.75 | +5.03 |
| 5 | 8.01 | -8 | +15.73 | +8.35 |

**The agent never approaches par**, running 1.7x the blind optimum even when
observation is free, and its excess grows with the charged price.

**Correction to how R6 was read.** Par being identical at charged 0 and 2 was
first taken to mean a charged price of 2 does not make the task harder. That is
wrong. "Slack" above is the ticks an optimal sweep leaves before the mover
first relocates at tick 8: seven at charged 0, **one** at charged 2, and
negative at charged 5. Cost 2 does not raise the minimum observation count but
converts a forgiving task into a knife-edge one, where any wasted observation
restarts the search. Par is unaffected only because an optimal player never
reaches that edge; the agent, already above par, falls off it repeatedly. This
is the mechanism behind "charging raises effort rather than lowering it".

**Proportional effects.** The stated-price effect is monotonic in relative as
well as absolute terms: -9.3%, -19.9%, -31.1% at charged 0, 2, 5. This rules
out the objection that the interaction is a floor artifact of there being more
to cut when totals are larger.

---

## R10. Does the agent notice the false price?

**Date** 2026-09-01 · **Script** `check_lie_detection.py`

The tick counter appears in every environment reply, so in the quoted-5,
charged-0 cell an agent could in principle detect that the quoted price is
false and discount it on rational grounds. That reading would invert the
paper's claim, turning insensitivity into competence.

Across all **204 transcripts** in that cell, 12% mention cost at all and
**none** contains any reasoning about the quoted price differing from the
observed one. The agent is not discounting a price it has caught out.

Cost language does track the **charged** price: it appears in 22% of episodes
at charged 0 against 57% at charged 5, while moving from 30% to 39% across the
quoted price. Converging evidence for the behavioural result, from the model's
own words rather than its action counts.

---

## Open items

1. **Unexplained staleness cell.** `say=2 do=5` gave excess 10.16 against 1.04
   and 4.00 either side of it. No claim rests on the staleness column.
2. **Salient prompt confound** (R7). Needs rewording and a rerun of that arm.
3. **Success is near ceiling**, so observation count carries every analysis.
4. **Par is a policy-class best**, not a proven optimum. A better blind policy
   would widen the reported excesses, not narrow them.
5. **Episodes are independent**, so this measures within-episode use of a
   quoted price. Whether an agent could learn to discount a repeatedly false
   price across episodes is untested.
6. **`place` does not require travel** to the destination, making the task one
   action shorter than the description implies. Applies identically in every
   cell.
