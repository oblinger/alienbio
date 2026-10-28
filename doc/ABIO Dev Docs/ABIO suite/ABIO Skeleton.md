---
description: "`skeleton`: the recursive `SkeletonBlock` tree every generated world is built from — ports and pool bindings, the `Fragment` each block emits, `Skeleton.materialize` into a `WorldImpl`, the `validate` canaries, the `oracle` read off the crux, `indirection_depth`. Source: `src/alienbio/suite/skeleton.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Skeleton](ha://p/ABIO%20Skeleton) 
# ABIO Skeleton
The composition core of the world generators: a tree of blocks wired by shared pools, which `materialize` turns into one `WorldImpl` under a seed and `oracle` simulates to read the generator-held truth off one named block.

![ABIO Skeleton](ABIO%20Skeleton.svg) 
*Pool ids and binding* is the topic that governs the dotted `bound` arrow (each child's ports are resolved by its parent before it realizes); *Validate* governs the two canaries, one of which is vacuous today (‡).

`suite/skeleton.py` holds the machinery only: `Port` and `PoolBinding`, the `SkeletonBlock` base, the `Fragment` accumulator, `Provenance`, the two enums, `SkeletonError`, the `Skeleton` wrapper and three timeline readers. It carries no concrete block; the catalog is `suite/blocks.py` (§ [The block library](#the-block-library)). Nothing here is re-exported from `alienbio.suite`; every generator, `blocks.py`, `boundedness.py` and `expr_heads.py` import it directly. What `materialize` hands to is [ABIO WorldImpl](../ABIO%20bio/ABIO%20WorldImpl.md); the chemistry it builds is [ABIO ChemistryImpl](../ABIO%20bio/ABIO%20ChemistryImpl.md); the W1 skeleton and its gates are [ABIO PressureGen](ABIO%20PressureGen.md). The architect's view, with the design decisions this module ratifies (Q1–Q4), is [ABIO Skeleton Arch](../../ABIO%20Design/ABIO%20Skeleton%20Arch/ABIO%20Skeleton%20Arch.md); the subsystem view and its seams is [ABIO-Generators](../../ABIO%20Architecture/ABIO-Generators.md).



## Skeleton Interface
A frozen dataclass and a thin wrapper, not a block subclass: the root of a block tree, the chemistry it builds once materialized, the levers and the crux by path. Authoring is functional (`dataclasses.replace`); `materialize` is the one impure member, caching the realized tree and the chemistry onto the frozen instance with `object.__setattr__`. Every `build_*_skeleton` in the generators returns one unmaterialized.

| Skeleton | |
| --- | --- |
| [root](#^root) | The root block of the tree |
| [chemistry](#^chemistry) | The built chemistry, `None` until materialized |
| [control_surface](#^control-surface) | Lever port paths, read only by `indirection_depth` |
| [crux](#^crux) | Path of the block whose `ground_truth` is the answer |
| [conservation](#^conservation) | The conservation verdict `validate` recorded |
| [materialize](#^materialize) | Realize the tree into a `WorldImpl` under a seed |
| [validate](#^validate) | Pool-direction and conservation canaries |
| [oracle](#^oracle) | Materialize, simulate, read the crux |
| [indirection_depth](#^indirection-depth) | Fewest block hops from a lever to the crux |

**root**`: SkeletonBlock`
    The authored tree until `materialize` runs, then its realized copy: every block's `provenance` and `resolved_ports` filled, children replaced by their realized copies. A drafter reads pool ids off this tree after materializing (`skeleton.root.walk()`, `skeleton.root.children[1]`). ^root

**chemistry**`: Optional[ChemistryImpl] = None`
    `None` on an authored skeleton; set by `materialize` to the `ChemistryImpl` named `f"{root.name}_chem"`. `validate` refuses to run while it is `None`. ^chemistry

**control_surface**`: tuple[PortRef, ...] = ()`
    The lever ports as global paths (`"root/source.out"`). Only `indirection_depth` reads it; no drafter, brief or runner does. The levers an agent is actually given come from each generator's own reader (§ [Control surface and indirection depth](#control-surface-and-indirection-depth)). ^control-surface

**crux**`: BlockRef = ""`
    The `/`-separated path from the root to the block `oracle` reads (`"root/crux"`, or `"root"` when the root block carries `ground_truth`). The empty default makes `oracle` raise `SkeletonError` (the path does not start at the root). ^crux

**conservation**`: Optional[str] = None`
    Set by `validate`: `bio.conservation.conservation_outcome`'s verdict on the chemistry (`balanced`, `vacuous: no atoms`, `partial: …`, `violated: …`). Every skeleton-minted world reads `vacuous: no atoms` today. `None` before `validate` runs; `compare=False`, and not persisted with the world. ^conservation

**materialize**`(seed: Seed) -> WorldImpl`
    Realizes the tree under `seed.child(root.name)`, builds one `ChemistryImpl` from the merged fragment's molecules and reactions, places the fragment's compartments (one default `cell` of volume 1 when no block declared any), folds `initial` concentrations onto them, and returns `WorldImpl(chem, compartments, flows=…, population_laws=…)`. Caches the realized root and the chemistry onto `self`. Raises `SkeletonError` from `Fragment.merge` on a namespace collision and from binding resolution on an unknown port or child. Calling it again re-realizes the already-realized tree, overwriting both caches. § [Materialize](#materialize). ^materialize

**validate**`() -> Optional[SkeletonError]`
    Returns `None` when clean, else one `SkeletonError` joining every violation; it never raises for a content violation. Raises `SkeletonError` when called before `materialize`. Checks that every pool has an `OUT` and an `IN` port, then runs `validate_conservation` on the chemistry and records `conservation_outcome`'s verdict on [conservation](#^conservation). § [Validate](#validate). ^validate

**oracle**`(seed: Seed, sim_cfg: SimConfig = SimConfig()) -> Any`
    `materialize(seed)`, `verify.simulate(world, sim_cfg, seed.child("oracle-sim"))`, find the `crux` block in the realized tree, return its `ground_truth(timeline)`. Deterministic in `seed`. The return shape is the crux block's: a tuple on every generator crux, a multiplicity on `PopulationBlock`. Because it materializes, it replaces the cached root and chemistry of a skeleton already materialized under another seed. ^oracle

**indirection_depth**`() -> int`
    The fewest block-to-block hops, over "these two blocks share a pool" adjacency built from the authored `pool_bindings`, from any `control_surface` lever's block to the `crux` block. Works before `materialize`. Raises `SkeletonError` on an empty `control_surface` or when no lever reaches the crux. Called only by `tests/suite/test_skeleton.py`. ^indirection-depth



## SkeletonBlock Interface
The abstract base of every block: a frozen dataclass that is both a tree node and a template. A block declares its ports and children and, as the parent, the bindings between them; it implements `realize` to emit its own content over already-resolved ports, and `ground_truth` when it can serve as a crux. The base `realize` returns an empty `Fragment`, so a plain `SkeletonBlock` is a pure composition node; recursion into children and binding resolution are done once, generically, by the private `_realize_tree`. There is no `make` on the base; every library block adds a `make` classmethod that builds its fixed ports and children, by convention only.

| SkeletonBlock | |
| --- | --- |
| [name](#^name) | The block's name, its path segment and seed label |
| [role](#^role) | Its `Role`, for introspection only |
| [ports](#^ports) | The pools it binds to |
| [params](#^params) | Free authoring tags |
| [children](#^children) | Its child blocks |
| [provenance](#^provenance) | What it produced, set by materialize |
| [pool_bindings](#^pool-bindings) | Which of its own and its children's ports are one pool |
| [resolved_ports](#^resolved-ports) | Own port name to molecule id, set by materialize |
| [realize](#^realize) | Emit this block's own fragment |
| [walk](#^walk) | Pre-order walk of the subtree |
| [ground_truth](#^ground-truth) | Read the answer off a timeline |

**name**`: str`
    One segment of every path that names this block (`"root/crux/route_fast2"`), the namespace of every id it mints, and the label of its seed (`seed.child(name)`). Siblings must differ: `_block_by_path` takes the first match and binding resolution keys children by name. ^name

**role**`: Role`
    The block's declared purpose. Nothing in `skeleton.py` branches on it. ^role

**ports**`: tuple[Port, ...] = ()`
    The pools this block consumes (`IN`) or produces (`OUT`). Each is either bound by the parent or, unbound, minted fresh as `f"{ns}/{port.name}"`. ^ports

**params**`: Tags = field(default_factory=dict)`
    Free tags carried for authors and generators; the core never reads them. ^params

**children**`: tuple["SkeletonBlock", ...] = ()`
    Child blocks, realized in order after this block's own fragment. Each gets the namespace `f"{ns}/{child.name}"` and the seed `seed.child(child.name)`. ^children

**provenance**`: tuple[Provenance, ...] = ()`
    Empty on an authored block; on the realized copy, the provenance of this block's own fragment only (not its children's). A crux's `ground_truth` reads containers off it (`PopulationBlock`). ^provenance

**pool_bindings**`: tuple[PoolBinding, ...] = ()`
    The parent's statement of which ports are one pool, in local refs (`"self.out"`, `"route_a.in"`). Resolved one level at a time; a pool spanning several levels threads through because each level hands its resolved molecule down as the child's `bound`. § [Pool ids and binding](#pool-ids-and-binding). ^pool-bindings

**resolved_ports**`: Mapping[str, str] = field(default_factory=dict)`
    Empty on an authored block; on the realized copy, each own port name mapped to the molecule id it resolved to. This is how every generator reads its pool ids ("ground truth, never guessed from id strings"). ^resolved-ports

**realize**`(seed: Seed, ns: str, bound: Mapping[str, MoleculeImpl]) -> Fragment`
    Emits this block's own molecules, reactions, compartments, flows, population laws and initial values. `bound` maps every own port name to its resolved `MoleculeImpl`, already unified with whatever the port is bound to; `ns` is the block's full path. A primitive overrides it and samples its `Dist` holes from children of `seed`; it must not recurse into children. The base returns `Fragment()`. ^realize

**walk**`()`
    A generator over the subtree, pre-order: this block, then each child's walk. Drafters use it on the realized root to find blocks by name. ^walk

**ground_truth**`(timeline: Timeline) -> Any`
    Overridden by a crux-bearing block to read its answer off a simulated timeline, usually through `final_amount` on its own `resolved_ports`; implementations raise `SkeletonError` when those are empty, that is, on an unrealized block. The base raises `NotImplementedError`. ^ground-truth



## Fragment Interface
A frozen dataclass: what one block's `realize` emits and what `_realize_tree` merges up the tree. Blocks name containers and molecules by string, because the integer-indexed world does not exist yet; `WorldImpl` resolves them.

| Fragment | |
| --- | --- |
| [molecules](#^molecules) | Molecules by id |
| [reactions](#^reactions) | Reactions by id |
| [compartments](#^compartments) | Compartment records |
| [initial](#^initial) | Starting values by container and molecule |
| [provenance](#^fragment-provenance) | What produced each reaction, flow or law |
| [flows](#^flows) | Cross-compartment transport specs |
| [population_laws](#^population-laws) | Count-based rate-law specs |
| [merge](#^merge) | Collision-checked union |

**molecules**`: Mapping[str, MoleculeImpl] = field(default_factory=dict)`
    Every molecule the block's reactions, modifiers or compartments touch, keyed by id. ^molecules

**reactions**`: Mapping[str, ReactionImpl] = field(default_factory=dict)`
    The block's reactions, keyed by id (`f"{ns}/rxn"` in the library). ^reactions

**compartments**`: tuple[Compartment, ...] = ()`
    Compartment records the block declares. Only transport, lattice and population blocks declare any; when the whole tree declares none, `materialize` supplies one `cell`. ^compartments

**initial**`: Mapping[tuple[NodeId, str], float] = field(default_factory=dict)`
    `(container_id, molecule_id) -> concentration`, folded onto the compartments by `materialize`. Only `SpatialLatticeBlock` sets it in the library. ^initial

**provenance**`: tuple[Provenance, ...] = ()`
    One `Provenance` per reaction, flow or population law produced. ^fragment-provenance

**flows**`: tuple[Transport, ...] = ()`
    `Transport` specs (string ids), passed straight to `WorldImpl`. ^flows

**population_laws**`: tuple[PopulationLawSpec, ...] = ()`
    `GrowthLaw`, `DeathLaw` and `CountFlowSpec` records, passed straight to `WorldImpl`. ^population-laws

**merge**`(other: "Fragment") -> "Fragment"`
    The union of two fragments. A molecule id on both sides is accepted only when it is the same object (a bound pool), a reaction id on both sides always raises `SkeletonError`, and a compartment id on both sides is accepted when the two records are equal (neighbouring transport blocks declaring one shared container) or differ only in that one leaves `parent` unset, the placed one winning — so a `TransportBlock` chain `A → B → C` nests B under A and C under B; any other difference raises. `initial` is a plain dict union, the right side winning on a shared key; `provenance`, `flows` and `population_laws` concatenate unchecked. ^merge



## Port Interface
A frozen dataclass: one pool a block binds to. There is one port kind; a modifier species is an `IN` port like a consumed one.

| Port | |
| --- | --- |
| [name](#^port-name) | Local port name |
| [container](#^container) | Container id, or `None` for the default |
| [direction](#^direction) | `IN` or `OUT` |

**name**`: str`
    The name local refs and `bound` use (`"out"`, `"precursor"`), and the last segment of a minted pool id. ^port-name

**container**`: Optional[NodeId]`
    The container the block's reactions or flows are attributed to; `None` means `cell` in the library. `materialize` places no compartment for it: a reaction block's container reaches only its `Provenance`, and the reaction runs in whatever compartments exist. ^container

**direction**`: PortDir`
    Whether the block consumes or produces the pool; `validate`'s producer and fate checks read nothing else. ^direction



## PoolBinding Interface
A frozen dataclass owned by the parent block: two local refs named as one pool. A ref is `"self.<port>"` for the parent's own port or `"<child>.<port>"` for a direct child's.

| PoolBinding | |
| --- | --- |
| [a](#^a) | One side |
| [b](#^b) | The other side |

**a**`: str`
    A local ref; malformed (no `.`) raises `SkeletonError` at materialize. ^a

**b**`: str`
    A local ref. Binding is symmetric in meaning but not in naming: for a pool the parent does not own, the union-find root names the minted molecule, and a single binding's root is `b` (§ [Pool ids and binding](#pool-ids-and-binding)). ^b



## Provenance Interface
A frozen dataclass: one link from a block to something it produced.

| Provenance | |
| --- | --- |
| [reaction_id](#^reaction-id) | The reaction produced, or `""` |
| [container_id](#^container-id) | The container it is attributed to |
| [flow_id](#^flow-id) | The transport flux produced, or `""` |
| [population_law_id](#^population-law-id) | The population law produced, or `""` |

**reaction_id**`: str`
    Set by every reaction-emitting block; `""` on a flow or law entry. ^reaction-id

**container_id**`: NodeId`
    The port's container, `cell` by default; for `PopulationBlock`, the population compartment, which its `ground_truth` reads. ^container-id

**flow_id**`: str = ""`
    Set by `TransportBlock` and `SpatialLatticeBlock`. ^flow-id

**population_law_id**`: str = ""`
    Set by `PopulationBlock`. ^population-law-id



## PortDir Interface
An `Enum`: the direction of a port.

| PortDir | |
| --- | --- |
| [IN](#^in) | The block consumes or reads the pool |
| [OUT](#^out) | The block produces the pool |

**IN**` = "in"`
    A reactant, a drained pool, a transported pool, or a non-consumed modifier. ^in

**OUT**` = "out"`
    A product or a source's output. ^out



## Role Interface
An `Enum`: a block's declared purpose. Introspection only; nothing in this module branches on it.

| Role | |
| --- | --- |
| [SUPPLY](#^supply) | Sources and plain composites |
| [SINK](#^sink) | Drains |
| [CRUX](#^role-crux) | Crux blocks and their routes |
| [SIGNALING](#^signaling) | The modifier blocks |
| [TRANSPORT](#^transport) | Transport and lattice |
| [PRESSURE](#^pressure) | `PressureBlock` |
| [POPULATION](#^population) | `PopulationBlock` |

**SUPPLY**` = "supply"`
    Also the role every generator's root composite takes. ^supply

**SINK**` = "sink"`
    `SinkBlock`. ^sink

**CRUX**` = "crux"`
    `ConflictCruxBlock`, its two routes, and the generators' private cruxes. ^role-crux

**SIGNALING**` = "signaling"`
    Signaling, inhibition, enzyme and cooperative-binding blocks. ^signaling

**TRANSPORT**` = "transport"`
    `TransportBlock`, `SpatialLatticeBlock`. ^transport

**PRESSURE**` = "pressure"`
    `PressureBlock`. ^pressure

**POPULATION**` = "population"`
    `PopulationBlock`. ^population



## SkeletonError Interface
A `ValueError` subclass for a well-formedness violation. It is raised by binding resolution (a malformed ref, an unknown own port or child), by `Fragment.merge` on a collision, by path resolution, by `indirection_depth`, by `validate` called before `materialize`, and by every block's `ground_truth` on an unrealized block; `validate` returns one instead of raising for a content violation. The generators raise it for their own gates too (`pressure_gen`'s pressure and passive gates, `phase1_gen`'s passive gate).



## skeleton Interface
The module-level exports: the two path aliases and three readers of a simulated state, which every crux's `ground_truth` and several scorers use. `drafters.py` imports `final_amount`; `pressure_gen.py` imports `state_amount` for its windowed score reads.

| skeleton | |
| --- | --- |
| [BlockRef](#^blockref) | A block path from the root |
| [PortRef](#^portref) | A block path plus `.port` |
| [final_amount](#^final-amount) | A molecule's total in the last state |
| [state_amount](#^state-amount) | A molecule's total in one state |
| [final_multiplicity](#^final-multiplicity) | A compartment's multiplicity in the last state |

**BlockRef**` = str`
    `"root/sink"`: block names from the root, `/`-separated, the first segment the root's own name. ^blockref

**PortRef**` = str`
    `"root/source.out"`: a `BlockRef` plus `.` and a port name; the port is split off at the last `.`. ^portref

**final_amount**`(timeline: Timeline, molecule_id: str) -> float`
    `state_amount(timeline.states[-1], molecule_id)`. Raises `ValueError` on a timeline with no states. ^final-amount

**state_amount**`(state: Any, molecule_id: str) -> float`
    The molecule's column of the state's `as_array()`, summed over every compartment. Raises `ValueError` when the state carries no `molecule_ids` axis, `KeyError` when the molecule is not on it. ^state-amount

**final_multiplicity**`(timeline: Timeline, compartment_id: str) -> float`
    The last state's `get_multiplicity` for the compartment. Raises `ValueError` on no states or no `compartment_ids` axis, `KeyError` on an unknown compartment. ^final-multiplicity




# Skeleton Semantics

## The tree and its fragments
A skeleton is woven two ways. Vertically, a block's children are its content: a pattern block (`ConflictCruxBlock`, every generator crux, every root) has no `realize` of its own and is nothing but children and bindings. Horizontally, siblings share pools through their parent's `pool_bindings`. `_realize_tree` walks the tree once, pre-order: resolve the block's own ports, resolve its bindings into each child's `bound`, call its `realize`, then recurse into each child in order and merge each child's fragment into the running one. The realized copy of each block records its own `provenance` and `resolved_ports`.

Seeds follow tree position, not iteration order: the root realizes under `seed.child(root.name)`, each child under `seed.child(child.name)` of its parent's seed, and a library block samples its rate from `seed.child("rate")`. Two blocks at the same path in two skeletons draw the same numbers; renaming a block re-draws everything under it.

Every id is a path: a reaction is `f"{ns}/rxn"`, a flow `f"{ns}/transport"`, a law `f"{ns}/growth"`, where `ns` is the block's path from the root. Ids are therefore collision-free by construction as long as siblings have distinct names; `Fragment.merge` is the check that they were.



## Pool ids and binding
Within one block, `_realize_tree` unions every binding's two sides, then gives each connected group one `MoleculeImpl` object:

| The group contains | Its molecule |
| --- | --- |
| A `self.<port>` ref | The parent's own resolved port (bound from above, or minted) |
| Only child refs | Minted as `f"{ns}/{root}"` with `.` replaced by `_` |
| Nothing (an unbound port) | Minted by the child itself as `f"{ns}/{port}"` |

`root` is the union-find representative, and `union(a, b)` makes `b`'s root the representative, so the name of a composed pool depends on the order and the sides of the bindings: W1's `PoolBinding("source.out", "crux.precursor")` mints `root/crux_precursor`, and its clean feed pool comes out as `root/crux/uptake_waste_in`. The ids are deterministic, which is all the goldens need, but reordering or flipping a binding renames a pool and moves every recorded id. Generators never spell these ids; they read them off `resolved_ports` after materializing.

The shared object is the invariant: two blocks that see one pool hold the same `MoleculeImpl`, and `Fragment.merge` refuses two different objects under one id. That is the aliasing bug this module exists to rule out.



## Materialize
In order: realize the tree into one fragment; build the chemistry with `mk.C(f"{root.name}_chem", molecules, reactions)`; take the fragment's compartments, or `Compartment("cell", None, "cell", 1.0)` when there are none; fold `initial` onto them; build `WorldImpl(chem, compartments, flows=fragment.flows, population_laws=fragment.population_laws)`; cache the realized root and the chemistry onto the skeleton. `WorldImpl`'s constructor then builds the integer tree, the initial state and the simulator-ready flows and laws ([ABIO WorldImpl](../ABIO%20bio/ABIO%20WorldImpl.md) § Resolution: string ids to integers).

Nothing is hidden here. `Fragment` has no hidden-id field and `materialize` projects nothing out; the structurally hidden pools of W2 and phase 1 are a generator's statement, written to `task.setup["hidden_ids"]` by `w2_gen` and `phase1_gen` and enforced by the runner and the brief.

A port's `container` does not create a compartment. Only blocks that put `Compartment` records in their fragment (transport, lattice, population) shape the world's tree; a reaction block on `container="vac"` in a tree with no declared compartments materializes into the default `cell` with a `Provenance` that says `vac`.



## Validate
Two checks, each appending to one error list:

| Check | Refuses | What it cannot see |
| --- | --- | --- |
| Pool direction | A pool (binding group or lone port, tree-wide, from the authored bindings) with no `OUT` port, or no `IN` port | Modifier ports are `IN`, so a pool read only as a modifier passes as having a fate while nothing drains it |
| Conservation | Any non-boundary reaction whose atoms do not balance (`bio.conservation.validate_conservation`) | Every skeleton-minted pool is `mk.M(id)` with no atoms, so every reaction balances trivially (‡) |

The conservation canary is vacuous on every assembled world today: no library block assigns atoms, so `molecule_quantity` returns `{}` for every molecule and nothing can fail. `validate` no longer lets that read as a pass: it records `conservation_outcome`'s verdict on `Skeleton.conservation`, `vacuous: no atoms` on every skeleton-minted world (`40c5c09`). Making the canary real is the follow-up filed at F013: assign per-tag atoms, as F018 did. Namespace collisions are not re-checked; `materialize` already raised on them.

`validate` does not run the boundedness gate. `suite/boundedness.py`'s `check_boundedness(world_or_skeleton, seed)` accepts a `Skeleton` (materializing it) and runs the static bounded-fate walk and the simulate-and-check classification, but it is opt-in and no production code calls it; only its tests do.

Of the generators, only `phase1_gen.draft_phase1_world` calls `validate`, raising what it returns. The W1, W2, conflict and delta drafts never call it.



## The oracle
Ground truth by construction and by simulation: `oracle` materializes under the seed, simulates under `seed.child("oracle-sim")`, resolves `crux` from the root and calls that block's `ground_truth`. The answer is whatever that block reads off the final state, through `final_amount` on its realized ports:

| Crux block | Module | Returns |
| --- | --- | --- |
| `ConflictCruxBlock` | `blocks.py` | `(prodA, prodB)` |
| `_SingleRouteCrux` | `conflict_gen.py` | `(out,)` |
| `_PressureCruxBlock` | `pressure_gen.py` | `(T, byproduct)` |
| `_CleanOnlyRoot` | `pressure_gen.py` | `(T,)` |
| `_W2CruxBlock` | `w2_gen.py` | `(T, tracked)` |
| `_Phase1Root` | `phase1_gen.py` | `(T, byproduct)` |
| `_DeltaCruxBlock` | `delta_gen.py` | `(T, driver, decoy)` |
| `PopulationBlock` | `blocks.py` | final multiplicity |

The generators use `oracle` for their passive baselines and gates (`passive_reach`, the `pi = 1` clean-only gate, the delta cut tests), each on a freshly built skeleton. The truth the drafter heads write to `task.setup["oracle"]` is assembled by the heads from those numbers and from `resolved_ports`; this module writes nothing to `setup`.



## The block library
`suite/blocks.py` is the catalog; a few blocks live with the one generator or head that needs them. Every primitive emits one reaction, flux or law set per realize.

| Block | Adds | Used by |
| --- | --- | --- |
| `ReactionBlock` | One mass-action reaction: `IN` ports reactants, `OUT` products, a `Dist` rate, optional `stoich` | Every generator (routes, hops) |
| `SourceBlock` | `∅ -> pool` | Every generator |
| `SinkBlock` | `pool -> ∅` | Every generator |
| `ConflictCruxBlock` | Pattern: a shared precursor into two routes and two sinks | `conflict_gen` |
| `PressureBlock` | A sink drain plus an optional Poisson insult schedule (metadata) | Expr `insult` |
| `SignalingBlock` | One `in -> out` reaction with a linear activator or inhibitor modifier | `phase1_gen` (down variants' `scrub`), Expr `signal` |
| `InhibitionBlock` | A linear inhibitor modifier | Expr `inhibit` |
| `EnzymeBlock` | A Michaelis catalyst modifier | Expr `enzyme` |
| `CooperativeBindingBlock` | A Hill modifier | Expr `cooperative` |
| `TransportBlock` | One `Transport` flux and both its compartments | Expr `transport` |
| `SpatialLatticeBlock` | A chain of `k` compartments, neighbour fluxes, `initial` by cell | Expr `lattice` |
| `PopulationBlock` | Population and pool compartments, a growth law, an optional death law | Expr `population` |
| `ModulatedSourceBlock` | `∅ -> out` with an activator modifier (`w2_gen.py`) | `w2_gen` distractor chains |
| `RateLawBlock` | A reaction carrying a compiled rate law (`expr_heads.py`) | Expr `reaction` |

The generators compose them as follows. `pressure_gen.build_pressure_skeleton`: a source bound to `_PressureCruxBlock` (two routes, the side-product leg, the feed uptakes and inlets, the hop chains). `w2_gen.build_w2_skeleton`: W1's crux at `complexity = 0` with the harm chain, `ModulatedSourceBlock` distractor chains and the custodial reserve spliced in. `phase1_gen.build_phase1_skeleton`: a flat `_Phase1Root` task chain with a tracked pool, two inlet levers and, for the down variants, a `SignalingBlock` scrub. `conflict_gen.build_conflict_skeleton`: a source into `ConflictCruxBlock` (and a single-route rung). `delta_gen.build_delta_skeleton`: `_DeltaCruxBlock`, two signal sources, one of which drives `T`.



## Control surface and indirection depth
`Skeleton.control_surface` and the levers an agent is given are two different things that share a name. The agent's levers come from each generator's reader of the realized tree: `pressure_gen.control_surface(skeleton)` returns `{"feed_clean": …, "feed_fast": …}` off the uptake blocks' `in` ports, and `phase1_gen.phase1_surface` reads `feed_route` and `feed_neutral` the same way. The field is consulted only by `indirection_depth`, and only its test calls that.

The field disagrees with the drafter on W1: `build_pressure_skeleton` sets `control_surface=("root/source.out",)` (`pressure_gen.py:611`), the background source, while the declared levers are the two feed pools; W2 copies it (`w2_gen.py:346`). `indirection_depth()` on W1 returns 1 (source and crux share the precursor), a depth for a lever the agent does not hold. Phase 1 names one of its two levers (`phase1_gen.py:247`).

`indirection_depth` counts block hops, not reaction steps: blocks are adjacent when any binding group contains a port of each, so a composite is adjacent to each child it binds through `self`, and a chain of ten reactions inside one pattern block is one hop away. A crux that owns no port in any binding never enters the graph: the clean-only ablation (`crux="root"`, `pressure_gen.py:661`) and phase 1 (`crux="root"`) both raise "no control-surface lever reaches the crux".



## Expr heads and template namespacing
`suite/expr_heads.py` registers each library block as an Expr head (`source`, `sink`, `reaction`, `crux`, `signal`, `inhibit`, `enzyme`, `cooperative`, `insult`, `transport`, `lattice`, `population`), plus `block`, `skeleton` and `world`. The `block` head binds pools by name rather than by explicit binding: for every child port it adds a parent port of the same name (`OUT` if any child produces it) and a `PoolBinding("self.<port>", "<child>.<port>")`, so in Expr a pool is just a name. `world` materializes under the node's seed and applies an `initial` map by pool name, rebuilding the `WorldImpl`.

Pool names inside a template instance are namespaced by `Env.pool` (`expr/env.py`): a name becomes `f"{instance}.{name}"` unless it arrived as an argument, in which case it keeps the caller's spelling; that is how a parent wires a template's pools. This happens before any block exists; `skeleton.py` sees only the resulting port names.

Depth is capped on the Expr side only: every template level counts toward `limits.depth` (default 100, `expr/env.py:52`, checked in `expr/interp.py`). `_realize_tree` recurses in Python with no cap of its own, so a skeleton built directly in Python is bounded by the interpreter's recursion limit.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD `09c4c05`; pool ids, the vacuous conservation result, the modifier-only pass, the container drop and the `indirection_depth` values were read from local materializations of W1, the clean-only ablation, phase 1 and two toy trees, no spend. The block library is one table, not a member block per block: each block's own signature is in `blocks.py`, and the generators' blocks are on their own pages. Left out: the design decisions' history (on [ABIO Skeleton Arch](../../ABIO%20Design/ABIO%20Skeleton%20Arch/ABIO%20Skeleton%20Arch.md)), the private helpers (`_realize_tree`, `_UnionFind`, `_block_by_path`, `_global_ports`, `_collect_global_edges`, `_bfs_distance`, `_seed_initial`), described in prose only, and the boundedness module's own interface.
- 2026-10-28 — refreshed against 0eb23e5: `Skeleton.conservation` added (`40c5c09`); `Fragment.merge` accepts a parentless compartment declaration beside a placed one (`6631831`).
