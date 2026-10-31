---
description: "`carve`: the FT03 subgraph engine — `carve` finds a reuse-maximal, injective, predicate-gated embedding of a `Motif` into a host chemistry by a pruned backtracking search capped at `MAX_EMBEDDINGS` and returns a `CarveResult` (or `CarveFail`); `splice` rebuilds the host with the skeleton's synthesized nodes and motif edges realized. Source: `src/alienbio/suite/carve.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Carve](ha://p/ABIO%20Carve) 
# ABIO Carve
The engine that binds an abstract motif's roles onto nodes of a host chemistry, synthesizing a node only when no host node fits, and then writes the motif's edges into a copy of the host.

![ABIO Carve](ABIO%20Carve.svg) 
*Adjacency* is the topic behind both operations (one `_edge_holds` test decides when an edge already holds, for carve and splice alike; ‡ a molecule–molecule edge reads `_adjacent`).

`suite/carve.py` treats a `ChemistryImpl` as a bipartite graph of molecules and reactions reached through `neighbors`, `molecules` and `reactions` by name ([ABIO ChemistryImpl](../ABIO%20bio/ABIO%20ChemistryImpl.md)); role constraints are opaque predicates called on the bound object. Its run-path caller is `pipeline.build_suite`'s carved branch (the `identify_pathway` archetype): draft a host, `carve` the motif, `splice`, and refuse when the carve synthesized nodes. The `Motif`, `RoleSlot` and `CarveResult` types are [ABIO Types](ABIO%20Types.md)'s. `carve` and `splice` are re-exported from `alienbio.suite`. The design is [ABIO Suite Construction](../../ABIO%20Architecture/ABIO%20Suite%20Construction.md).



## carve Interface
Two operations, one result type and three constants.

| carve | |
| --- | --- |
| [carve](#^carve) | Embed a motif, reusing host nodes |
| [splice](#^splice) | Apply a skeleton's edits to a host copy |
| [CarveFail](#^carvefail) | No embedding, with a reason |
| [MAX_EMBEDDINGS](#^max-embeddings) | The search's cap, 10 000 |
| [_MODIFIER_RELATIONS](#^modifier-relations) | Relations splice realizes as modifiers |
| [_TYPE_TAG_KINDS](#^type-tag-kinds) | The two type tags that gate a role |

**carve**`(host: ChemistryImpl, motif: Motif, seed: Seed = Seed(0), allow_add: bool = True) -> CarveResult | CarveFail`
    Candidates per role are the host nodes passing every constraint, and of the role's kind when its `type_tag` is `molecule` or `reaction` ([_TYPE_TAG_KINDS](#^type-tag-kinds)), sorted by name. A backtracking search tries each candidate (injective); an edge between two existing nodes must satisfy `_edge_holds` (cached per `(u, v, relation)`), an edge touching a synthesized node is deferred. It runs with no synthesis first; only when that finds nothing, and `allow_add` is set, it runs again for `k = 1, 2, …` synthesized `"{role}#new"` roles, stopping at the first `k` that finds a binding and pruning every branch that would need more. Every complete binding at that reuse is collected; they are sorted and `seed.value % count` picks one. More than `MAX_EMBEDDINGS` at that reuse refuses as a `CarveFail` naming the motif's role count and the host's node, molecule and reaction counts. `added` lists the synthesized ids; `removed` is always `()`. `CarveFail` when no binding exists. ^carve

**splice**`(host: ChemistryImpl, skeleton: CarveResult) -> ChemistryImpl`
    Creates each added id as an atom-free molecule described by its role's `type_tag`; for each motif edge `_edge_holds` does not find: a molecule–reaction edge adds the molecule as a modifier (relation in `_MODIFIER_RELATIONS`), a product (edge from the reaction) or a reactant, moving it off the other side when the host had it backwards unless another motif edge asks for that side (a feedback pair keeps the molecule on both); a move that would empty a side raises `ValueError` naming the edge; a molecule–molecule edge inserts `rxn::u->v` at rate 1.0; a reaction–reaction edge is skipped. Then checks every non-reaction–reaction motif edge holds on the result (`AssertionError` naming the ones that do not) and drops removed nodes from every reaction. Returns a chemistry named `"splice"`. § [What a rebuilt reaction keeps](#what-a-rebuilt-reaction-keeps). ^splice

**CarveFail**`(reason: str)`
    Names the unbindable roles when `allow_add` is false, else "no injective embedding satisfies the motif edges"; or the cap ([MAX_EMBEDDINGS](#^max-embeddings)) with the sizes. ^carvefail

**MAX_EMBEDDINGS**` = 10_000`
    The most embeddings `carve` holds before it refuses (T091 AF4): the pick is `seed % len(top)` over every reuse-maximal embedding, so carve must hold them all, and a long motif in a large host has combinatorially many. Only the frontier counts — bindings at the reuse the search keeps, never a lower-reuse one it would discard (T091 AM1). ^max-embeddings

**_MODIFIER_RELATIONS**
    `catalyzes`, `catalyst`, `modifies`, `regulates`, `inhibits`, `activates`, compared lowercased. The one place a relation tag is interpreted: `_edge_holds` and splice's modifier branch both read it. ^modifier-relations

**_TYPE_TAG_KINDS**` = {"molecule": host.molecules, "reaction": host.reactions}`
    The two `type_tag` values carve reads (T091 AM4): a role tagged `molecule` binds only to a host molecule, `reaction` only to a host reaction, so `!pattern {roles: {a: molecule}}` no longer binds `a` to a reaction. Every other tag is opaque, copied onto a synthesized node and never interpreted. ^type-tag-kinds




# Carve Semantics

## Adjacency
`_edge_holds(host, u, v, relation)` (T088) is the edge test both `carve`'s `edge_ok` and `splice` use, and every case of it is directed the way `splice` builds the edge: a molecule–reaction edge whose relation is in `_MODIFIER_RELATIONS` holds only when the molecule is a modifier of the reaction; any other molecule–reaction edge holds `mol → rxn` only when the molecule is a reactant and `rxn → mol` only when it is a product (T091 AF2 — a substrate role bound to a reaction's product was M36.7's backwards binding on the bipartite edge); a molecule–molecule edge reads `_adjacent`, which holds when one reaction has `u` as a reactant and `v` as a product (directed since M36.7). So carve never binds a role against the chemistry's direction. A motif edge `(E, R, "catalyzes")` no longer binds onto a consumed reactant (before T088 it did, and `splice` left it a reactant).



## Search size
`carve` collects every binding at the best reuse before choosing, since the seed picks among all of them. Two things bound the work (T091 AF4). The no-synthesis pass runs alone first: when every role binds to a host node, those bindings are the reuse-maximal set, so the pick equals what one full search would make. The synthesis pass, run only when that finds nothing, deepens the number of synthesized roles one at a time (T091 AM1): at `k` the bound is `n − k`, so a leaf is reached only at that reuse and the first `k` that finds one yields exactly the reuse-maximal set. Before AM1 the pass pruned against the best reuse found so far, so lower-reuse bindings a later branch would discard counted toward the cap and could refuse a carve whose frontier was small. Unconstrained roles still grow as the falling factorial of the host size, so past `MAX_EMBEDDINGS` bindings carve refuses rather than enumerate — before AF4, four unconstrained roles over a 30-molecule chain collected about 657 000 bindings in 1.9 s.



## What a rebuilt reaction keeps
When `splice` adds a reactant, product or modifier, and for every reaction on a removal, it rebuilds through [`rebuild_reaction`](../ABIO%20bio/ABIO%20ReactionImpl.md) (T088), which keeps `rate`, the compiled `rate_law` and `description`. Before T088 the law and description were dropped, so a spliced reaction ran mass action instead of its law.

A molecule bound backwards is moved to the side the edge asks for, with two limits (T091 AM2, AM7). A feedback motif (`x -product-> m` and `m -substrate-> x`) asks for both sides; `splice` collects the sides every motif edge demands first, and a move never undoes another edge's side. A move that would empty a side refuses: `A -> B` re-bound the other way would become the sink `A + B -> ∅`, which the conservation canary exempts as a boundary reaction. After the edges are written, every motif edge not joining two reactions is re-tested with `_edge_holds` on the rebuilt chemistry.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be`; the relation-blind carve, the dropped `rate_law` and the 1.9 s enumeration confirmed on hand-built chemistries from the HEAD export, no spend. Consumer census: `pipeline.build_suite` (carved branch) and the `alienbio.suite` re-exports.
- 2026-10-28 — refreshed against `9db219f`: carve and splice test edges with `_edge_holds` (the relation tag decides modifier vs side), and splice keeps `rate_law`/description via `rebuild_reaction` (`b32d46b`).
- 2026-10-30 — refreshed for `288bf7a` (T091 AF2, AF4): molecule–reaction edges are read directed (reactant in, product out) and splice moves a backwards molecule to the other side; the search runs without synthesis first, prunes below the best reuse, caches edge checks and refuses above `MAX_EMBEDDINGS` (new block). Figure's `_edge_holds` box and cost note rewritten.
- 2026-10-30 — refreshed for `2a29e7b` (T091 AM1, AM2, AM4, AM7): the synthesis pass deepens `k` synthesized roles and `MAX_EMBEDDINGS` counts the frontier only; `_TYPE_TAG_KINDS` (new block) gates `molecule`/`reaction`-tagged roles; splice keeps a feedback pair, refuses emptying a side and checks every motif edge after. Figure's cost note rewritten.
