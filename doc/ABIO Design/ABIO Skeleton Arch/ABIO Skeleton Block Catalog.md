---
description: "The complete enumeration of Skeleton building blocks — role, typed ports, params, emitted fragment, and purpose for each. The buildable catalog behind ABIO Skeleton Architecture."
---
:>> [[ABIO]] → [[ABIO Design]] → [[ABIO Skeleton Arch]] → [ABIO Skeleton Block Catalog](ha://p/ABIO%20Skeleton%20Block%20Catalog) 
# ABIO Skeleton Block Catalog
The complete, buildable enumeration of typed blocks the Skeleton subsystem stacks — one spec per block.

## Overview

Ten typed blocks span the roles the [[ABIO Experiment Catalog]] experiments need: **supply** (Source), **removal** (Sink), **work** (Conversion), **the crux** (Conflict-Crux), **regulation** (Homeostasis), **modulation** (Signaling), **stress** (Environmental-Pressure), **transport** (Compartment-Flow), **latency** (Buffer), and **observation** (Readout). Each is a pure `Block` (see [[ABIO Skeleton Data Model]]) that `build`s a namespaced chemistry fragment of constant-rate mass-action reactions. The minimal set for a forced-tradeoff experiment (EXP-2 / EXP-7) — Source + Conflict-Crux + Environmental-Pressure + Signaling + Homeostasis — is **engine-ready today**; two blocks (Signaling's catalytic variant, Transport) reach further and force the gated engine additions S2/S3.

## Architecture diagram

![[skeleton-blocks.svg|3000]] 

↗ [Clickable](skeleton-blocks.svg) | ✎ [Edit](skeleton-blocks.svg) 

## Catalog at a glance

Column 1 stacks **class / role / key-params**; column 2 stacks **in-ports / out-ports** (`S:` species, `C:` control; `(opt)` = optional). Engine-readiness caveats are in § Notes, not a column.

> ⚠️ **Under revision (2026-07-18)** — owner review is collapsing this list toward a *reaction primitive + recursive patterns + invariants* model (see [[ABIO Skeleton Arch]] § S7). `ConversionBlock` folds into the reaction primitive; `HomeostasisBlock` becomes a system invariant + feedback pattern; `ReadoutBlock` becomes an observation dial. Table below is the pre-revision snapshot; the coverage-driven roster is in the next section.

## Coverage-driven roster (2026-07-18)

Derived from the [[Block Grammar Coverage 2026-07-18]] stress-test (20 biological situations). The **structural bound** that shapes everything: mass-action rates only ever *increase* with reactants, so negative regulation is never a primitive — it needs a modifier (S2, made bidirectional) or a sequestration idiom.

**Primitives** (leaf blocks = one reaction each): `SourceBlock` (∅→pool), `SinkBlock` (pool→∅), and the bare **reaction** (sink inputs, source outputs).

**Recursive pattern blocks** (expand into reactions/sub-blocks):
- `ConflictCruxBlock` ✦ — the crux (two routes on a shared precursor pool).
- `SignalingBlock` — feedback via rate modulation (needs S2; bidirectional).
- `TransportBlock` — cross-compartment flux (needs S3).
- `PressureBlock` — exogenous perturbation on a pool.
- **`EnzymeBlock`** *(new — G1)* — catalysis; hides the `E+S⇌ES→E+P` complex idiom (or a bare modifier once S2 lands).
- **`InhibitionBlock`** *(new — G2)* — negative regulation; a bidirectional-modifier throttle (S2) or competitive-sequestration idiom.
- **`CooperativeBindingBlock`** *(new — G7)* — parameterized Hill/sigmoidal response over multi-step binding.
- **`PopulationBlock`** *(new — G6, resolved)* — population-as-counts: adjusts a nested population-compartment's **`multiplicity`** (instance count) via **count-based rate laws** (per-capita growth/death, size-class transitions), **mass-coupled** to a resource pool so it conserves and self-limits. This is the concrete driver for the F012 Q3 count-based rate-law path.

**Not blocks:** conservation + boundedness (generation invariants, F012); observation (a dial). **À la carte (documented, not roadmap — see [[ABIO Skeleton Arch]] § À la carte extensions):** voltage/electrophysiology (G4), true cell-by-cell division (G6-ii), spatial/diffusion (G5), time-delay (G9). **Out of scope:** runtime species diversity (G8), mechanical force (G10).

| Block · role · params | Ports (in / out) | Purpose |
|---|---|---|
| **`SourceBlock`**<br>SUPPLY<br>`species, base_rate` | in `C:rate` (opt)<br>out `S:supply` | Injects a precursor; constant, or **mediated** when `C:rate` is wired — the feedstock lever. |
| **`SinkBlock`**<br>SINK<br>`rate` | in `S:target`, `C:rate` (opt)<br>out — | Degradation / efflux; mediated = regulated removal. |
| **`ConflictCruxBlock`** ✦<br>CRUX<br>`split_kinetics` | in `S:precursor`<br>out `S:prodA`, `S:prodB` | One precursor feeds two rival routes: raising A starves B. The marked crux. |
| **`SignalingBlock`**<br>SIGNALING<br>`sensitivity, sign` | in `S:sensed`<br>out `C:signal` | Reads a level, emits a control that modulates a downstream rate — the core indirection block. |
| **`PressureBlock`**<br>PRESSURE<br>`magnitude, stochasticity` | in `S:stressed`<br>out — | Exogenous drain / insult / drift that makes the crux *matter*; may be stochastic. |
| **`TransportBlock`**<br>TRANSPORT<br>`permeability` | in `S:sp@c1`, `C:gate` (opt)<br>out `S:sp@c2` | Flux across a membrane; mediated (gated) = the mediated-flow crux input. |
| **`BufferBlock`**<br>BUFFER<br>`capacity` | in/out `S:pool` | A large pool that damps dynamics — pure latency / indirection. |

### Notes
- **`SignalingBlock`** — the catalytic (non-consumed) rate-modulation variant needs the S2 simulator term; the consumed-reactant variant is engine-ready today.
- **`TransportBlock`** — the true cross-compartment flux needs the S3 simulator term; modelled as a Source/Sink pair within one compartment until then.
- **Folded / removed under revision:** `ConversionBlock` (→ the reaction primitive), `HomeostasisBlock` (→ boundedness invariant + feedback pattern), `ReadoutBlock` (→ observation dial). See § S7.

## Per-block specifications

Each block below lists what its `realize(params, seed, ns)` emits into the fragment. All reactions are constant mass-action. Each `### ` heading leads with the concrete class name.

### `SourceBlock` — Source / Feedstock (SUPPLY)
- **Emits:** a supply molecule `supply`; a zero-reactant production reaction `∅ → supply @ base_rate` (a bounded influx). Mediated variant: the reaction's *effective* rate is gated by a wired `C:rate` modulating species.
- **Purpose:** the only inflow of a shared precursor — this is what makes the crux budget analytic (total supply is the sum of Source rates). Often exposed as an agent lever.

### `SinkBlock` — Sink / Drain (SINK)
- **Emits:** a consuming reaction `target → ∅ @ rate`. Mediated variant gated by `C:rate`.
- **Purpose:** balances a pool; a regulated sink is a homeostatic actuator or an env-pressure efflux.

### `ConversionBlock` — Conversion / Pathway (CONVERSION)
- **Emits:** a chain of `chain_len` reactions `in → x1 → … → out`, each constant-rate.
- **Purpose:** the "work being done"; each hop is a step of indirection between a lever and the crux.

### `ConflictCruxBlock` ✦ — Conflict-Crux (CRUX)
- **Emits:** a shared `precursor` pool and two competing routes `precursor → prodA` and `precursor → prodB` with `split_kinetics`. Marked as the skeleton crux.
- **Purpose:** the real finite-resource tension (the D1 decision): the Pareto frontier between prodA and prodB is what the task grades. Budget guaranteed by construction (single precursor, bounded Source inflow); exact frontier mapped by `oracle()` simulation.

### `HomeostasisBlock` — Homeostasis (HOMEOSTASIS)
- **Emits:** a `regulated` species plus a negative-feedback loop (a production and a sink whose balance restores a setpoint after perturbation), tuned by `gain`. Optional `C:setpoint` shifts the target.
- **Purpose:** buffers a signal so downstream effects are indirect and delayed; the agent must infer the loop to move the crux. A primary indirection source.

### `SignalingBlock` — Signaling / Transducer (SIGNALING)
- **Emits (engine-ready, S2-A):** a reaction in which the `sensed` species participates as a **consumed reactant** in the target reaction, so its abundance gates the rate by mass-action (the signal depletes as it acts).
- **Emits (S2-B, gated):** a **catalytic** modifier — `sensed` attached as a non-consumed modifier that scales the target rate. Requires confirming/adding modifier-rate physics in the simulator.
- **Purpose:** converts a state reading into a rate modulation — the mechanism behind *mediated flow* and the deepest indirection.

### `PressureBlock` — Environmental-Pressure (PRESSURE)
- **Emits:** an exogenous drain / periodic insult / boundary drift on `stressed`. Stochastic variant draws its schedule from `seed.child(ns)` (still reproducible).
- **Purpose:** makes regulation and the crux consequential; a stochastic pressure is what the `ScriptedAgent`'s conditional policy is tested against.

### `TransportBlock` — Transport / Compartment-Flow (TRANSPORT)
- **Emits (interim, S3-A):** within one compartment, a Source/Sink pair approximating net flow. **True form (S3-B, gated):** a cross-compartment flux term `sp@c1 ⇌ sp@c2` limited by `permeability`; optional `C:gate` makes it mediated. Requires a simulator addition (reactions never cross compartments today).
- **Purpose:** transport-limited pressure; the mediated (gated) variant is the owner's "mediated flow" crux input.

### `BufferBlock` — Buffer / Reservoir (BUFFER)
- **Emits:** a large-capacity pool coupled to `pool` by fast bidirectional exchange, damping fluctuations.
- **Purpose:** adds latency/inertia; increases effective indirection depth without new topology. May fold into Homeostasis (S-open).

### `ReadoutBlock` — Readout / Sensor (READOUT)
- **Emits:** no mass — a boundary annotation marking `x` observable, optionally with measurement `noise`.
- **Purpose:** defines the agent's observation surface; the hook into `suite/observation.py` (partial observability M28.2 + noise M28.3).

## See also
- [[ABIO Skeleton Arch]] — subsystem overview, materialization, invariant, open decisions S1–S6.
- [[ABIO Skeleton Data Model]] — the `SkeletonBlock`/`Port`/`Wire` types these instantiate.
- [[ABIO Experiment Catalog]] — EXP-2 / EXP-7 are the drivers for the minimal block set.
