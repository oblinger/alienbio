---
description: "`mk`: the maker pegboard — `Pegboard`, a registry of one-letter entity makers with an ambient anchor stack, and `mk`, its one instance, so `mk.M(\"A\")` builds a molecule anchored on `MockDat(\"mol/A\")` or on whatever `with mk.anchor(target)` names. Source: `src/alienbio/infra/mk.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO infra Modules](ABIO%20infra%20Modules.md) → [ABIO Pegboard](ha://p/ABIO%20Pegboard) 
# ABIO Pegboard
The page for how `mk.M("A")` becomes an anchored entity: maker registration, the attribute lookup that turns a key into a maker, and the three ways a new entity gets its anchor.

![ABIO Pegboard](ABIO%20Pegboard.svg) 
*Anchor resolution* is the topic behind the three-way choice inside `make`: an explicit `dat=` or `parent=`, the innermost `mk.anchor` target, or a minted `MockDat`.

`mk.py` holds no entity knowledge: the three makers it dispatches to (`M`, `R`, `C`) are registered by `bio/makers.py` at import and documented in [ABIO Makers](../ABIO%20bio/ABIO%20Makers.md); the entities and anchors they build are [ABIO infra Entity](ABIO%20infra%20Entity.md). `mk` is imported by `bio/__init__.py` and eight `suite/` modules (blocks, skeleton, pipeline, boundedness, expr_heads and the three archetype drafters), always for `mk.M`/`mk.R`/`mk.C` with no anchor, so every generated world is built on `MockDat`s. `mk.anchor` has no caller in `src/`; `tests/unit/test_mk.py` is its user. The feature record is F009; the subsystem view is [ABIO-Infra](../../ABIO%20Architecture/ABIO-Infra.md).



## Pegboard Interface
A plain class: a dict of registrations and a list used as a stack. Instances do not share state, but the process uses one, `mk`.

| Pegboard | |
| --- | --- |
| [Pegboard](#^pegboard) | An empty board |
| [register](#^register) | Bind a key to a maker and a prefix |
| [registered_keys](#^registered-keys) | The keys, sorted |
| [anchor](#^anchor) | Context: anchor new entities to a target |
| [&lt;key&gt;](#^key) | The maker for a registered key |

**Pegboard**`()`
    `_registry = {}`, `_anchor_stack = []`. ^pegboard

**register**`(key: str, *, prefix: str, build: Maker) -> None`
    Stores `_Registration(key, prefix, build)`. A key already held by a different `build` object raises `ValueError`; the same `build` again replaces the registration, prefix included, so re-importing `makers.py` is harmless and a changed prefix is taken without notice (§ [Registration](#registration)). Keys are any string; `bio/makers.py` uses `M`, `R`, `C` with prefixes `mol`, `rxn`, `chem`. ^register

**registered_keys**`() -> list[str]`
    Sorted keys; `["C", "M", "R"]` once `alienbio.bio` is imported. ^registered-keys

**anchor**`(target: Entity | Any) -> ContextManager`
    Pushes `target` for the block and pops it on exit, exceptions included; nestable, innermost wins. An `Entity` target makes new entities its children; anything else is taken for a dat. Yields `target`. ^anchor

**&lt;key&gt;**`(local_name: str, *args, dat=None, parent=None, **kwargs) -> Entity`
    `mk.M`, `mk.R`, `mk.C`: `__getattr__` finds the registration (`AttributeError` listing the registered keys otherwise) and returns a fresh closure named `mk.<key>` that resolves the anchor (§ [Anchor resolution](#anchor-resolution)) and calls `build(local_name, anchor, *args, **kwargs)`. Built anew on every attribute access, so `mk.M is mk.M` is false. ^key



## mk Interface
The module-level surface.

| mk | |
| --- | --- |
| [mk](#^mk) | The process's one pegboard |
| [Maker](#^maker) | The build callable's type |

**mk**`: Pegboard`
    Created at import; `bio/makers.py` registers on it, and `alienbio`, `alienbio.infra` and `alienbio.bio` re-export it. ^mk

**Maker**` = Callable[..., Entity]`
    Called as `build(local_name, anchor, *args, **kwargs)`, where `anchor` is `{"dat": …}` or `{"parent": …}` ready to splat into an entity constructor. ^maker




# Pegboard Semantics

## Anchor resolution
`make` picks exactly one anchor: `dat=` when given, else `parent=` when given, else the top of the anchor stack (`{"parent": target}` for an `Entity`, `{"dat": target}` otherwise), else `{"dat": MockDat(f"{prefix}/{local_name}")}`. Passing both `dat=` and `parent=` keeps the dat and drops the parent without a word, where `Entity(name, dat=d, parent=p)` would build a sub-root child of `p`. The stack is a plain list on the instance, not a context variable: two threads building under `mk.anchor` would see each other's targets. Nothing in `src/` uses the stack, so generated worlds never meet either case.



## Registration
Identity of the `build` object is the test for "same maker", which is what makes a module re-import safe (`makers.py` binds the same function objects) and an `importlib.reload` of `makers.py` unsafe (new function objects, so `M` raises). A same-`build` re-registration overwrites the prefix: `register("E", prefix="ent", build=b)` then `register("E", prefix="other", build=b)` leaves `other` in force.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `7d390d6` (read from a `git archive` export; a concurrent worker editing `src/suite/`). Run against that export: a same-`build` re-registration taking the new prefix; `dat=` with `parent=` dropping the parent. Callers by `git grep -w` over `src/` and `tests/` at that sha. Not determined: whether any concurrent drafting path will ever adopt `mk.anchor` (it would need a context variable). Findings filed on T088.
