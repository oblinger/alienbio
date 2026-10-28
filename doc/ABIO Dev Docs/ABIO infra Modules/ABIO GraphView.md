---
description: "`graph_ops`: the domain-free bipartite graph algorithms behind `ChemistryImpl`'s four graph queries — `GraphView` (ordered species and reaction ids, incidence, a comparison key per species) and `neighbors`, `paths`, `subgraph_selection`, `edge_set`, `match`. Source: `src/alienbio/infra/graph_ops.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO infra Modules](ABIO%20infra%20Modules.md) → [ABIO GraphView](ha://p/ABIO%20GraphView) 
# ABIO GraphView
The page for the reaction-network graph as the algorithms see it: the id-only view a chemistry is adapted into, and the adjacency, path, induced-subgraph and pattern-embedding queries that run on it.

![ABIO GraphView](ABIO%20GraphView.svg) 
*The bipartite model* is the topic behind the single incidence map every query reads: species and reactions share one id space and a reaction touches every species it names; *Embedding* governs `match`'s backtracking edge.

`graph_ops.py` never sees a molecule or a reaction: `ChemistryImpl` builds a `GraphView` on every query (`_reaction_graph_view`, chemistry.py 30–57) and delegates, so the adapter's choices — molecule and reaction `name`s as ids, reactants, products and modifiers as incidence, `(name, symbol, bdepth, molecular_weight)` as the species key — are on [ABIO ChemistryImpl](../ABIO%20bio/ABIO%20ChemistryImpl.md). The module was shared with the retired neutral `ReactionNetwork` and has one caller left. Of the four queries, only `neighbors` is used in `src/` (degree and two-hop reach in `suite/validity.py`, degree in `suite/augment.py`, adjacency in `suite/carve.py`); `paths`, `subgraph` and `match` are reached from tests only. The declared surface is the `Chemistry` Protocol on [ABIO Bio Protocols](../ABIO%20protocols%20Modules/ABIO%20Bio%20Protocols.md); the subsystem view is [ABIO-Infra](../../ABIO%20Architecture/ABIO-Infra.md).



## GraphView Interface
A frozen dataclass. The id tuples are ordered and their order is the enumeration order of `match` and the index order of `subgraph_selection`; nothing checks that the two namespaces are disjoint (the chemistry adapter's caller, `ChemistryImpl`, refuses a shared id).

| GraphView | |
| --- | --- |
| [species_ids](#^species-ids) | Species node ids, in source order |
| [reaction_ids](#^reaction-ids) | Reaction node ids, in source order |
| [incidence](#^incidence) | Reaction id → the species it touches |
| [species_key](#^species-key) | Species id → comparison key for `match` |

**species_ids**`: tuple[str, ...]`
    Also held as a frozenset (`_species_set`, built in `__post_init__`, excluded from equality) for membership tests. ^species-ids

**reaction_ids**`: tuple[str, ...]`
    Likewise mirrored in `_reaction_set`. ^reaction-ids

**incidence**`: Mapping[str, frozenset[str]]`
    The one adjacency structure: undirected, unweighted, with no record of which side of the reaction a species is on. A reaction missing from it touches nothing. ^incidence

**species_key**`: Mapping[str, Any] = {}`
    Compared with `==` and nothing else; a species with no entry has key `None`, which equals every other missing key. ^species-key



## graph_ops Interface
Five functions over a view; each is pure and returns new containers.

| graph_ops | |
| --- | --- |
| [neighbors](#^neighbors) | Adjacent nodes of one node |
| [paths](#^paths) | Every simple path up to a length |
| [subgraph_selection](#^subgraph-selection) | Kept species and reactions, in order |
| [edge_set](#^edge-set) | Every undirected edge |
| [match](#^match) | Every embedding of a pattern view |

**neighbors**`(view, node) -> set[str]`
    For a species, every reaction whose incidence holds it (a scan of all reactions); for a reaction, its incidence; for an id in neither namespace, the empty set. An id in both namespaces gets the union. ^neighbors

**paths**`(view, a, b, max_len: int = 8) -> list[list[str]]`
    Depth-first over simple paths from `a`, alternating species and reactions, each of at most `max_len` edges, returned as id lists. Neighbours are visited sorted by id, not in source order, so results are deterministic but not in the module docstring's "source order". `a == b` returns `[[a]]` whether or not `a` is a node (already on T088 under bio/chemistry). The count is exponential in a dense network; `max_len` is the only bound. ^paths

**subgraph_selection**`(view, nodes) -> tuple[tuple[str, ...], tuple[str, ...]]`
    The species and reaction ids found in `nodes`, each in view order. Rebuilding the reactions with their dropped endpoints removed is the caller's job (`ChemistryImpl.subgraph`). ^subgraph-selection

**edge_set**`(view) -> set[frozenset[str]]`
    Every `{u, v}` pair `neighbors` yields. An id that is both a species and a reaction it touches produces a one-element set, which `match` cannot handle (§ [Embedding](#embedding)). ^edge-set

**match**`(view, pattern) -> list[dict[str, str]]`
    Every injective map from the pattern's nodes (species first, then reactions, in pattern order) into the view that keeps node type, equal `species_key` on species, and every pattern edge as a host edge. Extra host edges between mapped nodes are allowed: this is subgraph monomorphism, not induced. Reactions match any reaction. `[]` when none. ^match




# GraphView Semantics

## The bipartite model
A chemistry is two node kinds and one relation: a reaction is adjacent to every species it consumes, produces or is modulated by, and there are no species–species or reaction–reaction edges. Direction is gone in the view, so a path from `A` to `B` may run backwards through a reaction that consumes `B` and produces `A`; `paths` answers "connected through", not "can be made from". Stoichiometry, rates and modulation kind are not in the view either.



## Embedding
`match` builds each pattern node's candidate list once (every host species with an equal key, or every host reaction), then backtracks node by node, rejecting a candidate already used or one missing a host edge to an already-mapped neighbour. Through `ChemistryImpl` the species key includes the molecule `name`, so a pattern molecule can map only to the host molecule of the same name and the search is free only over reactions. On a hand-built view whose species and reaction namespaces overlap, an id adjacent to itself makes `edge - {pn}` empty and `match` raises `StopIteration` (checked); `ChemistryImpl` refuses the shared id first, so no chemistry reaches it.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `7d390d6` (read from a `git archive` export; a concurrent worker editing `src/suite/`). Run against that export: a self-adjacent id making `match` raise `StopIteration`; a two-species pattern matching four ways on a three-species chain; 400 `neighbors` calls on a 400-reaction view in under 0.01 s (cost is not a concern at catalog sizes). Callers by `git grep` over `src/` and `tests/` at that sha. Findings filed on T088.
