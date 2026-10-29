---
description: "`PopulationLaw` + `PerCapitaGrowth`, `PerCapitaDeath`, `CountFlow` and `apply_population_laws`: the population pass on the multiplicity axis. Source: `src/alienbio/bio/population.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO bio](ABIO%20bio.md) → [ABIO PopulationLaw](ha://p/ABIO%20PopulationLaw) 
# ABIO PopulationLaw
The population pass: three count-based rate laws that grow, kill and move a compartment's `multiplicity`, and the one function that rations their summed demand off the frozen state.

![[ABIO PopulationLaw.svg|2400]] 
*The summed-demand ration* is the topic that governs the ration box (every law that draws a key short of its demand scales by the tightest ratio over the keys it draws); *Resource coupling and what is conserved* governs the `draws stoich·ΔN` edge.

The simulator's only path that writes `multiplicity` during a run (F017). This page covers the laws and `apply_population_laws`; the step that calls it is [[ABIO WorldSimulatorImpl]] (pass 3, after flows), the JAX host path is [[ABIO JaxWorldSimulator]], the molecule-pool sibling on the flow pass is [[ABIO TransportFlux]], and `ROUNDING_FLOOR` lives with [[ABIO RateExpr]]. The string-id specs that become these laws are `GrowthLaw`, `DeathLaw` and `CountFlowSpec` in `bio/world.py`; the subsystem view is [[ABIO-Bio-Engine]].



## PopulationLaw Interface
Abstract base for a typed, declarative count-based rate law: no callable rate, only fields. A law never mutates state; `contribute` reads the frozen start-of-step state and adds its deltas and `Carry` records into containers the caller owns, so order among laws does not matter. `__slots__` all the way down (the ABC base declares none of its own fields), so no attribute can be added; the fields have no setters but are not frozen — `_rate_constant` can still be assigned. Exported from `alienbio.bio` with the three subclasses.

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

**contribute**`(frozen: WorldStateImpl, dt: float, mult_delta: MultDelta, mol_delta: MolDelta, carries: Carries) -> None` (abstract)
    Read `frozen` and add this law's Δmultiplicity into `mult_delta`, its Δamount (not a concentration) into `mol_delta`, and one `Carry` per content move into `carries`. Never mutates `frozen` and never reads the containers back. `apply_population_laws` hands each law fresh ones, so a subclass may assume they start empty but must accumulate with `get(key, 0.0) +` regardless ([[#The summed-demand ration]]). ^contribute

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

**contribute**`(frozen: WorldStateImpl, dt: float, mult_delta: MultDelta, mol_delta: MolDelta, carries: Carries) -> None`
    `raw = compute_extent(frozen) · dt`; returns at once when `raw ≤ 0`. With `stoich > 0`, when `stoich · raw` exceeds the resource AMOUNT in the frozen state the extent is scaled down to fit, so this one law alone never over-draws. Adds `+raw` to `mult_delta[compartment]`, a birth `Carry(compartment, compartment, raw, removes=False)` (born-full), and, with `stoich > 0`, the amount `−stoich · raw` to `mol_delta[(resource_compartment, resource)]`. When the resource is drawn from `compartment` itself the birth's `skip` names the resource: the newborns share the pool that funds them rather than also copying it ([[#Resource coupling and what is conserved]]). ^percapitagrowth-contribute

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

**contribute**`(frozen: WorldStateImpl, dt: float, mult_delta: MultDelta, mol_delta: MolDelta, carries: Carries) -> None`
    `raw = min(compute_extent(frozen) · dt, N)`; returns when `raw ≤ 0`. Adds `−raw` to `mult_delta[compartment]`, a death `Carry(compartment, None, raw, removes=True)` (the dead take their contents out of the world), and, when a release is configured, the amount `+release_stoich · raw` to `mol_delta[(release_compartment, release_resource)]`, always under the named compartment. Where that compartment ends the step at size 0, `apply_population_laws` moves the release (§ [Resource coupling and what is conserved](#resource-coupling-and-what-is-conserved)); until `2e9cd6a` this method redirected it off the frozen size, which missed a release compartment emptied by this step's own deaths, and until 2026-10 it was dropped. The clamp to `N` bounds this law alone; two deaths on one compartment are bounded by the ration ([[#The summed-demand ration]]). ^percapitadeath-contribute

**attributes**`() -> Dict[str, Any]`
    `type`, `name`, `compartment`, `rate_constant`, `release_compartment`, `release_resource`, `release_stoich`. `__repr__`, unlike this, omits the three release fields. ^percapitadeath-attributes



## CountFlow Interface
A size-class transition (maturation edge): moves `rate_constant · N_origin · dt` of multiplicity from `origin` to `dest`, floored at 0 and clamped to `N_origin`. The same extent leaves and enters, so headcount is conserved exactly, and the movers carry their own contents, so molecule amount is too ([[#Resource coupling and what is conserved]]). The multiplicity-axis parallel of [[ABIO TransportFlux]]. Inherits `name`.

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

**contribute**`(frozen: WorldStateImpl, dt: float, mult_delta: MultDelta, mol_delta: MolDelta, carries: Carries) -> None`
    `raw = min(compute_extent(frozen) · dt, N_origin)`; returns when `raw ≤ 0`. Adds `−raw` to `mult_delta[origin]`, `+raw` to `mult_delta[dest]` and a move `Carry(origin, dest, raw, removes=True)`; never touches `mol_delta`. Under the ration all three scale together, so the headcount and contents moved are what the flow actually got. ^countflow-contribute

**attributes**`() -> Dict[str, Any]`
    `type`, `name`, `origin`, `dest`, `rate_constant`. ^countflow-attributes



## population Interface
The pass itself and the module's type aliases. `alienbio.bio` exports the four classes only; `apply_population_laws` is imported directly by `world_simulator.py` and `jax_simulator.py`, its only callers. `snap_residue` (and through it `ROUNDING_FLOOR`) is imported from `bio/rate_expr.py`, not defined here.

| population | |
| --- | --- |
| [[#^apply-population-laws\|apply_population_laws]] | Run every law, ration summed demand, write once |
| [[#^multdelta\|MultDelta]] | Δmultiplicity accumulator, by compartment |
| [[#^moldelta\|MolDelta]] | Δamount accumulator, by pool |
| [[#^carry\|Carry]] | One content move: a birth, death or departure |
| [[#^carries\|Carries]] | `Carry` accumulator |
| [[#^moleculeid\|MoleculeId]] | Alias for a molecule's integer id |
| [[#^compartmentid\|CompartmentId]] | Alias for a compartment's integer id |

**apply_population_laws**`(laws: Sequence[PopulationLaw], new_state: WorldStateImpl, frozen: WorldStateImpl, dt: float) -> None`
    Ask every law for its deltas against `frozen`, each into its own fresh containers; ration multiplicity, then molecule draws, by the summed demand per key; scale every delta and carry of a law by the smallest ratio over the keys that law draws; write once — multiplicity directly, molecules as amounts divided by the new `multiplicity · volume` — snapping a result in `(−ROUNDING_FLOOR · max(1, pre), 0)` to 0 with `snap_residue` — a multiplicity against the pre-pass multiplicity, a molecule's amount against its pre-pass amount, before dividing by size (relative since `3269751`, T091 C3) ([[#The summed-demand ration]], [[#Resource coupling and what is conserved]]). Before accumulating molecules it computes the multiplicities it will write, and a death's release whose compartment ends the step at multiplicity · volume 0 is re-keyed to the dying compartment. Mutates `new_state` in place and returns nothing; `frozen` is only read. An empty `laws` writes nothing. Raises nothing of its own; ids are not checked, and the state's lists index them as given. ^apply-population-laws

**MultDelta**`= Dict[CompartmentId, float]`
    Δmultiplicity keyed by compartment. ^multdelta

**MolDelta**`= Dict[tuple[CompartmentId, MoleculeId], float]`
    Δamount (`multiplicity · volume · concentration`, not a concentration) keyed by `(compartment, molecule)`; until 2026-10 it was a per-instance concentration on the frozen count, which is what leaked amount when the count changed in the same pass. ^moldelta

**Carry**`(src, dst, count, removes, skip=frozenset())` (frozen dataclass)
    `count` instances' contents, read per instance (`volume · concentration`) off `src` in the state being written. `removes=False` copies them into `src` (a birth); `removes=True` takes them out of `src` and into `dst`, or out of the world when `dst` is `None` (a death). `skip` names molecules a birth does not copy. ^carry

**Carries**`= List[Carry]`
    The accumulator `contribute` appends to. ^carries

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
| the ration | `new_state` multiplicity and amount per drained key | — |
| the write | `new_state` (already holding the reaction and flow results) | `new_state` multiplicity and concentration |

`frozen` is the step's input — subnormal-flushed on the reference, the raw input on the JAX host path. Positive deltas (births, a flow's arrivals, a release) are never counted as supply within the step: a draw is rationed against the pool as the earlier passes left it, the reaction pass's rule for its own products, and since `2e9cd6a` the docstring states and a test pins this as deliberate. A pool emptied by a draw and refilled by a release ends at the release; the draw that wanted more gets it next step.



## The summed-demand ration
Each law caps its own draw at the frozen pool, but before T053 two laws drawing one key each saw the whole pool: two deaths on a compartment of 10 took it to −10 in a step, and the shipped microcosm's two growth laws both draw `pond/food`. Now, per drained key (a compartment's multiplicity first, then a `(compartment, molecule)` amount):

1. demand = the sum of the negative deltas all laws put on that key;
2. ratio = `min(1, value in new_state / demand)` — the pool the earlier passes left, floored at 0; for a molecule, less what the multiplicity-rationed deaths and departures carry out of it, so a growth draw and a death on one pool cannot together take it negative;
3. each law's scale = the smallest ratio over every key it drew, 1 if it drew none;
4. all of that law's deltas and carries — draws and gains alike — are multiplied by its scale.

A growth law cut on its resource therefore grows by the same fraction less; a `CountFlow` cut on its origin delivers the same fraction less to `dest`. With nothing over-drawn every ratio is exactly `1.0` and the multiply is bit-exact; a key the pass does not account as an amount keeps its concentration untouched. This is the single-pass min-ratio scheme `WorldSimulatorImpl._apply_reactions` uses, and it shares that scheme's conservatism: a law drawing two contested keys is cut by the tighter one even if the other could have covered it. `tests/suite/test_population.py` pins the cases: two deaths → 0, death plus count flow on one compartment (each gets 10/12), two growth laws on one pool (each gets half), and a starved 4000-step run with no negative value.



## Resource coupling and what is conserved
A growth of ΔN draws `stoich · ΔN` AMOUNT from the resource pool, so amount is conserved when `stoich` equals the amount each new instance is born holding (`volume · biomass_conc` for `PopulationBlock`, whose `1.0`/`1.0` defaults balance by construction).

The write keeps a key's concentration untouched (born-full / die-full: the count changes, the per-instance contents do not) unless a law touches it as an amount, a `CountFlow` lands movers in its compartment, or a birth skips it. Those keys are accounted as amounts — the pool before the pass, plus what births copy, minus what deaths and departures carry out, plus what arrivals carry in, plus draws and releases — and divided by the compartment's new `multiplicity · volume`. Until 2026-10 molecule deltas were concentrations on the frozen count, which leaked whenever the count moved in the same pass (the third and last rows below, and the dropped release).

| Law | Headcount | Molecule amount |
| --- | --- | --- |
| growth, resource in another compartment, matched `stoich` | +ΔN | conserved |
| growth, `stoich = 0` | +ΔN | created (the canary's red case) |
| growth, resource in its own compartment | +ΔN | the resource: pre-draw amount less the draw, spread over the new count (`N=2, [R]=1, k=1, dt=0.1` ends at 1.8; it was 1.98); other contents born-full |
| death, no release | −ΔN | the dead instances' contents leave the world |
| death with release | −ΔN | `release_stoich · ΔN` returns to the release pool; to the dying compartment when the release compartment ends the step at size 0 (read off the multiplicities this pass writes); out of the world with the dead when both end empty |
| `CountFlow` | conserved | conserved: the movers carry their own contents and `dest` ends at the amount-weighted mix (a two-compartment probe that went 20 → 18 now stays 20); a mover changing volume changes concentration |

What the write cannot conserve: an amount landing in a compartment left at multiplicity · volume 0 — a release whose release compartment and dying compartment both end the step empty leaves with the dead's contents. `tests/bio/test_moddoc_findings_population.py` pins each row. The fix moved the shipped microcosm (100 steps of 0.1): the adults' per-instance `food` went 5.443 → 3.924, because juveniles of volume 0.1 mature into adults of volume 0.2 and now bring their amount, not the adults' concentration; pond `food`/`detritus` and every count are unchanged to 1e-15.



## The cross-pass over-draw
The ratios read `new_state`, not `frozen`: a pool the reaction or flow pass already drew this step is rationed against what they left (floored at 0). Until 2026-10 they read `frozen`, so one compartment with `[A] = 1`, a fast reaction A → B and a growth law with `stoich = 1` drawing A ended the step at `[A] = −1.0`, B = 1 and one new instance — the same A spent twice. Each law's own `contribute` cap still reads the frozen pool; that is its demand. Multiplicity ratios read `new_state` too, which equals `frozen` here because no earlier pass writes multiplicity.



## JAX paths
`JaxWorldSimulator` takes `population_laws` and, in `step` (and so `run`), runs `apply_population_laws` on the host after the device reaction step and the host flow pass, from the same function the reference calls; before T053 it had no such parameter and a world with laws ran a different model there (microcosm juveniles 172 against 20). `run_fast` and `run_batch` raise `ValueError` when any law is present, because the device array carries no multiplicity. `tests/unit/test_m24_jax.py::TestPopulationParity` holds the host path to the reference and pins both refusals.



## From declared spec to law
Blocks and Expr author string-id specs: `GrowthLaw`, `DeathLaw`, `CountFlowSpec` (frozen dataclasses in `bio/world.py`, together `PopulationLawSpec`). `PopulationBlock.realize` emits one `GrowthLaw` and, when the sampled death rate is non-zero, one `DeathLaw`; the Expr constructor heads `GrowthLaw`, `DeathLaw` and `CountFlow` (`suite/expr_heads.py`) build them directly. `Skeleton.materialize` concatenates every fragment's `population_laws` into `WorldImpl`, whose `__init__` resolves each spec against the same compartment and molecule indices as the state, raising `KeyError` for an unknown compartment or molecule and `TypeError` for any other type, and keeps both forms: `population_laws` (specs, which `suite/runner` threads unchanged into each per-turn rebuild so dynamics persist turn to turn) and `population_law_objs` (the laws, which `suite/verify.simulate` hands to `WorldSimulatorImpl.from_chemistry`).




# BRIEF
- 2026-10-18 — written as an ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD 84f8190; every member and claim traced to `bio/population.py`, `world_simulator.py`, `jax_simulator.py`, `world_state.py`, `world.py`, `suite/blocks.py`, `suite/skeleton.py`, `suite/verify.py`, `suite/expr_heads.py`, `suite/runner.py` and the tests named above. The cross-pass over-draw, the same-compartment growth leak and the `CountFlow` amount change were reproduced with throwaway scripts against HEAD, not fixed. Left out: `__repr__`/`__str__` on the three laws (only the `PerCapitaDeath.__repr__` omission is mentioned). Constructor block ids are `^init` and `^{class}-init`. Drift in the source, not fixed: the module docstring (line 39) names `WorldSimulatorImpl._population_pass`, which does not exist — the method is `_apply_population_laws`; `compute_extent`'s docstring calls a rate a Δmultiplicity; `tests/capabilities/test_simulator_conformance.py` passes `world.population_laws` (specs, not laws) to both simulators, harmless only because no entry in its `BLOCK_DOCS` has a population, so that property never exercises the population pass despite its comment.
- 2026-10-28 — the population pass conserves amount: `MolDelta` is an amount, `contribute` takes a `Carries` accumulator, a self-drawing growth's newborns share the drawn pool, `CountFlow` movers carry their contents, a death releasing into a size-0 compartment releases into the dying one; § Resource coupling rewritten, the microcosm's moved number recorded there.
- 2026-10-28 — refreshed against 0eb23e5: a death's release is placed by `apply_population_laws` against the post-pass sizes, not by `contribute` off the frozen size (`2e9cd6a`); the same-pass-gains rule is stated as deliberate; the conservation table and its closing line follow. Figure still true.
- 2026-10-29 — refreshed for `3269751` (T091 C3): the pass snaps with `snap_residue`, relative to the pre-pass multiplicity and the pre-pass amount. Figure still true.
