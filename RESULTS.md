# Results

Every number below is produced by a script in this repo against a run saved
under `runs/`. Model is `gpt-5.2` throughout. 3,046 episodes in total.

Notation: **T_say** is the per-look cost named in the prompt, **T_do** is the
latency the world charges to its clock, and **P** is the mover's dwell, how
long it stays put before relocating.

---

## Preconditions

**Channel audit.** `test_channel_audit.py`, six sections, all passing.

- Only `ObserveResult` carries object identity, checked structurally.
- Navigation, failed picks, `place`, `done` and malformed actions render
  byte-identical across 60 worlds differing only in object placement.
- `pick` reveals at most the single bit of whether the named object is here:
  grouped by (object, co-located), every response collapses to one string, and
  no response names a place or another object.
- Tick counts after a fixed action sequence do not vary with placement, and a
  failed `pick` costs exactly what a successful one costs, so the clock is not
  a side channel.
- An observation reports the scene before its cost is charged.
- `observe`, `pick` and the referee resolve against the same clock; the clock
  shown to the agent is monotone; a deadline is never overshot.

**Feasibility** (`feasibility.py`, 24 seeds per cell). Under an unpredictable
schedule the task is winnable **exactly when `P > T_do`**, and par staleness in
that region is **exactly `T_do`**. Outside it the win rate collapses. Under a
periodic schedule the win rate holds but par staleness climbs to 15-24 where
`P <= T_do`, because the only way to win is to wait for the cycle to come back;
that is extrapolation rather than grounding, which is why the two schedule
families are reported separately. All later runs use `P = 8`, keeping
`T_do` in {0, 2, 5} inside the feasible region.

**Competence gate** (`run_gate.py`, 15 episodes per family, `T_do = 0`).
Success **1.00** on both families, against a 0.70 threshold. Zero malformed
actions, zero turn caps. The dynamic target costs about one extra observation
even when looking is free (3.00 against 2.13), which is the task working as
intended. Both families sit at the success ceiling, so any signal has to come
from observation counts rather than success.

**Par** (`fair_par.py`). Blind, and the mean over all 120 sweep orders of the
five places, because the prompt never tells the agent which three the mover can
occupy and a blind player cannot choose the lucky order.

| T_do | par | best order |
|---|---|---|
| 0 | 3.00 | 1.92 |
| 2 | 4.77 | 1.92 |
| 5 | 14.71 | 8.45 |

At `T_do = 0` this matches theory: the mover's place has expected rank
`(1+2+3+4+5)/5 = 3`. With the mover fixed for the episode, par is **3.00 at
every T_do**, since a costlier look cannot make a stationary target harder to
find. Par is a policy-class mean rather than a proven optimum, so excesses
above it are lower bounds.

---

## Main grid: T_say x T_do, P = 8

`run_grid.py`, 50 episodes per cell, 449 episodes, turn cap 120.

| T_do | T_say | obs | excess over par | success | turns |
|---|---|---|---|---|---|
| 0 | 0 | 3.66 | +0.66 | 1.00 | 8.6 |
| 0 | 2 | 3.44 | +0.44 | 1.00 | 8.2 |
| 0 | 5 | 3.32 | +0.32 | 1.00 | 8.1 |
| 2 | 0 | 8.69 | +3.93 | 1.00 | 15.7 |
| 2 | 2 | 9.12 | +4.35 | 1.00 | 16.0 |
| 2 | 5 | 6.96 | +2.19 | 1.00 | 12.7 |
| 5 | 0 | 23.74 | +9.03 | 0.86 | 33.3 |
| 5 | 2 | 20.70 | +5.99 | 0.94 | 33.1 |
| 5 | 5 | 16.36 | +1.65 | 0.94 | 27.5 |

Par rises 4.90x across this range against the agent's 7.11x, so raw counts
overstate the behavioural component and the excess column is the one to read.
At `T_do = 5`, stating the true figure takes the agent from 9.03 above par to
1.65. At `T_do = 0` every excess is under 0.7, so there is little available to
cut and the arm is a weak test by construction.

**Effect sizes** (`effect_size.py`). Stating 5 rather than 0, per T_do, with
bootstrap intervals on the per-episode counts:

| T_do | cut | 95% CI |
|---|---|---|
| 0 | 0.34 | [-1.04, +0.34] |
| 2 | 1.73 | [-4.77, +1.28] |
| 5 | 7.38 | [-14.96, -0.02] |

At `T_do = 0` the difference is -0.34 with a Welch t of -0.95; the interval
includes zero.

---

## Replication of the four corners

`run_grid.py` restricted to `T_say, T_do` in {0, 5}, 200 episodes per cell,
798 episodes.

| T_say | T_do | obs | success | turns |
|---|---|---|---|---|
| 0 | 0 | 3.23 | 1.00 | 8.1 |
| 5 | 0 | 2.96 | 1.00 | 7.5 |
| 0 | 5 | 23.01 | 0.87 | 33.5 |
| 5 | 5 | 13.79 | 0.97 | 24.1 |

**The interaction** (`interaction.py`), bootstrapping episodes within cells:

| metric | estimate | 95% CI |
|---|---|---|
| observations | **-8.94** | [-12.16, -5.82] |
| success | **+0.11** | [+0.06, +0.16] |
| turns | -8.91 | [-13.18, -4.67] |

All three exclude zero. The same interaction read off the 50-per-cell grid is
-7.04 with an interval of [-14.50, +0.46], which includes zero, so the smaller
grid cannot resolve this contrast and the replication is what establishes it.

**The gain is Pareto.** Success rises 0.87 to 0.97 while observation falls
23.01 to 13.79 and turns 33.5 to 24.1. Nothing is traded away, so the
behaviour at `T_say = 0` is better described as inefficient than as well
adapted to the cost.

---

## Controls

Both remove staleness while leaving `T_do` applied exactly as before. They are
not equally informative.

**Frozen mover, `P = 2000`** (`run_grid.py --family slow-target`, 450
episodes). Keeps the cup as the target, so the object, the five-place search
and par are unchanged and only the going-stale is removed. Verified before the
run: over 200 seeds the cup lands 74/65/61 across the three roaming places and
moves in 0 of 200 within 700 ticks.

| T_do | T_say=0 | T_say=2 | T_say=5 |
|---|---|---|---|
| 0 | 3.16 | 3.28 | 3.14 |
| 2 | 3.50 | 3.36 | 3.38 |
| 5 | 3.50 | 3.48 | 3.16 |

Success **1.00 in all nine cells**. Raising `T_do` from 0 to 5 changes
observation by **+0.34**, CI [-0.34, +1.00]. The interaction that is -8.94 with
the mover moving is **-0.32**, CI [-1.22, +0.56]. Both include zero.

This is not a ceiling artifact. The measure retains variance: 6 distinct counts
spanning 1 to 6, standard deviation **1.64**. And the agent spends 23.74
observations with the mover moving at `T_do = 5` against 3.50 with it frozen at
the same `T_do`, so wasteful looking is affordable at that latency and simply
not taken once nothing invalidates the answer.

**Immobile target** (`--family static-target`, 450 episodes). Replaces the cup
with the bowl. Observation sits between 1.98 and 2.06 across all nine cells at
success 1.00. Reported for completeness only: swapping the target changes its
identity and the difficulty of the task along with its mobility, and the
measure has almost no variance to explain, with 442 of 450 episodes at exactly
two observations and a standard deviation of 0.25. The frozen-mover arm is the
control the comparison rests on.

---

## Other conditions

`run_grid.py` via `queue.ps1`, 50 per cell, cap 120. Change in mean
observations from stating 5 rather than 0:

| condition | T_do = 0 | T_do = 5 |
|---|---|---|
| moving, unpredictable | -0.34 | -7.38 |
| moving, unpredictable, salient prompt | -0.74 | -8.64 |
| moving, periodic relocation | +0.34 | -14.27 |
| immobile target | -0.08 | -0.04 |

Across four grids, 6 turn-cap hits total (0.3%) and 1 malformed response, so
censoring is not a factor at cap 120.

**A stated figure does little on its own in every condition**, whether the
warning is prominent or quiet and whether the world is predictable or not:
every `T_do = 0` entry falls within +/-0.75 observations.

**Predictability changes magnitude, not shape.** Periodic relocation gives the
largest `T_do = 5` effect (-14.27). Under free or cheap observation the agent
exploits the cycle and uses only 1.1-1.6 observations, against 3.4-9 under an
unpredictable schedule.

---

## Where the observations go

`selectivity.py`, 449-episode grid. Each observation is classified by what it
could contribute: a first look at a place, a repeat of a place already found
empty, a sighting of the mover not acted on, and the single sighting the
successful pick was made from, capped at one per episode by construction.

| T_do | T_say | first | repeat | sighting | the pick's | total |
|---|---|---|---|---|---|---|
| 0 | 0 | 2.24 | 0.00 | 0.42 | 1.00 | 3.66 |
| 0 | 5 | 2.30 | 0.00 | 0.04 | 0.98 | 3.32 |
| 2 | 0 | 2.96 | 2.71 | 2.02 | 1.00 | 8.69 |
| 2 | 5 | 3.04 | 2.28 | 0.66 | 0.98 | 6.96 |
| 5 | 0 | 3.98 | 15.18 | 3.76 | 0.82 | 23.74 |
| 5 | 5 | 3.52 | 9.84 | 2.16 | 0.84 | 16.36 |

Proportion of each kind removed by stating 5 rather than 0, where negative
means more of them:

| T_do | first | repeat | sighting | the pick's |
|---|---|---|---|---|
| 0 | -3% | n/a | 90% | 2% |
| 2 | -3% | 16% | 67% | 2% |
| 5 | 12% | 35% | 43% | -2% |

Two readings. Most of the excess at `T_do = 5` is waste: 15.18 of the 23.74
observations are re-inspections of places already found empty. And the
reduction is a reallocation rather than uniform suppression, taking 35% of
those repeats and 12% of first looks while leaving the decisive sighting alone
to within 2%. `n/a` marks a kind absent from the baseline, so no proportion
exists; it is not a zero.

---

## Does the agent notice a figure the world does not charge?

`check_lie_detection.py`. The tick counter appears in every environment reply,
so at `T_say = 5, T_do = 0` an agent could in principle detect that the quoted
figure is false and discount it on rational grounds, which would invert the
reading of the result.

Across all 200 transcripts in that cell, 12% mention cost at all and **none**
contains any reasoning about the quoted figure differing from the observed one.
The agent does not remark on the discrepancy, which is not the same as showing
it fails to register it.

Cost language tracks the charged figure rather than the stated one, appearing
in 22% of episodes at `T_do = 0` against 57% at `T_do = 5`, while moving only
from 30% to 39% across `T_say`. That is converging evidence from the model's
own words rather than its action counts.

---

## Open items

1. **P was varied at two points**, so the effect is shown to vanish when the
   world stops and nothing is known about the shape in between. A world that
   changes slowly rather than not at all is the common case. A continuous sweep
   of `P` against a fixed `T_do` would separate an agent tracking the rate at
   which information decays from one that only detects whether the world moves.
2. **Success is at ceiling** in both control arms and in most of the main grid,
   so observation count carries every analysis.
3. **Par is a policy-class mean**, not a proven optimum. A better blind policy
   would widen the reported excesses rather than narrow them.
4. **Episodes are independent**, so this measures within-episode response to a
   stated figure, not whether an agent could learn across episodes to discount
   one it repeatedly found inaccurate.
5. **`place` does not require travel** to the destination, making the task one
   action shorter than the description implies. This applies identically in
   every cell.
6. **One model, one text environment.** The method should transfer; these
   magnitudes should not be expected to.
