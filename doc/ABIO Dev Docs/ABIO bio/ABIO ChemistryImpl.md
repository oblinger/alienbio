---
description: "`ChemistryImpl`: the container of atoms, molecules and reactions every world is built on, with its one-namespace id rule and bipartite graph queries. Source: `src/alienbio/bio/chemistry.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO bio](ABIO%20bio.md) → [ABIO ChemistryImpl](ha://p/ABIO%20ChemistryImpl) 
# ABIO ChemistryImpl
The chemistry of a world: three dicts of atoms, molecules and reactions, one id namespace across the last two, and the reaction network as a bipartite graph.

![[ABIO ChemistryImpl.svg|2400]] 
*Ids and the shared-id refusal* is the topic that governs the hub's dashed box: one id may not name both a molecule and a reaction.

This page covers the container: what it holds, how it is built, the id rule it enforces and the four graph queries it answers. The entities it holds are `bio/atom.py`, `bio/molecule.py` and `bio/reaction.py` (with `Modulation`); the graph algorithms are `infra/graph_ops.py`; how a chemistry becomes an integrator is [[ABIO WorldSimulatorImpl]] (`from_chemistry`) and [[ABIO JaxWorldSimulator]]; where it sits in the substrate is [[ABIO-Bio-Engine]].



## ChemistryImpl Interface
The `Chemistry` Protocol's implementation (`protocols/bio.py`, held to it by `protocols/_conformance.py` under `pyright src/`), registered as Entity head `"Chemistry"`. It owns three public dicts and nothing else (`__slots__ = ("atoms", "molecules", "reactions")`); the entities in them are shared by reference, not copied and not made Entity children. Its docstring calls it conceptually immutable — built complete by the constructor — but nothing enforces that: the dicts are plain and writable, and a write after construction bypasses the shared-id check. The id check runs once, in `__init__`, so every construction path inherits it. From `Entity` it inherits `local_name`, `dat()`, `root()`, `full_name`, `to_dict()` and the rest, and requires a `parent` or a `dat`.

| ChemistryImpl | |
| --- | --- |
| [[#^chemistryimpl\|ChemistryImpl]] | Build from three dicts; refuse a shared id |
| [[#^atoms\|atoms]] | Atoms by symbol |
| [[#^molecules\|molecules]] | Molecules by id, in simulator index order |
| [[#^reactions\|reactions]] | Reactions by id |
| [[#^hydrate\|hydrate]] | Build from a nested dict |
| [[#^validate\|validate]] | List the membership errors |
| [[#^neighbors\|neighbors]] | Bipartite adjacency of one node |
| [[#^paths\|paths]] | Every simple path between two nodes |
| [[#^subgraph\|subgraph]] | The induced sub-chemistry over some nodes |
| [[#^match\|match]] | Every embedding of a pattern chemistry |
| [[#^attributes\|attributes]] | The chemistry as a plain dict |

**ChemistryImpl**`(name: str, *, atoms: Optional[Dict[str, AtomImpl]] = None, molecules: Optional[Dict[str, MoleculeImpl]] = None, reactions: Optional[Dict[str, ReactionImpl]] = None, parent: Optional[Entity] = None, dat: Optional[DatLike] = None, description: str = "") -> None`
    Initialize the `Entity` (`ValueError` without a `parent` or `dat`, or with a space in `name`), store a shallow copy of each dict (an absent one is `{}`), refuse a molecule or reaction key that differs from its entity's `name`, refuse two different atoms under one symbol anywhere in `atoms` or the molecules' compositions (since `40c5c09`), then refuse any key present in both `molecules` and `reactions` with `ValueError` naming the sorted shared ids — see [[#Ids and the shared-id refusal]]. Checks nothing else: a reaction naming a molecule outside the dict, or a molecule whose atoms are not in `atoms`, is accepted and reported only by `validate`. ^chemistryimpl

**atoms**`: Dict[str, AtomImpl]`
    Atoms keyed by element symbol (`"C"`, `"Na"`). Neither conservation nor the simulators read this dict — they read each molecule's own `atoms` — so it is a declaration that `validate` checks molecules against; see [[#What the three dicts hold]]. ^atoms

**molecules**`: Dict[str, MoleculeImpl]`
    Molecules keyed by id. Insertion order is load-bearing: `WorldImpl` and `WorldSimulatorImpl.from_chemistry` both take `list(molecules.keys())` as the species index order ([[#Order]]). Each key must equal the molecule's `name`; the constructor refuses one that does not ([[#Keys and names]]). ^molecules

**reactions**`: Dict[str, ReactionImpl]`
    Reactions keyed by id, sharing the molecules' namespace. The runner resolves an `Intervene` lever against this dict before `molecules`, which is why a shared id would silently change meaning by action. ^reactions

**hydrate**`(data: dict[str, Any], *, dat: Optional[DatLike] = None, parent: Optional[Entity] = None, local_name: Optional[str] = None) -> Self` (classmethod)
    Build from a nested dict: atoms first (`{symbol: {name, atomic_weight}}`, as `attributes()` writes them, or an `AtomImpl`), then molecules (each entry a dict passed to `MoleculeImpl.hydrate`, or any non-dict meaning a bare molecule named by its key), then reactions against those molecules (`ReactionImpl.hydrate`, which raises `KeyError` on an unknown reactant, product or modifier); a non-dict reaction entry is `ValueError`. The name is `local_name`, else `data["name"]`, else `"chemistry"`; with neither `dat` nor `parent` it mints `MockDat("chem/<name>")`. Each molecule's `{symbol: count}` composition resolves against those atoms; a symbol the chemistry lacks is `KeyError`. `hydrate(attributes())` is the identity — atoms, compositions and coefficients included (`tests/bio/test_moddoc_findings_chemistry.py`; until 2026-10 atoms, compositions and coefficients were all lost) ([[#Construction paths]]). ^hydrate

**validate**`() -> list[str]`
    One message per broken membership, `[]` when clean: each molecule's atoms must be in `atoms` (`AtomImpl` equality, symbol and weight since `40c5c09`), each reaction's reactants, products and modifiers must be in `molecules` (compared by identity — `MoleculeImpl` defines no equality; modifiers were unchecked until 2026-10). Nothing is raised. ^validate

**neighbors**`(node: str) -> set[str]`
    For a molecule, every reaction that names it as reactant, product or modifier; for a reaction, every molecule it names. An unknown node is the empty set. Node ids are `name`s ([[#The graph view]]). ^neighbors

**paths**`(a: str, b: str, max_len: int = 8) -> List[List[str]]`
    Every simple path from `a` to `b` of at most `max_len` edges, alternating molecule and reaction ids, found depth-first over sorted neighbours. `[[a]]` when `a == b`, whether or not `a` is a node. ^paths

**subgraph**`(nodes: Iterable[str]) -> "ChemistryImpl"`
    A new chemistry named `"subgraph"` (on `MockDat("chem/subgraph")`) holding the kept molecules by identity and every atom, with each kept reaction rebuilt with its reactants, products and modifiers filtered to the kept molecules and its `rate` and `rate_law` carried through (until 2026-10 modifiers and `rate_law` were dropped). The rebuilt reactions drop their description, and both dicts are re-keyed by `name` ([[#The graph view]]). ^subgraph

**match**`(pattern: "ChemistryImpl") -> List[Dict[str, str]]`
    Every injective embedding of `pattern`'s graph into this one as `{pattern_id: host_id}`, `[]` when none. A molecule matches only a molecule with equal `(name, symbol, bdepth, molecular_weight)` — the name is part of the key, so species match by name; a reaction matches any reaction, and every pattern edge must exist between the mapped nodes. ^match

**attributes**`() -> Dict[str, Any]`
    The Entity attributes (`name`, `description` when set) plus, each only when non-empty, `atoms` as `{symbol: {name, atomic_weight}}` and `molecules` and `reactions` as `{id: entity.attributes()}`. `to_dict()` serializes through this; the entities are not Entity children, so a recursive `to_dict` adds no `args`. ^attributes



## chemistry Interface
The module exports `ChemistryImpl`, re-exported from `alienbio.bio` and `alienbio`. Its two helpers are private by name: `_reaction_graph_view(chem)` builds the `graph_ops.GraphView` every graph query runs on, and `_mock_dat(path)` returns a `MockDat` typed `Any` for derived entities — imported by `suite/carve.py`, `suite/augment.py` and `suite/perturbations.py` despite the underscore.




# ChemistryImpl Semantics

## Ids and the shared-id refusal
Molecules and reactions live in one id namespace. The two dicts are independent, so before T054 a chemistry could hold a molecule and a reaction under one id; the opaque name map then wrote molecules and reactions into one dict, the reaction won the surface name, the molecule got none, and the runner resolved the one token as the reaction for `Intervene` and the molecule for `Measure` (T051 box 4, T054 #1). `__init__` now refuses the intersection of the two key sets with `ValueError`. `build_name_map` in `suite/naming.py` repeats the check as a backstop, since it is the place that would lose the entry; the Expr `!Chemistry` head surfaces the refusal as an `ExprError` (`tests/expr/test_constructors.py`). The check reads dict keys, which the constructor also holds equal to each entity's `name`, so a `name` cannot carry a second id; an id written into a dict after construction is not caught ([[#Keys and names]]). Atoms are keyed by symbol in their own dict and take no part.



## What the three dicts hold
A reaction holds its molecules as `{MoleculeImpl: coefficient}` for reactants and products and `{MoleculeImpl: Modulation | str}` for modifiers; a molecule holds `{AtomImpl: count}`. The chemistry's dicts only index those objects — the edges live on the entities. Conservation (`bio/conservation.py`) reads each internal reaction's reactants and products and each molecule's `atoms`, never the chemistry's `atoms` dict; modifiers and boundary reactions are exempt. `from_chemistry` reads `rate`, `rate_law` and modifiers off each reaction and looks each molecule up by `name`.



## Keys and names
Three identifiers can differ: the dict key, the entity's `local_name`, and its `name`. A reaction's `name` is its `local_name`; a molecule's `name` defaults to its `local_name` but `MoleculeImpl(..., name=…)` can set a display name. The graph queries, `subgraph`'s re-keying and `from_chemistry`'s lookup all use `name`, while `WorldImpl`, the name map and the runner use dict keys — so the chemistry is only coherent when every key equals its entity's `name`. Every builder in the tree keeps them equal (`mk.C` keys by `local_name`; `hydrate` passes the key as `local_name`), and since 2026-10 the constructor refuses a key that differs from its entity's `name` with `ValueError`, so the two keyings cannot diverge (a display name differing from the key is therefore refused inside a chemistry).



## Construction paths

| Path | Calls | Atoms carried |
| --- | --- | --- |
| `mk.C(name, mols, rxns)` (`bio/makers.py`) | the constructor, lists keyed by `local_name` | none (no `atoms=`) |
| `Skeleton.materialize` (`suite/skeleton.py`) | `mk.C` over the realized fragment | none in the dict; on molecules if the blocks set them |
| `!Chemistry {…}` (`suite/expr_heads.py`) | `hydrate`, molecules re-hydrated from fields | those in an `atoms:` field; a molecule naming any other symbol refuses |
| `hydrate(data)` | `MoleculeImpl.hydrate`, `ReactionImpl.hydrate` | `data["atoms"]`, and each molecule's composition |
| Suite derivers — `carve`, `augment`, `perturbations`, the runner's `_chemistry_with_rate` | the constructor directly, sharing molecules | whatever they pass |
| `subgraph(nodes)` | the constructor | every atom of the source |

So `attributes()` followed by `hydrate()` keeps both the `atoms` dict and every molecule's composition; until 2026-10 it lost both.



## The graph view
Every query rebuilds a `GraphView` from scratch (no cache): species ids are molecule `name`s and reaction ids reaction `name`s, each in dict order; a reaction's incidence is its reactants, products and modifiers; a species' match key is `(name, symbol, bdepth, molecular_weight)`. Modifiers are first-class edges (F008) for `neighbors`, `paths` and `match`, and `subgraph` keeps a kept modifier on the rebuilt reaction.



## Order
Dict insertion order is the species and reaction index order downstream: `WorldImpl` lays out state columns, and `from_chemistry` numbers molecules, by `molecules.keys()`. The graph view preserves it, `match` enumerates in the pattern's order, and `paths` visits neighbours sorted by id, so all three are deterministic for a given chemistry.




# BRIEF
- 2026-10-18 — written as an ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD 84f8190; behaviours that read as defects (`subgraph` dropping modifiers, `hydrate` dropping atoms, key-vs-name re-keying) were confirmed by running them against the venv, not inferred. Left out: `__repr__` (a debug string), the members inherited unchanged from `Entity` (they belong to an Entity doc), and the published page `ABIO Chemistry`, a separate older page this doc does not link. The figure's consumers are the four that read the chemistry's dicts directly; `energy.py`, `boundedness.py` and the suite's validity predicates also take a `ChemistryImpl` and are omitted for density.
- 2026-10-28 — refreshed against 0eb23e5: the constructor's one-atom-per-symbol refusal and symbol-and-weight atom equality (`40c5c09`) added; the `molecules` block and the shared-id section no longer say the key-equals-`name` rule is unchecked (`32fe1f8`). Figure still true.
