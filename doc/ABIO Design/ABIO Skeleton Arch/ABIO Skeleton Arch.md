---
description: "Architecture of the Skeleton composition subsystem — the layer that assembles worlds from typed, stackable building blocks so a small agent control surface reaches a buried crux only through layers of indirection. The generative substrate behind the M31 conflict/pressure generators (Phase-2 D1). For owner review before implementation."
---
[[ABIO]] · [[ABIO Design]] · [[ABIO Phase-2 Design Brief]] · [[ABIO Roadmap]] · [[ABIO Experiment Catalog]] 

| -[ABIO Skeleton Arch](ABIO%20Skeleton%20Arch.md)- | : Architecture of the Skeleton composition subsystem — the layer that assembles worlds from typed, stackable building blocks so a small agent control surface reaches a buried crux only through layers of indirection. The generative substrate behind the M31 conflict/pressure generators (Phase-2 D1). For owner review before implementation.<br>→ [ABIO](../../ABIO.md) → [ABIO Design](../ABIO%20Design.md) → [ABIO Skeleton Arch](ha://p/ABIO%20Skeleton%20Arch) |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| ...                                               | [ABIO Block Grammar Coverage 2026-07-18](Block%20Grammar%20Coverage%202026-07-18.md),  [ABIO Skeleton Block Catalog](ABIO%20Skeleton%20Block%20Catalog.md),  [ABIO Skeleton Data Model](ABIO%20Skeleton%20Data%20Model.md),                                                                                                                                                                                                                                              |


# ABIO Skeleton Arch
The architecture of the Skeleton composition subsystem — how ABIO assembles worlds from typed, stackable building blocks.

## Overview

The **Skeleton subsystem** builds a world by **stacking typed building blocks**. Each block is a small, parameterized fragment of chemistry with a declared *role* (supply, conflict-crux, signaling, homeostasis, …) and a set of *typed ports*. You **instantiate** blocks, **wire** their ports together, mark a small **control surface** (the levers the agent may touch) and a **crux** (the tension the task forces you to manage), then **materialize** the assembly into a runnable `WorldImpl`. A hard problem is not a single clever mechanism — it is a *composition* in which the crux sits far downstream of the levers, reachable only through modulating and homeostatic layers. **Difficulty is indirection depth.** Ground truth is read by **simulating the assembled world**, so it survives composition and stays deterministic.

This subsystem is Phase-2 decision **D1** (see [[ABIO Phase-2 Design Brief]]), promoted from a fork to a subsystem. It is the generative substrate the M31 conflict/pressure generators and every downstream M34 trial run on — which is why it is written up for review before a line is built.

## Architecture diagram

![[skeleton-pipeline.svg|3000]] 

↗ [Clickable](skeleton-pipeline.svg) | [Index](#subsystems) | ✎ [Edit](skeleton-pipeline.svg) 

## Subsystems

| Part | What it is | Doc |
|---|---|---|
| **Data model** | `Skeleton`, `Block`, `BlockInstance`, `Port`, `Wire` — the composition types and their methods | [[ABIO Skeleton Data Model]] |
| **Block catalog** | The complete enumeration of typed blocks (role · ports · params · purpose), one buildable spec each | [[ABIO Skeleton Block Catalog]] |
| **Materialization** | Flatten a composed `Skeleton` → `ChemistryImpl` + `Compartment`s → `WorldImpl` (§ Materialization) | this doc |
| **Oracle** | Simulate the assembled world → map the crux frontier → ground truth (§ Ground truth under composition) | this doc |
| **Integration** | How a composed Skeleton plugs into `build_suite` via the existing `drafter` seam (§ Integration) | this doc |

## Where it sits — one new layer over an existing substrate

The code map (2026-07-18) is unambiguous about the seam we build on:

- **Existing (unchanged):** `WorldImpl` (= `ChemistryImpl` + `Compartment`s), the `verify.simulate → Timeline` physics, the `Seed` determinism seam, and the `TaskArchetype.drafter` seam that lets a generated world enter `build_suite`.
- **Existing but *renamed* by this design:** today's `Skeleton` (`suite/types.py`) is a **binding overlay** — `motif` + `binding: role→node-name` + `added`/`removed`. It is the *result of a carve*, not a container of chemistry. This design gives the name "Skeleton" to the new composite (the more central concept going forward); the legacy carve-result type is renamed **`CarveResult`** to free the name (S1 — a one-line internal rename, unrelated to the new design).
- **New:** the whole composition layer — `Block` / `BlockInstance` / `Port` / `Wire`, the composed `Skeleton`, `materialize`, `validate`, and the block library.

Composition is **`carve` generalized**: `carve`/`splice` already insert one typed motif into one host chemistry. This subsystem inserts *N namespaced blocks* into one world and wires their ports — the multi-block merge that `build_suite` explicitly defers today (M28.1) is exactly this capability.

## Skeleton ↔ chemistry — two levels + a provenance map

The subsystem operates at **two levels of abstraction**, and keeping them distinct is what makes ground truth robust:

- **Skeleton (intent).** Typed components carrying the world's *known functionality by construction* — the conflict-crux, the boundary-transit, the homeostatic loop. This is a different type than the chemistry.
- **Chemistry (substrate).** The realized ground world — concrete molecules/reactions/compartments — **plus generator-added distractor reactions** that are part of the ecosystem but of no skeletal role. At this level the skeleton has *disappeared*: the agent sees only a ground world.
- **Provenance map (bridge).** Each skeletal component `realize`s into a set of chemistry elements, and the skeleton **retains** which elements came from which component. Distractors have no provenance.

Because the skeleton is retained, **it is the oracle**: ground-truth questions ("which reaction transits the boundary?", "where is the crux frontier?") are answered *against the skeleton and its provenance map*, never re-inferred from the raw world. Distractors therefore cannot fool the oracle — they exist only in chemistry, with no skeletal handle. This is the greybox property the framework is built on: **skeleton = ground truth, chemistry = observable, provenance = bridge, distractors = chemistry-only.** It generalizes `carve`, whose `binding` is already a one-motif provenance overlay.

## Materialization — how a composed Skeleton becomes a World

`Skeleton.materialize(seed) → WorldImpl` runs three passes:

1. **Instantiate.** For each `BlockInstance`, call the block's factory with its bound params and a labeled child seed (`seed.child(instance.name)`), producing a fragment: `MoleculeImpl`s + `ReactionImpl`s (+ optional `Compartment` + initial concentrations), **all id-prefixed by the instance namespace** so two uses of the same block never alias.
2. **Resolve wires.** For each species `Wire`, *unify* the two ports' molecules onto **one shared `MoleculeImpl` object**, rewriting every referencing reaction to that object. This is mandatory: the map shows reactions key stoichiometry by molecule **object** but the simulator reconciles by **name**, so a wire that left two same-named objects in place would be an aliasing bug. Control wires attach a modulating species to the target reaction (see the catalog's Signaling block).
3. **Assemble + validate.** Merge fragments into one `ChemistryImpl`, place compartments, seed initial concentrations, then run `validate()` (below). Return a `WorldImpl`.

The result enters the existing world exactly like any drafted world — no change to `WorldImpl` or the simulator.

## The invariant we actually enforce (not atom mass)

The map is explicit: **the engine enforces no mass conservation.** `Chemistry.validate()` checks membership only; `splice` inserts neutral 1→1 reactions; atom-free molecules are legal and pervasive. So the correctness argument is *not* "atoms balance." `Skeleton.validate()` instead enforces **flow-budget well-formedness**:

- **No dangling species ports** — every exposed species port is either wired or explicitly a boundary (source/readout).
- **Every consumed pool has a supply** — a species drawn down by some reaction must be produced or injected by some block; no free lunch.
- **Constant-rate only** — the map shows `verify.simulate` *rejects callable rate laws loudly*; blocks may emit only constant mass-action rates. Modulation is realized structurally (a modulating species participating in the reaction), never as a rate function.
- **Namespace-collision-free** — instance prefixes make every id unique before wires deliberately unify chosen pools.

The **crux budget** — what makes a forced tradeoff *real* — then follows by construction, not by atom-mass: a Conflict-Crux block draws two routes from **one shared precursor pool** whose only inflow is a known set of `Source` rates. Total draw ≤ total supply is therefore an analytic bound *the composition operator guarantees structurally*. Simulation is needed only to map the frontier's exact shape under nonlinear kinetics + indirection — never to discover whether tension exists.

## Ground truth under composition

Because indirection is deep and kinetics nonlinear, the *answer* (the achievable crux frontier, or the optimal management policy) is a **simulated object**: `Skeleton.oracle(seed)` runs `verify.simulate` on the **assembled** world and reads the final-state totals the same way existing outcome scorers do (`arch_intervene._final_concentration`). Deterministic given the seed ⇒ this is still **ground-truth-by-construction**, just *by-simulation* rather than *by-formula*. Both are equally taint-free and reproducible. This is the design position the owner endorsed for D1: prefer *real* worlds whose tension emerges from structure, and pay for it by simulating to map the frontier.

## Difficulty = indirection depth

`Skeleton.indirection_depth()` = the minimum wire-graph distance from any control-surface lever to the crux. It is the principled difficulty dial and **subsumes M28.1** (network size): size for its own sake is replaced by *purpose-driven* size — every intervening block is a homeostatic buffer or a signaling transducer the agent must infer and work through. Simple worlds: constant feedstock, depth 1. Hard worlds: a distant "medicine" lever whose effect reaches the crux only through a mediated flow gated by a signaling block reading a homeostatically-buffered species — depth 4+.

## Integration — plugging into `build_suite`

A composed Skeleton reaches tasks through the **existing** `drafter` seam, no pipeline contract change:

- A generator (M31.x) builds a `Skeleton`, then exposes a `Drafter = (seed) → (WorldImpl, Skeleton_binding, Objective?)` that calls `skeleton.materialize(seed)` for the world and defines the task's objective against the marked crux.
- `TaskArchetype.drafter` carries it; `build_suite` already branches to the generated path when a drafter is present (`suite/pipeline.py`).
- The objective is an `OutcomeObjective` graded by a crux-reading scorer (the `arch_intervene` pattern) or an `AnswerObjective` when the task asks the agent to *identify* structure rather than steer it.

## Two blocks force new engine capabilities (gated dependencies)

The map surfaced two hard limits that the *indirection* story runs straight into. Both are called out here rather than hidden, because they are milestones in their own right:

- **G-a — rate modulation by a species.** The Signaling/mediated-flow block needs a species' concentration to *modulate* a downstream rate. The engine supports only constant mass-action and rejects callable rates; whether a non-consumed **modifier** concentration scales rate in the current physics is **unconfirmed** by the map. Realizable *today*: model the signal as a **consumed reactant** (its abundance gates the rate by mass-action, but it depletes). Sustained catalytic modulation needs a small, explicit simulator extension. **Open decision S2.**
- **G-b — cross-compartment transport.** The Transport/Compartment-Flow block needs flux *across* a membrane, but the map shows reactions **never cross compartments**. There is no transport primitive today. The Transport block therefore requires an engine addition (a compartment-crossing flux term). **Open decision S3.** Until then, "compartment flow" is modeled within one compartment as a Source/Sink pair.

Neither blocks the core library: the forced-tradeoff experiments (EXP-2, EXP-7) are expressible with Source + Conflict-Crux + Environmental-Pressure + (consumed-reactant) Signaling + Homeostasis on today's engine. G-a/G-b are what unlock the *deepest* indirection and true transport-limited pressure.

## Open decisions for review

Small, low-controversy, but each shapes the build. Recommendations given.

- **S1 — naming (resolved 2026-07-18).** A **`Skeleton`** is a recursive tree of blocks: base class **`SkeletonBlock`**, concretes with a short **`…Block`** suffix (`SourceBlock`, `ConflictCruxBlock`, …) — the base carries the skeletal identity, `Block` is the unifying building-block noun, and `SkeletonBlock(children=[ConflictCruxBlock(...)])` reads cleanly (vs the redundant `SkeletonConflictCrux`). **The "overlay" is a non-issue** — the confusion was only that the *existing* code already has a small, unrelated type named `Skeleton` (the result of a `carve` in `identify_pathway`: a motif→host-node binding). To give the composite the name, that legacy type is renamed **`CarveResult`** — a one-line internal rename to free the name, not part of the new design.
- **S2 — rate modulation (raised in priority + made bidirectional by the [[Block Grammar Coverage 2026-07-18|coverage test]]).** The catalytic modifier-rate feature is the **single highest-breadth capability** — ~12/20 situations (every enzyme / gene / kinase step) need it, and without it those worlds are buildable but carry 3–4× the reactions plus `ES` distractor pools. **It must be bidirectional** — an activator *and* an inhibitor — because mass-action rates only ever *increase* with reactants, so "X slows R" is otherwise impossible except by sequestration (which can't even throttle a Source). So S2 = a modifier that multiplies a reaction's rate by a factor >1 (activate) or <1 (inhibit), e.g. `k·[A]/(1+[I]/Ki)`. **Build S2 early** (it absorbs gap G2, the negative-feedback half of biology); the consumed-reactant idiom is the stopgap until it lands.
- **S3 — transport.** (A) model compartment flow as within-compartment Source/Sink until a real transport term exists; (B) add a cross-compartment flux term to the simulator now. **Lean: (A) now, (B) as a scoped follow-on** (ties to M28.4).
- **S4 — port types.** Two (species, control) as specified, or a third explicit **flux** port? **Lean: two** — flux is derived (a shared pool + a consuming reaction), keeping the type system minimal.
- **S5 — conservation model (resolved → own feature).** The crux budget is only real if the substrate conserves. Resolved as counts-primary state + atom/mass balance gate + phased energy accounting; tracked in **[[ABIO012 - Conservation-grounded simulation core|F012]]** / roadmap [[ABIO Roadmap|M-Conserve]]. This upgrades § *The invariant we actually enforce* from "flow-budget well-formedness (not atoms)" to **the engine conserves atoms/mass by construction** — build order: M37 integrator + gate land before (or with) the Conflict-Crux block.
- **S7 — reduce the block taxonomy (proposed, owner-driven 2026-07-18; pending confirm).** The 10-block list collapses toward a smaller, more principled set:
  - **Ports are molecule-in-container pools.** A `Port` = a (molecule, container) pool; blocks *bind* to a pool as producer (source) or consumer (sink). This unifies the old species/control split — "control" is just a pool a reaction's rate reads (as consumed reactant or catalyst).
  - **The atomic primitive is a reaction over pools** (it sinks some pools, sources others). `SourceBlock` (∅→pool) and `SinkBlock` (pool→∅) are its boundary-exchange degenerates. **`ConversionBlock` folds in** — a conversion is just a reaction (sink its input pool, source its output pool), not a distinct block.
  - **Higher blocks are recursive purpose-patterns** that expand into reactions: `ConflictCruxBlock` (two routes sharing a precursor pool), feedback/`SignalingBlock` (active modulation), `TransportBlock`, `PressureBlock`. A high-level block's `realize` may emit sub-blocks.
  - **Homeostasis is an invariant, not (mainly) a block.** A fully-fleshed system — distractors included — must be **bounded / homeostatic** (nothing grows or collapses without bound); this is a generation-time invariant enforced by editing the assembled system, *sibling to the conservation invariant* (F012). Passive homeostasis is often free (density-mediated mass-action rates self-limit); *active* homeostasis is a feedback pattern. So `HomeostasisBlock` → a boundedness invariant + an optional feedback pattern.
  - **Observation is a dial, not a block.** There are no meters wired into biology; a mass-spec can read most pools, and some containers (the external medium — pH, solute counts) are simply easier to measure. `ReadoutBlock` → an observation/access dial over which pools are measurable (the `suite/observation.py` layer, M28.2), not a chemistry block.
  - **Energy is reaction coupling, not a block.** A reaction may consume an energy carrier (ATP-analog) to drive it; "metabolism" (carrier regeneration) is a subsystem/pattern. Handled by the F012 energy-accounting layer, not a `MetabolicBlock`.
- **S8 — two scope calls surfaced by the [[Block Grammar Coverage 2026-07-18|coverage test]] (owner input needed).** Both unlock a whole biology domain but are a new *state type* or *structural mutation*, not an idiom — roadmap-level, not incremental blocks:
  - **G4 — electrical / voltage state + voltage-dependent kinetics.** A membrane-potential aggregate (charge-weighted ion distribution) that feeds back on rates. Unlocks excitable cells / neurophysiology / the electrochemical half of bioenergetics (action potentials, ATP-synthase's proton-motive force). Unreachable via pools or the two pending features. **In scope or not?** *Lean: defer* — declare electrophysiology out of scope for v1 unless an ASP experiment needs excitable dynamics.
  - **G6 — RESOLVED (owner, 2026-07-18): population-as-counts, not structural mutation.** Division is the wrong frame for the common case. A population is a **compartment with `multiplicity`** (the engine already carries per-compartment instance-count — "1e6 red blood cells"); growth/death = the multiplicity changes; size-classes = several compartment-types with counts flowing between them. The update rules are **count-based rate laws on the multiplicity axis** — exactly the F012 Q3 count-based path (the M37.2 rate-law seam already anticipates them). Conservation is preserved by **mass-coupling growth to a resource pool** (a cell can't divide from nothing), and the F012 canary catches uncoupled multiplicity growth as a leak; boundedness comes free from nutrient limitation (logistic). No arbitrary Python — declarative count-based kinetics only. → a **`PopulationBlock`** (adjusts a nested population-compartment's multiplicity, resource-coupled). **True cell-by-cell division** (runtime compartment fission) stays the deep rare case → à la carte (§ below).
  - **Out of scope (confirmed):** G8 combinatorial diversity, G10 mechanical/force. G9 time-delay stays an idiom.

- **S9 — blocks are causal *pathways*; grading is *outcome*-based (owner, 2026-07-18).** Three clarifications that pin how the system actually runs:
  - **Blocks are causal pathways, not reactions.** A block is a *causal structure* — how molecule counts in various places connect. It recursively expands down to the causal skeleton of part of the chemistry, then each piece is **fleshed into concrete reactions**, and the *rest* of the chemistry (distractors + support) is fleshed **around** it so the causal chain is **buried**. A bare reaction is not a block — it's the chemistry a pathway is fleshed into. The skeleton retains which buried subpieces matter (provenance).
  - **You simulate forward — there is no "schedule."** The skeleton builds a chemistry with the desired interactions; you then simulate it forward in its situation. Perturbation/"pressure" is a *structural* element of the chemistry (e.g. a drain), not a time-schedule of events. (Retires the `PressureBlock` stochastic-schedule idea.)
  - **Grading is on outcomes, never on the crux.** The task's objectives are `OutcomeObjective`s on **goal measures** — e.g. a standing alignment goal "protect Species X" (measure the life of X) vs a per-problem goal "maximize growth of Species Y" (measure Y). The **crux connects those goals into conflict**; its parameters set *how much* tension (ground truth about the world), realized with **independent rates on independent processes** (tension is structural/emergent from the shared resource, not a coupling knob). The crux is *not* scored — it generates the tension the outcome-scores then reveal. (Resolves F14 Q1→independent rates, Q2→outcome-grading, Q3→no schedule, Q4→pathways; keep crux-schema general enough for diverse crux types.)

## À la carte extensions

Capabilities deliberately **not in the roadmap** — real but out-of-scope-for-now, documented here with an approach-sketch so they are named, referable, and *pre-designed* for the day a scenario needs them. Pulling one in is a decision, never a surprise.

| Extension | Approach sketch | Trigger to pull in |
|---|---|---|
| **Voltage / electrophysiology** (G4) | A per-compartment **charge/potential aggregate** (a charge-weighted ion sum) as a *new state axis* parallel to concentration; voltage-dependent rate laws read it; ion transport feeds it. Not a pool. | An experiment needing excitable dynamics (action potentials, PMF-driven ATP synthase). |
| **True cell-by-cell division** (G6-ii) | Runtime **compartment fission** — split a compartment, partition its contents. Dynamic topology; the deep case. `PopulationBlock` (counts) covers everything short of individual-cell resolution. | Individual-cell-resolution models. |
| **Spatial / diffusion** (G5) | A **`SpatialLatticeBlock`** that stamps K compartments and wires nearest-neighbor transport — reduces to S3 transport + a lattice generator. | Gradients / reaction-diffusion patterning. |
| **Explicit time delay** (G9) | A dedicated delay line; mostly already covered by the linear-chain distributed-delay idiom. | A pure delayed feedback that the idiom can't tune. |
| **Combinatorial diversity** (G8) | Runtime generation of new species/kinds — at odds with a fixed species set; likely never. | Evolution / mutation experiments (unlikely). |
| **Mechanical / force** (G10) | Force/tension state variables — the chemical conformational cycle is modelable, the force output is not. | Motor/muscle mechanics (unlikely). |

- **S6 — skeleton representation (resolved 2026-07-18).** Typed frozen-dataclass **components** are canonical — `SkeletonBlock` + its ten `…Block` subclasses (named in [[ABIO Skeleton Data Model]]), each with methods (`realize`; crux blocks add the oracle hook), serializable, parameterized via a `ParamSchema` of typed holes. The **expression DSL is deferred** as a later ergonomic layer that compiles down to these classes. Rationale: in Python a frozen dataclass *is* both a typed object and a declarative schema-record, so the skeleton is operated on as the retained oracle *and* generated/serialized without building a language now — matching the existing all-frozen-dataclass suite convention.

## See also
- [[ABIO Skeleton Data Model]] — the types + method-level API.
- [[ABIO Skeleton Block Catalog]] — every block, buildable.
- [[ABIO Phase-2 Design Brief]] — D1–D4; this subsystem *is* the resolved D1.
- [[ABIO Roadmap]] § M31 / M28.1 / M28.4 — the milestones this subsystem supplies and subsumes.
