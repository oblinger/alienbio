---
description: "`io`: the `IO` context entities name themselves through — prefix bindings (`W:cytoplasm.glucose`), absolute references (`</runs/exp1.cytoplasm>`), loading an entity tree back from a dat's `entities.yaml`, the orphan root, and thin `Dat.load`/`Dat.create` wrappers over dvc-dat 3.0; plus `imports`, the optional `tests.fixtures` import. Source: `src/alienbio/infra/io.py`, `src/alienbio/infra/imports.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO infra Modules](ABIO%20infra%20Modules.md) → [ABIO infra IO](ha://p/ABIO%20infra%20IO) 
# ABIO infra IO
The page for how an entity is written as a string and found again from one: prefix and absolute references, the dat-backed loader, the orphan root, and the one place alienbio touches dvc-dat.

![ABIO infra IO](ABIO%20infra%20IO.svg) 
*Two reference forms* is the topic behind the split between `ref` and `lookup`: a prefix form relative to a bound entity, and an absolute form that names the dat; *Loading a tree* governs the edge from `entities.yaml` back to entities.

`io.py` is the entity tree's outside: the tree itself is [ABIO infra Entity](ABIO%20infra%20Entity.md), which reaches an `IO` only through the module attribute `alienbio.bio.io` (`None` until assigned). Nothing in `src/` assigns it or builds an `IO`; its users are `tests/unit/test_entity.py` and `tests/unit/test_io.py`. With no IO attached, `Entity.__str__` prints `full_name` and `detach` raises. The published class page is [ABIO IO](../../ABIO%20Ref/ABIO%20Classes/ABIO%20IO.md); the subsystem view is [ABIO-Infra](../../ABIO%20Architecture/ABIO-Infra.md), and the dvc-dat surface the repo uses is described on [ABIO DAT](../../ABIO%20Ref/ABIO%20DAT.md).



## IO Interface
One instance holds the bindings and two caches; nothing is shared between instances, and nothing is thread-safe. Every method that loads goes through `Dat.load`, which resolves a name against the dat manager's folders and raises `KeyError` when it finds none.

| IO | |
| --- | --- |
| [IO](#^io) | An empty context |
| [prefixes](#^prefixes) | A copy of the bindings |
| [bind_prefix](#^bind-prefix) | Bind a prefix to an entity or a dat path |
| [unbind_prefix](#^unbind-prefix) | Remove a binding |
| [resolve_prefix](#^resolve-prefix) | The entity behind a prefix |
| [ref](#^ref) | Entity to `PREFIX:path` or absolute |
| [lookup](#^lookup) | `PREFIX:path` or absolute to entity |
| [resolve_refs](#^resolve-refs) | `<…>` strings in data to entities |
| [insert_refs](#^insert-refs) | Entities in data to `<…>` strings |
| [orphan_root](#^orphan-root) | Where detached entities go |
| [load](#^load) | `Dat.load` |
| [save](#^save) | Save a dat, or create one from a value |

**IO**`()`
    No bindings, empty caches; the data root and the orphan root are built on first use. ^io

**prefixes**`: dict[str, Entity | str]` (property)
    A copy. Holds `ORPHAN` once `orphan_root` has been read; `D` is never in it (§ [The D: prefix](#the-d-prefix)). ^prefixes

**bind_prefix**`(prefix: str, target: Entity | str) -> None`
    Overwrites any earlier binding. A string target is a dat path, loaded on the first `resolve_prefix` and cached by path. ^bind-prefix

**unbind_prefix**`(prefix: str) -> Entity | str | None`
    Returns what was bound, `None` when nothing was. ^unbind-prefix

**resolve_prefix**`(prefix: str) -> Entity`
    `D` is the virtual data root; an unbound prefix raises `KeyError`; a string binding becomes `Entity(<last path segment>, dat=Dat.load(path))`, cached in `_path_entity_cache`. That entity is a bare `Entity` even when the dat holds an `entities.yaml`, and it is a different object from the one an absolute lookup of the same dat returns (§ [Two caches](#two-caches)). ^resolve-prefix

**ref**`(entity: Entity, prefer_short: bool = True, absolute: bool = False) -> str`
    With `absolute`, `</<dat path name>.<dotted path from the root>>`. Otherwise every binding is resolved and each one that is the entity or an ancestor of it gives a candidate `PREFIX:rest`, plus a `D:` candidate; the shortest `rest` wins (`prefer_short`), else the first bound. No candidate: `entity.full_name`. Resolving every binding means one string binding whose dat will not load makes every `ref` raise `KeyError`, whatever the entity. ^ref

**lookup**`(string: str) -> Entity`
    `</…>` goes to the absolute form, split at the first `.` into a dat path and a dotted entity path. Otherwise the text before the first `:` is the prefix (`ValueError` when there is no `:` or the prefix is empty) and the rest is walked child by child (`KeyError` naming the missing child). ^lookup

**resolve_refs**`(obj: Any) -> Any`
    Rebuilds dicts and lists, replacing every string that starts with `<`, ends with `>` and is longer than two characters by `lookup` of its inside. Any such string is taken for a reference, so a value like `"<html>"` raises `ValueError`. ^resolve-refs

**insert_refs**`(obj: Any) -> Any`
    The inverse shape: each `Entity` becomes `"<" + ref(entity) + ">"`; tuples and other containers pass through untouched. ^insert-refs

**orphan_root**`: Entity` (property)
    Built on first read as `Entity("orphans", dat=_OrphanDat())` and bound to `ORPHAN`, so a detached entity prints `ORPHAN:name`. `_OrphanDat.save` raises, and `Entity.save` refuses an orphan-rooted tree before reaching it. ^orphan-root

**load**`(path: str | Path) -> Dat`
    `Dat.load(str(path))`. ^load

**save**`(obj: Any, path: str | Path) -> Dat`
    A `Dat` is saved and returned; anything else becomes `Dat.create(path=…, spec=obj)` for a dict, `spec={"value": obj}` otherwise. The docstring's `Dat.manager.sync_folder` no longer exists in dvc-dat 3.0; the path resolves against the manager's first dat folder. ^save



## io Interface
The module-level helper and the two virtual stand-ins.

| io | |
| --- | --- |
| [_dat_root](#^dat-root) | The first dat folder |
| [_RootEntity](#^rootentity) | What `D:` resolves to |
| [_OrphanDat](#^orphandat) | The orphan root's anchor |

**_dat_root**`() -> str`
    `Dat.manager._dat_folders[0]` without a trailing `/`, an absolute real path; `RuntimeError` naming the manager's type when the list is missing or empty. dvc-dat 3.0 publishes no accessor, so this reads a private attribute (T066/`80c6bef`). ^dat-root

**_RootEntity**
    Duck-typed like an entity: empty `local_name`, no parent, `full_name` = `_dat_root()`, and a `children` dict nothing ever fills. ^rootentity

**_OrphanDat**
    `get_path_name()` and `get_path()` both `"<orphans>"`; `save()` raises `ValueError`. ^orphandat



## imports Interface
`imports.py` is eleven lines: `from tests import fixtures` inside `try/except ImportError`, imported by `alienbio/__init__.py` so that dotted names dvc-dat's `do` system might resolve (`"fixtures.process_data"`, written in `tests/fixtures/__init__.py`) are already in `sys.modules`. Nothing in `src/` calls `do`. Kept on this page because dvc-dat is its only reason to exist and `io.py` is the only other module that imports dvc-dat. What it imports depends on the working directory (§ [Import side effect](#import-side-effect)).




# IO Semantics

## Two reference forms
A prefix reference `W:cytoplasm.glucose` is relative to whatever `W` is bound to and means nothing without that binding; `ref` picks the shortest one available, so the same entity prints differently as bindings change. An absolute reference `</runs/exp1.cytoplasm.glucose>` names the dat by its path name and is what `Entity.to_dict` writes for a child under another dat. `lookup` splits it at the first `.`, so a dat whose path name contains a `.` (`runs/v1.2`) writes a reference that does not read back: `</runs/v1.2.c>` loads the dat `runs/v1` and fails.



## The D: prefix
`D` always resolves, to a `_RootEntity` standing for the first dat folder, and `ref` always offers a `D:` candidate. The candidate compares the entity's `full_name` with `_dat_root()` as strings; `full_name` starts with the dat's path name relative to its folder (`runs/exp1`) and `_dat_root()` is an absolute path, so the comparison never succeeds for a dvc-dat or `MockDat` root and `ref` falls through to `full_name`. Read the other way, `lookup("D:runs.exp1.g")` walks `_RootEntity.children`, which is empty, and raises `KeyError`. Neither direction of `D:` works today.



## Loading a tree
`lookup` of an absolute reference loads the dat once per path (`_dat_entity_cache`). With an `entities.yaml` in the dat folder, `_create_entity_from_dict` builds the root by its `head` (an unknown head becomes a plain `Entity`, with no message), calling `cls(name, parent=, dat=, description=)`, and recurses into `args`: a dict child is built inline under it, an absolute-reference child is looked up and moved under it with `set_parent` (keyed by its own local name, not the `args` key), anything else is skipped. Because only `name` and `description` reach the constructor, a saved `MoleculeImpl` with `bdepth: 3` loads back as a `MoleculeImpl` with the default `bdepth` (checked). With no `entities.yaml`, the root is a bare `Entity` named after the path's last segment.



## Two caches
A dat reached through a string binding is cached in `_path_entity_cache` as a bare `Entity`; the same dat reached through `</…>` is cached in `_dat_entity_cache` as the loaded tree. They are different objects (checked), so an entity found by one route is not an ancestor of anything found by the other, and `ref` does not relate them.



## Import side effect
`import alienbio` runs `from tests import fixtures`. From the repository root the current directory is first on `sys.path` and that is the repo's `tests` package. From anywhere else the first `tests` on the path in this venv is `site-packages/tests` (shipped by `mkdocs_roamlinks_plugin`), which has no `fixtures`: the `ImportError` is swallowed, but `sys.modules["tests"]` is now that foreign package for the rest of the process (checked from `/private/tmp`).




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `7d390d6` (read from a `git archive` export; a concurrent worker editing `src/suite/`), against dvc-dat `6eca674`. Run against that export with a scratch dat folder: a saved `MoleculeImpl` losing `bdepth` on load; `</runs/v1.2.c>` failing to load; prefix and absolute routes giving two objects for one dat; `ref` raising `KeyError` once one string binding cannot load; `D:` matching nothing in either direction; `"<html>"` raising in `resolve_refs`; `import alienbio` outside the repo binding the site-packages `tests`. Not determined: whether AUP or any script outside the repo builds an `IO`. Findings filed on T088.
