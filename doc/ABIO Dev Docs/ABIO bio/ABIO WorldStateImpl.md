---
description: "`WorldStateImpl`: the dense multi-compartment store of concentrations, multiplicities and volumes that every simulator step reads and copies. Source: `src/alienbio/bio/world_state.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO bio](ABIO%20bio.md) → [ABIO WorldStateImpl](ha://p/ABIO%20WorldStateImpl) 
# ABIO WorldStateImpl
The world's state at one instant: a flat list of concentrations indexed compartment × molecule, plus a multiplicity and a volume per compartment, optionally labelled with real compartment and molecule ids.

![[ABIO WorldStateImpl.svg|2400]] 
*Storage layout and indexing* is the topic that governs the flat `_concentrations` row and its unchecked overflow arc; *Copies across a step* governs the frozen-input / written-copy pair along the top.

The value every simulator passes around: [[ABIO WorldImpl]] builds the initial one, [[ABIO WorldSimulatorImpl]] and [[ABIO JaxWorldSimulator]] read a frozen state and return a written copy, and the trial runner reads observations, readouts and the final record off it and writes `Intervene` setpoints into it. This page covers the store and the contract its readers and writers rely on; what each pass computes is on the simulator pages, [[ABIO TransportFlux]] and [[ABIO PopulationLaw]]; the topology it is indexed by is `bio/compartment_tree.py`; the subsystem view, with its seams, is [[ABIO-Bio-Engine]].



## WorldStateImpl Interface
A mutable, unvalidated container: every setter writes in place, nothing checks an index against the axes it should fit ([[#Storage layout and indexing]]), and nothing stops two holders of one instance seeing each other's writes. The simulators keep it safe by convention — they never write their input, only a `copy()`, which duplicates the three lists and the id axes (O(compartments × molecules)) and shares the compartment tree ([[#Copies across a step]]). Pure Python `List[float]`; `__slots__`, so no attribute can be added after construction. It does not inherit the `WorldState` Protocol (`protocols/bio.py`); conformance is structural, asserted under `TYPE_CHECKING` in `protocols/_conformance.py`. The Protocol names neither volume, `amount`, the id axes nor `concentration`.

| WorldStateImpl | |
| --- | --- |
| [[#^init\|__init__]] | Build a state over a tree; zeros and ones by default |
| [[#^tree\|tree]] | The compartment topology, shared with copies |
| [[#^num-compartments\|num_compartments]] | Compartment count, read live from the tree |
| [[#^num-molecules\|num_molecules]] | Size of the molecule axis |
| [[#^compartment-ids\|compartment_ids]] | Real id per compartment index, or `None` |
| [[#^molecule-ids\|molecule_ids]] | Real id per molecule index, or `None` |
| [[#^get\|get]] | Read one concentration by integer index |
| [[#^set\|set]] | Write one concentration by integer index |
| [[#^get-compartment\|get_compartment]] | One compartment's concentrations, as a new list |
| [[#^set-compartment\|set_compartment]] | Overwrite one compartment's concentrations |
| [[#^concentration\|concentration]] | Read one concentration by real ids |
| [[#^get-multiplicity\|get_multiplicity]] | Instance count of a compartment |
| [[#^set-multiplicity\|set_multiplicity]] | Write a compartment's instance count |
| [[#^get-all-multiplicities\|get_all_multiplicities]] | Every multiplicity, as a new list |
| [[#^get-volume\|get_volume]] | Volume of a compartment |
| [[#^set-volume\|set_volume]] | Write a compartment's volume |
| [[#^get-all-volumes\|get_all_volumes]] | Every volume, as a new list |
| [[#^amount\|amount]] | Multiplicity × volume × concentration |
| [[#^total-molecules\|total_molecules]] | Multiplicity × concentration, volume ignored |
| [[#^copy\|copy]] | An independent state on the same tree |
| [[#^as-array\|as_array]] | Concentrations as a `[C × M]` array |
| [[#^from-array\|from_array]] | Overwrite concentrations from an array |

**__init__**`(tree: CompartmentTreeImpl, num_molecules: int, initial_concentrations: Optional[List[float]] = None, initial_multiplicities: Optional[List[float]] = None, compartment_ids: Optional[List[str]] = None, molecule_ids: Optional[List[str]] = None, initial_volumes: Optional[List[float]] = None) -> None`
    Size the store from `tree.num_compartments` at this moment and `num_molecules`. Each given list is copied; `ValueError` when `initial_concentrations` is not exactly `num_compartments × num_molecules` long, or `initial_multiplicities` / `initial_volumes` not `num_compartments` long. Defaults: concentrations 0.0, multiplicities 1.0, volumes 1.0. The id lists become tuples; their lengths must match the axes — `ValueError` when `molecule_ids` is not `num_molecules` long or `compartment_ids` not `num_compartments` long (until 2026-10 a wrong length was accepted) ([[#Self-describing and pure-int states]]). ^init

**tree**`: CompartmentTreeImpl` (property)
    The tree passed at construction, the same object every `copy()` carries. `CompartmentTreeImpl` is mutable (`add_root`, `add_child`); the class docstring and `copy()`'s comment call it immutable, but nothing enforces that ([[#Copies across a step]]). ^tree

**num_compartments**`: int` (property)
    `tree.num_compartments`, read on every call rather than stored, so it tracks the tree and can disagree with the store's size if the tree grows after construction. ^num-compartments

**num_molecules**`: int` (property)
    The `num_molecules` given at construction: the row width of the flat store. ^num-molecules

**compartment_ids**`: Optional[tuple[str, ...]]` (property)
    `compartment_ids[i]` names compartment index `i`; `None` on a pure-int state. [[ABIO WorldImpl]] fills it from `build_tree`'s order. ^compartment-ids

**molecule_ids**`: Optional[tuple[str, ...]]` (property)
    `molecule_ids[j]` names molecule index `j`; `None` on a pure-int state. [[ABIO WorldImpl]] fills it with `chemistry.molecules.keys()`, the order `WorldSimulatorImpl.from_chemistry` assigns ids in. ^molecule-ids

**get**`(compartment: CompartmentId, molecule: MoleculeId) -> float`
    The concentration at flat index `compartment × num_molecules + molecule`. `IndexError` naming the id and its bound when either id is negative or past its axis ([[#Storage layout and indexing]]). ^get

**set**`(compartment: CompartmentId, molecule: MoleculeId, value: float) -> None`
    Write `value` at the same flat index, in place, with the same bounds check as `get`. Accepts any value — negative, NaN, infinite. Every simulator pass writes through it. ^set

**get_compartment**`(compartment: CompartmentId) -> List[float]`
    A new list of compartment `compartment`'s `num_molecules` concentrations (a slice). An out-of-range compartment raises `IndexError`. `JaxWorldSimulator` builds its device array from it. ^get-compartment

**set_compartment**`(compartment: CompartmentId, values: List[float]) -> None`
    Overwrite one compartment's row, in place. `ValueError` unless `len(values) == num_molecules`; an out-of-range compartment, negative included, raises `IndexError`. `JaxWorldSimulator` writes its result back through it. ^set-compartment

**concentration**`(compartment_id: str, molecule_id: str) -> float`
    The concentration by real ids: each id's position in its axis (`tuple.index`, a linear scan), then the flat store. `ValueError` on a pure-int state; `KeyError` naming the id when either is absent from its axis. `suite/arch_predict.py` and the verify and grade tests read through it. ^concentration

**get_multiplicity**`(compartment: CompartmentId) -> float`
    How many instances of the compartment exist; concentrations are per instance ([[#Concentration, amount and multiplicity]]). An out-of-range compartment, negative included, raises `IndexError`; so do `set_multiplicity`, `get_volume` and `set_volume`. ^get-multiplicity

**set_multiplicity**`(compartment: CompartmentId, value: float) -> None`
    Write the instance count, in place. Only the population pass changes it during a run (`apply_population_laws`, `bio/population.py`); [[ABIO WorldImpl]] sets it at construction. ^set-multiplicity

**get_all_multiplicities**`() -> List[float]`
    A copy of the multiplicity list, one entry per compartment. ^get-all-multiplicities

**get_volume**`(compartment: CompartmentId) -> float`
    The compartment's volume; 1.0 unless set, which keeps concentration equal to amount per instance in worlds that never set one. ^get-volume

**set_volume**`(compartment: CompartmentId, value: float) -> None`
    Write the volume, in place. Only [[ABIO WorldImpl]] sets it; no simulator pass changes it. ^set-volume

**get_all_volumes**`() -> List[float]`
    A copy of the volume list. ^get-all-volumes

**amount**`(compartment: CompartmentId, molecule: MoleculeId) -> float`
    `multiplicity × volume × concentration`: the extensive count that flows and population resource draws ration against and conservation checks read ([[#Concentration, amount and multiplicity]]). Same unchecked molecule index as `get`. ^amount

**total_molecules**`(compartment: CompartmentId, molecule: MoleculeId) -> float`
    `multiplicity × concentration`, volume ignored — equal to `amount` only where the volume is 1.0. Kept for the `WorldState` Protocol, which declares it; nothing in `src/` calls it. ^total-molecules

**copy**`() -> WorldStateImpl`
    A new state built through `__init__` with copies of the concentration, multiplicity and volume lists and the id axes, sharing the same `tree` object. Writes to either state never reach the other; a change to the tree reaches both ([[#Copies across a step]]). ^copy

**as_array**`() -> Any`
    The concentrations as a float64 numpy array of shape `(num_compartments, num_molecules)`; without numpy, a list of per-compartment lists. It is a copy (`np.array` copies), so writing the result does not reach the state; the docstring says so (it said "a view" until 2026-10). `ValueError` from `reshape` if the tree has grown since construction. `full_observation` reads every observation through it. ^as-array

**from_array**`(arr: Any) -> None`
    Replace the concentration list from an array, flattened row-major. With numpy the shape must be exactly `(num_compartments, num_molecules)` (`ValueError` otherwise — a transposed array of the right size used to be accepted silently); without numpy nothing is checked and a short input leaves the tail unchanged. `suite/verify.simulate` uses it to apply the environmental-pressure overlay to a copy. ^from-array



## world_state Interface
`alienbio.bio` and the top-level `alienbio` package both export `WorldStateImpl`; the Protocol it satisfies, `WorldState`, lives in `protocols/bio.py` and is exported from `alienbio.bio` too. The module's own names besides the class:

| world_state | |
| --- | --- |
| [[#^moleculeid\|MoleculeId]] | Alias for a molecule's integer index |
| [[#^compartmentid\|CompartmentId]] | Alias for a compartment's integer index |

**MoleculeId**`= int`
    A column of the store: the molecule's position on the molecule axis. ^moleculeid

**CompartmentId**`= int`
    A row of the store: the compartment's index in the tree. ^compartmentid




# WorldStateImpl Semantics

## Storage layout and indexing
Concentrations sit in one Python list of `num_compartments × num_molecules` floats, row-major: compartment `c`'s molecules occupy `c × num_molecules` up to `(c + 1) × num_molecules`. The row order is the tree's compartment numbering, which [[ABIO WorldImpl]] gets from `build_tree`; the column order is `chemistry.molecules.keys()`, the same order `WorldSimulatorImpl.from_chemistry` gives molecule ids, which is what lets a simulator's integer ids address a world's state. Multiplicities and volumes are two parallel lists of length `num_compartments`.

`_index` is `compartment × num_molecules + molecule` after one range test per axis: a molecule id outside `[0, num_molecules)` or a compartment id outside `[0, num_compartments)` raises `IndexError` naming the id and the bound, on `get`, `set`, `amount`, `total_molecules`, the compartment-row and multiplicity/volume accessors alike. The bound is the axes the state was sized for, fixed at construction. Until 2026-10 nothing was checked (verified against HEAD 84f8190 on a 2-compartment, 3-molecule state): `set(0, 3, v)` wrote the next compartment's first slot, `set(0, -1, v)` the last slot of the list, `get_multiplicity(-1)` returned the last compartment's and `get_compartment(2)` returned `[]`. The check costs nothing measurable on a golden run (12.1–12.8 s before, 12.1–12.2 s after). Pinned by `tests/bio/test_moddoc_findings_world_state.py`.



## Concentration, amount and multiplicity
Three quantities, two of them stored:

| Quantity | Stored | Meaning |
| --- | --- | --- |
| concentration | yes, per compartment × molecule | per instance, per unit volume |
| multiplicity | yes, per compartment | instance count (1e6 red cells is one compartment) |
| volume | yes, per compartment | per instance; 1.0 by default |
| `amount` | no | `multiplicity × volume × concentration`, the count conserved |
| `total_molecules` | no | `multiplicity × concentration`; volume dropped |

Who reads which:

- **Reaction pass** — reads and writes concentrations only (`WorldSimulatorImpl._apply_reactions`).
- **Flow pass** — rations each draw against `frozen.amount` (`bio/flow.py:493`) and writes `Δamount / (multiplicity × volume)` back as concentration (`TransportFlux.apply_events`).
- **Population pass** — rations multiplicity against `get_multiplicity` and resource draws against `get`, a resource law's own clamp against `amount` (`bio/population.py`), and writes both axes.
- **Conservation tests** — `tests/unit/test_conservation.py` checks `amount`.
- **Readouts and records** — read concentration via `get` ([[#Observation and intervention surface]]).

Where volume and multiplicity are 1.0 everywhere, concentration, `amount` and `total_molecules` agree, and the distinction is invisible.



## Copies across a step
`copy()` is the only way a new state is derived from an old one; nothing implements copy-on-write. Each simulator step is operator splitting over one frozen state:

1. **Flush** — `WorldSimulatorImpl.step` calls `_flush_subnormals`, which reads the private `_concentrations` list directly; if any value is subnormal it returns a `copy()` whose list it replaces with the flushed one, otherwise the input itself. This is the frozen state.
2. **Copy** — `new_state = state.copy()`.
3. **Passes** — every pass reads the frozen state and writes `new_state` through `set` / `set_multiplicity`, so no pass sees another's writes (a `GeneralFlow` excepted). The input is never written.
4. **Timeline** — `run` records `current.copy()` at each sample and at the end, so every timeline entry is independent.

`JaxWorldSimulator` crosses the same boundary by value: `_state_to_array` concatenates `get_compartment` rows into its device array `S`, and `_array_to_state` copies the input state (so multiplicity, volume and id axes come along unchanged) and writes each row back with `set_compartment`. It does no subnormal flush on the host; XLA's denormals-are-zero does it on the device, and the host flow and population passes read the unflushed input.

The tree is the one thing copies share. Because `num_compartments` is read live from it while the lists were sized once, adding a compartment to a tree that states already reference leaves them inconsistent: on a 2 × 3 state, `add_child` makes `num_compartments` 3 while the store still holds 6 floats, and `as_array` raises `ValueError` from `reshape`. No code path grows a tree after a state is built today.



## Self-describing and pure-int states
A state built with both id lists is *self-describing*: it can be read by name and folded back onto `Compartment` specs. [[ABIO WorldImpl]] always builds one, `copy()` propagates the axes, and so every state a trial produces carries them. A state built without them is *pure-int*, the form the simulator docstrings and many unit tests use.

| Reader | On a pure-int state |
| --- | --- |
| `concentration` | `ValueError` |
| `full_observation`, `narrow_observation` | `ValueError` |
| `_world_from_state` (runner) | `ValueError` |
| `readout_values`, `final_state_dict` | `{}` |
| simulators, `get`/`set` | unaffected |

The axes are labels only; the store never consults them. A molecule axis shorter than `num_molecules` leaves the unnamed molecules out of every observation and record with no error.



## Observation and intervention surface
How `suite/` reads and writes a state, as far as this module is involved:

- **Observation** — `full_observation` (`suite/observation.py`) reads `as_array` into one `{molecule_id: value}` dict per compartment; `narrow_observation` then hides ids by the `observability` dial, and the runner removes a drafter's `setup["hidden_ids"]` with `project_observation`. The state itself is never filtered.
- **Readouts** — `readout_values` (`suite/trial.py:270`) sums `get` across compartments per molecule, i.e. concentration; its docstring says "amount summed across compartments", which is true only where multiplicity and volume are 1.0.
- **Final record** — `final_state_dict` is `{compartment_id: {molecule_id: get(…)}}`.
- **Intervene on a molecule** — `_state_with_concentration` (`suite/runner.py:355`) copies the state and `set`s the molecule's concentration to the value in every compartment: a concentration setpoint, not an amount. An `Intervene` on a reaction changes the chemistry and leaves the state alone.
- **Destructive assay** — `_state_scaled` copies and multiplies every concentration by `1 − kill`; multiplicity is untouched.
- **Turn boundary** — `_world_from_state` reads `get`, `get_multiplicity` and `get_volume` for every compartment and builds a new [[ABIO WorldImpl]], whose constructor builds a fresh state; nothing carries the old instance across turns.




# BRIEF
- 2026-10-18 — written as an ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD 84f8190; every member and claim traced to `bio/world_state.py` and its readers and writers (`world.py`, `world_simulator.py`, `jax_simulator.py`, `flow.py`, `population.py`, `suite/runner.py`, `suite/trial.py`, `suite/observation.py`, `suite/verify.py`, `protocols/bio.py`). The unchecked-index table, the negative wrap, the `get_compartment` empty list, the copy-not-view `as_array`, the shape-blind `from_array`, the unchecked id-axis lengths and the grown-tree desync were each reproduced against HEAD, not fixed. Left out: `_index` (in Semantics, no block), `__repr__` and `__str__` (`__str__` counts only positive concentrations as nonzero). Constructor block id is `^init`. Drift recorded, not fixed: the "view" in `as_array`'s docstring, the "immutable" tree in the class docstring and `copy()`, and `readout_values`' "amount" docstring.
