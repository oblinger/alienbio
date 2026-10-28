---
description: "`WorldImpl` + its declaration records (`Compartment`, `Transport`, `GrowthLaw`, `DeathLaw`, `CountFlowSpec`) and `build_tree`: the one place string ids become integer indices. Source: `src/alienbio/bio/world.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO bio](ABIO%20bio.md) → [ABIO WorldImpl](ha://p/ABIO%20WorldImpl) 
# ABIO WorldImpl
A runnable world: a chemistry plus a flat list of compartment records, from which the constructor derives the integer-indexed tree, the initial state and the simulator-ready flows and population laws, once.

![[ABIO WorldImpl.svg|2400]] 
*Resolution: string ids to integers* is the topic that governs the dotted arrows leaving the declarations: each one is re-keyed through `build_tree`'s `comp_to_int` and the chemistry's molecule order.

The world every trial runs: the suite's generators and the Expr heads author it in readable string ids, and `suite/verify.simulate` hands its derived parts to the simulator. This page covers the records a world is declared from, the constructor that resolves them, and `build_tree`. The chemistry it holds is [[ABIO ChemistryImpl]]; the state it derives is `bio/world_state.py`; what its flows and laws become at run time is [[ABIO TransportFlux]] and [[ABIO PopulationLaw]]; the stepper that reads it is [[ABIO WorldSimulatorImpl]] and its JAX twin [[ABIO JaxWorldSimulator]]; the subsystem view, with its seams, is [[ABIO-Bio-Engine]].



## WorldImpl Interface
A chemistry, a tuple of `Compartment` records and optional `Transport` and population-law records, with everything the simulator needs derived from them in `__init__` and stored. It is the bio engine's single resolution point: no other code turns a compartment id or a molecule name into an integer index. It implements no Protocol (`protocols/bio.py` has no `World`), and `alienbio.bio` does not export it — callers import `alienbio.bio.world`, though that package's docstring lists it. `__slots__` and read-only properties, so attributes cannot be added or reassigned; the objects behind them are not frozen ([[#Immutability and rebuilds]]).

| WorldImpl | |
| --- | --- |
| [[#^init\|__init__]] | Build the world; derive tree, state, flows, laws |
| [[#^chemistry\|chemistry]] | The chemistry, as given |
| [[#^compartments\|compartments]] | The compartment records, as given |
| [[#^initial-state\|initial_state]] | The derived starting state |
| [[#^flows\|flows]] | The `Transport` records, as given |
| [[#^flow-objs\|flow_objs]] | The resolved `TransportFlux` objects |
| [[#^population-laws\|population_laws]] | The population-law records, as given |
| [[#^population-law-objs\|population_law_objs]] | The resolved `PopulationLaw` objects |

**__init__**`(chemistry: ChemistryImpl, compartments: tuple[Compartment, ...], flows: tuple[Transport, ...] = (), population_laws: tuple[PopulationLawSpec, ...] = ()) -> None`
    Store `chemistry` and `tuple(compartments)`, call `build_tree`, build a self-describing `WorldStateImpl` on that tree and fill it from each record ([[#The initial state's shape]]), then resolve every `Transport` to a `TransportFlux` and every law record to its `PopulationLaw` ([[#Resolution: string ids to integers]]). `ValueError` from `build_tree` when the records are not one rooted tree; `KeyError` when a record's concentrations, or any flow or law, name a compartment or molecule that does not exist; `TypeError` for a `population_laws` entry of any other type; `ValueError` from `TransportFlux` for a `rate_law` other than `"gradient"` or `"first_order"`. `ValueError` naming the transport and the compartment when a flux would move amount into a compartment of multiplicity × volume 0 (`dest`, or `origin` for an antiported species): it would hold none, so the sender's share would vanish (2026-10). Two records sharing an id are refused by `build_tree` with `ValueError` naming the id ([[#The compartment tree]]; until `235377b` a bare `KeyError` carrying an integer). The empty defaults for `flows` and `population_laws` leave a world that never sets them as it was before either existed. ^init

**chemistry**`: ChemistryImpl` (property)
    The chemistry passed in, the same object; its molecule dict's insertion order is the state's molecule axis. ^chemistry

**compartments**`: tuple[Compartment, ...]` (property)
    The records passed in, as a tuple, in the caller's order — not the tree's integer order, which `initial_state.compartment_ids` carries. ^compartments

**initial_state**`: WorldStateImpl` (property)
    The state derived in `__init__`, carrying both id axes so it can be read by name. The stored object itself, not a copy: a caller about to step it copies first, as `suite/verify.simulate` does. ^initial-state

**flows**`: tuple[Transport, ...]` (property)
    The string-id records passed in. Kept so a rebuilt world can re-thread them through a new constructor (`suite/runner._world_from_state` does each turn) and have them resolved against the new tree. ^flows

**flow_objs**`: tuple[Flow, ...]` (property)
    One `TransportFlux` per entry of `flows`, in the same order, with integer compartment and molecule ids — what `WorldSimulatorImpl.from_chemistry` takes as `flows=`. ^flow-objs

**population_laws**`: tuple[PopulationLawSpec, ...]` (property)
    The string-id law records passed in; kept for rebuilds, as `flows` is. ^population-laws

**population_law_objs**`: tuple[PopulationLaw, ...]` (property)
    One `PerCapitaGrowth`, `PerCapitaDeath` or `CountFlow` per entry of `population_laws`, in the same order — what `from_chemistry` takes as `population_laws=`. ^population-law-objs



## Compartment Interface
One node of a world's compartment tree, with its initial condition on board. A frozen dataclass built positionally in field order; the tree is the flat tuple of these, each naming its parent, so there is no separate topology record. Nothing in the record is checked until a `WorldImpl` is built from it.

| Compartment | |
| --- | --- |
| [[#^id\|id]] | The compartment's readable id |
| [[#^parent\|parent]] | The parent's id; `None` for the root |
| [[#^kind\|kind]] | A free label, such as `"cell"` |
| [[#^volume\|volume]] | Volume of one instance |
| [[#^concentrations\|concentrations]] | Initial concentration by molecule name |
| [[#^multiplicity\|multiplicity]] | Number of identical instances |

**id**`: NodeId`
    The string id flows and laws use to name this compartment, and the tree's name for the node. Must be unique among the world's records; nothing says so by name ([[#The compartment tree]]). ^id

**parent**`: Optional[NodeId]`
    The id of the enclosing compartment. Exactly one record per world has `None`. ^parent

**kind**`: str`
    Carried and copied by rebuilders; `WorldImpl` never reads it. ^kind

**volume**`: float`
    Written to the state when it is not `1.0`; the state's default is `1.0`. With multiplicity and concentration it gives amount ([[#The initial state's shape]]). ^volume

**concentrations**`: Mapping[str, float] = {}`
    Initial concentration per molecule name, per instance. A molecule left out starts at 0.0; a name not in the chemistry is a `KeyError` at construction. The mapping is held by reference inside the frozen record. ^concentrations

**multiplicity**`: float = 1.0`
    How many identical instances of this compartment exist; written to the state when it is not `1.0`. The population laws move it. ^multiplicity



## Transport Interface
A cross-compartment flux declared in string ids, so a block can author it before any integer tree exists (`suite.blocks.TransportBlock` does, at realize time). A frozen dataclass; `WorldImpl` turns each into a `TransportFlux`, whose arithmetic is [[ABIO TransportFlux]]'s.

| Transport | |
| --- | --- |
| [[#^origin\|origin]] | Compartment the flux draws from |
| [[#^dest\|dest]] | Compartment the flux feeds |
| [[#^stoichiometry\|stoichiometry]] | Molecule name → count moved per event |
| [[#^driver-molecule\|driver_molecule]] | Molecule whose concentration sets the rate |
| [[#^rate-constant\|rate_constant]] | `D` or `k`, by rate law |
| [[#^rate-law\|rate_law]] | `"gradient"` or `"first_order"` |
| [[#^name\|name]] | Label used in error messages |

**origin**`: NodeId`
    Any compartment id; origin and destination need no tree relation. ^origin

**dest**`: NodeId`
    Any compartment id. ^dest

**stoichiometry**`: Mapping[str, float]`
    Every species that moves, by name, with its count per event; each name must be in the chemistry. Need not contain `driver_molecule`. ^stoichiometry

**driver_molecule**`: str`
    The species whose concentration drives the rate law; must be in the chemistry. ^driver-molecule

**rate_constant**`: float = 1.0`
    Copied to the flux unchecked. ^rate-constant

**rate_law**`: str = "gradient"`
    Not checked here; `TransportFlux` raises `ValueError` for anything but the two laws. ^rate-law

**name**`: str = ""`
    Quoted in this module's `KeyError` messages. When empty, `TransportFlux` names itself from the integer ids (`transport_0_to_1`). ^name



## GrowthLaw Interface
Resource-coupled per-capita growth declared in string ids, authored by `suite.blocks.PopulationBlock` or the `!GrowthLaw` head. A frozen dataclass; `WorldImpl` turns it into a `PerCapitaGrowth`.

| GrowthLaw | |
| --- | --- |
| [[#^compartment\|compartment]] | Population whose multiplicity grows |
| [[#^resource-compartment\|resource_compartment]] | Compartment holding the resource |
| [[#^resource\|resource]] | Resource molecule name |
| [[#^stoich\|stoich]] | Resource amount drawn per new instance |
| [[#^growthlaw-rate-constant\|rate_constant]] | The per-capita rate `k` |
| [[#^growthlaw-name\|name]] | Label used in error messages |

**compartment**`: NodeId`
    Must name a compartment of the world. ^compartment

**resource_compartment**`: NodeId`
    Must name a compartment; may equal `compartment`. ^resource-compartment

**resource**`: str`
    Must be in the chemistry. ^resource

**stoich**`: float`
    No default. `0.0` is the deliberately leaky uncoupled form: growth with no draw. ^stoich

**rate_constant**`: float = 1.0`
    Copied unchecked. ^growthlaw-rate-constant

**name**`: str = ""`
    Quoted in error messages; empty lets the runtime law name itself. ^growthlaw-name



## DeathLaw Interface
Per-capita death declared in string ids, optionally releasing biomass to a pool — the reverse of `GrowthLaw`'s draw. A frozen dataclass; `WorldImpl` turns it into a `PerCapitaDeath`.

| DeathLaw | |
| --- | --- |
| [[#^deathlaw-compartment\|compartment]] | Population whose multiplicity shrinks |
| [[#^deathlaw-rate-constant\|rate_constant]] | The per-capita rate `k` |
| [[#^release-compartment\|release_compartment]] | Compartment receiving released biomass |
| [[#^release-resource\|release_resource]] | Molecule receiving released biomass |
| [[#^release-stoich\|release_stoich]] | Amount released per instance lost |
| [[#^deathlaw-name\|name]] | Label used in error messages |

**compartment**`: NodeId`
    Must name a compartment of the world. ^deathlaw-compartment

**rate_constant**`: float = 1.0`
    Copied unchecked. ^deathlaw-rate-constant

**release_compartment**`: Optional[NodeId] = None`
    Checked against the tree only when set. Setting it without `release_resource`, or the reverse, is accepted here; the runtime law releases only when all three release fields are supplied. ^release-compartment

**release_resource**`: Optional[str] = None`
    Checked against the chemistry only when set. ^release-resource

**release_stoich**`: float = 0.0`
    Copied unchecked. ^release-stoich

**name**`: str = ""`
    Quoted in error messages. ^deathlaw-name



## CountFlowSpec Interface
A size-class transition declared in string ids: multiplicity moving from one compartment to another, as a maturation edge — `Transport`'s shape on the multiplicity axis. A frozen dataclass; `WorldImpl` turns it into a `CountFlow`. The `!CountFlow` head builds it.

| CountFlowSpec | |
| --- | --- |
| [[#^countflowspec-origin\|origin]] | Compartment instances leave |
| [[#^countflowspec-dest\|dest]] | Compartment instances enter |
| [[#^countflowspec-rate-constant\|rate_constant]] | The per-capita rate `k` |
| [[#^countflowspec-name\|name]] | Label used in error messages |

**origin**`: NodeId`
    Must name a compartment of the world. ^countflowspec-origin

**dest**`: NodeId`
    Must name a compartment of the world. ^countflowspec-dest

**rate_constant**`: float = 1.0`
    Copied unchecked. ^countflowspec-rate-constant

**name**`: str = ""`
    Quoted in error messages. ^countflowspec-name



## world Interface
The module's free names besides the six classes. Nothing here is re-exported by `alienbio.bio`.

| world | |
| --- | --- |
| [[#^build-tree\|build_tree]] | Records → integer tree and id map |
| [[#^nodeid\|NodeId]] | Alias for a compartment's string id |
| [[#^populationlawspec\|PopulationLawSpec]] | Any of the three law records |
| [[#^rebuild-world\|rebuild_world]] | Swap chemistry or compartments, keep flows and laws |

**build_tree**`(compartments: tuple[Compartment, ...]) -> tuple[CompartmentTreeImpl, dict[NodeId, int]]`
    Build a `CompartmentTreeImpl` whose node names are the record ids, and return it with the `id → integer` map. The root gets 0; the rest follow in the order described in [[#The compartment tree]]. `ValueError` when there is not exactly one record with `parent=None`, or when some record cannot be reached from the root (a missing parent, a cycle, a self-parent). Reads only `id` and `parent`. Called by `WorldImpl.__init__` and nothing else in `src/` or `tests/`. ^build-tree

**NodeId**`= str`
    A compartment's readable id (`"cell"`, `"c0"`). ^nodeid

**PopulationLawSpec**`= Union[GrowthLaw, DeathLaw, CountFlowSpec]`
    The type of a `population_laws` entry. ^populationlawspec

**rebuild_world**`(world: WorldImpl, chemistry: Optional[ChemistryImpl] = None, compartments: Optional[tuple[Compartment, ...]] = None) -> WorldImpl`
    A new world with `chemistry` and/or `compartments` swapped in and `world`'s `flows` and `population_laws` carried, re-resolved by the constructor. The rebuild `perturbations`, `augment` and `arch_diagnose.perturb_reaction_rate` call (T088: they called `WorldImpl(chem, compartments)` and dropped both). ^rebuild-world




# WorldImpl Semantics

## The compartment tree
`build_tree` turns the flat records into integer ids in rounds. The root is added first, as 0. Each round then walks the remaining records in their given order and adds every one whose parent already has an id — including a parent added earlier in the same round — and a round that adds nothing raises `ValueError`. So a list that names every parent before its children gets ids in list order in a single round; any other order still succeeds, with ids following the rounds. The integers are the state's compartment rows and every resolved flow's and law's compartment ids.

Ids must be unique: `build_tree` raises `ValueError` naming a repeated id before building anything. Until 2026-10 a second record with an existing id overwrote the map entry and surfaced as `KeyError: 1` (two children both named `"c"`) or `KeyError: 0` (a child named like the root) in `__init__`. `kind` is never read; `volume` and the initial values are applied after the tree is built.



## The initial state's shape
The derived `WorldStateImpl` is a dense row-major store, `concentrations[row × num_molecules + column]`, labelled on both axes so `concentration(compartment_id, molecule_id)` works by name.

| Axis | Index | Order fixed by | Labels |
| --- | --- | --- | --- |
| Compartment (row) | 0 … n−1 | `build_tree`, root = 0 | `compartment_ids`, the record ids |
| Molecule (column) | 0 … m−1 | `chemistry.molecules` insertion order | `molecule_ids`, the dict keys |

The molecule order is the one `WorldSimulatorImpl.from_chemistry` takes, so the state and the simulator agree on columns without any reload, and a world rebuilt over a larger chemistry gives every new molecule a starting concentration of 0. Values: each record's `concentrations` are written to its row, everything else is 0.0; `multiplicity` and `volume` are written only when they differ from 1.0, the state's own default. Concentration is per volume per instance, so the amount the reaction and flow passes conserve is `multiplicity × volume × concentration` (`WorldStateImpl.amount`).



## Resolution: string ids to integers
After the state, `__init__` rewrites every flow and law record with the same two maps — compartment id → row from `build_tree`, molecule name → column from the chemistry — so a resolved object's references line up with the state however the tree was built. Order is kept: `flow_objs[i]` comes from `flows[i]`.

| Record | Becomes | Checked against the maps | Error |
| --- | --- | --- | --- |
| `Transport` | `TransportFlux` | `origin`, `dest`, `driver_molecule`, every `stoichiometry` key | `KeyError` |
| `GrowthLaw` | `PerCapitaGrowth` | `compartment`, `resource_compartment`, `resource` | `KeyError` |
| `DeathLaw` | `PerCapitaDeath` | `compartment`; each release field when set | `KeyError` |
| `CountFlowSpec` | `CountFlow` | `origin`, `dest` | `KeyError` |
| anything else | — | — | `TypeError` |

Each `KeyError` quotes the record's `name` (empty quotes when it has none) and the unknown id. Numbers are copied as given: no rate constant, stoichiometry, volume or multiplicity is range-checked on this path, and neither the population-law constructors nor `TransportFlux` check them either (`TransportFlux` checks only `rate_law`). Resolution happens once; the simulators take `flow_objs` and `population_law_objs` and never see a string id.



## Construction paths
Every path ends in this constructor; they differ in what they pass.

| Path | Where | Compartments | Flows and laws |
| --- | --- | --- | --- |
| `Skeleton.materialize` | `suite/skeleton.py` | the fragment's, or one `"cell"` root | carried from the `Fragment` |
| `!World` head | `suite/expr_heads.py` | given, or one `"cell"` root; checks concentration names first (`ExprError`) | given |
| `world` head | `suite/expr_heads.py` | `materialize`'s, with `initial:` overlaid on one record | carried |
| `_world_from_state` | `suite/runner.py` | each turn, the records refilled from the last end state | carried |
| the single-compartment drafters | `suite/arch_diagnose.py`, `arch_predict.py`, `arch_intervene.py`, `pipeline.py` | one record | none |
| `rebuild_world` | `suite/perturbations.py`, `augment.py`, `arch_diagnose.perturb_reaction_rate`, the discover drafter's `_world` | `world.compartments`, or the edited records (the catalyst added, on discover) | carried |

The per-turn rebuild gets the same integer ids every turn: it passes the records in the state's row order, which names every parent before its children, so `build_tree` assigns rows in one round in that order. The `mk` makers build the chemistry (`mk.C`), not the world.



## Immutability and rebuilds
A world is changed by building a new one. `__slots__` and getter-only properties stop reassignment, and the raw `flows` and `population_laws` are kept precisely so a rebuild can re-resolve them against its own tree. The immutability is shallow:

- **`initial_state`** — the stored `WorldStateImpl` is returned, not a copy. Writing to it changes the world's start for every later reader; `verify.simulate` copies before stepping, and the runner's lever and assay edits each work on a copy (`_state_with_concentration`, `_state_scaled`).
- **`chemistry`** — its dicts are plain and writable. A molecule added after construction is on the simulator's axis (`from_chemistry` reads the dict again) but not on the state's, whose `num_molecules` was fixed at construction.
- **The records** — frozen dataclasses, but `concentrations` and `stoichiometry` are mappings held by reference.




# BRIEF
- 2026-10-18 — written as an ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD 84f8190; every member and claim traced to `bio/world.py`, `compartment_tree.py`, `world_state.py`, `flow.py`, `population.py`, `suite/skeleton.py`, `expr_heads.py`, `runner.py`, `verify.py` and the rebuilders. Left out: `__repr__`, and the dataclasses' generated constructors, which are their field lists. Constructor block id is `^init`. `CompartmentImpl` (`bio/compartment.py`), named in the module docstring as a precedent, is the M1 entity and is not on this path, so it is not drawn. The duplicate-id `KeyError` was reproduced against HEAD; the rebuilders dropping flows and laws, and `alienbio.bio` not exporting `WorldImpl` while its docstring lists it, were read from the source; none fixed.
- 2026-10-28 — refreshed against 0eb23e5: the constructor block no longer says a duplicate compartment id surfaces as a bare `KeyError` (`build_tree` names it since `235377b`, as § The compartment tree already said). Figure still true.
- 2026-10-28 — refreshed against `b32d46b`: new module function `rebuild_world` (carries flows and population laws) given a block and index row; the rebuilders row now carries them (the discover drafter's `_world` too, at the round's last commit). Figure still true.
