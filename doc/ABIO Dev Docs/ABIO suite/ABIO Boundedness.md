---
description: "`boundedness`: the opt-in F019 homeostasis gate — `static_bounded_fate` flags pools that are produced but never a reactant and fed by a boundary source, `repair_static` gives each a dilution sink, `simulate_boundedness` classifies every pool's growth over a trailing window, `check_boundedness` runs both into a `BoundednessReport`. Source: `src/alienbio/suite/boundedness.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Boundedness](ha://p/ABIO%20Boundedness) 
# ABIO Boundedness
The gate that asks whether any pool of an assembled world grows or collapses without bound, once as a graph walk over the reactions and once over a simulated trajectory.

![ABIO Boundedness](ABIO%20Boundedness.svg) 
*The two layers* is the topic behind the split: the static walk is necessary only, the window ratio is a heuristic (‡: what each one misreads).

`suite/boundedness.py` is opt-in: no generator, drafter or runner calls it, and `Skeleton.materialize` does not ([ABIO Skeleton](ABIO%20Skeleton.md)). Its one caller outside the tests is the Organism example's `bounded` guard (`catalog/examples/organism/helpers.py`), which raises `GuardViolation` naming every pool a report flags. The simulation is `suite/verify.simulate` over a `WorldImpl` ([ABIO WorldImpl](../ABIO%20bio/ABIO%20WorldImpl.md)); the amounts it reads are `WorldStateImpl.amount`; the repair builds its sink with `mk.R` and its chemistry with `mk.C` ([ABIO ChemistryImpl](../ABIO%20bio/ABIO%20ChemistryImpl.md)). Its static sibling for mass balance is [ABIO Conservation](../ABIO%20bio/ABIO%20Conservation.md); population laws are [ABIO PopulationLaw](../ABIO%20bio/ABIO%20PopulationLaw.md). Nothing here is re-exported from `alienbio.suite`. The subsystem view is [ABIO-Generators](../../ABIO%20Architecture/ABIO-Generators.md).



## boundedness Interface
Four functions; the defaults are module constants `_DEFAULT_THETA = 10.0`, `_DEFAULT_WINDOW = 0.25`, `_DEFAULT_REPAIR_RATE = 0.01` and the denominator floor `_EPS = 1e-9`. Every trip is logged at `WARNING`.

| boundedness | |
| --- | --- |
| [static_bounded_fate](#^static-bounded-fate) | Source-fed pools produced but never consumed |
| [repair_static](#^repair-static) | Add a dilution sink per flagged pool |
| [simulate_boundedness](#^simulate-boundedness) | Classify each pool over the window |
| [check_boundedness](#^check-boundedness) | Both layers in one report |

**static_bounded_fate**`(chemistry: ChemistryImpl) -> list[UnboundedPool]`
    Collects every molecule that is a product of some reaction, a reactant of none, and fed by a boundary source (a reaction with no reactants, `∅ → X`) directly or through a chain of reactions, sorted by name, each with a reason naming the producing reactions. Reads `chemistry.reactions` only: modifiers, flows and population laws count neither way. § [The two layers](#the-two-layers). ^static-bounded-fate

**repair_static**`(chemistry: ChemistryImpl, *, rate: float = 0.01) -> ChemistryImpl`
    Returns `chemistry` itself when nothing is flagged; otherwise a new chemistry named `f"{local_name}_bounded"` with one `pool → ∅` reaction `_boundedness/<pool>_dilution` at `rate` per flagged pool, molecules and atoms copied. Raises `ValueError` when that id already exists. Returns a chemistry, not a world: compartments, flows and population laws are the caller's to rebuild. ^repair-static

**simulate_boundedness**`(world: WorldImpl, seed: Seed = Seed(0), *, theta: float = 10.0, window: float = 0.25, sim_cfg: SimConfig = SimConfig()) -> BoundednessReport`
    Simulates `world`, finds the first sampled time at or after `t_end − window · horizon`, and for each molecule compares its total amount over compartments there with the final state: `factor = |final| / max(|start|, 1e-9)`. Diverging when `factor ≥ theta`; collapsing when `|start| > 1e-9` and `factor ≤ 1/theta`; else bounded. Raises `ValueError` on an empty timeline or a final state without `molecule_ids`. The report's `static_unbounded` is empty. Neither `theta` nor `window` is validated. ^simulate-boundedness

**check_boundedness**`(world_or_skeleton: WorldImpl | Skeleton, seed: Seed = Seed(0), *, theta, window, sim_cfg) -> BoundednessReport`
    Materializes a `Skeleton` under `seed` (a world is used as given), then returns `static_bounded_fate(world.chemistry)` and `simulate_boundedness(world, …)` in one report. Never repairs. ^check-boundedness



## BoundednessReport Interface
A frozen dataclass: the combined verdict.

| BoundednessReport | |
| --- | --- |
| [static_unbounded](#^static-unbounded) | Pools the static walk flagged |
| [dynamic](#^dynamic) | One trajectory per molecule |
| [diverging](#^diverging) | Trajectories classified diverging |
| [collapsing](#^collapsing) | Trajectories classified collapsing |
| [ok](#^ok) | Neither layer flagged anything |

**static_unbounded**`: tuple[UnboundedPool, ...] = ()`
    From `static_bounded_fate`; empty on a `simulate_boundedness` report. ^static-unbounded

**dynamic**`: tuple[PoolTrajectory, ...] = ()`
    One entry per molecule of the final state, in its id order. ^dynamic

**diverging**`: tuple[PoolTrajectory, ...]` (property)
    `dynamic` filtered to `"diverging"`. ^diverging

**collapsing**`: tuple[PoolTrajectory, ...]` (property)
    `dynamic` filtered to `"collapsing"`. ^collapsing

**ok**`: bool` (property)
    No static flag, nothing diverging, nothing collapsing. ^ok



## UnboundedPool Interface
A frozen dataclass: one static flag.

| UnboundedPool | |
| --- | --- |
| [name](#^name) | The molecule's name |
| [reason](#^reason) | The producing reactions, in words |

**name**`: str`
    The flagged molecule. ^name

**reason**`: str`
    `"produced by [ids] with no consuming reaction, sink, or dilution term"`. ^reason



## PoolTrajectory Interface
A frozen dataclass: one molecule's dynamic classification.

| PoolTrajectory | |
| --- | --- |
| [name](#^trajectory-name) | The molecule's id |
| [factor](#^factor) | Final over window-start amount |
| [classification](#^classification) | Diverging, collapsing or bounded |

**name**`: str`
    The molecule id. ^trajectory-name

**factor**`: float`
    `|final| / max(|start|, 1e-9)`. ^factor

**classification**`: str`
    `"diverging"`, `"collapsing"` or `"bounded"`. ^classification




# Boundedness Semantics

## The two layers
The static walk is per molecule, not per compartment, and reads stoichiometry alone. It is a necessary condition for an open system: a pool that is only ever produced grows while its producer runs. A closed world's terminal product is not flagged: `a → b → c` from `a = 1` with no source leaves `c` unflagged, mass conservation bounding it (T088 boundedness 1). It still misreads one shape: a source-fed pool consumed only by a population law (a growth law's resource) is flagged although it has a fate, since population laws are not reactions. An autocatalytic `x → 2x` passes the walk, `x` being a reactant; only the dynamic layer catches it.

The dynamic layer compares two samples, not a trend. A pool that is zero at the window's start and positive at the end reads as diverging (the floor makes the factor huge), and a pool already near zero that keeps decaying reads as collapsing: the batch world `a → b → c` flags `a` (1.4e-7 → 7e-10) and `b` as collapsing. `window = 0` puts the start at the final sample, so every factor is 1 and every pool reads bounded.



## Repair, not redraw
F019 Q2 = C: a static accumulator has one unambiguous fix, a dilution sink, so `repair_static` makes it. A dynamic divergence has no local fix that leaves the author's crux intact, so it is reported only; redrawing is the caller's.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be`; the closed-batch false flags (static `c`, collapsing `a` and `b`) and the vacuous `window = 0` confirmed by running `check_boundedness` on a three-pool world from the HEAD export, no spend. Consumer census: `catalog/examples/organism/helpers.py` and `tests/suite/test_boundedness.py`. Not determined: whether any generator should call it (T088 § suite/boundedness).
- 2026-10-28 — refreshed against `9db219f`: the static walk flags a produced-never-consumed pool only when a boundary source feeds it, so a closed world's terminal product is no longer flagged.
