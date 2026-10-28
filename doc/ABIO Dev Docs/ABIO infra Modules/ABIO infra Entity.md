---
description: "`entity`: the `Entity` base class every chemistry object derives from — a local name in a parent/child tree whose root holds a dat anchor, the head registry `__init_subclass__` fills, `to_dict`/`hydrate`/`save` — plus `MockDat`, the stand-in anchor, and the `alienbio.infra` package's export list. Source: `src/alienbio/infra/entity.py`, `src/alienbio/infra/__init__.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO infra Modules](ABIO%20infra%20Modules.md) → [ABIO infra Entity](ha://p/ABIO%20infra%20Entity) 
# ABIO infra Entity
The page for the object tree under every molecule, reaction, chemistry and compartment: how an entity is anchored, named, re-parented and serialized, and what the head registry holds.

![ABIO infra Entity](ABIO%20infra%20Entity.svg) 
*The top slot* is the topic behind the two kinds of anchor arrow: a root's `_top` is its dat, every other entity's `_top` is its root, so `root()` and `dat()` never walk; *Re-parenting* governs the `set_parent` edge and the orphan root it falls back to.

`entity.py` is the tree and nothing above it: the four subclasses `src/` defines are `MoleculeImpl`, `ReactionImpl`, `ChemistryImpl` and `CompartmentImpl` under [ABIO bio](../ABIO%20bio/ABIO%20bio.md) (each overrides `hydrate` and `attributes`); the one-line makers that build them are [ABIO Pegboard](ABIO%20Pegboard.md); prefix references, the orphan root and loading a tree back from disk are [ABIO infra IO](ABIO%20infra%20IO.md), reached only through `alienbio.bio.io`, which nothing in `src/` assigns (only `tests/unit/test_entity.py` does). The published class page is [ABIO entity](../../ABIO%20Ref/ABIO%20Classes/ABIO%20entity.md); the subsystem view is [ABIO-Infra](../../ABIO%20Architecture/ABIO-Infra.md).



## Entity Interface
A plain class with `__slots__` (`_local_name`, `_parent`, `_children`, `_top`, `description`). Every instance has a parent or a dat anchor or both; the constructor refuses neither. What `src/` uses of it is construction, `local_name`, `full_name` (the drafters strip a `mol/` prefix off it) and `parent`; `to_dict`, `save`, `detach`, `ancestors`, `descendants` and `to_str` have no caller in `src/`.

| Entity | |
| --- | --- |
| [Entity](#^entity) | Construct under a parent, a dat, or both |
| [hydrate](#^hydrate) | Build from a dict (base: name, description) |
| [local_name](#^local-name) | Name in the parent's children |
| [parent](#^parent) | The containing entity |
| [children](#^children) | A copy of the children dict |
| [head](#^head) | The registered type name |
| [description](#^description) | Free text |
| [attributes](#^attributes) | Semantic content as a dict |
| [dat](#^dat) | The tree's anchor, O(1) |
| [root](#^root) | The anchored ancestor, O(1) |
| [full_name](#^full-name) | Dat path plus dotted local names |
| [set_parent](#^set-parent) | Move under another entity |
| [detach](#^detach) | Move under the orphan root |
| [to_dict](#^to-dict) | Head, attributes and optional args |
| [to_str](#^to-str) | `name(child, child)` to a depth |
| [ancestors](#^ancestors) | Parent up to root |
| [descendants](#^descendants) | Depth-first below |
| [save](#^save) | Write `entities.yaml` into the dat |

**Entity**`(name: str, *, parent: Entity | None = None, dat: DatLike | None = None, description: str = "")`
    Raises `ValueError` when both `parent` and `dat` are `None` or when `name` contains a space (any other character is accepted, a `.` included). With `dat`, `_top` is the dat and the entity is a root, or a sub-root when a `parent` is also given (§ [The top slot](#the-top-slot)); with `parent` alone, `_top` is the parent's root. A `parent` is attached through `set_parent`, so a name its parent already holds raises. ^entity

**hydrate**`(data: dict, *, dat=None, parent=None, local_name=None) -> Self` (classmethod)
    The base reads `name` (default the lowercased class name) and `description`, and with no anchor mints `MockDat("<classname>/<name>")`. Every subclass in `src/` overrides it with its own fields and its own prefix (`mol/`, `rxn/`, `chem/`), so the base form is reached only by a subclass that does not. ^hydrate

**local_name**`: str` (property)
    The constructor's `name`; never changes, since nothing renames an entity. ^local-name

**parent**`: Entity | None` (property)
    `None` for a root built with a dat alone. ^parent

**children**`: dict[str, Entity]` (property)
    A fresh copy each access, keyed by local name in insertion order; mutating it changes nothing. ^children

**head**`: str` (property)
    The first name in the head registry whose class is exactly `type(self)`, else the class name. A class whose name a later class re-registered falls back to its own class name. ^head

**description**`: str`
    The constructor's text; written by `attributes` only when non-empty. ^description

**attributes**`() -> dict`
    `{"name": local_name}` plus `description` when set. Subclasses extend it; `to_dict` and `IO`'s loader are its readers. ^attributes

**dat**`() -> DatLike`
    The root's `_top`. A sub-root answers its own dat, not its parent tree's. ^dat

**root**`() -> Entity`
    `self` when `_top` is a dat, else `_top`. ^root

**full_name**`: str` (property)
    A root's `dat.get_path_name()`; otherwise the parent's `full_name`, a `.`, and the local name, so it walks the parent chain (it does not use `_top`). Under a `MockDat("mol/A")` the molecule `A` reads `mol/A`; a child of it `mol/A.x`. ^full-name

**set_parent**`(parent: Entity | None) -> None`
    Falls back to `bio.io.orphan_root` for `None` (raising `RuntimeError` when no IO is attached), refuses with `ValueError` a parent that is the entity or one of its descendants and a name the new parent already holds for another entity, then removes the entity from its old parent's children, sets `_parent`, registers it, and repoints `_top` across the subtree. Both refusals come before anything moves (§ [Re-parenting](#re-parenting)); re-setting the current parent is a no-op. ^set-parent

**detach**`() -> None`
    `set_parent(bio.io.orphan_root)`; the entity then prints `ORPHAN:<name>`. `RuntimeError` with no IO attached. ^detach

**to_dict**`(recursive: bool = False) -> dict`
    `{"head": head, **attributes()}`, and with `recursive` an `args` dict: a child in the same root inlined by its own `to_dict`, a child under another root (a sub-root) as `bio.io.ref(child, absolute=True)`. ^to-dict

**to_str**`(depth: int = -1) -> str`
    `World(Cytoplasm(Glucose, ATP), Nucleus)`: local names only, `-1` unlimited, `0` the name alone. ^to-str

**ancestors**`() -> Iterator[Entity]`
    Parent, grandparent … up to the entity with no parent. ^ancestors

**descendants**`() -> Iterator[Entity]`
    Pre-order over the children dicts. ^descendants

**save**`() -> None`
    Only on a root, and not on the orphan root (`ValueError` for either). Dumps `to_dict(recursive=True)` as YAML to `<dat.get_path()>/entities.yaml`, then calls `dat.save()`. A `MockDat` root writes under `/mock/…`, which does not exist, so it raises `FileNotFoundError`. `IO._load_dat_entity` is the reader (§ [Serialized form](#serialized-form)). ^save



## MockDat Interface
The anchor every test, generator and maker uses in place of a dvc-dat `Dat`: a path string and the two methods `Entity` calls. `src/` builds one in eight modules, the pegboard among them.

| MockDat | |
| --- | --- |
| [MockDat](#^mockdat) | Wrap a path string |
| [get_path_name](#^get-path-name) | The path as given |
| [get_path](#^get-path) | `/mock/<path>` |

**MockDat**`(path: str)`
    Stores `path`; no validation, no filesystem access. ^mockdat

**get_path_name**`() -> str`
    `path`, which becomes a root entity's `full_name`. ^get-path-name

**get_path**`() -> str`
    `"/mock/" + path`, the folder `save` writes into. ^get-path



## entity Interface
The module-level surface: the head registry and the anchor alias.

| entity | |
| --- | --- |
| [register_head](#^register-head) | Bind a head name to a class |
| [get_entity_class](#^get-entity-class) | Look a head up |
| [get_registered_heads](#^get-registered-heads) | Copy of the registry |
| [DatLike](#^datlike) | The anchor type, `Any` |

**register_head**`(name: str, cls: type[Entity]) -> None`
    Writes `_head_registry[name] = cls`, replacing any earlier class silently. Called by `Entity.__init_subclass__` with the `head=` class keyword or the class name, and once at import for `Entity` itself. ^register-head

**get_entity_class**`(name: str) -> type[Entity]`
    `KeyError` naming an unknown head. Its one `src/` caller is `IO._create_entity_from_dict`, which lets the `KeyError` through. ^get-entity-class

**get_registered_heads**`() -> dict[str, type[Entity]]`
    A copy. `suite/expr_heads.py` iterates it once at import to register an Expr constructor head per entity head other than `Entity`, `Compartment`, `Reaction` and `Chemistry` (which have hand-written ones), so a class defined after that import gets no `!Head` constructor. ^get-registered-heads

**DatLike**` = Any`
    A dvc-dat `Dat`, a `MockDat`, or one of `io.py`'s virtual dats; anything with `get_path_name()`, and `get_path()` for `save`. ^datlike



## infra Interface
`alienbio.infra` re-exports `Entity`, `IO`, `Pegboard` and `mk`; `alienbio/__init__.py` re-exports the same four; the `infra.imports` side-effect module is gone (T088). `MockDat` is exported from `alienbio.bio`, not from here.




# Entity Semantics

## The top slot
One slot answers both "which dat" and "which root". A root's `_top` is its dat; every other entity's `_top` is the root entity, and `set_parent` rewrites it through the whole subtree (`_update_top`), stopping at any descendant that holds a dat of its own. That descendant is a sub-root: built with both `parent` and `dat`, it sits in its parent's children but answers `root()` with itself, `dat()` and `full_name` with its own dat, and `to_dict` serializes it as an absolute reference rather than inline. `full_name` is the exception that walks: it climbs `_parent`, so a long chain costs its depth.



## Re-parenting
`set_parent` checks before it moves: resolve `None` to the orphan root, refuse a parent that is the entity itself or appears among its descendants (found by walking the new parent's `ancestors()` for the entity), refuse a name the new parent holds for a different entity, and only then pop from the old parent, assign `_parent`, register and repoint `_top`. A refused call leaves the entity, its old parent and the new parent as they were. Until 2026-10-28 the pop and the assignment came first, so a name collision left the entity in neither tree, and a cycle either recursed to `RecursionError` (non-root) or succeeded with `ancestors()` and `descendants()` looping forever (root).



## Serialized form
`save` writes the shape `to_dict(recursive=True)` gives: `head`, the attributes, and `args` mapping each child's local name to its own dict or to an absolute reference `</dat/path.a.b>`. `IO` reads it back by head through each class's own `hydrate`, and refuses when the rebuilt `attributes()` differ from the saved ones, so a class either round-trips its fields or does not load (§ [Loading a tree](ABIO%20infra%20IO.md#loading-a-tree) on the IO page).




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `7d390d6` (read from a `git archive` export, a concurrent worker editing `src/suite/`). Run against that export: the name-collision `set_parent` leaving the entity in neither tree; a cycle through a non-root raising `RecursionError` and through a root succeeding; a shadowed class's `head` falling back to its class name. Callers counted by `git grep -w` over `src/` and `tests/` at that sha. Not determined: whether any caller outside `src/` (AUP's launchers) uses `save`, `detach` or `to_dict`. Findings filed on T088.
- 2026-10-28 — refreshed against `234de0d`: `set_parent` refuses a name clash or a cycle before moving anything; `__str__` falls back to `full_name` only when no IO is attached; `get_entity_class`'s `KeyError` now reaches the loader's caller (`76bfc54`).
