---
description: "`WorldSimulatorImpl` + `ReactionSpec`: the reference stepper — reaction, flow and population passes off a frozen state. Source: `src/alienbio/bio/world_simulator.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO bio](ABIO%20bio.md) → [ABIO WorldSimulatorImpl](ha://p/ABIO%20WorldSimulatorImpl) 
# ABIO WorldSimulatorImpl
The reference simulator: advances a multi-compartment `WorldStateImpl` one `dt` at a time through a reaction pass, a flow pass and a population pass, each read off the frozen start-of-step state.

![[ABIO WorldSimulatorImpl.svg|2400]] 
*The min-ratio ration* is the topic that governs every pass box (each scales its demand to what the frozen state holds); *Rounding floor, rate cap and subnormals* governs `_flush_subnormals`, `_desired_extent` and `eval_rate`.

The Python stepper every trial's trajectory comes from: `suite/verify.simulate` builds one with `from_chemistry` and calls `run`, and the vectorised [[ABIO JaxWorldSimulator]] is held to it by a CI conformance test. This page covers the reaction pass, which lives here, and how the step sequences the other two; the flow pass is `apply_flows` in `bio/flow.py`, the population pass `apply_population_laws` in `bio/population.py`, the rate-law tree and its constants `bio/rate_expr.py`, the state store `bio/world_state.py`, and the chemistry it is built from [[ABIO ChemistryImpl]]. The subsystem view, with its seams, is [[ABIO-Bio-Engine]].



## WorldSimulatorImpl Interface
An immutable bundle of topology, reaction specs, flows, population laws and step size, with no state of its own: `step` and `run` take a `WorldStateImpl` and return new ones, never mutating the input, so one simulator can step any number of states. It does not inherit the `Simulator` Protocol (`protocols/bio.py`: `tree`, `dt`, `step`, `run`); conformance is structural and `protocols/_conformance.py` asserts it under `TYPE_CHECKING`, beside `JaxWorldSimulator`. Pure Python over `List[float]`, float64 throughout; `__slots__`, so no attribute can be added after construction.

| WorldSimulatorImpl | |
| --- | --- |
| [[#^from-chemistry\|from_chemistry]] | Build from a `ChemistryImpl` and a compartment tree |
| [[#^init\|__init__]] | Build from already-indexed reaction specs |
| [[#^step\|step]] | Advance one `dt`; returns a new state |
| [[#^run\|run]] | Step repeatedly; returns the sampled timeline |
| [[#^tree\|tree]] | The compartment topology |
| [[#^reactions\|reactions]] | The reaction specs, in pass order |
| [[#^flows\|flows]] | The flows run by the flow pass |
| [[#^population-laws\|population_laws]] | The laws run by the population pass |
| [[#^num-molecules\|num_molecules]] | Size of the molecule vocabulary |
| [[#^dt\|dt]] | The step size |

**from_chemistry**`(chemistry: ChemistryImpl, tree: CompartmentTreeImpl, flows: Optional[Sequence[Flow]] = None, dt: float = 1.0, population_laws: Optional[Sequence[PopulationLaw]] = None) -> WorldSimulatorImpl` (classmethod)
    The production constructor. Molecule ids are the positions of `chemistry.molecules`' keys, in insertion order — the order `bio/world.py` and `suite/verify.py` rely on when they read a state back by name. Each reaction becomes a `ReactionSpec` active in every compartment (`compartments=None`), its modifiers coerced by `Modulation.from_value` (a bare role string is rate-inert) and its `rate_law` re-keyed name → id by `map_species`. `KeyError` when a reactant, product, modifier or rate-law species is not in `chemistry.molecules`. It does not check `reaction.rate`: `ReactionImpl` refuses a non-number at construction and in `set_rate` (2026-10), so its own guard, unreachable since, was removed. `num_molecules` is `len(chemistry.molecules)`. ^from-chemistry

**__init__**`(tree: CompartmentTreeImpl, reactions: List[ReactionSpec], flows: Sequence[Flow], num_molecules: int, dt: float = 1.0, population_laws: Optional[Sequence[PopulationLaw]] = None) -> None`
    Store the arguments as given; nothing is validated or copied — not that every molecule id in `reactions` is below `num_molecules`, nor that ids fit the states later passed in. `flows` is required (pass `[]`); `population_laws=None` becomes `[]`, the fast path on which `step` skips the population pass entirely. ^init

**step**`(state: WorldStateImpl) -> WorldStateImpl`
    One time step: flush subnormal concentrations to zero, copy, then the reaction pass per compartment, the flow pass when `flows` is non-empty and the population pass when `population_laws` is non-empty, every pass reading the flushed input and writing the copy ([[#One step, in order]]). Returns the copy; the input is never mutated. Raises nothing of its own. A molecule id at or beyond the state's `num_molecules` is not caught: the state indexes a flat list (`compartment × num_molecules + molecule`), so it reads and writes the next compartment's slot, and raises `IndexError` only past the last one. ^step

**run**`(state: WorldStateImpl, steps: int, sample_every: Optional[int] = None) -> List[WorldStateImpl]`
    Call `step` `steps` times from a copy of `state` and return copies of the states sampled on the way plus the final one ([[#Sampling]]). `sample_every=None` keeps every state. ^run

**tree**`: CompartmentTreeImpl` (property)
    The topology; the reaction pass iterates `range(tree.num_compartments)`, The states it returns carry the input state's tree (`WorldStateImpl.copy` shares the reference), not this one; nothing checks that the two are the same. ^tree

**reactions**`: List[ReactionSpec]` (property)
    The specs as passed, the same list object. Their order does not affect the result ([[#The min-ratio ration]]). ^reactions

**flows**`: Sequence[Flow]` (property)
    The flows as passed: any mix of `TransportFlux` (rationed together) and `GeneralFlow` (arbitrary edits, run after the fluxes, in list order). ^flows

**population_laws**`: Sequence[PopulationLaw]` (property)
    `PerCapitaGrowth`, `PerCapitaDeath` and `CountFlow` records driving the multiplicity axis (F017); `[]` when none were given. ^population-laws

**num_molecules**`: int` (property)
    The vocabulary size given at construction. Read only by `__repr__`; the passes take sizes from the state. ^num-molecules

**dt**`: float` (property)
    The step size, multiplied into every reaction's extent and handed to both other passes. ^dt



## ReactionSpec Interface
One reaction in the id-indexed form the simulators run: molecule ids instead of `MoleculeImpl`s, a stoichiometry dict per side, and the compiled rate. Public — `alienbio.bio` exports it, and `JaxWorldSimulator` takes the same list — but in production built only by `from_chemistry`. A plain mutable record with `__slots__`; nothing checks it, and `implicit_mass_action` is computed once in the constructor, so assigning `rate_law` afterwards leaves it stale.

| ReactionSpec | |
| --- | --- |
| [[#^reactionspec-init\|__init__]] | Build a spec; derives `implicit_mass_action` |
| [[#^name\|name]] | The reaction's name |
| [[#^reactants\|reactants]] | Molecule id → stoichiometry consumed |
| [[#^products\|products]] | Molecule id → stoichiometry produced |
| [[#^rate-constant\|rate_constant]] | The mass-action constant |
| [[#^compartments\|compartments]] | Where it runs; `None` for everywhere |
| [[#^modulators\|modulators]] | Non-consumed species that scale the rate |
| [[#^rate-law\|rate_law]] | A compiled rate expression, or `None` |
| [[#^implicit-mass-action\|implicit_mass_action]] | Whether mass action multiplies the law |

**__init__**`(name: str, reactants: Dict[MoleculeId, float], products: Dict[MoleculeId, float], rate_constant: float = 1.0, compartments: Optional[List[CompartmentId]] = None, modulators: Optional[Dict[MoleculeId, Modulation]] = None, rate_law: Optional[Any] = None) -> None`
    Store the fields; `modulators=None` becomes `{}`. Sets `implicit_mass_action` from `rate_law` and `reactants` (`True` when there is no law). ^reactionspec-init

**name**`: str`
    Human-readable; the simulator never reads it. ^name

**reactants**`: Dict[MoleculeId, float]`
    Consumed per unit extent. Only entries with stoichiometry `> 0` count toward demand and rationing; a zero or negative entry still raises the concentration to that power in mass action and is still subtracted. ^reactants

**products**`: Dict[MoleculeId, float]`
    Added per unit extent, after the reactants are subtracted. A molecule on both sides is subtracted then added, never netted. ^products

**rate_constant**`: float`
    The mass-action `k`. Ignored whenever `rate_law` is set — a law that should scale by `k` carries it as a constant ([[#Rate laws and modulation]]). ^rate-constant

**compartments**`: Optional[List[CompartmentId]]`
    The compartments the reaction runs in; `None` means all. `from_chemistry` always writes `None`. ^compartments

**modulators**`: Dict[MoleculeId, Modulation]`
    Modifier species that scale the rate without being consumed (F015 S2); `{}` is the fast path. ^modulators

**rate_law**`: Optional[Any]`
    A `rate_expr` tree with species by molecule id (M47.10), or `None` for plain mass action. ^rate-law

**implicit_mass_action**`: bool`
    `True` when the law names no reactant, so mass action over the reactants multiplies it; `False` when the law is the whole rate. ^implicit-mass-action



## world_simulator Interface
`alienbio.bio` exports `WorldSimulatorImpl` and `ReactionSpec`; the top-level `alienbio` package exports `WorldSimulatorImpl` alone. The module's own names besides the two classes:

| world_simulator | |
| --- | --- |
| [[#^subnormal-floor\|SUBNORMAL_FLOOR]] | Below this magnitude a concentration is zero |
| [[#^moleculeid\|MoleculeId]] | Alias for a molecule's integer id |
| [[#^compartmentid\|CompartmentId]] | Alias for a compartment's integer id |

**SUBNORMAL_FLOOR**`: float = sys.float_info.min`
    The smallest normal float, about 2.2e-308. `step` reads any concentration whose magnitude is above zero and below this as zero ([[#Rounding floor, rate cap and subnormals]]). ^subnormal-floor

**MoleculeId**`= int`
    A column of the state: the molecule's position in the vocabulary. ^moleculeid

**CompartmentId**`= int`
    A row of the state: the compartment's index in the tree. ^compartmentid




# WorldSimulatorImpl Semantics

## One step, in order
`step` is operator splitting over one frozen snapshot. Every pass reads the same input and adds its deltas into one output copy, so no pass sees another's writes.

| Order | Pass | Runs when | Reads off the frozen state | Writes |
| --- | --- | --- | --- | --- |
| 0 | `_flush_subnormals` | always | — | a flushed copy, only if something needed it; this is the frozen state |
| 1 | reactions, per compartment | the compartment has an active reaction | concentrations of reactants and modifiers | reactant and product concentrations |
| 2 | `apply_flows` | `flows` non-empty | each `TransportFlux`'s demand, as amounts | concentrations in origin and destination |
| 3 | `apply_population_laws` | `population_laws` non-empty | multiplicities and pools | multiplicities and concentrations |

A `GeneralFlow` is the exception to the frozen rule: `apply_flows` runs it after the fluxes, on the output, in list order. The class docstring's four phases (rates, fluxes, apply reactions, apply flows) predate the population pass and the shared flow pass; the table is what the code does.



## The min-ratio ration
Each pass resolves competition for a pool in one shot, without iterating. For the reaction pass, within one compartment: every active reaction's desired extent is computed from the frozen state; demand on each molecule is the sum of `extent × stoichiometry` over reactions with a positive extent and a positive stoichiometry; each molecule's ratio is `min(1, available / demand)`; each reaction is scaled by the tightest ratio over its reactants; and all scaled extents are applied together. The result is independent of the order of `reactions` (H4, `tests/unit/test_h4_simultaneous.py`), never takes a pool below zero within the pass, and reduces to a plain clamp when nothing competes. `apply_flows` (amounts, per `(compartment, molecule)`) and `apply_population_laws` (multiplicity and pools) run the same scheme in their own modules.

Every pass reads its demand off the frozen state; the flow pass rations against what the reaction pass left in `new_state`, and the population pass against what the flow pass left, so the passes together never over-draw a pool. Until 2026-10 each rationed against the full frozen pool: one compartment holding 1.0 of A, a reaction A → B and a `TransportFlux` moving A out, both fast, ended the step at A = −1.0 (total mass conserved). Pinned by `tests/bio/test_moddoc_findings_world_simulator.py`.



## Rate laws and modulation
`_desired_extent` turns one spec into a pre-ration extent.

- **No law** — `rate_constant × Π [reactant]^stoichiometry`.
- **Law naming a reactant** — `eval_rate(rate_law)` is the whole rate (`Vmax·S/(Km+S)`); `rate_constant` is ignored.
- **Law naming no reactant** — `eval_rate(rate_law) × Π [reactant]^stoichiometry`; `rate_constant` is still ignored.
- **Powers** — each `[reactant]^stoichiometry` is `ieee_pow`, so a concentration below the snap under a fractional stoichiometry is NaN and the reaction does not run, as JAX reads it; until 2026-10 the power was complex and raised `TypeError` at the clamp.
- **Modulators** — the rate is multiplied by `_modulation_factor`, the product over modifiers of the terms below, read at the frozen concentration `m`.
- **Then** — `× dt`; NaN becomes 0; the result is clamped to `[0, RATE_CAP]`.

| `Modulation.kind` | Needs | Term |
| --- | --- | --- |
| `activator` | `a` | numerator × `(1 + a·m)` |
| `inhibitor` | `Ki` | denominator × `(1 + m/Ki)` |
| `michaelis` | `Vmax`, `K` | × `Vmax·m / (K + m)`, 0 when `K + m ≤ 0` |
| `hill` | `Vmax`, `K`, `n` | × `Vmax·mⁿ / (Kⁿ + mⁿ)`, 0 when the denominator ≤ 0 |
| anything else, or a needed field `None` | — | inert, factor 1 |

A `mod` node inside a `rate_law` uses `rate_expr.modulation_factor`, the same arithmetic but with defaults `Vmax = 1.0` and `n = 2.0` where the modulator path above treats a missing field as inert.



## Rounding floor, rate cap and subnormals

| Constant | Value | Where | Effect |
| --- | --- | --- | --- |
| `SUBNORMAL_FLOOR` | ≈ 2.2e-308 | start of `step` | a subnormal concentration is zero |
| `ROUNDING_FLOOR` | 1e-12 | reactant subtraction | a result in `(−1e-12, 0)` is float residue of an exact zero and is written as 0 |
| `ROUNDING_FLOOR` | 1e-12 | `eval_rate`'s `div` | a divisor smaller than this in magnitude yields 0, on both backends |
| `RATE_CAP` | 1e150 | end of `_desired_extent` | an infinite desire is "all of it" |

The subnormal flush copies XLA's denormals-are-zero, which the JAX core already runs under; without it a non-Lipschitz law such as `sqrt(x)` takes off from a 1e-309 seed on one backend and never on the other. The cap leaves the bound to the ration, which scales a capped extent down to what the pool holds. `ROUNDING_FLOOR` and `RATE_CAP` live once, in `bio/rate_expr.py`, and both simulators import them (T054). Only reactant subtraction snaps; a negative left by a flow or the cross-pass over-draw above is not snapped.



## Parity with JaxWorldSimulator
[[ABIO JaxWorldSimulator]] takes the same `ReactionSpec` list, runs the reaction pass as padded tensors on device, and runs `apply_flows` and `apply_population_laws` on the host from the same functions, so only the reaction arithmetic is implemented twice. `tests/capabilities/test_simulator_conformance.py` holds the two to `abs=1e-8, rel=1e-8` over hypothesis-generated systems and every suite block, and to 1e-9 on the pinned divide-by-an-exhausted-species case.

| | `WorldSimulatorImpl` | `JaxWorldSimulator` |
| --- | --- | --- |
| Subnormals | flushed explicitly | XLA denormals-are-zero; the host passes get the unflushed input |
| Flows | any `Flow` | any `Flow` in `step`/`run`; `native_flows` tuples on device |
| Population laws | `step`, `run` | `step`, `run`; `run_fast` and `run_batch` raise `ValueError` |
| Final state only, batched | — | `run_fast`, `run_batch` |
| Precision | float64 | float64 by default; `dtype="float32"` gives up parity |



## Sampling
`run` copies `state`, then for `i` in `0 … steps−1` records a copy of the current state when `i % sample_every == 0` and steps once; it always appends a copy of the final state. The timeline therefore starts with the initial state, holds `ceil(steps / sample_every) + 1` states, and its last entry is the state after `steps` steps even when that step is off the sampling grid. `steps = 0` returns the initial copy alone; `sample_every = 0` raises `ZeroDivisionError`. Every state shares the input state's tree; `suite/verify.simulate` mirrors these indices when it labels a timeline.




# BRIEF
- 2026-10-18 — written as the first ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD 84f8190; every member and claim traced to `bio/world_simulator.py`, `flow.py`, `population.py`, `rate_expr.py`, `world_state.py`, `jax_simulator.py` and the conformance tests. Left out: the private passes (`_desired_extent`, `_modulation_factor`, `_apply_reactions`, `_apply_population_laws`, `_flush_subnormals`), which appear in the figure and Semantics but get no member block, and `__repr__`. Constructor block ids are `^init` and `^reactionspec-init`, not the literal `--init--`. The cross-pass over-draw (§ The min-ratio ration) was reproduced against HEAD, not fixed; the class docstring's example (`GeneralFlow(child=…, molecule=…, rate_constant=…)`) and its pointer to the deleted `ReferenceSimulatorImpl` are stale in the source.
- 2026-10-28 — § Rate laws and modulation: the mass-action powers go through `ieee_pow` (a negative base under a fractional stoichiometry raised `TypeError` on the reference, read 0 on JAX).
- 2026-10-28 — `from_chemistry`'s non-numeric-rate guard removed (unreachable since `ReactionImpl` refuses one), with the matching dead guards in `suite/verify.simulate` and `suite/perturbations.perturb_rate`.
