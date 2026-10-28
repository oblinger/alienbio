---
description: "`PopulationLaw` + `PerCapitaGrowth`, `PerCapitaDeath`, `CountFlow` and `apply_population_laws`: the population pass on the multiplicity axis. Source: `src/alienbio/bio/population.py`."
---
:>> [[ABIO]] → [[ABIO Dev Docs]] → [ABIO PopulationLaw](ha://p/ABIO%20PopulationLaw) 
# ABIO PopulationLaw
The population pass: three count-based rate laws that grow, kill and move a compartment's `multiplicity`, and the one function that rations their summed demand off the frozen state.

![[ABIO PopulationLaw.svg|2400]] 
*The summed-demand ration* is the topic that governs the ration box (every law that draws a key short of its demand scales by the tightest ratio over the keys it draws); *Resource coupling and what is conserved* governs the `draws stoich·ΔN` edge.

The simulator's only path that writes `multiplicity` during a run (F017). This page covers the laws and `apply_population_laws`; the step that calls it is [[ABIO WorldSimulatorImpl]] (pass 3, after flows), the JAX host path is [[ABIO JaxWorldSimulator]], the molecule-pool sibling on the flow pass is [[ABIO TransportFlux]], and `ROUNDING_FLOOR` lives with [[ABIO RateExpr]]. The string-id specs that become these laws are `GrowthLaw`, `DeathLaw` and `CountFlowSpec` in `bio/world.py`; the subsystem view is [[ABIO-Bio-Engine]].



## PopulationLaw Interface
Abstract base for a typed, declarative count-based rate law: no callable rate, only fields. A law never mutates state; `contribute` reads the frozen start-of-step state and adds its deltas into dicts the caller owns, so order among laws does not matter. `__slots__` all the way down (the ABC base declares none of its own fields), so no attribute can be added; the fields have no setters but are not frozen — `_rate_constant` can still be assigned. Exported from `alienbio.bio` with the three subclasses.

| PopulationLaw | |
| --- | --- |
| [[#^init\|__init__]] | Store the name |
| [[#^name\|name]] | Human-readable name |
| [[#^contribute\|contribute]] | Add this law's deltas against the frozen state |
| [[#^attributes\|attributes]] | Semantic content for serialization |

**__init__**`(name: str = "") -> None`
    Store `name`. Each subclass computes a default name before calling it when its own `name` is empty. ^init

**name**`: str` (property)
    The name given or defaulted; the pass never reads it. ^name

**contribute**`(frozen: WorldStateImpl, dt: float, mult_delta: MultDelta, mol_delta: MolDelta) -> None` (abstract)
    Read `frozen` and add this law's Δmultiplicity into `mult_delta` and its Δconcentration into `mol_delta`. Never mutates `frozen` and never reads the dicts back. `apply_population_laws` hands each law a fresh pair, so a subclass may assume both start empty but must accumulate with `get(key, 0.0) +` regardless ([[#The summed-demand ration]]). ^contribute

**attributes**`() -> Dict[str, Any]` (abstract)
    A plain dict of the law's fields with a `"type"` tag; nothing in the repo reads it back. ^attributes



## PerCapitaGrowth Interface
Resource-coupled per-capita growth: `extent = rate_constant · N · [resource] · dt`, floored at 0, where `N` is the population compartment's multiplicity and `[resource]` is the resource concentration in `resource_compartment`. Bilinear, so growth slows as the pool draws down — logistic boundedness from nutrient limitation, no cap ([[#Resource coupling and what is conserved]]). Inherits `name`.

| PerCapitaGrowth | |
| --- | --- |
| [[#^percapitagrowth-init\|__init__]] | Build a growth law |
| [[#^compartment\|compartment]] | The population compartment that grows |
| [[#^resource-compartment\|resource_compartment]] | The compartment holding the resource |
| [[#^resource\|resource]] | The resource molecule id |
| [[#^stoich\|stoich]] | Resource amount drawn per new instance |
| [[#^rate-constant\|rate_constant]] | The rate constant `k` |
| [[#^compute-extent\|compute_extent]] | The unrationed rate off the frozen state |
| [[#^percapitagrowth-contribute\|contribute]] | Add growth and the resource draw |
| [[#^percapitagrowth-attributes\|attributes]] | Fields, tagged `per_capita_growth` |

**__init__**`(compartment: CompartmentId, resource_compartment: CompartmentId, resource: MoleculeId, stoich: float, rate_constant: float = 1.0, name: str = "") -> None`
    Store the fields; an empty `name` becomes `growth_at_{compartment}`. Nothing is validated: a negative `stoich` or `rate_constant` is stored as given, and ids are not checked against any state. `resource_compartment` may equal `compartment`. ^percapitagrowth-init

**compartment**`: CompartmentId` (property)
    The population compartment whose multiplicity grows. ^compartment

**resource_compartment**`: CompartmentId` (property)
    The compartment holding the resource pool. ^resource-compartment

**resource**`: MoleculeId` (property)
    Molecule id of the resource. ^resource

**stoich**`: float` (property)
    Resource AMOUNT consumed per new instance. `0.0` is the uncoupled configuration: growth happens and nothing is drawn, so the amount canary (`conservation.total_quantity`) fires — kept on purpose as the red half of F017's conservation test. ^stoich

**rate_constant**`: float` (property)
    `k`. ^rate-constant

**compute_extent**`(frozen: WorldStateImpl) -> float`
    `max(0, k · N · [resource])` read off `frozen`. This is a rate; `contribute` multiplies it by `dt`. The docstring calls it a Δmultiplicity, which it is only at `dt = 1`. ^compute-extent

**contribute**`(frozen: WorldStateImpl, dt: float, mult_delta: MultDelta, mol_delta: MolDelta) -> None`
    `raw = compute_extent(frozen) · dt`; returns at once when `raw ≤ 0`. With `stoich > 0`, when `stoich · raw` exceeds the resource AMOUNT in the frozen state the extent is scaled down to fit, so this one law alone never over-draws. Adds `+raw` to `mult_delta[compartment]` and, with `stoich > 0`, `−stoich · raw / (N_r · V_r)` to `mol_delta[(resource_compartment, resource)]`, the amount converted to a per-instance concentration with the frozen multiplicity and volume of the resource compartment. When that `N_r · V_r` is 0 the draw is skipped, but the available amount is then 0 too, so `raw` was already scaled to 0. ^percapitagrowth-contribute

**attributes**`() -> Dict[str, Any]`
    `type`, `name`, `compartment`, `resource_compartment`, `resource`, `stoich`, `rate_constant`. ^percapitagrowth-attributes



## PerCapitaDeath Interface
Per-capita death: `extent = rate_constant · N · dt`, floored at 0 and clamped to `N`. Optionally releases biomass to a named pool, the reverse of growth's draw; without a release, death is a pure multiplicity shrink. Inherits `name`.

| PerCapitaDeath | |
| --- | --- |
| [[#^percapitadeath-init\|__init__]] | Build a death law |
| [[#^percapitadeath-compartment\|compartment]] | The population compartment that shrinks |
| [[#^percapitadeath-rate-constant\|rate_constant]] | The rate constant `k` |
| [[#^release-compartment\|release_compartment]] | Compartment receiving released biomass |
| [[#^release-resource\|release_resource]] | Molecule receiving released biomass |
| [[#^release-stoich\|release_stoich]] | Amount released per death |
| [[#^percapitadeath-compute-extent\|compute_extent]] | The unrationed rate off the frozen state |
| [[#^percapitadeath-contribute\|contribute]] | Add the shrink and any release |
| [[#^percapitadeath-attributes\|attributes]] | Fields, tagged `per_capita_death` |

**__init__**`(compartment: CompartmentId, rate_constant: float = 1.0, release_compartment: Optional[CompartmentId] = None, release_resource: Optional[MoleculeId] = None, release_stoich: float = 0.0, name: str = "") -> None`
    Store the fields; an empty `name` becomes `death_at_{compartment}`. Nothing is validated. ^percapitadeath-init

**compartment**`: CompartmentId` (property)
    The population compartment whose multiplicity shrinks. ^percapitadeath-compartment

**rate_constant**`: float` (property)
    `k`. ^percapitadeath-rate-constant

**release_compartment**`: Optional[CompartmentId]` (property)
    Where released biomass goes; `None` for no release. ^release-compartment

**release_resource**`: Optional[MoleculeId]` (property)
    The molecule released biomass becomes; `None` for no release. ^release-resource

**release_stoich**`: float` (property)
    Resource AMOUNT released per death. A release happens only when this is `> 0` and both `release_compartment` and `release_resource` are set; any one missing silently means no release. ^release-stoich

**compute_extent**`(frozen: WorldStateImpl) -> float`
    `max(0, k · N)` read off `frozen`; a rate, as on growth. ^percapitadeath-compute-extent

**contribute**`(frozen: WorldStateImpl, dt: float, mult_delta: MultDelta, mol_delta: MolDelta) -> None`
    `raw = min(compute_extent(frozen) · dt, N)`; returns when `raw ≤ 0`. Adds `−raw` to `mult_delta[compartment]` and, when a release is configured, `+release_stoich · raw / (N_rel · V_rel)` to `mol_delta[(release_compartment, release_resource)]`. When the release compartment's frozen `N_rel · V_rel` is 0 the release is dropped and that biomass is lost. The clamp to `N` bounds this law alone; two deaths on one compartment are bounded by the ration ([[#The summed-demand ration]]). ^percapitadeath-contribute

**attributes**`() -> Dict[str, Any]`
    `type`, `name`, `compartment`, `rate_constant`, `release_compartment`, `release_resource`, `release_stoich`. `__repr__`, unlike this, omits the three release fields. ^percapitadeath-attributes



## CountFlow Interface
A size-class transition (maturation edge): moves `rate_constant · N_origin · dt` of multiplicity from `origin` to `dest`, floored at 0 and clamped to `N_origin`. The same extent leaves and enters, so headcount is conserved exactly; molecule amount is not ([[#Resource coupling and what is conserved]]). The multiplicity-axis parallel of [[ABIO TransportFlux]]. Inherits `name`.

| CountFlow | |
| --- | --- |
| [[#^countflow-init\|__init__]] | Build a count flow |
| [[#^origin\|origin]] | The compartment counts leave |
| [[#^dest\|dest]] | The compartment counts enter |
| [[#^countflow-rate-constant\|rate_constant]] | The rate constant `k` |
| [[#^countflow-compute-extent\|compute_extent]] | The unrationed rate off the frozen state |
| [[#^countflow-contribute\|contribute]] | Add the move out of origin and into dest |
| [[#^countflow-attributes\|attributes]] | Fields, tagged `count_flow` |

**__init__**`(origin: CompartmentId, dest: CompartmentId, rate_constant: float = 1.0, name: str = "") -> None`
    Store the fields; an empty `name` becomes `count_flow_{origin}_to_{dest}`. `origin == dest` is not refused (the two deltas cancel). ^countflow-init

**origin**`: CompartmentId` (property)
    The compartment this flow moves multiplicity out of. ^origin

**dest**`: CompartmentId` (property)
    The compartment this flow moves multiplicity into. ^dest

**rate_constant**`: float` (property)
    `k`. ^countflow-rate-constant

**compute_extent**`(frozen: WorldStateImpl) -> float`
    `max(0, k · N_origin)` read off `frozen`; a rate. ^countflow-compute-extent

**contribute**`(frozen: WorldStateImpl, dt: float, mult_delta: MultDelta, mol_delta: MolDelta) -> None`
    `raw = min(compute_extent(frozen) · dt, N_origin)`; returns when `raw ≤ 0`. Adds `−raw` to `mult_delta[origin]` and `+raw` to `mult_delta[dest]`; never touches `mol_delta`. Under the ration both sides scale together, so the headcount moved is what the flow actually got. ^countflow-contribute

**attributes**`() -> Dict[str, Any]`
    `type`, `name`, `origin`, `dest`, `rate_constant`. ^countflow-attributes



## population Interface
The pass itself and the module's type aliases. `alienbio.bio` exports the four classes only; `apply_population_laws` is imported directly by `world_simulator.py` and `jax_simulator.py`, its only callers. `ROUNDING_FLOOR` is imported from `bio/rate_expr.py`, not defined here.

| population | |
| --- | --- |
| [[#^apply-population-laws\|apply_population_laws]] | Run every law, ration summed demand, write once |
| [[#^multdelta\|MultDelta]] | Δmultiplicity accumulator, by compartment |
| [[#^moldelta\|MolDelta]] | Δconcentration accumulator, by pool |
| [[#^moleculeid\|MoleculeId]] | Alias for a molecule's integer id |
| [[#^compartmentid\|CompartmentId]] | Alias for a compartment's integer id |

**apply_population_laws**`(laws: Sequence[PopulationLaw], new_state: WorldStateImpl, frozen: WorldStateImpl, dt: float) -> None`
    Ask every law for its deltas against `frozen`, each into its own fresh pair of dicts; sum the negative deltas per key into a demand; give each key the ratio `min(1, frozen value / demand)`; scale every delta of a law by the smallest ratio over the keys that law draws; add the scaled deltas into `new_state` once, snapping a result in `(−ROUNDING_FLOOR, 0)` to 0 ([[#The summed-demand ration]]). Mutates `new_state` in place and returns nothing; `frozen` is only read. An empty `laws` writes nothing. Raises nothing of its own; ids are not checked, and the state's lists index them as given. ^apply-population-laws

**MultDelta**`= Dict[CompartmentId, float]`
    Δmultiplicity keyed by compartment. ^multdelta

**MolDelta**`= Dict[tuple[CompartmentId, MoleculeId], float]`
    Δconcentration (per instance, not amount) keyed by `(compartment, molecule)`. ^moldelta

**MoleculeId**`= int`
    A column of the state. ^moleculeid

**CompartmentId**`= int`
    A row of the state, and the key of `multiplicity`. ^compartmentid




# PopulationLaw Semantics

## Counts on the multiplicity axis
`WorldStateImpl` keeps one `multiplicity` and one `volume` per compartment beside the `[compartment × molecule]` concentrations. Concentrations are per instance; the extensive quantity is `amount = multiplicity · volume · concentration` (`WorldStateImpl.amount`). A population is a compartment whose multiplicity is large and changes. Changing `multiplicity` leaves concentrations alone, so every instance — old, newborn or dying — carries the compartment's per-instance concentrations: births add contents, deaths remove them. That is the born-full rule (F017 Q4=A). Multiplicity is a per-compartment scalar, not a pool, which is why it has its own pass rather than a fake species in the reaction ration.



## One pass, off the frozen state
`WorldSimulatorImpl.step` calls `_apply_population_laws` (a one-line wrapper over `apply_population_laws`) last, after reactions and `apply_flows`, and only when `population_laws` is non-empty, so a world without laws steps byte-identically to before F017.

| | Reads | Writes |
| --- | --- | --- |
| each law's `contribute` | `frozen`: multiplicity, volume, concentration, amount | its own `MultDelta` / `MolDelta` |
| the ration | `frozen` multiplicity and concentration per drained key | — |
| the write | `new_state` (already holding the reaction and flow results) | `new_state` multiplicity and concentration |

`frozen` is the step's input — subnormal-flushed on the reference, the raw input on the JAX host path. Positive deltas (births, a flow's arrivals, a release) are never counted as supply within the step.



## The summed-demand ration
Each law caps its own draw at the frozen pool, but before T053 two laws drawing one key each saw the whole pool: two deaths on a compartment of 10 took it to −10 in a step, and the shipped microcosm's two growth laws both draw `pond/food`. Now, per drained key (a compartment's multiplicity, or a `(compartment, molecule)` concentration):

1. demand = the sum of the negative deltas all laws put on that key;
2. ratio = `min(1, value in new_state / demand)` — the pool the earlier passes left, floored at 0;
3. each law's scale = the smallest ratio over every key it drew, 1 if it drew none;
4. all of that law's deltas — draws and gains alike — are multiplied by its scale.

A growth law cut on its resource therefore grows by the same fraction less; a `CountFlow` cut on its origin delivers the same fraction less to `dest`. With nothing over-drawn every ratio is exactly `1.0` and the multiply is bit-exact. This is the single-pass min-ratio scheme `WorldSimulatorImpl._apply_reactions` uses, and it shares that scheme's conservatism: a law drawing two contested keys is cut by the tighter one even if the other could have covered it. `tests/suite/test_population.py` pins the cases: two deaths → 0, death plus count flow on one compartment (each gets 10/12), two growth laws on one pool (each gets half), and a starved 4000-step run with no negative value.



## Resource coupling and what is conserved
A growth of ΔN draws `stoich · ΔN` AMOUNT from the resource pool, so amount is conserved when `stoich` equals the amount each new instance is born holding (`volume · biomass_conc` for `PopulationBlock`, whose `1.0`/`1.0` defaults balance by construction). Measured against HEAD:

| Law | Headcount | Molecule amount |
| --- | --- | --- |
| growth, resource in another compartment, matched `stoich` | +ΔN | conserved |
| growth, `stoich = 0` | +ΔN | created (the canary's red case) |
| growth, resource in its own compartment | +ΔN | not conserved: the newborns are born holding the post-draw resource concentration, so `N=2, [R]=1, k=1, dt=0.1` ends at amount 1.98, not 1.8 |
| death, no release | −ΔN | the dead instances' contents leave the world |
| death with release | −ΔN | `release_stoich · ΔN` returns to the release pool |
| `CountFlow` | conserved | not conserved unless origin and dest hold the same per-instance amounts; the movers take on `dest`'s concentrations (20 → 18 in a two-compartment probe) |

The `PerCapitaGrowth.__init__` docstring permits `resource_compartment == compartment` without saying the coupling is then inexact.



## The cross-pass over-draw
The ratios read `new_state`, not `frozen`: a pool the reaction or flow pass already drew this step is rationed against what they left (floored at 0). Until 2026-10 they read `frozen`, so one compartment with `[A] = 1`, a fast reaction A → B and a growth law with `stoich = 1` drawing A ended the step at `[A] = −1.0`, B = 1 and one new instance — the same A spent twice. Each law's own `contribute` cap still reads the frozen pool; that is its demand. Multiplicity ratios read `new_state` too, which equals `frozen` here because no earlier pass writes multiplicity.



## JAX paths
`JaxWorldSimulator` takes `population_laws` and, in `step` (and so `run`), runs `apply_population_laws` on the host after the device reaction step and the host flow pass, from the same function the reference calls; before T053 it had no such parameter and a world with laws ran a different model there (microcosm juveniles 172 against 20). `run_fast` and `run_batch` raise `ValueError` when any law is present, because the device array carries no multiplicity. `tests/unit/test_m24_jax.py::TestPopulationParity` holds the host path to the reference and pins both refusals.



## From declared spec to law
Blocks and Expr author string-id specs: `GrowthLaw`, `DeathLaw`, `CountFlowSpec` (frozen dataclasses in `bio/world.py`, together `PopulationLawSpec`). `PopulationBlock.realize` emits one `GrowthLaw` and, when the sampled death rate is non-zero, one `DeathLaw`; the Expr constructor heads `GrowthLaw`, `DeathLaw` and `CountFlow` (`suite/expr_heads.py`) build them directly. `Skeleton.materialize` concatenates every fragment's `population_laws` into `WorldImpl`, whose `__init__` resolves each spec against the same compartment and molecule indices as the state, raising `KeyError` for an unknown compartment or molecule and `TypeError` for any other type, and keeps both forms: `population_laws` (specs, which `suite/runner` threads unchanged into each per-turn rebuild so dynamics persist turn to turn) and `population_law_objs` (the laws, which `suite/verify.simulate` hands to `WorldSimulatorImpl.from_chemistry`).




# BRIEF
- 2026-10-18 — written as an ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD 84f8190; every member and claim traced to `bio/population.py`, `world_simulator.py`, `jax_simulator.py`, `world_state.py`, `world.py`, `suite/blocks.py`, `suite/skeleton.py`, `suite/verify.py`, `suite/expr_heads.py`, `suite/runner.py` and the tests named above. The cross-pass over-draw, the same-compartment growth leak and the `CountFlow` amount change were reproduced with throwaway scripts against HEAD, not fixed. Left out: `__repr__`/`__str__` on the three laws (only the `PerCapitaDeath.__repr__` omission is mentioned). Constructor block ids are `^init` and `^{class}-init`. Drift in the source, not fixed: the module docstring (line 39) names `WorldSimulatorImpl._population_pass`, which does not exist — the method is `_apply_population_laws`; `compute_extent`'s docstring calls a rate a Δmultiplicity; `tests/capabilities/test_simulator_conformance.py` passes `world.population_laws` (specs, not laws) to both simulators, harmless only because no entry in its `BLOCK_DOCS` has a population, so that property never exercises the population pass despite its comment.
