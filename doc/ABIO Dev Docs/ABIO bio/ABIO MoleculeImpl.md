---
description: "`molecule` + `atom`: `MoleculeImpl`, the chemical-species entity (atom composition, biosynthetic depth, display name, formation energy, the derived formula and weight, its dict round-trip), and `AtomImpl` with the `COMMON_ATOMS` table it is composed from. Source: `src/alienbio/bio/molecule.py`, `src/alienbio/bio/atom.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO bio](ABIO%20bio.md) → [ABIO MoleculeImpl](ha://p/ABIO%20MoleculeImpl) 
# ABIO MoleculeImpl
The page for the species entity and the element it is built from: what a molecule carries, which of its fields anything downstream reads, how it round-trips through a dict, and the fixed atom table.

![ABIO MoleculeImpl](ABIO%20MoleculeImpl.svg) 
*Composition is opaque* is the topic behind the two dotted reader edges: atoms feed only the conservation check and formation energy only the energy check, and no simulator reads either.

`atom.py` (118 lines, one small class and a fourteen-entry table) is folded into this page rather than given its own; its section is [AtomImpl Interface](#atomimpl-interface). A `MoleculeImpl` is an `Entity` (`infra/entity.py`), so it carries a local name, a `dat` or `parent` anchor and a description; the `Entity` machinery is not repeated here. Molecules are collected by [ABIO ChemistryImpl](ABIO%20ChemistryImpl.md), which hydrates them with its own atom registry; the simulators see only molecule indices (`ReactionSpec` keys, [ABIO WorldSimulatorImpl](ABIO%20WorldSimulatorImpl.md)), never this object. The two readers of its content are [ABIO Conservation](ABIO%20Conservation.md) (atoms) and `bio/energy.py` (formation energy). Tests build molecules with `mk.M("A")` (`bio/makers.py`); the published class page is [ABIO Molecule](../../ABIO%20Ref/ABIO%20Classes/ABIO%20Molecule.md).



## MoleculeImpl Interface
A slotted `Entity` subclass registered under the head `Molecule` and the biotype `molecule`. Every content field is optional and defaults to empty, so a molecule with only a name is valid; that is the form every skeleton block mints. Mutable only through its private slots: each property returns a value or a copy.

| MoleculeImpl | |
| --- | --- |
| [MoleculeImpl](#^moleculeimpl) | Build a molecule |
| [hydrate](#^hydrate) | Build one from a dict and an atom registry |
| [atoms](#^atoms) | Composition, `{AtomImpl: count}` |
| [bdepth](#^bdepth) | Biosynthetic depth |
| [name](#^name) | Display name |
| [formation_energy](#^formation-energy) | Assigned free energy, or `None` |
| [symbol](#^symbol) | Formula from the atoms |
| [molecular_weight](#^molecular-weight) | Sum of atomic weights |
| [attributes](#^attributes) | The dict `hydrate` reads back |

**MoleculeImpl**`(local_name, *, parent=None, dat=None, description="", atoms=None, bdepth=0, name=None, formation_energy=None)`
    The `Entity` constructor first, which raises `ValueError` unless `dat` or `parent` is given. `atoms` is copied; `name` defaults to `local_name`. No field is validated: a negative `bdepth`, a zero or fractional atom count, or a non-numeric `formation_energy` is stored as given. ^moleculeimpl

**hydrate**`(data, *, dat=None, parent=None, local_name=None, atoms=None) -> MoleculeImpl` (classmethod)
    Reads the keys `attributes` writes: `name` (the local name, unless `local_name` overrides; `"molecule"` when both are missing), `description`, `atoms` as `{symbol: count}`, `bdepth`, `display_name`, `formation_energy`. Each atom symbol resolves against the `atoms` registry; a composition with no registry raises `ValueError` and an unknown symbol `KeyError`, so a composition is never dropped. With neither `dat` nor `parent`, mints `MockDat(f"mol/{name}")`. ^hydrate

**atoms**`: Dict[AtomImpl, int]`
    A copy of the composition. Keys compare by symbol (§ [AtomImpl Interface](#atomimpl-interface)). Read by `conservation.molecule_quantity`. ^atoms

**bdepth**`: int`
    Biosynthetic depth, 0 for a primitive. Carried and serialized; nothing in `src/` reads it. ^bdepth

**name**`: str`
    The display name; the local name unless one was given. Serialized as `display_name` only when it differs. ^name

**formation_energy**`: Optional[float]`
    An opaque assigned scalar (F018), never derived from the atoms; `None` books nothing in the energy check. Read by `energy.reaction_delta_g`. ^formation-energy

**symbol**`: str`
    The formula: each atom's symbol, followed by its count when the count is not 1, carbon first, hydrogen second, the rest alphabetical; `""` with no atoms. § [Formula order](#formula-order). ^symbol

**molecular_weight**`: float`
    `Σ atomic_weight · count`; `0.0` with no atoms. ^molecular-weight

**attributes**`() -> Dict[str, Any]`
    `Entity.attributes()` (`name`, `description` when set) plus `atoms` as `{symbol: count}`, `bdepth`, `formation_energy` and `display_name`, each only when it differs from its default. `hydrate(m.attributes(), atoms=registry)` rebuilds a molecule with the same fields (the round trip fixed in `af28794`); molecules define no `__eq__`, so the two compare by identity. ^attributes



## AtomImpl Interface
`bio/atom.py`: a slotted value class for a chemical element, and the fixed table every caller in `src/` draws from. Atoms are never entities; they have no anchor.

| AtomImpl | |
| --- | --- |
| [AtomImpl](#^atomimpl) | Build an element |
| [symbol](#^atom-symbol) | One or two letters |
| [atom name](#^atom-name) | English name |
| [atomic_weight](#^atomic-weight) | Atomic mass in u |
| [__eq__](#^eq) | Equal by symbol |
| [COMMON_ATOMS](#^common-atoms) | The fourteen-element table |
| [get_atom](#^get-atom) | Look one up by symbol |

**AtomImpl**`(symbol: str, name: str, atomic_weight: float)`
    Raises `ValueError` when `symbol` is empty or longer than two characters; nothing else is checked. ^atomimpl

**symbol**`: str`
    `"C"`, `"Na"`. The atom's identity. ^atom-symbol

**name**`: str`
    `"Carbon"`. ^atom-name

**atomic_weight**`: float`
    Mass in atomic mass units; the only number `molecular_weight` reads. ^atomic-weight

**__eq__**`(other) -> bool`
    True for another `AtomImpl` with the same symbol, whatever its name or weight; `__hash__` is `hash(symbol)`. Two atoms that differ only in weight are one dict key. ^eq

**COMMON_ATOMS**`: Dict[str, AtomImpl]`
    H, C, N, O, P, S, Na, K, Ca, Mg, Cl, Fe, Zn, Cu by symbol, built once at import. ^common-atoms

**get_atom**`(symbol: str) -> AtomImpl`
    `COMMON_ATOMS[symbol]`, raising `KeyError("Unknown atom symbol: …")` for any other. ^get-atom




# MoleculeImpl Semantics

## What reads a molecule
Of the fields, two are read outside this file and both by opt-in checks: `atoms` by the conservation check and `formation_energy` by the energy check. `bdepth`, `name`, `symbol` and `molecular_weight` are carried, printed and serialized but feed no simulation, preflight or score. The simulators address species by integer index; a molecule's index is its position in `chemistry.molecules`, the order [ABIO WorldImpl](ABIO%20WorldImpl.md) resolves once for the state and the simulator alike.



## Formula order
`symbol` sorts carbon first, hydrogen second, and every other element alphabetically, whether or not the molecule has carbon. The Hill system the docstring names puts hydrogen second only when carbon is present and sorts everything alphabetically otherwise, so a carbon-free molecule differs: hydrogen chloride prints `HCl` here and `ClH` under Hill, water `H2O` under both. A zero count is kept and printed (`C0O2`).



## Hydration and the atom registry
A composition travels as `{symbol: count}` and is resolved against a registry the caller passes, so two chemistries can carry different atom tables. `ChemistryImpl.hydrate` passes its own; the only table in `src/` is `COMMON_ATOMS`. Because atoms compare by symbol, a registry whose `"C"` has a different weight still matches a molecule built with the common carbon, and the molecule's weight is computed from whichever object is the dict key.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `038c399` (read from a `git archive` export, a concurrent worker editing `src/`). `atom.py` is folded in because it is one value class and a table; a page of its own would repeat the composition story. Checked locally against the export: `HCl` and `C0O2` as printed, atom equality across different weights. Readers of each field found by grep over `src/`. Not determined: whether `bdepth` has a planned reader. Findings filed on T088.
- 2026-10-28 — T088 bio and operator round: `symbol` is Hill order (carbon-free formulas fully alphabetical: `HCl` → `ClH`); atoms are equal by symbol and weight; a molecule or chemistry carrying two different atoms under one symbol refuses.
