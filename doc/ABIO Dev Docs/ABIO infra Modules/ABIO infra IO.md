---
description: "`io`: the `IO` context entities name themselves through — prefix bindings (`W:cytoplasm.glucose`), absolute references (`</runs/exp1.cytoplasm>`), loading an entity tree back from a dat's `entities.yaml`, the orphan root, and thin `Dat.load`/`Dat.create` wrappers over dvc-dat 3.0. Source: `src/alienbio/infra/io.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO infra Modules](ABIO%20infra%20Modules.md) → [ABIO infra IO](ha://p/ABIO%20infra%20IO) 
# ABIO infra IO
The page for how an entity is written as a string and found again from one: prefix and absolute references, the dat-backed loader, the orphan root, and the one place alienbio touches dvc-dat.

![ABIO infra IO](ABIO%20infra%20IO.svg) 
*Two reference forms* is the topic behind the split between `ref` and `lookup`: a prefix form relative to a bound entity, and an absolute form that names the dat; *Loading a tree* governs the edge from `entities.yaml` back to entities.

`io.py` is the entity tree's outside: the tree itself is [ABIO infra Entity](ABIO%20infra%20Entity.md), which reaches an `IO` only through the module attribute `alienbio.bio.io` (`None` until assigned). Nothing in `src/` assigns it or builds an `IO`; its users are `tests/unit/test_entity.py` and `tests/unit/test_io.py`. With no IO attached, `Entity.__str__` prints `full_name` and `detach` raises. The published class page is [ABIO IO](../../ABIO%20Ref/ABIO%20Classes/ABIO%20IO.md); the subsystem view is [ABIO-Infra](../../ABIO%20Architecture/ABIO-Infra.md), and the dvc-dat surface the repo uses is described on [ABIO DAT](../../ABIO%20Ref/ABIO%20DAT.md).



## IO Interface
One instance holds the bindings and one cache (dat path → root entity); nothing is shared between instances, and nothing is thread-safe. Every method that loads goes through `Dat.load`, which resolves a name against the dat manager's folders and raises `KeyError` when it finds none.

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
    No bindings, an empty cache; the orphan root is built on first use. ^io

**prefixes**`: dict[str, Entity | str]` (property)
    A copy. Holds `ORPHAN` once `orphan_root` has been read. `D` is an ordinary name since the `D:` data-root prefix was retired (§ [The D: prefix](#the-d-prefix)). ^prefixes

**bind_prefix**`(prefix: str, target: Entity | str) -> None`
    Overwrites any earlier binding. A string target is a dat path, loaded here through the same loader and cache an absolute lookup uses; a dat that will not load raises `KeyError` naming the prefix and the path, and nothing is bound. ^bind-prefix

**unbind_prefix**`(prefix: str) -> Entity | str | None`
    Returns what was bound, `None` when nothing was. ^unbind-prefix

**resolve_prefix**`(prefix: str) -> Entity`
    An unbound prefix raises `KeyError`; a string binding gives the dat's root entity from the one cache — the typed tree when the dat holds an `entities.yaml`, and the same object an absolute lookup of that dat returns (§ [One cache](#one-cache)). ^resolve-prefix

**ref**`(entity: Entity, prefer_short: bool = True, absolute: bool = False) -> str`
    With `absolute`, `</<dat path name>.<dotted path from the root>>`. A dat path name containing `.` raises `ValueError` here, since the reference would read back as a different dat (§ [Two reference forms](#two-reference-forms)). Otherwise every binding is resolved and each one that is the entity or an ancestor of it gives a candidate `PREFIX:rest`; the shortest `rest` wins (`prefer_short`), else the first bound. No candidate: `entity.full_name`. Every string binding loaded at `bind_prefix`, so resolving them reads the cache. ^ref

**lookup**`(string: str) -> Entity`
    `</…>` goes to the absolute form, split at the first `.` into a dat path and a dotted entity path. Otherwise the text before the first `:` is the prefix (`ValueError` when there is no `:` or the prefix is empty) and the rest is walked child by child (`KeyError` naming the missing child). ^lookup

**resolve_refs**`(obj: Any) -> Any`
    Rebuilds dicts and lists, replacing every reference-shaped string by `lookup` of its inside: `<PREFIX:dotted.path>` with an identifier prefix, or `</dat/path.entity.path>`, neither holding whitespace (`_REF_SHAPE`). Other angle-bracketed text (`"<html>"`, `"<a b>"`, `"<>"`) passes through; a reference-shaped string with an unbound prefix still raises `KeyError`. ^resolve-refs

**insert_refs**`(obj: Any) -> Any`
    The inverse shape: each `Entity` becomes `"<" + ref(entity) + ">"`; tuples and other containers pass through untouched. ^insert-refs

**orphan_root**`: Entity` (property)
    Built on first read as `Entity("orphans", dat=_OrphanDat())` and bound to `ORPHAN`, so a detached entity prints `ORPHAN:name`. `_OrphanDat.save` raises, and `Entity.save` refuses an orphan-rooted tree before reaching it. ^orphan-root

**load**`(path: str | Path) -> Dat`
    `Dat.load(str(path))`. ^load

**save**`(obj: Any, path: str | Path) -> Dat`
    A `Dat` is saved and returned; anything else becomes `Dat.create(path=…, spec=obj)` for a dict, `spec={"value": obj}` otherwise. A relative path resolves against dvc-dat 3.0's dat folders. ^save



## io Interface
The reference pattern and the orphan root's virtual anchor.

| io | |
| --- | --- |
| [_REF_SHAPE](#^ref-shape) | What `resolve_refs` reads as a reference |
| [_OrphanDat](#^orphandat) | The orphan root's anchor |

**_REF_SHAPE**`: re.Pattern`
    `<PREFIX:path>` with an identifier prefix, or `</…>`; no whitespace or nested angle brackets. ^ref-shape

**_OrphanDat**
    `get_path_name()` and `get_path()` both `"<orphans>"`; `save()` raises `ValueError`. ^orphandat



# IO Semantics

## Two reference forms
A prefix reference `W:cytoplasm.glucose` is relative to whatever `W` is bound to and means nothing without that binding; `ref` picks the shortest one available, so the same entity prints differently as bindings change. An absolute reference `</runs/exp1.cytoplasm.glucose>` names the dat by its path name and is what `Entity.to_dict` writes for a child under another dat. `lookup` splits it at the first `.`, so a dat whose path name contains a `.` (`runs/v1.2`) would write a reference that does not read back (`</runs/v1.2.c>` would load the dat `runs/v1`); `ref(…, absolute=True)` refuses such a dat with `ValueError` instead.



## The D: prefix
Retired 2026-10-28 (T088). It stood for the first dat folder and worked in neither direction: `ref` compared a relative dat path name with an absolute folder path, so it never offered `D:`, and `lookup("D:runs.exp1.g")` walked a children dict nothing filled. The absolute form names any entity in any dat, so `D` is now an unbound name like any other, and `_dat_root` and `_RootEntity` are gone.



## Loading a tree
A dat is loaded once per path (`_dat_entity_cache`). With an `entities.yaml` in the dat folder, `_create_entity_from_dict` looks the `head` up in the registry — an unknown head raises `KeyError` — and rebuilds the entity with that class's own `hydrate(saved, dat=, parent=, local_name=)`, where `saved` is the dict less `head` and `args`. The rebuilt entity's `attributes()` must equal `saved`: a class whose `hydrate` cannot carry a field it wrote refuses with `ValueError` naming the fields, rather than loading a default. `MoleculeImpl` and `ChemistryImpl` round-trip (a saved `bdepth: 3` comes back as 3); a test class with an extra field and no `hydrate` refuses; a `ReactionImpl` root cannot load standalone, its `hydrate` needs the molecules. It then recurses into `args`: a dict child is built inline, an absolute-reference child is looked up and moved under it with `set_parent`, refusing when the `args` key is not the child's local name; anything else is skipped. With no `entities.yaml`, the root is a bare `Entity` named after the path's last segment.

The model is narrower than the class pages once described: `Entity.save` writes one `entities.yaml` per dat and this loader reads it back, and nothing in `src/` calls either. Whether entities persist through dats at all is not settled; [ABIO DAT](../../ABIO%20Ref/ABIO%20DAT.md) describes only the dvc-dat surface the package uses.



## One cache
A string binding and an absolute reference to one dat reach the same `_load_dat_entity` and the same cache entry, so they give one object (checked). Until 2026-10-28 a binding built a bare `Entity` in a second cache, ignoring `entities.yaml`, and `ref` could not relate the two routes.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `7d390d6` (read from a `git archive` export; a concurrent worker editing `src/suite/`), against dvc-dat `6eca674`. Run against that export with a scratch dat folder: a saved `MoleculeImpl` losing `bdepth` on load; `</runs/v1.2.c>` failing to load; prefix and absolute routes giving two objects for one dat; `ref` raising `KeyError` once one string binding cannot load; `D:` matching nothing in either direction; `"<html>"` raising in `resolve_refs`; `import alienbio` outside the repo binding the site-packages `tests`. Not determined: whether AUP or any script outside the repo builds an `IO`. Findings filed on T088.
- 2026-10-28 — refreshed against `76bfc54`: the loader hydrates by head and refuses a lost field or an unknown head, one cache, string bindings load at `bind_prefix`, `D:` retired, a dotted dat path name refused at write, `resolve_refs` reads reference-shaped text only; `imports.py` deleted (`6ec2fb0`), so its section and the import side effect are gone.
