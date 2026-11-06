---
description: "`verify`: the bridge from a `WorldImpl` to a `Timeline` — `SimConfig` (dt, steps, sample_every), `simulate` (copy the initial state, run `WorldSimulatorImpl`, stamp sample times, apply an optional environmental-pressure overlay) and `verify`/`VerifyResult` (baseline and perturbed simulation scored by a predicate). Source: `src/alienbio/suite/verify.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Verify](ha://p/ABIO%20Verify) 
# ABIO Verify
The one function every generator, oracle and the runner call to integrate a world: `simulate`, plus the `SimConfig` it takes and a small reject-sampling helper.

![ABIO Verify](ABIO%20Verify.svg) 
*Sample times* is the topic behind the stamped `times` (every `sample_every` step plus the final step; ‡ `SimConfig` validates its fields at construction, T088).

`suite/verify.py` reimplements no physics: `simulate` hands the world's chemistry, compartment tree, flows and population laws to `WorldSimulatorImpl.from_chemistry` and runs it ([ABIO WorldSimulatorImpl](../ABIO%20bio/ABIO%20WorldSimulatorImpl.md), [ABIO WorldImpl](../ABIO%20bio/ABIO%20WorldImpl.md)). Nineteen suite modules import it: the runner simulates one `SimConfig` burst per turn ([ABIO Runner](ABIO%20Runner.md)), [ABIO Skeleton](ABIO%20Skeleton.md)'s `oracle` and every generator read their truth from it, [ABIO Boundedness](ABIO%20Boundedness.md) and the M27 archetypes simulate through it. The `pressure=` overlay is [ABIO EnvironmentalPressure](ABIO%20EnvironmentalPressure.md)'s. The `Timeline` is [ABIO Types](ABIO%20Types.md)'s. All four names are re-exported from `alienbio.suite`; the work cap and its three functions are not (`expr_heads` and `expr_experiment` import `check_sim_work` from here). The subsystem view is [ABIO-Bio-Engine](../../ABIO%20Architecture/ABIO-Bio-Engine.md).



## SimConfig Interface
A frozen dataclass: how long and how finely to integrate.

| SimConfig | |
| --- | --- |
| [dt](#^dt) | Step length in seconds |
| [steps](#^steps) | Number of steps |
| [sample_every](#^sample-every) | Steps between recorded states |

**dt**`: float = 0.1`
    A positive finite real (bool refused). The default horizon is `steps · dt` = 20 s; the runner's own default burst is `SimConfig(steps=10, sample_every=10)`, 1 s per turn. ^dt

**steps**`: int = 200`
    A positive int (bool refused); `0` raises `ValueError`. ^steps

**sample_every**`: int = 10`
    A positive int (bool refused); `0` raises `ValueError` at construction (it was a bare `ZeroDivisionError` from `simulate` before T088). ^sample-every



## verify Interface
Six functions, a cap, its nine weights and one result type.

| verify | |
| --- | --- |
| [simulate](#^simulate) | Integrate a world into a timeline |
| [verify](#^verify) | Simulate a world and its perturbation |
| [VerifyResult](#^verifyresult) | The predicate's verdict and both timelines |
| [MAX_EXPR_SIM_WORK](#^max-expr-sim-work) | Work an Expr head's simulations may cost together |
| [W_*](#^w-weights) | Per-term weights of one step's work |
| [work_terms](#^work-terms) | One step's work as `(what, count, weight)` terms |
| [step_work](#^step-work) | The work of one simulator step on a world |
| [sim_work](#^sim-work) | The work a world and `SimConfig` cost |
| [check_sim_work](#^check-sim-work) | Refuse simulations past the cap |

**simulate**`(world: WorldImpl, sim_cfg: SimConfig = SimConfig(), seed: Seed = Seed(0), pressure: Optional[EnvironmentalPressure] = None) -> Timeline`
    Copies `world.initial_state` (the world stays pristine), builds the simulator on that state's tree with `world.flow_objs` and `world.population_law_objs`, runs `steps` steps sampling every `sample_every`, and stamps `times = step · dt` for each sampled step and the final step (`steps = 25` gives `(0, 1, 2, 2.5)`). Deterministic in `(world, sim_cfg)`; `seed` matters only for a jittered pressure. With `pressure`, each sampled state is copied and scaled after the run. Compiled rate laws run here (M47.10); a callable `rate` is refused by `ReactionImpl` itself. ^simulate

**verify**`(world, perturbation, predicate, sim_cfg=SimConfig(), seed=Seed(0)) -> VerifyResult`
    `simulate(world)` and `simulate(perturbation(world))` under the same seed, then `predicate(baseline, perturbed)`. No caller in `src/`: `pipeline._draft_valid_world` and the Expr `verify` head run the same loop themselves with child seeds per attempt. ^verify

**VerifyResult**`(passed: bool, discard: bool, baseline: Timeline, perturbed: Timeline)`
    `discard` is `not passed`, the reject-sampling signal. ^verifyresult

**MAX_EXPR_SIM_WORK**` = 40_000_000`
    The integration work an Expr head (the `verify` expander, `predict_q`) may cost, in units of `sim_work` (one unit about 0.05 µs of CPU), summed over every simulation the head runs — both run two, the base world and its perturbation (`1c098be`, T091 AW; `d907f16`, T091 AY; `abf1194`, T091 BA). Over 20 measured shapes the weighted count costs 0.025–0.071 µs per unit, so a head at the cap costs about 2.8 s of CPU on the slowest shape (2 000 active flows); the largest work in use is 133 280 (the kinetics example's `predict_q`, two simulations of 80 steps × 833), 300× under the cap (`catalog/`, `tests/` and the scripted examples surveyed; AUP uses neither head). A simulation runs outside the evaluation clock: before `d907f16` the count left out compartments and fan-in, so a 575-byte spec (1 000 reactions × 1 000 compartments, 20 steps) held a load 72 s at 3 % of the cap then; before `abf1194` a death law counted one unit while walking every molecule, so a 689-byte spec held a load 27 s at 5 % of it. ^max-expr-sim-work

**W_MOLECULE** … **W_POPULATION_CARRY**
    Each weight is the measured CPU of one term divided by the unit (`abf1194`, T091 BA; the AY count charged every term one unit, while the terms cost from 0.06 µs to 137 µs): ^w-weights

| Weight | Value | Charges | Measured |
| --- | --- | --- | --- |
| `W_MOLECULE` | 1 | one pool in one compartment: state copy and subnormal flush | 0.06 µs |
| `W_COMPARTMENT` | 24 | the reaction pass's setup in one compartment; only when the chemistry has reactions, since `step` skips the pass otherwise | 1.2 µs |
| `W_REACTION_TERM` | 13 | each of a reaction's `1 + reactants + products`, per compartment: extent, rationing and writes walk them | 0.6–0.85 µs |
| `W_MODULATOR` | 6 | one modifier read by `_modulation_factor`, per compartment | 0.15–0.4 µs |
| `W_RATE_LAW_NODE` | 3 | one compiled rate-law node evaluated by `eval_rate`, per compartment | 0.12–0.22 µs |
| `W_FLOW` | 14 | one transport flux: demand and ration | with `W_FLOW_SPECIES`, 0.85 µs idle to 2.4 µs moving |
| `W_FLOW_SPECIES` | 20 | each species in a `TransportFlux`'s stoichiometry | (above) |
| `W_POPULATION_LAW` | 44 | one population law's contribution and ration | 2.2 µs |
| `W_POPULATION_CARRY` | 7 | per law per molecule once any law moves content (a death that releases, a growth that draws, a count flow): `apply_population_laws` then walks every molecule for every carry | 0.26–0.47 µs per molecule |

**work_terms**`(world: WorldImpl) -> list[tuple[str, int, int]]`
    The terms of one step as `(what, count, weight)`: molecules × compartments; compartments with a reaction pass (0 with no reactions); reaction terms (`1 + reactants + products`) × compartments; modulators × compartments; rate-law nodes × compartments; flows; flow species (summed over `TransportFlux` stoichiometries); population laws; population carries (laws × molecules, 0 unless a law moves content). Compartments count at least 1; every reaction counts in every compartment (`from_chemistry` runs each in all of them). The rate-law tree is counted iteratively, so a deep one cannot overflow the stack (`d907f16`, T091 AY). ^work-terms

**step_work**`(world: WorldImpl) -> int`
    One step's work: `Σ count × weight` over `work_terms(world)` (`abf1194`, T091 BA). ^step-work

**sim_work**`(world: WorldImpl, cfg: SimConfig) -> int`
    `steps × step_work(world)`, the per-step term at least 1: the work of one simulation. ^sim-work

**check_sim_work**`(head: str, worlds: Sequence, cfg) -> None`
    Raises `ValueError` when the summed `sim_work` of `worlds` passes `MAX_EXPR_SIM_WORK`, naming the head, the number of simulations, the work, each simulation's `steps x work per step` (these sum to the total), the cap, and the heaviest simulation's world with its nonzero `count what x weight` terms (these sum to that world's per-step work; an empty world reads `1`) (`abf1194`, T091 AZ7). A `cfg` that is not a `SimConfig` skips the check, and so does a sequence holding no `WorldImpl` (non-worlds are dropped from the sum): the simulator's own validation owns that verdict. Called by `predict_q` with `(world, world)` before its recipe, and by the `verify` expander with `(w, w)` before each attempt's base simulation and `(w, w_pert)` after the perturbation ([ABIO ExprHeads](ABIO%20ExprHeads.md), [ABIO ExprExperiment](ABIO%20ExprExperiment.md)); `simulate` itself and the runner are not capped by it. ^check-sim-work




# Verify Semantics

## Sample times
The simulator's `run` returns one state per sampled step plus the final one; `simulate` derives the step indices the same way and zips them with the states, so the two must agree (they do: 25 steps sampled every 10 gave four states at 0, 10, 20, 25). Times are `step · dt` from zero, so each per-turn burst the runner simulates is stamped from 0 again. `SimConfig.__post_init__` refuses a `dt` that is not a positive finite real and a `steps` or `sample_every` that is not a positive int, bool included, with `ValueError` `"SimConfig.<field> must be …"` (T088; before it, `sample_every = 0` raised `ZeroDivisionError` and a negative `steps` or `dt` reached the simulator).




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be`; the sample times, `steps = 0` and the `sample_every = 0` crash confirmed on a two-molecule world from the HEAD export, the importer list by `git grep`, no spend.
- 2026-10-28 — refreshed against `9db219f`: `SimConfig` validates `dt`, `steps`, `sample_every` at construction; the module docstring names compiled rate laws.
- 2026-11-06 — refreshed for `1c098be` (T091 AW): new `MAX_EXPR_SIM_WORK`, `sim_work` and `check_sim_work`, the work cap the Expr `verify` expander and `predict_q` check before each simulation. The figure draws `simulate` and its callers, not the Expr heads' cap: still true.
- 2026-11-06 — refreshed for `d907f16` (T091 AY, after verifier AX1): `MAX_EXPR_SIM_WORK` is 4 000 000 and bounds the summed work of every simulation a head runs; new `step_work` counts each reaction's fan-in, fan-out, modulators and rate-law nodes in every compartment; `check_sim_work` takes a sequence of worlds. The pass-12 blocks were corrected in place. The figure draws `simulate` and its callers, not the cap: still true.
- 2026-11-06 — refreshed for `abf1194` (T091 AZ1-AZ3, AZ7): `step_work` is the weighted sum of the new `work_terms`; new block for the nine `W_*` weights (a table); `MAX_EXPR_SIM_WORK` is 40 000 000 (about 2.8 s at the cap on the slowest shape, 300× the largest in use); `check_sim_work`'s refusal lists each simulation's work and the heaviest world's terms. The AY-era cap and `step_work` blocks were corrected in place. The figure draws `simulate` and its callers, not the cap: still true.
