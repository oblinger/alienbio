---
description: "The Skeleton composition data model — Skeleton as a recursive SkeletonBlock tree woven by pool-ports, its concrete blocks, and the provenance links to the constructed chemistry. Module-doc-format companion to ABIO Skeleton Architecture."
---
:>> [[ABIO]] → [[ABIO Design]] → [[ABIO Skeleton Arch]] → [ABIO Skeleton Data Model](ha://p/ABIO%20Skeleton%20Data%20Model) 
# ABIO Skeleton Data Model
The composition types — `Skeleton`, `SkeletonBlock` (recursive; a small set of concrete `…Block` subclasses), `Port` (a pool), and the provenance to the constructed chemistry — with their fields, class names and method-level API.

> ⚠️ **Under active revision (2026-07-18, S7).** The *structure* below (recursive block tree, one pool-port kind, provenance to a separate chemistry) is settled with the owner. The *block roster* is still being stress-tested against ~20 biological situations before it is frozen — expect the concrete `…Block` list to grow. See [[ABIO Skeleton Arch]] § S7.

## Overview

A **`Skeleton`** is a **recursive tree of `SkeletonBlock`s** — one top-level block whose children are blocks, whose children are blocks, down to primitive reactions. Blocks are woven together two ways: **horizontally**, by sharing **pool-ports** (a parent's or sibling's port and this block's port name the *same pool*); and **vertically**, a block **expands** (`realize`) into child blocks, binding its own ports down to theirs. From that tree the skeleton **constructs a `ChemistryImpl`** (a *separate* object it points to), and every block keeps **provenance** — links to the exact reactions-in-compartments it produced — so methods can *climb the tree* to ask questions and verify results against ground truth. All types are frozen dataclasses; construction is pure and seed-deterministic.

## Architecture diagram

![[skeleton-datamodel.svg|3000]] 

↗ [Clickable](skeleton-datamodel.svg) | ✎ [Edit](skeleton-datamodel.svg) — *(figure predates the S7 recursive refinement; update pending)*

## `Port` — a pool (a molecule in a container)

There is exactly **one kind of port: a pool** (S7). The old species/control split is gone — "regulatory" influence is just a pool that a reaction's *rate* reads. A block **binds** to a pool as producer or consumer.

| Field | Type | Meaning |
|---|---|---|
| `name` | `str` | Port name, unique within the block. |
| `container` | `NodeId \| None` | Compartment the pool lives in (`None` = the block's default / inherited-from-parent container). |
| `direction` | `PortDir` | `IN` (block consumes the pool) or `OUT` (block produces it). |

Two ports **bound together name the same pool** (a `PoolBinding`). At construction, bound ports resolve to one shared `MoleculeImpl` — the fix for the object-vs-name aliasing hazard the code map flagged. A parent binds its ports to its children's ports when it expands.

## `SkeletonBlock` — the recursive block (base + concrete subclasses)

`SkeletonBlock` is the abstract base of every building block — the name carries **Skeleton** so the family reads as skeletal; concretes take a short **`…Block`** suffix (`Block` is the unifying building-block noun). A block is both a **tree node** and a **template**: it holds its params, its child blocks, its pool-ports, and — after construction — its provenance.

| Field | Type | Meaning |
|---|---|---|
| `name` | `str` | Node name; also the **namespace prefix** for every chemistry id this block emits, so two uses never alias in the flat name-space. |
| `role` | `Role` | Purpose enum (`SUPPLY`, `SINK`, `CRUX`, `SIGNALING`, `TRANSPORT`, `PRESSURE`). |
| `ports` | `tuple[Port, ...]` | The pools this block exposes for weaving. |
| `params` | `Tags` | The block's parameter values (sampled from a `ParamSchema` of typed holes). |
| `children` | `tuple[SkeletonBlock, ...]` | Sub-blocks this block expands into (empty for a primitive). |
| `provenance` | `tuple[Provenance, ...]` | After construction: the `(reaction_id, container_id)` pairs this block produced — the block→chemistry link the oracle reads. |

| Method | Signature | Description |
|---|---|---|
| `realize` | `realize(seed, ns, bound) -> Fragment` | (abstract) Expand this block: emit its own `ReactionImpl`s over its pools **and** recurse into `children` (binding parent ports down to child ports), namespaced by `ns`, recording provenance. A *primitive* emits one reaction; a *pattern* emits sub-blocks. |
| `walk` | `walk() -> Iterator[SkeletonBlock]` | Pre-order tree walk (self + descendants) — how the oracle climbs the skeleton. |
| `ground_truth` | `ground_truth(timeline) -> Any` | (crux-bearing blocks) Read this block's answer off a simulated `Timeline` via its provenance. |

**Concrete blocks (roster under revision — S7).** A tiny primitive set + a few recursive purpose-patterns:

| Class | Kind | Role | Expands into |
|---|---|---|---|
| `SourceBlock` | primitive | SUPPLY | one boundary reaction `∅ → pool` |
| `SinkBlock` | primitive | SINK | one boundary reaction `pool → ∅` |
| `ConflictCruxBlock` ✦ | pattern | CRUX | two routes drawing on one shared precursor pool (the crux) |
| `SignalingBlock` | pattern | SIGNALING | a reaction whose rate a sensed pool modulates (feedback) |
| `TransportBlock` | pattern | TRANSPORT | cross-compartment flux (needs S3 engine term) |
| `PressureBlock` | pattern | PRESSURE | an exogenous perturbation on a pool |

Removed vs the first draft (S7): `ConversionBlock` → *is* a reaction (sink input pool, source output pool); `HomeostasisBlock` → the boundedness invariant + a feedback pattern (F012 D-f); `ReadoutBlock` → an observation dial; `BufferBlock` → a pattern if kept. Full specs: [[ABIO Skeleton Block Catalog]].

`Fragment` is a small record the `realize` recursion accumulates: `molecules`, `reactions`, `compartments`, `initial` concentrations, and the `provenance` links.

## `Skeleton` — the composite (root block + the chemistry it constructs)

A thin composite over the tree: the root block, the constructed chemistry it points to, and the task-level markers.

| Field | Type | Meaning |
|---|---|---|
| `root` | `SkeletonBlock` | The top-level block; its `children` are the whole tree. |
| `chemistry` | `ChemistryImpl \| None` | The constructed chemistry the skeleton points to (set by `materialize`; distractors live here too, without provenance). |
| `control_surface` | `tuple[PortRef, ...]` | Exposed pools/params the agent may set (the levers). |
| `crux` | `BlockRef` | The block the task/oracle is defined against. |

| Method | Signature | Description |
|---|---|---|
| `materialize` | `materialize(seed) -> WorldImpl` | Recursively `realize` the root (expanding children, unifying bound pools) into one `ChemistryImpl` + `Compartment`s → `WorldImpl`; store `chemistry`; keep every block's provenance. |
| `validate` | `validate() -> None \| SkeletonError` | Well-formedness: every pool has a producer and a bounded fate (F012 D-f); bound ports type-match; namespaces collision-free; every internal reaction atom-balanced (F012 gate). |
| `oracle` | `oracle(seed) -> GroundTruth` | `verify.simulate` the assembled world; climb the tree to the `crux` block and read its `ground_truth` off the final state (the retained-skeleton oracle). |
| `indirection_depth` | `indirection_depth() -> int` | Min pool-graph distance from any lever to the crux — the difficulty dial. |

Frozen-dataclass note: builders return a **new** `Skeleton`/`SkeletonBlock` (functional update via `dataclasses.replace`), matching the suite convention (`generative.py` uses `replace`); a thin mutable builder may wrap them for ergonomics.

## See also
- [[ABIO Skeleton Arch]] — subsystem overview, the two-level provenance model, materialization, invariants, and open decisions S1–S7.
- [[ABIO Skeleton Block Catalog]] — the concrete `…Block` subclasses (roster under revision).
