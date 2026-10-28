---
description: "`protocols.bio`: the nine typing Protocols that state the chemistry substrate's surface — `Atom`, `Molecule`, `Reaction`, `Flow`, `GeneralFlow`, `Chemistry`, `CompartmentTree`, `WorldState`, `Simulator` — plus `_conformance`, the pyright-only file that assigns each implementation to its Protocol, and the package's export list. Source: `src/alienbio/protocols/bio.py`, `src/alienbio/protocols/_conformance.py`, `src/alienbio/protocols/__init__.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO protocols Modules](ABIO%20protocols%20Modules.md) → [ABIO Bio Protocols](ha://p/ABIO%20Bio%20Protocols) 
# ABIO Bio Protocols
The page for what the chemistry substrate promises its callers: the nine Protocols, the members each one requires, which concrete class satisfies it, and how that satisfaction is checked.

![ABIO Bio Protocols](ABIO%20Bio%20Protocols.svg) 
*Conformance* is the topic behind the dotted edges from each implementation to its Protocol: they are pyright assignments in a file that never runs, so a drift is a red `pyright src/`, not a runtime error.

`bio.py` declares; nothing in it executes. Each Protocol has one implementation in `bio/` — `AtomImpl`, `MoleculeImpl`, `ReactionImpl`, `ChemistryImpl`, `CompartmentTreeImpl`, `WorldStateImpl`, the `TransportFlux` and `GeneralFlow` classes of `bio/flow.py`, and two simulators, `WorldSimulatorImpl` and `JaxWorldSimulator` — each documented under [ABIO bio](../ABIO%20bio/ABIO%20bio.md). `bio/__init__.py` re-exports seven of the Protocols and the two id aliases beside the `*Impl` classes; its `Flow` and `GeneralFlow` are the ABCs from `bio/flow.py`, not the Protocols. In `src/` the Protocols annotate only `WorldState` under `TYPE_CHECKING` in `suite/observation.py` and `suite/types.py`; `isinstance(x, Reaction)` appears in tests alone. The tree the chemistry objects stand on is [ABIO infra Entity](../ABIO%20infra%20Modules/ABIO%20infra%20Entity.md) and the graph queries `Chemistry` declares run in [ABIO GraphView](../ABIO%20infra%20Modules/ABIO%20GraphView.md). The published listing is [ABIO Protocols](../../ABIO%20Ref/ABIO%20Protocols.md); the subsystem view is [ABIO-Infra](../../ABIO%20Architecture/ABIO-Infra.md).



## Atom Interface
`@runtime_checkable`. Implemented by `AtomImpl` (`bio/atom.py`).

| Atom | |
| --- | --- |
| [symbol](#^symbol) | One or two letters |
| [name](#^name) | Human-readable element name |
| [atomic_weight](#^atomic-weight) | Mass in atomic mass units |

**symbol**`: str` (property)
    `"C"`, `"Na"`. The key a `Chemistry`'s `atoms` mapping uses. ^symbol

**name**`: str` (property)
    `"Carbon"`. ^name

**atomic_weight**`: float` (property)
    Read by `Molecule.molecular_weight`. ^atomic-weight



## Molecule Interface
`@runtime_checkable`. Implemented by `MoleculeImpl` (`bio/molecule.py`).

| Molecule | |
| --- | --- |
| [local_name](#^local-name) | Name inside its parent entity |
| [atoms](#^atoms) | Composition, atom → count |
| [bdepth](#^bdepth) | Biosynthetic depth |
| [name](#^molecule-name) | Human-readable name |
| [symbol](#^molecule-symbol) | Formula derived from atoms |
| [molecular_weight](#^molecular-weight) | Sum of atom weights |

**local_name**`: str` (property)
    From `Entity`. ^local-name

**atoms**`: Mapping[Any, int]` (property)
    Keyed by atom; typed `Any` because `Mapping` keys are invariant and `AtomImpl` would not assign to `Atom`. ^atoms

**bdepth**`: int` (property)
    0 for a primitive; part of the graph-match key. ^bdepth

**name**`: str` (property)
    The id every graph query and the name map use. ^molecule-name

**symbol**`: str` (property)
    `"C6H12O6"`. ^molecule-symbol

**molecular_weight**`: float` (property)
    Computed from `atoms`. ^molecular-weight



## Reaction Interface
`@runtime_checkable`. Implemented by `ReactionImpl` (`bio/reaction.py`). A reaction acts within one compartment; there is no `rate_law` member, though `ReactionImpl` carries one and both simulators read it.

| Reaction | |
| --- | --- |
| [local_name](#^reaction-local-name) | Local name |
| [name](#^reaction-name) | Human-readable name |
| [symbol](#^reaction-symbol) | `A + B -> C` |
| [reactants](#^reactants) | Molecule → coefficient consumed |
| [products](#^products) | Molecule → coefficient made |
| [modifiers](#^modifiers) | Molecule → modulation or role tag |
| [rate](#^rate) | The mass-action constant |

**local_name**`: str` (property)
    From `Entity`. ^reaction-local-name

**name**`: str` (property)
    The reaction's id. ^reaction-name

**symbol**`: str` (property)
    The formula string. ^reaction-symbol

**reactants**`: Mapping[Any, float]` (property)
    Keyed by molecule, typed `Any` for the reason `atoms` is. ^reactants

**products**`: Mapping[Any, float]` (property)
    As `reactants`. ^products

**modifiers**`: Mapping[Any, Any]` (property)
    A `bio.reaction.Modulation` (activator, inhibitor, Hill …) changes the rate; a bare string role tag (`"catalyst"`) does not. Empty for an unmodified reaction. ^modifiers

**rate**`: float` (property)
    A number only: a state-dependent rate is a compiled `rate_law`, and `ReactionImpl` refuses a callable. ^rate



## Flow Interface
`@runtime_checkable`. Implemented by `TransportFlux` (`bio/flow.py`), which `bio/flow.py`'s flow pass runs rationed.

| Flow | |
| --- | --- |
| [origin](#^origin) | The compartment the flow is anchored to |
| [name](#^flow-name) | Human-readable name |
| [is_membrane_flow](#^is-membrane-flow) | Origin ↔ parent transport |
| [is_general_flow](#^is-general-flow) | Arbitrary state edit |
| [compute_flux](#^compute-flux) | The flux for a state |
| [attributes](#^flow-attributes) | Semantic content |

**origin**`: CompartmentId` (property)
    An `int` compartment index. ^origin

**name**`: str` (property)
    The flow's id. ^flow-name

**is_membrane_flow**`: bool` (property)
    True for origin-to-parent transport. ^is-membrane-flow

**is_general_flow**`: bool` (property)
    True for a `GeneralFlow`. ^is-general-flow

**compute_flux**`(state: WorldStateImpl, tree: CompartmentTreeImpl) -> float`
    Typed on the concrete state and tree classes, not on the `WorldState` and `CompartmentTree` Protocols (§ [Concrete types in the contracts](#concrete-types-in-the-contracts)). ^compute-flux

**attributes**`() -> dict[str, Any]`
    For serialization, as `Entity.attributes`. ^flow-attributes



## GeneralFlow Interface
`@runtime_checkable`; extends `Flow`. Implemented by `bio.flow.GeneralFlow`. The docstring calls it a placeholder for edits the transport pattern does not fit.

| GeneralFlow | |
| --- | --- |
| [description](#^description) | What the edit does |
| [apply](#^apply) | Mutate the state in place |

**description**`: str` (property)
    Free text. ^description

**apply**`(state: WorldStateImpl, tree: CompartmentTreeImpl, dt: float) -> None`
    Only a general flow has one; a `TransportFlux` is applied by the flow pass, which rations it. ^apply



## Chemistry Interface
`@runtime_checkable`. Implemented by `ChemistryImpl` (`bio/chemistry.py`), whose graph queries delegate to `infra/graph_ops.py`.

| Chemistry | |
| --- | --- |
| [local_name](#^chemistry-local-name) | Local name |
| [atoms](#^chemistry-atoms) | Symbol → atom |
| [molecules](#^molecules) | Name → molecule |
| [reactions](#^reactions) | Name → reaction |
| [validate](#^validate) | Consistency messages |
| [neighbors](#^neighbors) | Bipartite adjacency |
| [paths](#^paths) | Simple paths by name |
| [subgraph](#^subgraph) | Induced sub-chemistry |
| [match](#^match) | Pattern embeddings |

**local_name**`: str` (property)
    From `Entity`. ^chemistry-local-name

**atoms**`: Mapping[str, Atom]` (property)
    By symbol. ^chemistry-atoms

**molecules**`: Mapping[str, Molecule]` (property)
    By name; dict order is the state's column order downstream. ^molecules

**reactions**`: Mapping[str, Reaction]` (property)
    By name. ^reactions

**validate**`() -> list[str]`
    An empty list when consistent. ^validate

**neighbors**`(node: str) -> set[str]`
    Molecule ↔ reaction adjacency by name. ^neighbors

**paths**`(a: str, b: str, max_len: int = 8) -> list[list[str]]`
    All simple paths within `max_len` edges. ^paths

**subgraph**`(nodes: Iterable[str]) -> Chemistry`
    Edges to dropped nodes removed. ^subgraph

**match**`(pattern: Any) -> list[dict[str, str]]`
    `pattern` is typed `Any`; `ChemistryImpl` takes a `ChemistryImpl`. ^match



## CompartmentTree Interface
`@runtime_checkable`. Implemented by `CompartmentTreeImpl` (`bio/compartment_tree.py`). Ids are `int`s.

| CompartmentTree | |
| --- | --- |
| [num_compartments](#^num-compartments) | Count |
| [parent](#^parent) | Parent id, `None` at the root |
| [children](#^children) | Child ids |
| [root](#^root) | The root id |
| [is_root](#^is-root) | Whether an id is the root |

**num_compartments**`: int` (property)
    The row count of every state on this tree. ^num-compartments

**parent**`(child: CompartmentId) -> CompartmentId | None`
    `None` for the root. ^parent

**children**`(parent: CompartmentId) -> list[CompartmentId]`
    A copy, in the order children were added. ^children

**root**`() -> CompartmentId`
    The one root. ^root

**is_root**`(compartment: CompartmentId) -> bool`
    True when the id's parent entry is `None`. ^is-root



## WorldState Interface
`@runtime_checkable`. Implemented by `WorldStateImpl` (`bio/world_state.py`): a dense compartments × molecules array plus a multiplicity per compartment, sharing its tree with its copies.

| WorldState | |
| --- | --- |
| [tree](#^tree) | The compartment tree |
| [num_compartments](#^worldstate-num-compartments) | Rows |
| [num_molecules](#^num-molecules) | Columns |
| [get](#^get) | One concentration |
| [set](#^set) | Write one concentration |
| [get_compartment](#^get-compartment) | One row |
| [get_multiplicity](#^get-multiplicity) | Instance count of a compartment |
| [set_multiplicity](#^set-multiplicity) | Write it |
| [total_molecules](#^total-molecules) | Multiplicity × concentration |
| [copy](#^copy) | A copy sharing the tree |
| [as_array](#^as-array) | The 2-D array |

**tree**`: CompartmentTree` (property)
    The Protocol type here, where `Simulator.tree` names the concrete class. ^tree

**num_compartments**`: int` (property)
    Equals `tree.num_compartments`. ^worldstate-num-compartments

**num_molecules**`: int` (property)
    The molecule vocabulary size. ^num-molecules

**get**`(compartment: CompartmentId, molecule: MoleculeId) -> float`
    Both `int` indices. ^get

**set**`(compartment: CompartmentId, molecule: MoleculeId, value: float) -> None`
    In place. ^set

**get_compartment**`(compartment: CompartmentId) -> list[float]`
    One row. ^get-compartment

**get_multiplicity**`(compartment: CompartmentId) -> float`
    The population axis. ^get-multiplicity

**set_multiplicity**`(compartment: CompartmentId, value: float) -> None`
    In place. ^set-multiplicity

**total_molecules**`(compartment: CompartmentId, molecule: MoleculeId) -> float`
    `get_multiplicity(c) * get(c, m)`. ^total-molecules

**copy**`() -> WorldState`
    The array copied, the tree shared. ^copy

**as_array**`() -> Any`
    `[compartments × molecules]`; on `WorldStateImpl` a fresh NumPy copy, so writing to it changes nothing. ^as-array



## Simulator Interface
Not `@runtime_checkable`, unlike the other eight: `isinstance(x, Simulator)` raises `TypeError`. Implemented by `WorldSimulatorImpl` (`bio/world_simulator.py`) and `JaxWorldSimulator` (`bio/jax_simulator.py`). The banner above it in the source still reads "State (for single-compartment Chemistry simulations)".

| Simulator | |
| --- | --- |
| [tree](#^simulator-tree) | The compartment tree |
| [dt](#^dt) | Step size |
| [step](#^step) | One step |
| [run](#^run) | Many steps, optionally sampled |

**tree**`: CompartmentTreeImpl` (property)
    The concrete class. ^simulator-tree

**dt**`: float` (property)
    Simulated seconds per step. ^dt

**step**`(state: WorldStateImpl) -> WorldStateImpl`
    Marked `@abstractmethod`, which matters only to a class that subclasses `Simulator` explicitly; both implementations conform structurally. ^step

**run**`(state: WorldStateImpl, steps: int, sample_every: int | None = None) -> list[WorldStateImpl]`
    The trajectory, every `sample_every` steps when given; a `run` without `sample_every` was one of the two drifts that led T057 to add the conformance file. ^run



## bio Interface
The module-level names besides the Protocols.

| bio | |
| --- | --- |
| [MoleculeId](#^moleculeid) | `int` |
| [CompartmentId](#^compartmentid) | `int` |

**MoleculeId**` = int`
    A column index. Exported from `alienbio.bio`, not from `alienbio.protocols`. ^moleculeid

**CompartmentId**` = int`
    A row index. Exported the same way. ^compartmentid



## protocols Interface
`alienbio.protocols` re-exports the nine Protocols and nothing else; `from alienbio.protocols import *` is pinned by `tests/unit/test_protocol_conformance.py`, and `reportUnsupportedDunderAll = "error"` in `pyproject.toml` refuses a ghost name in `__all__`. The package docstring and a commented-out import still describe `infra` protocols (`Entity`, `IO`, `Expr`, `Context`) and `Pathway`/`Generators` that do not exist.




# Bio Protocols Semantics

## Conformance
`_conformance.py` imports the ten implementations and the nine Protocols under `if TYPE_CHECKING:` and defines one function whose body assigns each implementation-typed parameter to a Protocol-typed local (`_m: Molecule = molecule`, `_sim2: Simulator = jax`). Python never runs the block; `pyright src/`, the CI gate, checks every assignment, so a member renamed, retyped or dropped on either side is a type error at review time. It was added by T057 after two drifts went unnoticed (`TransportFlux.stoichiometry` keyed by `int` against a `str` Protocol, and a `run` without `sample_every`). What it cannot catch is a Protocol member nothing needs: a contract that says more than callers use stays green.



## Runtime checks
Eight of the nine are `@runtime_checkable`, so `isinstance` works on them, but a runtime check sees only that each member name exists, not its type or signature: a reaction whose `rate` is a callable passes `isinstance(x, Reaction)`. The static check above is the one that compares types. `Simulator`, without the decorator, cannot be used with `isinstance` at all.



## Concrete types in the contracts
The module docstring says the Protocols let alternative implementations stand in. `Flow.compute_flux`, `GeneralFlow.apply`, `Simulator.tree`, `Simulator.step` and `Simulator.run` name `WorldStateImpl` and `CompartmentTreeImpl` (imported under `TYPE_CHECKING`), so a second state or tree class cannot satisfy them, while `WorldState.tree` names the `CompartmentTree` Protocol. Today one state class and one tree class exist (the comment at the import says so), so the mixture costs nothing yet.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `7d390d6` (read from a `git archive` export; a concurrent worker editing `src/suite/`). Run against that export: `isinstance(object(), Simulator)` raising `TypeError`; `protocols.__all__` matching the nine names. Users of each Protocol by `git grep` over `src/` and `tests/` at that sha. Not run: `pyright` (the conformance file is pinned green by CI per the Pilot's notes). The task named a `protocols/report.py`; there is none at this sha. Findings filed on T088.
