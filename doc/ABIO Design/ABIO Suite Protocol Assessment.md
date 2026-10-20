---
description: "F007 Phase 1 (read-only, Opus) assessment: per-shadow-type feasibility of protocol-izing the M26 suite over the biology classes, plus the blast-radius finding that reframes the whole refactor. Input to the Phase 2 decision."
---
:>> [[ABIO]] → [[ABIO Design]] → [ABIO Suite Protocol Assessment](ha://p/ABIO%20Suite%20Protocol%20Assessment) 
# [[ABIO]] · Suite Protocol Assessment — F007 Phase 1
The F007 Phase 1 read-only assessment of how the M26 suite types map onto the biology classes, and the owner decision (unified biological protocol model) that resulted.

> **Owner decision (2026-07-15): option (A) — the unified biological protocol model.** Not the (C→B) this doc originally leaned. Direction (enshrined in [[ABIO PRD]] § Design principle): one cohesive, biology-named data model where all the action is understood at the protocol level. So the per-type verdicts below are read as **absorption targets**, and biological naming wins: `Chemistry` *keeps its name and gains* the graph-query behavior (`neighbors`/`paths`/`subgraph`/`match`) rather than being renamed `ReactionNetwork`; `Species`→`Molecule`, `StateVector`→`WorldState`, `Trace`→`Timeline`, etc. Genuinely-neutral suite-construction abstractions (no biological parallel) stay neutral. Resolved sub-decision (per the principle): **human-readable ids at the protocol level; int indexing is an `*Impl` optimization.**

Read-only assessment (no code changed) answering F007 Phase 1's question: *for each M26 shadow type, can the biology class satisfy a `Protocol` cleanly, and what must it expose?* The answer is more interesting than the plan assumed — the eight "shadow types" are **not one kind of thing**, and the copy-adapters that motivated F007 are **almost entirely unwired**.

## Headline finding — the adapters barely exist in the running system

Grep of the whole repo (`src` + `tests`) for the copy-functions:

| Adapter | Production call sites | Only real consumer |
|---|---|---|
| `to_network` | **0** | tests only |
| `to_state` | **0** | tests only |
| `from_network` | **1** | `verify.simulate()` (rebuild a `Chemistry` to hand the real simulator) |
| `from_state` | **0** | tests only |

Consequences:

- **There is no running path where the same data lives in both a biology object and a neutral copy at once.** The neutral suite is a *standalone* model that the M26 engines construct directly (and M27 will generate directly); biology is a *separate simulation backend*. The "single source of truth violation" the owner objected to is a **type-definition smell, not a live data-duplication bug** — nothing currently forward-adapts biology into the neutral view in production.
- **The one real bridge is `from_network` inside `simulate`**, and it reconstructs a `Chemistry` only to drive integration. The lost tags (`symbol`, `molecular_weight`) are **never read by the simulator** — so the lossy round-trip is harmless to its sole consumer. The loss is only observable via the test-only `to_network(from_network(...))` round-trip.

## Per-type verdict — the "8 shadows" are four different things

| Neutral type | Biology counterpart | What the engines actually use | Verdict |
|---|---|---|---|
| **`Species`** | `Molecule` | `.id`, `.attrs` (structural `==` in `match`) | **Clean projection.** `Molecule` can implement a minimal read-Protocol (`.id`→`name`, add read-only `.attrs`). The one type where "protocol-ize over biology" is straightforward. |
| **`Reaction`** (neutral) | `Reaction` (bio) | `.id`, `.reactants`/`.products` as `tuple[NodeId,int]`, `.modifiers`, `.rate` | **Projection with a shape change.** Bio stores `Dict[Molecule,float]` (by object, float coeff); neutral is `tuple[NodeId,int]`. Feasible via an id-keyed view, but it's a re-shaping, not just an interface tag. |
| **`ReactionNetwork`** | `Chemistry` | `.species`/`.reactions` **plus `.neighbors`/`.paths`/`.subgraph`/`.match`** | **Algorithm-bearing — not a shadow.** `Chemistry` has the mappings but none of the graph algorithms. This is really a **group-2 engine** (graph library over a node/edge view), mis-filed as a data shadow. Keep it; retarget it to run over the `Species`/`Reaction` protocol surface. |
| **`Compartment`** / **`Topology`** | `CompartmentTree` | `.compartments` (objects w/ `.id`/`.parent`/`.kind`/`.volume`) | **Coordinate adapter (int↔str).** Bio uses **int** `CompartmentId` + `parent()`/`children()`/`root()` methods and no per-node object; neutral uses **string** ids + a tuple of value objects. The translation is real work, not duplication — it has to live somewhere. |
| **`StateVector`** | `WorldState` | `.get(comp,sp)`, `.compartments`, `.species`, `.data`, **value-`==`**, `c{i}`/`s{j}` relabel | **Coordinate adapter + value semantics.** Bio is an int-indexed dense array with identity-equality and no axis names; neutral adds string axes, value-equality, and relabeling. The delta is genuine impedance-matching. |
| **`Trace`** | *(none — `List[WorldState]` + dt)* | `.times`, `.states` | **New composite.** No biology equivalent; mild. |
| **`World`** (neutral) | *(none — Execution `World` is a different bundle)* | `.network`, `.topology`, `.initial` | **Standalone scenario-input bundle** — a group-3 abstraction, not a shadow of a biology class. |

**Net:** only **`Species`** (cleanly) and **`Reaction`** (with reshaping) are shadows of a single biology class you can attach a `Protocol` to. `ReactionNetwork` is an engine. `StateVector`/`Topology`/`Compartment` are coordinate adapters doing real int↔str translation. `Trace`/`World` are standalone composites. "Protocol-ize the 8 shadows over biology" only literally applies to ~2 of them.

## The fork this exposes (Phase 2 decision)

The owner approved (B) believing the eight are redundant duplicates of biology. The code says they're a mostly-independent model with one narrow, harmless bridge. So the real decision is **architectural intent**, not mechanics:

- **(A) View-over-biology.** Make the neutral types Protocols/views; have M27 author *real* biology objects and let the engines view them; delete `from_network` (simulate gets the real `Chemistry` directly, no reconstruction, no loss). Closest to "one source of truth" — but it commits M27 to building biology objects and requires the graph algorithms to run over `Chemistry`.
- **(B) Standalone model + fix the one bridge.** Accept the neutral suite as the primary generative model (its frozen value-semantics are an asset for generation/reproducibility); keep `from_network` as the single legitimate simulator bridge and make it lossless where it matters (or note that its consumer ignores the lost tags). Then there are essentially **no shadow types to retire** — and the biggest *real* cleanup is deleting the unused `to_network`/`to_state`/`from_state` (dead outside tests).
- **(C) Minimal.** Do only the two defensible moves regardless of A/B: (1) delete the three unused adapters + their round-trip tests (dead code); (2) give `Molecule` a read-`Species` protocol so `to_network` stops copying. Leaves the coordinate adapters as-is (they earn their keep).

**Recommendation: lean (C→B).** The duplication is largely illusory, the one live defect is harmless, and a full (A) view-over-biology rewrite is a large, risky change justified only if the owner specifically wants a single unified data model. (C) captures the honest cleanup now; (B) is the stable end-state. (A) is only worth it as a deliberate architectural unification.

## What Phase 0 already locks (so any of A/B/C is safe)

`tests/suite/test_phase0_boundary_golden.py` (PR #127) pins `to_network` on a real `Chemistry`, the `from_network` lossy-delta, and the `simulate` trajectory + determinism + mass-conservation — so whichever path is chosen, regressions at the boundary are caught.
