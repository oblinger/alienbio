---
description: "`TransportFlux`, `GeneralFlow`, `Flow` and `apply_flows`: amount-conserving transport between compartments and the flow pass both simulators run. Source: `src/alienbio/bio/flow.py`."
---
:>> [[ABIO]] → [[ABIO Dev Docs]] → [ABIO TransportFlux](ha://p/ABIO%20TransportFlux) 
# ABIO TransportFlux
The flow layer: `TransportFlux` moves a conserved amount of one or more species from one compartment to another, `GeneralFlow` is an arbitrary edit, and `apply_flows` runs every flow of a world as pass 2 of each simulator step.

![[ABIO TransportFlux.svg|2400]] 
*The simultaneous flow pass* is the topic that governs everything inside the `apply_flows` frame (demand off the frozen state, summed per pool, one ration, applied at once); *Cross-pass over-draw* governs the `available` edge, which counts only this pass's draws.

A world declares transport as string-id `Transport` specs authored by blocks; `WorldImpl` resolves each into a `TransportFlux`, and [[ABIO WorldSimulatorImpl]] and [[ABIO JaxWorldSimulator]] hand the whole list to `apply_flows` between the reaction pass and the population pass. This page covers the three classes and the pass. The step that sequences the passes, and the reaction pass's own ration, are on [[ABIO WorldSimulatorImpl]]; the population pass is `apply_population_laws` in `bio/population.py`; the state store is `bio/world_state.py`; the subsystem view is [[ABIO-Bio-Engine]].



## TransportFlux Interface
One directed, amount-conserving flux between two arbitrary compartments: `origin` and `dest` need no parent–child relation in the tree, which is what lets `SpatialLatticeBlock` wire any neighbour graph. One driver molecule's concentration sets the event rate; every species in `stoichiometry` moves by the same event count, so a co-transported group moves in lockstep. Strictly `origin → dest`: a negative rate is floored to zero, and two-way exchange takes a second, reversed flux. Immutable after construction (`__slots__`, read-only properties, `stoichiometry` copied in and out). The simulators never call `apply`; they call `demand` and `apply_events` through `apply_flows`.

| TransportFlux | |
| --- | --- |
| [[#^init\|__init__]] | Build a flux; checks the rate law name |
| [[#^dest\|dest]] | The compartment species move into |
| [[#^stoichiometry\|stoichiometry]] | Molecule id → count moved per event |
| [[#^driver-molecule\|driver_molecule]] | The molecule whose concentration sets the rate |
| [[#^rate-constant\|rate_constant]] | `D` (gradient) or `k` (first order) |
| [[#^rate-law\|rate_law]] | `"gradient"` or `"first_order"` |
| [[#^is-membrane-flow\|is_membrane_flow]] | Always `False` |
| [[#^is-general-flow\|is_general_flow]] | Always `False` |
| [[#^compute-flux\|compute_flux]] | Raw event rate from the rate law |
| [[#^demand\|demand]] | Event count and per-pool draws off a frozen state |
| [[#^apply-events\|apply_events]] | Move a given event count, mutating a state |
| [[#^apply\|apply]] | Step this one flux alone, rationed by itself |
| [[#^attributes\|attributes]] | The fields as a dict, `type: "transport"` |

**__init__**`(origin: CompartmentId, dest: CompartmentId, stoichiometry: Dict[int, float], driver_molecule: int, rate_constant: float = 1.0, rate_law: str = "gradient", name: str = "") -> None`
    Store the fields, copying `stoichiometry`. `ValueError` when `rate_law` is neither `"gradient"` nor `"first_order"`. An empty `name` becomes `transport_{origin}_to_{dest}`. Nothing else is checked: not that the compartment or molecule ids exist in any state, not that `rate_constant` is non-negative, not that `origin != dest`, and not that `driver_molecule` appears in `stoichiometry` (it need not — a driver can set the rate of a species it does not move). In production `WorldImpl` builds these, and it is where unknown names raise ([[#From block to simulator]]). ^init

**dest**`: CompartmentId` (property)
    The gaining compartment for every species with a positive count; the losing one for a negative count. ^dest

**stoichiometry**`: Dict[int, float]` (property)
    Molecule id → amount moved per event, returned as a copy. A positive count moves `origin → dest`; a negative count moves that species `dest → origin` on the same events (an antiport); a zero count is skipped. ^stoichiometry

**driver_molecule**`: int` (property)
    The molecule id whose concentration `compute_flux` reads — in `origin` for both laws, and also in `dest` for the gradient law. ^driver-molecule

**rate_constant**`: float` (property)
    The diffusion coefficient `D` under the gradient law, the rate `k` under first order ([[#Rate laws and direction]]). ^rate-constant

**rate_law**`: str` (property)
    `"gradient"` (Fickian, the default) or `"first_order"`. ^rate-law

**is_membrane_flow**`: bool` (property)
    `False`. Required by the `Flow` base and the `protocols.bio.Flow` Protocol; nothing in `src/` reads it ([[#The GeneralFlow escape]]). ^is-membrane-flow

**is_general_flow**`: bool` (property)
    `False`. Like `is_membrane_flow`, declared and never read; `apply_flows` tells the two kinds apart by `isinstance(flow, TransportFlux)`. ^is-general-flow

**compute_flux**`(state: WorldStateImpl, tree: CompartmentTreeImpl) -> float`
    The raw event rate, unfloored and unrationed: `rate_constant × [driver]_origin` under first order, `rate_constant × ([driver]_origin − [driver]_dest)` under gradient. Reads concentrations, not amounts. May be negative; `demand` floors it. `tree` is unused. ^compute-flux

**demand**`(frozen: WorldStateImpl, tree: CompartmentTreeImpl, dt: float = 1.0) -> tuple[float, Dict[tuple[CompartmentId, int], float]]`
    The event count this flux wants this step, `max(compute_flux(frozen, tree) × dt, 0)`, and the amount it would draw at that count from each losing `(compartment, molecule)`: `|count| × events`, from `origin` for a positive count and from `dest` for a negative one. Returns `(0.0, {})` when the count is not positive. Reads only `frozen`; mutates nothing (T053). ^demand

**apply_events**`(state: WorldStateImpl, scales: WorldStateImpl, event_count: float) -> None`
    For each species, `Δn = event_count × count`; subtract `Δn / (multiplicity × volume)` from the origin concentration and add `Δn / (multiplicity × volume)` to the destination's, each scale read off `scales`, each concentration read from and written to `state`. A side whose scale is not positive is skipped ([[#Amount conservation]]). Does nothing when `event_count ≤ 0`. No availability check: the caller has already rationed. ^apply-events

**apply**`(state: WorldStateImpl, tree: CompartmentTreeImpl, dt: float = 1.0) -> None`
    The one-flux path for a caller stepping a flux by hand: `demand` off `state`, the event count clamped against each draw's available amount in `state`, then `apply_events(state, state, count)` — so it reads and writes the same state. Not called by either simulator. The clamp reuses the already-reduced count in each iteration while `amount` is the draw at the full count, so when two species both bind the reductions compound: a two-species co-transport whose pools each cover half its demand moves a quarter of it here and half of it through `apply_flows` (flow.py 426–429). ^apply

**attributes**`() -> Dict[str, Any]`
    `type`, `name`, `origin`, `dest`, `stoichiometry` (a copy), `driver_molecule`, `rate_constant`, `rate_law`. Nothing in the module reads it back; there is no constructor from this dict. ^attributes



## GeneralFlow Interface
A flow that is a Python callable: `apply_fn(state, tree, dt)` edits the state however it likes. The docstring calls it a placeholder for an Expr-specified edit that needs a more general interpreter. No block, Expr head or `WorldImpl` constructs one; only hand-written code does (the JAX parity tests build one as a linear transfer). It states no demand, so `apply_flows` cannot ration it and runs it after the fluxes ([[#The GeneralFlow escape]]).

| GeneralFlow | |
| --- | --- |
| [[#^generalflow-init\|__init__]] | Build from an `apply_fn` and a description |
| [[#^description\|description]] | Free-text account of what it does |
| [[#^generalflow-is-membrane-flow\|is_membrane_flow]] | Always `False` |
| [[#^generalflow-is-general-flow\|is_general_flow]] | Always `True` |
| [[#^generalflow-compute-flux\|compute_flux]] | Always `0.0` |
| [[#^generalflow-apply\|apply]] | Call `apply_fn`, if any |
| [[#^generalflow-attributes\|attributes]] | The fields as a dict, `apply_fn` omitted |

**__init__**`(origin: CompartmentId, apply_fn: Optional[Callable[[WorldStateImpl, CompartmentTreeImpl, float], None]] = None, name: str = "", description: str = "") -> None`
    Store the fields. An empty `name` becomes `general_flow_at_{origin}`. `origin` is nominal — nothing reads it but `attributes` and `__repr__`. `apply_fn=None` makes a flow that does nothing. ^generalflow-init

**description**`: str` (property)
    The description given at construction. ^description

**is_membrane_flow**`: bool` (property)
    `False`; never read. ^generalflow-is-membrane-flow

**is_general_flow**`: bool` (property)
    `True`; never read. ^generalflow-is-general-flow

**compute_flux**`(state: WorldStateImpl, tree: CompartmentTreeImpl) -> float`
    `0.0`. A general flow has no rate; the work is in `apply`. ^generalflow-compute-flux

**apply**`(state: WorldStateImpl, tree: CompartmentTreeImpl, dt: float = 1.0) -> None`
    Call `apply_fn(state, tree, dt)` when it is set; otherwise nothing. Raises whatever `apply_fn` raises. ^generalflow-apply

**attributes**`() -> Dict[str, Any]`
    `type: "general"`, `name`, `origin`, `description`. `apply_fn` is not serialised and cannot be. ^generalflow-attributes



## Flow Interface
The abstract base both flows subclass (`abc.ABC`); `alienbio.bio` exports it under the same name as the `protocols.bio.Flow` Protocol, and `protocols/_conformance.py` asserts under `TYPE_CHECKING` that both subclasses satisfy that Protocol. It holds `origin` and `name` and declares the rest abstract, so it cannot be instantiated.

| Flow | |
| --- | --- |
| [[#^flow-init\|__init__]] | Store origin and name |
| [[#^origin\|origin]] | The compartment the flow is anchored to |
| [[#^name\|name]] | Human-readable identifier |
| [[#^flow-is-membrane-flow\|is_membrane_flow]] | Abstract |
| [[#^flow-is-general-flow\|is_general_flow]] | Abstract |
| [[#^flow-compute-flux\|compute_flux]] | Abstract: the flow's rate |
| [[#^flow-apply\|apply]] | Abstract: edit a state in place |
| [[#^flow-attributes\|attributes]] | Abstract: the fields as a dict |

**__init__**`(origin: CompartmentId, name: str = "") -> None`
    Store both; called by each subclass after it has filled in a default name. ^flow-init

**origin**`: CompartmentId` (property)
    For a `TransportFlux`, the losing compartment of every positive-count species; for a `GeneralFlow`, a label. ^origin

**name**`: str` (property)
    The name given, or the subclass default. Blocks set it to a namespaced flow id (`{ns}/transport`, `{ns}/edge{i}_fwd`), which also lands in the block's `Provenance`. ^name

**is_membrane_flow**`: bool` (abstract property)
    Documented as "origin ↔ parent"; a leftover of the deleted `MembraneFlow`, and `False` on both remaining subclasses. ^flow-is-membrane-flow

**is_general_flow**`: bool` (abstract property)
    `True` only on `GeneralFlow`. ^flow-is-general-flow

**compute_flux**`(state: WorldStateImpl, tree: CompartmentTreeImpl) -> float` (abstract)
    The flow's rate. The base docstring still says "positive = into origin for membrane flows"; on `TransportFlux` positive means `origin → dest`. ^flow-compute-flux

**apply**`(state: WorldStateImpl, tree: CompartmentTreeImpl, dt: float = 1.0) -> None` (abstract)
    Apply the flow to `state` in place. ^flow-apply

**attributes**`() -> Dict[str, Any]` (abstract)
    Semantic content for serialisation. ^flow-attributes



## flow Interface
`alienbio.bio` exports `Flow`, `GeneralFlow` and `TransportFlux`; `apply_flows` is imported from the module directly by both simulators. The module's own names besides the classes:

| flow | |
| --- | --- |
| [[#^apply-flows\|apply_flows]] | Run every flow of a world for one step |
| [[#^compartmentid\|CompartmentId]] | Alias for a compartment's integer id |

**apply_flows**`(flows: Sequence[Flow], new_state: WorldStateImpl, frozen: WorldStateImpl, tree: CompartmentTreeImpl, dt: float) -> None`
    The flow pass. Every `TransportFlux` states its `demand` off `frozen`; the draws are summed per losing `(compartment, molecule)`; each pool's ratio is `min(1, available / demand)` with `available` read off `frozen`; each flux's event count is scaled by the tightest ratio over the pools it draws and moved by `apply_events` into `new_state`, reading scales off `frozen`. Every other flow then runs `flow.apply(new_state, tree, dt)` in list order ([[#The simultaneous flow pass]]). Mutates `new_state` only; returns nothing; raises nothing of its own. ^apply-flows

**CompartmentId**`= int`
    A compartment's index in the tree. `alienbio.bio` re-exports the alias of the same name from `protocols.bio`, not this one. ^compartmentid




# TransportFlux Semantics

## The simultaneous flow pass
Before T053 the pass applied each flow in turn, so a flux read its predecessors' writes and list order decided a split: two first-order fluxes each wanting 0.8 of a pool holding 1.0 gave `b = 0.80, c = 0.16` or the reverse, depending on which came first. `apply_flows` now resolves the pass in one shot, the scheme the reaction pass uses:

| Step | Reads | Produces |
| --- | --- | --- |
| 1. Demand | `frozen` concentrations of each flux's driver | events and draws per flux |
| 2. Sum | the draws | demand per losing `(compartment, molecule)` |
| 3. Ration | `frozen.amount` of each pool | `min(1, available / demand)`<br>`1.0` when demand is zero |
| 4. Scale | the ratios over each flux's own draws | events × the smallest ratio |
| 5. Apply | `frozen` multiplicity × volume | concentration writes into `new_state`, all fluxes |
| 6. General flows | `new_state` as it now stands | arbitrary edits, in list order |

The split is independent of list order, and the pass never draws more than the frozen pool holds. With no pool over-drawn every ratio is exactly `1.0`, and the move equals `TransportFlux.apply` on the frozen state bit for bit (`tests/suite/test_transport.py`, `test_a_non_competing_flux_moves_exactly_what_it_did_before`); the one behaviour change for non-competing worlds is that a flux reads the frozen state rather than its predecessors' writes. A pool already below zero gives a negative ratio, which scales every flux that draws it to a non-positive count, and `apply_events` then moves nothing. The ratio is per flux, not per species: a co-transported group is throttled by its scarcest species, all members together.



## Rate laws and direction

| `rate_law` | Event rate | Moves while `[X]_origin = [X]_dest` | Use |
| --- | --- | --- | --- |
| `"gradient"` (default) | `D × ([X]_origin − [X]_dest)` | no | diffusion toward equal concentration |
| `"first_order"` | `k × [X]_origin` | yes | a pump or boundary drain |

`X` is `driver_molecule`. The rate is multiplied by `dt` and floored at zero before rationing, so one flux only ever moves `origin → dest`; when its gradient reverses it contributes nothing rather than flipping sign, which also stops a pair from oscillating once equal. Two-way exchange is two fluxes: `SpatialLatticeBlock` wires a forward and a reversed gradient flux on every neighbour edge, sharing one `D`, because a single one only relaxes a gradient that slopes the right way. The gradient law compares concentrations, so across compartments of different volume it equalises concentration, not amount.



## Amount conservation
A flux moves amount (`multiplicity × volume × concentration`, `WorldStateImpl.amount`), not concentration. For each species `apply_events` takes `Δn = events × count` out of the losing compartment and puts the same `Δn` into the other, converting each side by its own scale, so `Σ amount` over the two compartments is unchanged whatever their volumes or multiplicities (`test_transport_flux_conserves_amount_across_differing_volumes`). Within the pass the scales come from `frozen`; the population pass, which can change multiplicity, runs after.

Two places where the invariant does not hold, both in `apply_events` (flow.py 404–409):

- **A gaining side with zero scale** — a compartment whose multiplicity or volume is zero is skipped. The losing side still pays, so the amount vanishes. A positive-count flux into a compartment whose population has died out loses its whole transfer; reproduced against HEAD with an antiport into a zero-volume compartment (total `1.0 → 0.0`). A losing side with zero scale holds zero amount, so the ration already stops it.
- **The cross-pass over-draw** — the ration covers this pass only ([[#Cross-pass over-draw]]).



## The GeneralFlow escape
A `TransportFlux` can only move amount between two compartments at a rate set by one concentration, and it is bound by the ration. A `GeneralFlow` can do anything its `apply_fn` does — move molecules sideways, create or destroy amount, change multiplicity — and none of it is checked.

| | `TransportFlux` | `GeneralFlow` |
| --- | --- | --- |
| Reads | the frozen state | `new_state`, after reactions and fluxes |
| Rationed | yes, with every other flux | no |
| Conserves amount | yes, up to the edge cases above | only if `apply_fn` does |
| Order dependence | none | list order among general flows |
| Serialisable | `attributes` carries every field | `apply_fn` is dropped |
| Built by blocks or `WorldImpl` | yes | no; hand-written only |
| `JaxWorldSimulator.step` / `run` | yes, host side | yes, host side |
| `run_fast` / `run_batch` | refused | refused |

`run_fast` and `run_batch` raise `ValueError` for any Python flow — a `TransportFlux` included — even though the message names only "GeneralFlow objects"; the compiled path takes `native_flows` tuples instead, which `apply_flows` never sees. `JaxWorldSimulator.__init__` likewise annotates `flows` as `List[GeneralFlow]` while its `step` handles any `Flow` (`jax_simulator.py` 62, 224–227, 253–256). `is_membrane_flow` and `is_general_flow` are read nowhere; the pass dispatches on type.



## From block to simulator
Flows are authored with names, resolved to ids once per world, and carried across turns as the named specs.

| Stage | Code | Form |
| --- | --- | --- |
| Author | `TransportBlock.realize`, `SpatialLatticeBlock.realize` (`suite/blocks.py`); the `!Transport` Expr head (`suite/expr_heads.py`) | `Transport`, a frozen dataclass of string ids |
| Collect | `Fragment.flows`; `Fragment.merge` concatenates | `tuple[Transport, ...]` |
| Materialize | `Skeleton.materialize` → `WorldImpl(chem, compartments, flows=fragment.flows, …)` | — |
| Resolve | `WorldImpl.__init__`: `KeyError` for an unknown origin, dest, driver or molecule | `TransportFlux`s in `flow_objs`<br>specs kept in `flows` |
| Simulate | `suite/verify.simulate` → `WorldSimulatorImpl.from_chemistry(flows=list(world.flow_objs))` | `step` calls `apply_flows` |
| Next turn | `suite/runner._world_from_state(…, world.flows, …)` rebuilds the world from the end state | the same specs, resolved again |

`TransportBlock` moves one bound species with count `1.0`, driven by itself, at a rate sampled from its `rate` distribution, and declares both compartments (the destination as a child of the origin). `SpatialLatticeBlock` mints its own species and `k` chained compartments, with the reversed pair per edge described above. The `!Transport` head builds a one-species spec and checks the rate law name itself. The JAX simulator takes its `flows=` list from whoever constructs it.



## Cross-pass over-draw
`step` runs the reaction pass, then `apply_flows`, both reading the same frozen state and writing one `new_state`. Each rations against the whole frozen pool and knows nothing of the other's draw (`world_simulator.py` 213–225; flow.py 491–499). A pool consumed by a reaction and drained by a flux in the same step can therefore go negative: one compartment holding 1.0 of A, a reaction A → B with `k = 10` and a first-order flux of A out with `k = 10`, `dt = 1`, ends the step at A = −1.0 with B = 1.0 in place and A = 1.0 moved (total conserved; reproduced at HEAD 84f8190). The population pass is a third independent ration on the same frozen state. Nothing after the passes clamps; the reaction pass's `ROUNDING_FLOOR` snap covers only its own subtraction. A negative pool then blocks every flux that draws it on the next step ([[#The simultaneous flow pass]]).




# BRIEF
- 2026-10-18 — written as an ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD 84f8190; every member and claim traced to `bio/flow.py`, `world_simulator.py`, `jax_simulator.py`, `world_state.py`, `world.py`, `suite/blocks.py`, `suite/skeleton.py`, `suite/expr_heads.py`, `suite/verify.py`, `suite/runner.py`, `protocols/bio.py` and `tests/suite/test_transport.py`. Left out: `__repr__`/`__str__` on both subclasses, and the `Transport` spec dataclass (it lives in `bio/world.py`; named in § From block to simulator, no member block). Constructor block ids are `^init`, `^generalflow-init`, `^flow-init`. Three behaviours were reproduced against HEAD with scratch scripts and not fixed: the cross-pass over-draw (A = −1.0), the zero-scale gaining side destroying amount (flow.py 404–409), and `TransportFlux.apply` compounding its clamp across species (0.5 moved where `apply_flows` moves 1.0; flow.py 426–429). Stale in the source, not fixed: `Flow.compute_flux`'s "into origin for membrane flows", the `is_membrane_flow` abstract kept after `MembraneFlow`'s deletion, and the JAX `flows` annotation and refusal message naming only `GeneralFlow`.
