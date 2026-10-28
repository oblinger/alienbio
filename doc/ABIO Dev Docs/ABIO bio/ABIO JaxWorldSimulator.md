---
description: "`JaxWorldSimulator`: the JAX stepper that must match the reference world simulator to 1e-9. Source: `src/alienbio/bio/jax_simulator.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO bio](ABIO%20bio.md) → [ABIO JaxWorldSimulator](ha://p/ABIO%20JaxWorldSimulator) 
# ABIO JaxWorldSimulator
The JAX world simulator: the same reactions, flows and population laws as the reference, with the reaction step compiled into one vectorised kernel over a `[compartments, molecules]` array.

![[ABIO JaxWorldSimulator.svg|2400]] 
*Parity with the reference* is the topic that governs the step kernel's clamps (NaN → 0, `RATE_CAP`, the `ROUNDING_FLOOR` snap).

This page covers the class in `bio/jax_simulator.py`: what it builds once, what each of its four run paths accepts, and what holds it to the reference. The kernels it drives are in `bio/jax_core.py`, the rate-law tree and the shared constants in `bio/rate_expr.py`, the host passes in `bio/flow.py` (`apply_flows`) and `bio/population.py` (`apply_population_laws`). The reference it is measured against is [[ABIO WorldSimulatorImpl]]; the subsystem's seams are in [[ABIO-Bio-Engine]]. No instrument path builds one today — `suite/verify.simulate` runs the reference — so its callers are the conformance tests and `protocols/_conformance.py`, which pins it to the `Simulator` protocol under pyright.



## JaxWorldSimulator Interface
A stepper over one world's topology and reactions, built once and run many times. It satisfies `protocols.bio.Simulator` (`tree`, `dt`, `step`, `run`). Its construction lowers every reaction to padded tensors and compiled JAX functions; after that, `step` and `run` advance a `WorldStateImpl` with reactions on the device and flows and population laws on the host, while `run_fast` and `run_batch` keep the whole trajectory on the device and therefore refuse anything the device array cannot express: Python flow objects and population laws, which move multiplicity. It needs JAX installed and raises `ImportError` without it.

| JaxWorldSimulator | |
| --- | --- |
| [[#^jaxworldsimulator\|JaxWorldSimulator]] | Build the tensors and kernels for one world |
| [[#^tree\|tree]] | The compartment topology |
| [[#^dt\|dt]] | Time step |
| [[#^num-molecules\|num_molecules]] | Molecule vocabulary size |
| [[#^dtype\|dtype]] | `"float64"` or `"float32"` |
| [[#^flows\|flows]] | Host-side flow objects |
| [[#^native-flows\|native_flows]] | Compiled linear transfers |
| [[#^step\|step]] | One step: device reactions, then host passes |
| [[#^run\|run]] | Host loop over `step`, sampled timeline |
| [[#^run-fast\|run_fast]] | Whole trajectory on the device, final state |
| [[#^run-batch\|run_batch]] | Many trajectories in one `vmap` |

**JaxWorldSimulator** `(tree: CompartmentTreeImpl, reactions: List[ReactionSpec], num_molecules: int, dt: float = 1.0, flows: Optional[List[GeneralFlow]] = None, native_flows: Optional[Sequence[NativeFlow]] = None, population_laws: Optional[Sequence[PopulationLaw]] = None, dtype: str = "float64") -> None`
    Build the stepper. `reactions` must already be keyed by molecule id, rate laws included — `WorldSimulatorImpl.from_chemistry` produces exactly this, and the conformance tests pass its `_reactions` straight in. Raises `ImportError` when JAX is absent, `ValueError` when a reaction's `compartments` names an id outside `0..num_compartments-1` (`world_simulator.check_reaction_compartments`, the reference's own check, since `40c5c09`), and `ValueError` for any `dtype` but the two names. `"float64"` turns on JAX's process-wide `jax_enable_x64` flag. Builds the reaction, modulation and rate-law tensors once and the step and run kernels from them ([[#Lowering a world]]); population laws are held for the host pass and have no device form. ^jaxworldsimulator

**tree** `: CompartmentTreeImpl`
    The topology passed in; `num_compartments` is read from it once, at construction. ^tree

**dt** `: float`
    The step length every kernel was built with; fixed for the object's life. ^dt

**num_molecules** `: int`
    The width of the molecule axis of the state array. ^num-molecules

**dtype** `: str`
    The name given at construction, `"float64"` (the default, for parity) or `"float32"` (speed, at the cost of [[#Parity with the reference]]). ^dtype

**flows** `: List[GeneralFlow]`
    The list `step` hands to `apply_flows` each step. Typed `GeneralFlow`, but any `Flow` works: a `TransportFlux` takes the rationed frozen-state pass, a `GeneralFlow` runs after the fluxes, as in the reference. Its presence makes `run_fast` and `run_batch` refuse. ^flows

**native_flows** `: List[NativeFlow]`
    The `(src, dst, molecule, rate)` tuples compiled into the step kernel and so into all four paths ([[#Native flows]]). Captured by the kernels at construction; treat it as read-only. ^native-flows

**step** `(state: WorldStateImpl) -> WorldStateImpl`
    Copy the concentrations into an array, run the jitted step kernel (reactions, then native flows), copy the result back into a copy of `state`, then run `apply_flows` and `apply_population_laws` on the host against `state` as the frozen start-of-step state — the same passes and the same frozen state the reference uses. Returns a new state; `state` is not modified. See [[#What each path accepts]]. ^step

**run** `(state: WorldStateImpl, steps: int, sample_every: Optional[int] = None) -> List[WorldStateImpl]`
    A host loop over `step`, the same shape as the reference's `run`: a copy of the current state every `sample_every` steps (default every step), plus the final state always. Accepts everything `step` accepts; one host↔device copy per step. ^run

**run_fast** `(state: WorldStateImpl, steps: int) -> WorldStateImpl`
    Run `steps` steps inside one jitted `jax.lax.fori_loop`, the state never leaving the device, and return only the final state. Raises `ValueError` when the object holds population laws, then when it holds any `flows`, rather than dropping them; native flows are compiled in. Compiles once per distinct `steps` ([[#Compilation and batching]]). ^run-fast

**run_batch** `(states: Sequence[WorldStateImpl], steps: int) -> List[WorldStateImpl]`
    Stack the states into `[B, C, M]` and run every trajectory in one `jax.vmap` of the `run_fast` loop; returns the B final states in input order. The same two refusals as `run_fast`; an empty `states` returns `[]`. The states must share this object's topology and molecule count — nothing checks it beyond the stack's shapes. ^run-batch



## jax_simulator Interface
The module exports the class and three names it is typed by.

| jax_simulator | |
| --- | --- |
| [[#^has-jax\|HAS_JAX]] | Whether JAX imported |
| [[#^nativeflow\|NativeFlow]] | The native flow tuple type |
| [[#^array\|Array]] | The annotation for a JAX array |

**HAS_JAX** `: bool`
    `True` when `import jax` succeeded. The module imports without JAX so the package types and loads anyway; the constructor checks this and raises. ^has-jax

**NativeFlow** `= Tuple[int, int, int, float]`
    `(src_compartment, dst_compartment, molecule_id, rate)`, by integer index. ^nativeflow

**Array** `= Any`
    A JAX array in annotations, `Any` so the module types without JAX installed; the same alias as `jax_core.Array`. ^array




# JaxWorldSimulator Semantics

## Lowering a world
Construction turns the reaction list into device data once, through `jax_core`:

| Built by | What | Shape |
| --- | --- | --- |
| `build_reaction_tensors` | reactant and product stoichiometry, rate constants, active-compartment mask | `[Rn, M]`, `[Rn, M]`, `[Rn]`, `[Rn, C]` |
| `build_modulation_tensors` | each reaction's modulators: molecule, kind code (activator, inhibitor, michaelis, hill), parameters | `[Rn, Mn]`, `[Rn, Mn]`, `[Rn, Mn, 3]`, or `None` when no reaction is modulated |
| `build_rate_laws` | one `(index, fn, implicit)` per reaction with a `rate_law` | `fn: S -> [C]` |

Each law's `fn` calls `rate_expr.lower_jax` with the column function `int(mol_id)`, so the tree's species must already be molecule ids. The tree is traced once under `jit`, not interpreted per step. A law that names a reactant replaces mass action; one that names none multiplies it (`implicit_mass_action`); either way the reaction's `rate_constant` is not used. `make_step_fn` closes over all of it and returns a pure `S -> S` function (`apply_reactions`, then `apply_native_flows`), which the class jits as the step kernel and wraps in `make_run_fn`'s jitted `fori_loop`.

The modulation math in the kernel goes through `jax_core._where`, a typed three-argument `jnp.where`: after a jax upgrade (2026-10-07) the stub's return type widened to include the one-argument form's tuple, and arithmetic on the result became a pyright error.



## What each path accepts

| | reactions, native flows | `flows` | population laws | returns |
| --- | --- | --- | --- | --- |
| `step` | device | host, `apply_flows` | host, `apply_population_laws` | one state |
| `run` | device | host | host | sampled timeline |
| `run_fast` | device | refuses | refuses | final state |
| `run_batch` | device | refuses | refuses | B final states |

Inside a step the order is: reactions (simultaneous, rationed), native flows, then the flow pass, then the population pass — the reference's order, with native flows added after reactions. The two host passes read their demand off the input `state` as frozen, not the post-reaction state, and ration against the pool as it stands in the post-reaction `new_state`, matching the reference. Every returned state is a `copy()` of its input with the concentrations replaced, so multiplicity changes only through the population pass; on the device paths it comes back as it went in. Refusing rather than skipping is the F8 lesson: the JAX path once dropped flows in silence, and until T053 a world with population laws ran a different model here (microcosm juveniles 172 against 20).



## Parity with the reference
The contract is the one `bio/__init__.py` states: the reference and JAX steppers agree to 1e-9. It holds because both run the same arithmetic: desired extents from the frozen state, single-pass min-ratio rationing of shared reactants, extents applied at once. Three clamps and two zero rules are shared, with the constants imported from `rate_expr` by both:

- **NaN is no reaction** — a NaN desired extent becomes 0.
- **Infinity is everything** — a desired extent is capped at `RATE_CAP` (1e150), and rationing then bounds it by what is there.
- **Negative is nothing** — a desired extent is floored at 0.
- **Rounding snap** — a concentration in `(-ROUNDING_FLOOR, 0)` (1e-12) after the update is set to 0. The kernel snaps once, after the fused `extentᵀ · (P − R)`; the reference snaps each reactant subtraction before adding products, so the two differ only by rounding.
- **Divide by nearly zero** — a divisor below `ROUNDING_FLOOR` makes the quotient 0, in both `eval_rate` and `lower_jax`. Before T054 a `1/[x]` law read the reference's 1e-16 residue as a `RATE_CAP` rate while JAX read 0, and the two backends swapped 1.04 between two pools.

Subnormal concentrations are zero on both: XLA runs denormals-are-zero, and the reference flushes them at the start of each step to match. Float64 is the default for the same reason (F9); `"float32"` trades the contract for speed.

The tests in `tests/capabilities/test_simulator_conformance.py` hold it: hypothesis-drawn reaction systems (every modulation kind, compiled rate laws, one or two compartments) at 1e-8 absolute and relative over 60 examples; every library block, flows and population laws included, at 1e-8 on concentrations and multiplicity; and the `1/[x]` regression at 1e-9. `tests/unit/test_m24_jax.py` covers the dtype, the flow paths, the refusals and batching; `tests/suite/test_transport.py` checks that `step` runs the same rationed flow pass as the reference. Not covered by those properties: native flows (there is no reference form) and laws whose arithmetic Python refuses where JAX does not — `0 ** -1` raises in `eval_rate` and is `inf` in `lower_jax`.



## Native flows
A native flow `(src, dst, mol, rate)` moves `min(dt · rate, 1) · S[src, mol]` from `src` to `dst`, so a rate faster than the step empties the pool and cannot drive it negative (T053). It is a pure JAX op, so it compiles into every path. Native flows run in list order, after reactions, on the post-reaction array, and move concentration, not amount: compartment volume and multiplicity do not enter. That is a different rule from `apply_flows`, which reads the frozen state, rations summed demand and conserves amount, so a native flow and a `TransportFlux` with the same rate do not give the same trajectory.



## Compilation and batching
The step kernel is jitted once at construction and compiles on its first call. The run kernel is jitted with `steps` static, so each distinct `steps` value compiles its own loop. `run_batch` wraps a new `jax.jit` around the `vmap` on every call, so each call compiles again; the batch runs as one device program, and the B results come back by copying each slice into a copy of its own input state.




# BRIEF
- 2026-10-18 — written as an ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD 84f8190; claims checked against `jax_simulator.py`, `jax_core.py`, `rate_expr.py`, `world_simulator.py`, `flow.py`, `population.py`, `protocols/bio.py`, `protocols/_conformance.py` and the tests named in § Parity with the reference. The private converters (`_state_to_array`, `_array_to_state`) have no member blocks; § What each path accepts says what they do. `jax_core`'s own functions appear only as far as this class drives them, since `jax_core.py` has no module doc yet. The constructor's row carries the class name rather than `__init__`, because the facet's block-id rule would make `^--init--`. The stated contract is 1e-9 while the two hypothesis properties assert 1e-8; the page reports both and does not pick.
- 2026-10-28 — refreshed against 0eb23e5: the constructor block names the compartment-id refusal both simulators share (`40c5c09`). Figure still true.
