# Observation tax pilot

Proof-of-concept code for the proposal *Stated Budgets, Real Costs: Do Agents
in Moving 3D Scenes Economise or Comply?*

A text room simulator standing in for a 3D scene, reduced to its decision
structure so the observation channel can be audited exactly. The agent cannot
see the room. The only way it learns anything is `observe(place)`, which costs
time, during which the moving object keeps moving.

## The one property that matters

No action other than `observe` may reveal where anything is. If that fails,
the agent gets free observations, the cost stops binding, and nothing
downstream means anything. `test_channel_audit.py` proves it four ways:

- **structural**, only `ObserveResult` carries object identity
- **invariance**, non-observe responses are byte-identical across worlds that
  differ only in object placement
- **pick channel**, per object, one distinct response per co-location bit, and
  no response names any place
- **clock**, identical tick traces, and a failed pick costs what a successful
  one costs

## Files

| file | what it does |
|---|---|
| `world.py` | the simulator, the action API, the referee |
| `test_channel_audit.py` | the leak test described above |
| `oracle.py` | *informed* par: best staleness by search against the true world |
| `blind_par.py` | superseded: swept only the roaming zone, see fair_par |
| `fair_par.py` | **par under the agent's own information**, the one to use |
| `check_lie_detection.py` | does the agent notice when the quoted price is false? |
| `analyze.py` | consolidates every completed grid into cross-run tables |
| `effect_size.py` | bootstrap intervals and headroom-normalised effects |
| `runs_io.py` | the one run loader: drops incomplete grids, newest per config |
| `feasibility.py` | which (cost, relocation period) cells are winnable at all |
| `run_pilot.py` | measurement demonstration using fixed policies, no API needed |
| `agent.py` | ReAct loop over an OpenAI model |
| `run_gate.py` | the `T=0` competence gate, the project's stop condition |
| `run_e1.py` | E1, stated cost crossed with actual cost |
| `results.txt` | captured output of the three API-free scripts |

## Running

No API key needed:

```
python test_channel_audit.py
python feasibility.py
python run_pilot.py
```

With a key, put it in `pilot/.env` as `OPENAI_API_KEY=sk-...` (gitignored):

```
python run_gate.py --list-models
python run_gate.py --model gpt-5.2 --episodes 15
python run_e1.py  --model gpt-5.2 --episodes 25
```

## Findings so far

**Channel audit passes** on all four checks.

**Feasibility is a law, not a mush.** Under an unpredictable schedule the task
is winnable exactly when `period > cost`, and par staleness in that region is
exactly `cost`. Outside it the win rate collapses. Under a periodic schedule
the win rate stays high but par staleness climbs to 15 and 24, because the only
way to win is to wait for the cycle to return. That is extrapolation rather
than grounding, which is the argument for reporting the two schedule families
apart.

**Raw numbers drift, par-relative ones do not.** With policies that are fixed
code and never read the cost, raw staleness at commitment rises with cost
(0, 2, 5 for the diligent policy; 1, 3, 6 for the thrifty one) while excess
over par stays flat at exactly 0.00 and exactly 1.00. `rho_s` also drifts
upward with behaviour held constant, which is why the proposal does not report
it.

## Two design decisions worth knowing about

**The room is split into a roaming zone and a fixed zone**, with the target
place outside the mover's range. Without the split the mover can wander onto
the target by itself and the referee scores a success the agent never earned,
which makes the success measure meaningless.

**Par is blind, and is the mean over sweep orders.** `oracle.par_staleness`
knows the schedule and walks straight to the mover, so it is an *informed* par
and no fair benchmark for an agent that cannot see. `fair_par.py` is the one
the analysis uses: it sweeps all five places, because the prompt never tells
the agent which three the mover can occupy, and it averages over all 120 orders,
because a blind player cannot choose the lucky one. Either shortcut, sweeping
only the roaming zone or taking the best order, grants knowledge the agent
lacks and overstates the headroom above par.

Par is **3.00, 4.77 and 14.71** at charged 0, 2 and 5, matching theory at
charged 0 where the mover's place has expected rank (1+2+3+4+5)/5 = 3.

**Charging makes the task harder for everyone**, which is why nothing is read
off raw counts. Par itself rises fivefold from charged 0 to 5, because an
optimal sweep starts losing the mover mid-search. The agent's *excess* above
par grows too, 0.66 to 3.92 to 9.03, so it degrades faster than the task does.
At charged 0 it runs only 1.22x par, so it is close to a blind optimum when
observation is free.
