---
description: "`makers`: registers the biology makers `mk.M` / `mk.R` / `mk.C` on the `mk` pegboard — what each builds, how the anchor is chosen, and how `mk.C` turns entity lists into name-keyed dicts. Source: `src/alienbio/bio/makers.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO bio](ABIO%20bio.md) → [ABIO Makers](ha://p/ABIO%20Makers) 
# ABIO Makers
The page for the three short constructors every generator uses to build a chemistry: `mk.M` for a molecule, `mk.R` for a reaction, `mk.C` for a chemistry, wired onto the `mk` pegboard when `alienbio.bio` is imported.

![ABIO Makers](ABIO%20Makers.svg) 
*Anchoring* is the topic behind the `_anchor_for` box: an explicit `dat=` or `parent=` wins, then the innermost `mk.anchor(...)`, then a fresh `MockDat`; *Name-keyed collections* governs the ‡ on `_named_dict`.

`makers.py` holds no class and no public function: importing it registers three builders with the singleton `Pegboard` in `infra/mk.py`, which owns the accessor (`mk.M` resolves through `Pegboard.__getattr__`), the anchor stack and the registration check; the pegboard's own reference is [ABIO Factory Pegboard API](../../ABIO%20Ref/ABIO%20Factory%20Pegboard%20API.md). `alienbio.bio`'s `__init__` imports this module for its side effect, so `from alienbio.bio import mk` always has the three keys. The makers are not test sugar only: `Skeleton.materialize` mints every pool with `mk.M` and the chemistry with `mk.C` ([ABIO Skeleton](../ABIO%20suite/ABIO%20Skeleton.md)), and `suite/pipeline.py`, `boundedness.py` and the three `arch_*` drafters build their hosts with all three. What they build is [ABIO MoleculeImpl](ABIO%20MoleculeImpl.md), [ABIO ReactionImpl](ABIO%20ReactionImpl.md) and [ABIO ChemistryImpl](ABIO%20ChemistryImpl.md).



## makers Interface
Three maker keys and the helper behind `mk.C`. Each accessor is `make(local_name, *args, dat=None, parent=None, **kwargs)` from the pegboard: it resolves the anchor (§ [Anchoring](#anchoring)) and calls the builder registered here with `(local_name, anchor, *args, **kwargs)`.

| makers | |
| --- | --- |
| [mk.M](#^mk-m) | A molecule, prefix `mol` |
| [mk.R](#^mk-r) | A reaction, prefix `rxn` |
| [mk.C](#^mk-c) | A chemistry, prefix `chem` |
| [_named_dict](#^named-dict) | Entity list to name-keyed dict |

**mk.M**`(local_name, *, dat=None, parent=None, **kwargs) -> MoleculeImpl`
    `MoleculeImpl(local_name, **anchor, **kwargs)`: every molecule keyword (`atoms`, `bdepth`, `name`, `description`, `formation_energy`) passes through. With no anchor in scope the molecule gets `MockDat(f"mol/{local_name}")`, the same fallback `MoleculeImpl.hydrate` uses. ^mk-m

**mk.R**`(local_name, reactants=None, products=None, *, dat=None, parent=None, **kwargs) -> ReactionImpl`
    `ReactionImpl(local_name, reactants=…, products=…, **anchor, **kwargs)`, so `mk.R("R1", {a: 1.0}, {b: 1.0}, rate=0.5)` reads like the reaction. Reactants and products are dicts keyed by molecule objects; `rate`, `modifiers` and the rest pass through. Prefix `rxn`. ^mk-r

**mk.C**`(local_name, molecules=None, reactions=None, *, dat=None, parent=None, **kwargs) -> ChemistryImpl`
    `ChemistryImpl(local_name, molecules=_named_dict(molecules), reactions=_named_dict(reactions), **anchor, **kwargs)`: either collection may be a list of entities, a mapping (copied as is) or `None`. Prefix `chem`. ^mk-c

**_named_dict**`(items) -> dict[str, Any]`
    `None` → `{}`; a `Mapping` → a shallow copy with its own keys; any other iterable → `{entity.local_name: entity}`, raising `TypeError` on an element that is not an `Entity`, and on anything that is not iterable. Two different entities with one local name raise `ValueError`; the same object listed twice is kept once (§ [Name-keyed collections](#name-keyed-collections)). ^named-dict




# Makers Semantics

## Anchoring
Every root entity needs a `dat` or a `parent`; the pegboard supplies one. In order: an explicit `dat=` wins, then an explicit `parent=`, then the innermost `with mk.anchor(target):` (a parent `Entity` makes the new entity its child, anything else is used as the `dat`), and otherwise a fresh `MockDat("<prefix>/<local_name>")`. Generators never open an anchor, so each skeleton molecule, reaction and chemistry is its own `MockDat` root; the anchor stack is used by tests and by code that hangs entities under a real catalog root.



## Name-keyed collections
A chemistry holds its molecules and reactions in dicts keyed by name. Passing a list to `mk.C` keys each element by its `local_name`, which is what lets a generator write `mk.C("host", molecules + distractors, reactions)`. Since `40c5c09` the derivation refuses a repeat: `mk.C("w", [mk.M("A"), mk.M("A", description="second")], [])` raises `ValueError` naming `'A'`, where it used to build a one-molecule chemistry holding the second `A` and leave any reaction naming the first pointing outside it. The same object listed twice is one entity and is kept once. No shipped generator relied on the overwrite. A mapping is copied as given; a key that differs from its entity's name is refused by `ChemistryImpl` itself.



## Registration
The three `mk.register` calls run once, at import. The pegboard accepts a re-registration only when the builder is the identical function object, which a second import of an already-imported module satisfies; any other builder under `M`, `R` or `C` raises `ValueError`.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `038c399` (read from a `git archive` export, a concurrent worker editing `src/`), with `infra/mk.py` read for the accessor and anchor rules this module depends on. Checked locally against the export: the duplicate-name collapse in `mk.C`. Production callers found by grep over `src/`. The pegboard itself is documented here only as far as the makers rely on it; its own page belongs to the `infra/` pass. Findings filed on T088.
- 2026-10-28 — T088 bio and operator round: `mk.C` refuses two different entities sharing a local name (the same object twice is kept once); no shipped generator relied on the overwrite (suite green). A mapping keyed off its entity's name was already refused by `ChemistryImpl` (E3).
- 2026-10-28 — refreshed against 0eb23e5: `_named_dict` and *Name-keyed collections* state the duplicate-name refusal and the mapping key check in `ChemistryImpl`; figure's ‡ note rewritten.
