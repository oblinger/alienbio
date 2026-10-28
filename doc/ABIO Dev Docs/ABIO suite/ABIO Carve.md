---
description: "`carve`: the FT03 subgraph engine — `carve` finds a reuse-maximal, injective, predicate-gated embedding of a `Motif` into a host chemistry by exhaustive backtracking and returns a `CarveResult` (or `CarveFail`); `splice` rebuilds the host with the skeleton's synthesized nodes and motif edges realized. Source: `src/alienbio/suite/carve.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Carve](ha://p/ABIO%20Carve) 
# ABIO Carve
The engine that binds an abstract motif's roles onto nodes of a host chemistry, synthesizing a node only when no host node fits, and then writes the motif's edges into a copy of the host.

![ABIO Carve](ABIO%20Carve.svg) 
*Adjacency* is the topic behind both operations (one `_adjacent` predicate decides when an edge already holds; ‡ carve ignores the edge's relation tag, splice reads it).

`suite/carve.py` treats a `ChemistryImpl` as a bipartite graph of molecules and reactions reached through `neighbors`, `molecules` and `reactions` by name ([ABIO ChemistryImpl](../ABIO%20bio/ABIO%20ChemistryImpl.md)); role constraints are opaque predicates called on the bound object. Its run-path caller is `pipeline.build_suite`'s carved branch (the `identify_pathway` archetype): draft a host, `carve` the motif, `splice`, and refuse when the carve synthesized nodes. The `Motif`, `RoleSlot` and `CarveResult` types are [ABIO Types](ABIO%20Types.md)'s; [ABIO Augment](ABIO%20Augment.md) rebuilds chemistries the same way. `carve` and `splice` are re-exported from `alienbio.suite`. The design is [ABIO Suite Construction](../../ABIO%20Architecture/ABIO%20Suite%20Construction.md).



## carve Interface
Two operations, one result type and one constant.

| carve | |
| --- | --- |
| [carve](#^carve) | Embed a motif, reusing host nodes |
| [splice](#^splice) | Apply a skeleton's edits to a host copy |
| [CarveFail](#^carvefail) | No embedding, with a reason |
| [_MODIFIER_RELATIONS](#^modifier-relations) | Relations splice realizes as modifiers |

**carve**`(host: ChemistryImpl, motif: Motif, seed: Seed = Seed(0), allow_add: bool = True) -> CarveResult | CarveFail`
    Candidates per role are the host nodes passing every constraint, sorted by name. A backtracking search tries each candidate (injective) and, when `allow_add`, a synthesized `"{role}#new"`; an edge between two existing nodes must satisfy `_adjacent`, an edge touching a synthesized node is deferred. Every complete binding is collected; the ones reusing the most host nodes are sorted and `seed.value % count` picks one. `added` lists the synthesized ids; `removed` is always `()`. `CarveFail` when no binding exists. ^carve

**splice**`(host: ChemistryImpl, skeleton: CarveResult) -> ChemistryImpl`
    Creates each added id as an atom-free molecule described by its role's `type_tag`; for each motif edge not already adjacent: a molecule–reaction edge adds the molecule as a modifier (relation in `_MODIFIER_RELATIONS`), a product (edge from the reaction) or a reactant; a molecule–molecule edge inserts `rxn::u->v` at rate 1.0; a reaction–reaction edge is skipped. Then drops removed nodes from every reaction. Returns a chemistry named `"splice"`. § [What a rebuilt reaction keeps](#what-a-rebuilt-reaction-keeps). ^splice

**CarveFail**`(reason: str)`
    Names the unbindable roles when `allow_add` is false, else "no injective embedding satisfies the motif edges". ^carvefail

**_MODIFIER_RELATIONS**
    `catalyzes`, `catalyst`, `modifies`, `regulates`, `inhibits`, `activates`, compared lowercased. The one place a relation tag is interpreted. ^modifier-relations




# Carve Semantics

## Adjacency
`_adjacent(host, u, v)` holds when `v` is a bipartite neighbour of `u` (a molecule and a reaction it takes part in, either direction) or when one reaction has `u` as a reactant and `v` as a product. The reaction case is directed since M36.7, which stopped `identify_pathway` binding its chain backwards. The relation tag plays no part: a motif edge `(E, R, "catalyzes")` carved onto a host where `e` is a consumed reactant of `r` bound `E → e`, and `splice` then found the edge adjacent and left `e` a reactant. A motif that needs a catalyst gets a reactant whenever the host offers one.



## Exhaustive search
`carve` enumerates every binding before choosing, not the first or the best-so-far. With edges the candidate sets prune fast; without them the count is the falling factorial of the host size. Four unconstrained molecule roles over a 30-molecule chain collected about 657 000 bindings in 1.9 s; each further role multiplies the work by the remaining host size.



## What a rebuilt reaction keeps
When `splice` adds a reactant, product or modifier, it rebuilds the reaction from reactants, products, modifiers and `rate`; the reaction's compiled `rate_law` and `description` are dropped. A reaction built with `rate_law = const(2.0)` came back with `None` after a synthesized product was spliced onto it, so it runs mass action instead of its law. The same rebuild happens for every reaction on a removal. `identify_pathway` refuses synthesized nodes and its hosts carry no rate laws, so no run moves today.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be`; the relation-blind carve, the dropped `rate_law` and the 1.9 s enumeration confirmed on hand-built chemistries from the HEAD export, no spend. Consumer census: `pipeline.build_suite` (carved branch) and the `alienbio.suite` re-exports.
