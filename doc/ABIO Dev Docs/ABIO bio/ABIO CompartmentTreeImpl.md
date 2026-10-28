---
description: "`compartment_tree`: `CompartmentTreeImpl`, the int-indexed parent/child topology of a world's compartments — building it (`add_root`, `add_child`), reading it (`parent`, `children`, `ancestors`, `descendants`, `depth`), its dict form, and what in the engine actually reads it. Source: `src/alienbio/bio/compartment_tree.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO bio](ABIO%20bio.md) → [ABIO CompartmentTreeImpl](ha://p/ABIO%20CompartmentTreeImpl) 
# ABIO CompartmentTreeImpl
The page for the compartment topology every world state and simulator carries: how a tree is grown one integer id at a time, what each reader returns, its dict and text forms, and how little of it the physics consults.

![ABIO CompartmentTreeImpl](ABIO%20CompartmentTreeImpl.svg) 
*Topology is not physics* is the topic behind the dotted edges into the simulators: they read `num_compartments` and nothing else, so a compartment's parent never changes what a step does.

`compartment_tree.py` is one class and the alias `CompartmentId = int`. The one production builder is `world.build_tree`, which turns a `WorldImpl`'s flat compartment list into a tree after checking for one root, unique ids and no cycles ([ABIO WorldImpl](ABIO%20WorldImpl.md)); the tree then rides on the [ABIO WorldStateImpl](ABIO%20WorldStateImpl.md) (which sizes its arrays from it) and on both simulators ([ABIO WorldSimulatorImpl](ABIO%20WorldSimulatorImpl.md), [ABIO JaxWorldSimulator](ABIO%20JaxWorldSimulator.md)). It conforms to `protocols.bio.CompartmentTree` (`num_compartments`, `parent`, `children`, `root`, `is_root`). The published class page is [ABIO CompartmentTree](../../ABIO%20Ref/ABIO%20Classes/ABIO%20CompartmentTree.md); the subsystem view is [ABIO-Bio-Engine](../../ABIO%20Architecture/ABIO-Bio-Engine.md).



## CompartmentTreeImpl Interface
A slotted class holding a parent list, a children dict, a name list and the root id. Ids are dense integers in creation order: the root is 0 when it is added first, each child the next free index. Nothing is ever removed.

| CompartmentTreeImpl | |
| --- | --- |
| [CompartmentTreeImpl](#^compartmenttreeimpl) | An empty tree |
| [add_root](#^add-root) | Add the one root |
| [add_child](#^add-child) | Add a child under a parent |
| [num_compartments](#^num-compartments) | How many ids exist |
| [root](#^root) | The root id |
| [is_root](#^is-root) | True for a parentless id |
| [parent](#^parent) | A compartment's parent |
| [children](#^children) | A compartment's children |
| [name](#^name) | A compartment's name |
| [ancestors](#^ancestors) | Self up to the root |
| [descendants](#^descendants) | Everything below |
| [depth](#^depth) | Distance from the root |
| [to_dict](#^to-dict) | Parents and names as lists |
| [from_dict](#^from-dict) | Rebuild from that dict |
| [__str__](#^str) | An indented text tree |

**CompartmentTreeImpl**`()`
    An empty tree: no compartments, no root. `root()` raises until `add_root` runs. ^compartmenttreeimpl

**add_root**`(name: str = "root") -> CompartmentId`
    Appends a parentless compartment and records it as the root; raises `ValueError("Root already exists")` on a second call. Returns its id, which is 0 on a fresh tree. ^add-root

**add_child**`(parent: CompartmentId, name: str = "") -> CompartmentId`
    Appends a compartment under `parent` and returns its id; an empty `name` becomes `compartment_<id>`. Raises `ValueError("Parent … does not exist")` when `parent` is not an existing id — negative, past the end, a bool or a non-int — before the tree is touched (§ [Construction is checked first](#construction-is-checked-first)). ^add-child

**num_compartments**`: int`
    The number of ids, root included. The one member the simulators and the state read. ^num-compartments

**root**`() -> CompartmentId`
    The root id; `ValueError("Tree has no root")` on an empty tree. ^root

**is_root**`(compartment) -> bool`
    True when the compartment has no parent. ^is-root

**parent**`(child) -> Optional[CompartmentId]`
    The parent id, `None` for the root. An out-of-range id raises `IndexError`; a negative one indexes from the end. ^parent

**children**`(parent) -> List[CompartmentId]`
    The children in creation order, `[]` for an unknown id. Returns a copy: appending to it changes nothing. ^children

**name**`(compartment) -> str`
    The name given at creation. `build_tree` passes each `Compartment.id`, so in a world the name is the spec's compartment id. ^name

**ancestors**`(compartment) -> List[CompartmentId]`
    The compartment, its parent, and so on up to the root, inclusive. No path builds a cyclic parent list: `add_child` cannot, and `from_dict` refuses one. ^ancestors

**descendants**`(compartment) -> List[CompartmentId]`
    Every compartment below, not including itself, in depth-first stack order (last child first). ^descendants

**depth**`(compartment) -> int`
    Edges to the root; 0 for the root. ^depth

**to_dict**`() -> Dict`
    `{"parents": [...], "names": [...]}`, both copies. ^to-dict

**from_dict**`(data: Dict) -> CompartmentTreeImpl` (classmethod)
    Rebuilds the children lists and the root from `parents` and `names`, copying both lists. Raises `ValueError` on lists of different lengths, a non-empty list with zero or several roots, a parent that is out of range, not an int or the compartment itself, and a parent cycle. An empty dict gives an empty tree. No caller in `src/`. ^from-dict

**__str__**`() -> str`
    The tree as indented text, each line `name (id)`, with a `├──` / `└──` connector at every depth (§ [Text form](#text-form)); `repr` is `CompartmentTreeImpl(compartments=N)`. ^str




# CompartmentTreeImpl Semantics

## Topology is not physics
Across `src/` the tree is built through `add_root` and `add_child` and read through `num_compartments`; no simulator, flow or population pass calls `parent`, `children`, `ancestors` or `depth`. A `TransportFlux` names its own source and destination compartments, and a reaction's `compartments` list names ids directly, so the hierarchy is a label: two worlds that differ only in which compartment is whose parent run identically. The parent links matter only to `build_tree`'s validation and to anything a reader prints.



## Construction is checked first
`add_child` checks `parent` — an int, not a bool, in `0 ≤ parent < num_compartments` — before it appends anything, so a refused call leaves the tree as it was. It used to check only the upper bound, and a negative parent left a half-added, nameless compartment behind (fixed in `40c5c09`). `build_tree` only ever passes ids it has just been handed.



## Text form
`__str__` writes the root's line, then `_children_of` writes each child's connector line and recurses on that child with the deeper indent (`    ` under a last child, `│   ` otherwise), so every compartment below the root carries `├──` or `└──` at any depth: a three-level tree prints `│   ├── cell (3)`. Display only.



## Dict form
`to_dict` and `from_dict` both copy, so a rebuilt tree never shares its lists with the caller's dict. `from_dict` refuses what `add_root`/`add_child` could not have built — unequal lengths, zero or two roots, an out-of-range parent, a cycle — so the dict path keeps `build_tree`'s guarantees of one root and no cycle; it does not require parents to precede children.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `038c399` (read from a `git archive` export, a concurrent worker editing `src/`). Checked locally against the export: the connector-less grandchild line, the half-added compartment after `add_child(-1)` (5 → 6), `from_dict` mutating the caller's dict, two roots resolving to the last. The readers of each member found by grep over `src/`. Not run: the cyclic `ancestors` loop (read from the code). Findings filed on T088.
- 2026-10-28 — T088 bio and operator round: `add_child` refuses a negative or non-int parent before touching the tree; `__str__` draws a connector at every depth; `from_dict` copies its lists and refuses unequal lengths, zero or two roots, an out-of-range parent and a cycle; `children` returns a copy.
- 2026-10-28 — refreshed against 0eb23e5: the four `40c5c09` fixes (`add_child` checks first, connectors at every depth, `from_dict` copies and validates, `children` copies) now stated in the members and the three sections, the first renamed *Construction is checked first*; figure's `‡` and "no checks" label dropped.
