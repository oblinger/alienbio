---
description: "`verify`: the bridge from a `WorldImpl` to a `Timeline` — `SimConfig` (dt, steps, sample_every), `simulate` (copy the initial state, run `WorldSimulatorImpl`, stamp sample times, apply an optional environmental-pressure overlay) and `verify`/`VerifyResult` (baseline and perturbed simulation scored by a predicate). Source: `src/alienbio/suite/verify.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Verify](ha://p/ABIO%20Verify) 
# ABIO Verify
The one function every generator, oracle and the runner call to integrate a world: `simulate`, plus the `SimConfig` it takes and a small reject-sampling helper.

![ABIO Verify](ABIO%20Verify.svg) 
*Sample times* is the topic behind the stamped `times` (every `sample_every` step plus the final step; ‡ `SimConfig` validates its fields at construction, T088).

`suite/verify.py` reimplements no physics: `simulate` hands the world's chemistry, compartment tree, flows and population laws to `WorldSimulatorImpl.from_chemistry` and runs it ([ABIO WorldSimulatorImpl](../ABIO%20bio/ABIO%20WorldSimulatorImpl.md), [ABIO WorldImpl](../ABIO%20bio/ABIO%20WorldImpl.md)). Nineteen suite modules import it: the runner simulates one `SimConfig` burst per turn ([ABIO Runner](ABIO%20Runner.md)), [ABIO Skeleton](ABIO%20Skeleton.md)'s `oracle` and every generator read their truth from it, [ABIO Boundedness](ABIO%20Boundedness.md) and the M27 archetypes simulate through it. The `pressure=` overlay is [ABIO EnvironmentalPressure](ABIO%20EnvironmentalPressure.md)'s. The `Timeline` is [ABIO Types](ABIO%20Types.md)'s. All four names are re-exported from `alienbio.suite`. The subsystem view is [ABIO-Bio-Engine](../../ABIO%20Architecture/ABIO-Bio-Engine.md).



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
Two functions and one result type.

| verify | |
| --- | --- |
| [simulate](#^simulate) | Integrate a world into a timeline |
| [verify](#^verify) | Simulate a world and its perturbation |
| [VerifyResult](#^verifyresult) | The predicate's verdict and both timelines |

**simulate**`(world: WorldImpl, sim_cfg: SimConfig = SimConfig(), seed: Seed = Seed(0), pressure: Optional[EnvironmentalPressure] = None) -> Timeline`
    Copies `world.initial_state` (the world stays pristine), builds the simulator on that state's tree with `world.flow_objs` and `world.population_law_objs`, runs `steps` steps sampling every `sample_every`, and stamps `times = step · dt` for each sampled step and the final step (`steps = 25` gives `(0, 1, 2, 2.5)`). Deterministic in `(world, sim_cfg)`; `seed` matters only for a jittered pressure. With `pressure`, each sampled state is copied and scaled after the run. Compiled rate laws run here (M47.10); a callable `rate` is refused by `ReactionImpl` itself. ^simulate

**verify**`(world, perturbation, predicate, sim_cfg=SimConfig(), seed=Seed(0)) -> VerifyResult`
    `simulate(world)` and `simulate(perturbation(world))` under the same seed, then `predicate(baseline, perturbed)`. No caller in `src/`: `pipeline._draft_valid_world` and the Expr `verify` head run the same loop themselves with child seeds per attempt. ^verify

**VerifyResult**`(passed: bool, discard: bool, baseline: Timeline, perturbed: Timeline)`
    `discard` is `not passed`, the reject-sampling signal. ^verifyresult




# Verify Semantics

## Sample times
The simulator's `run` returns one state per sampled step plus the final one; `simulate` derives the step indices the same way and zips them with the states, so the two must agree (they do: 25 steps sampled every 10 gave four states at 0, 10, 20, 25). Times are `step · dt` from zero, so each per-turn burst the runner simulates is stamped from 0 again. `SimConfig.__post_init__` refuses a `dt` that is not a positive finite real and a `steps` or `sample_every` that is not a positive int, bool included, with `ValueError` `"SimConfig.<field> must be …"` (T088; before it, `sample_every = 0` raised `ZeroDivisionError` and a negative `steps` or `dt` reached the simulator).




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be`; the sample times, `steps = 0` and the `sample_every = 0` crash confirmed on a two-molecule world from the HEAD export, the importer list by `git grep`, no spend.
- 2026-10-28 — refreshed against `9db219f`: `SimConfig` validates `dt`, `steps`, `sample_every` at construction; the module docstring names compiled rate laws.
