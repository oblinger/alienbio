---
description: "Phase 2 of the M36 buildout: turning the 15 pure capability primitives in PR #155 into LIVE capabilities via an agent-loop / scenario runner + the M31 conflict/pressure generators, then M34 mass-trial. Documents the integration architecture and the load-bearing (simulator-binding, agent-loop-shape) design decisions with recommendations, surfaced for owner input rather than committed unsupervised."
---
:>> [[ABIO]] → [[ABIO Design]] → [ABIO Phase-2 Design Brief](ha://p/ABIO%20Phase-2%20Design%20Brief) 
# ABIO Phase-2 Design Brief
The design brief for ABIO Phase 2: the scenario runner, agent interface, trial record and world generators that make the Phase-1 primitives live, and the decisions behind them.

Phase 1 (PR #155, waves 1–5) built **15 pure capability primitives** — the task-family archetypes wired through `build_suite`, the substrate dials (observability, noise), and the measurement + analysis layer (deliberation-trace, surfacing, conflict, blind-spot, failure-mode, info-seeking, calibration, divergence, summary-stats, effect-size, reliability-grid). Every one is a pure function or frozen record over plain inputs, unit-tested to ground truth.

**Related**: [[ABIO]] · [[ABIO Roadmap]] · [[ABIO Experiment Catalog]] · [[ABIO Capability Dimensions]] · [[ABIO Track#^F011|F011]] 

They are **not yet alive**: nothing runs an agent against a world, captures its trace, and feeds the scorers. Phase 2 builds that spine. It is deliberately *not* in PR #155 because it turns on a few **load-bearing decisions** — how a generated world binds to the simulator, and the shape of the agent loop — whose wrong answer would become the substrate every Series-B/C experiment and all M34 trials run on. This brief lays out the architecture and surfaces those decisions with recommendations, so Phase 2 starts from a ratified foundation rather than an unsupervised guess.

## The spine Phase 2 must build

```
SuiteSpec ─build_suite→ Suite(worlds, tasks)
                              │
                    ScenarioRunner (NEW)
       ┌──────────────────────┼───────────────────────────┐
       │ per task:            │                             │
       │  Observation ──→ Agent ──→ Action                  │
       │       ↑              │        │                    │
       │       └── simulate ──┴────────┘  (turn loop,       │
       │           (existing verify.simulate)  budget-capped)│
       │                      │                             │
       │            DeliberationTrace + Timeline + ActionLog │
       └──────────────────────┼───────────────────────────┘
                              │
                 Scorers (PR #155) → TrialRecord
                              │
                 M34 mass-trial: many TrialRecords → stats_summary /
                 effect_size / reliability_grid → reliability map
```

Everything left of "Agent" and right of "Scorers" already exists. Phase 2 is the **ScenarioRunner** (the turn loop), the **Agent interface** (how a decision-maker is plugged in), the **TrialRecord** (what one run emits), and the **generators** (M31) that make worlds worth running.

## Load-bearing decisions (owner input wanted before building)

Each is a fork whose choice becomes foundational. Recommendations given; not committed.

> **Resolved (owner, 2026-07-18).**
> - **D1 — retired as a fork; promoted to a subsystem.** Not A/B/C. Worlds are **composed from typed skeletal building blocks**, each with a *role* and *typed ports*; conflict (finite-precursor, ex-B) and feedstock/compartment-flow (ex-C) are both *blocks in a library*, not competing couplings; **composition + indirection** are what create hard problems. Being designed as its own subsystem, written up for owner review *before* implementation — see **[[ABIO Skeleton Arch]]**. Ground-truth-by-construction must survive composition (mass conservation across every seam; the crux frontier mapped by simulating the *assembled* world). Difficulty = **indirection depth** (control-surface→crux graph distance), which subsumes M28.1's size dial.
> - **D2 — accepted; build early.** A distilled, immutable `TrialRecord` (NOT the raw simulation log — too large) in `suite/trial.py`; `condition_key` a sorted `(dial, level)` tuple so `reliability_grid` bins on it directly.
> - **D3 — lean accepted.** Full observation each turn; fresh immutable `WorldImpl` per turn; agent returns `(action, reasoning_steps)`, runner threads the steps into the `DeliberationTrace`.
> - **D4 — accepted; ScriptedAgent first, LLM second.** `Agent` Protocol + a deterministic **`ScriptedAgent`** driven by a small *declarative step/policy form* (data-defined steps + conditional hooks so it behaves sensibly in stochastic worlds), pure Python. Framework CI is green with `ScriptedAgent` only (no LLM). An **`LLMAgent`** via the existing `LLMOp` seam is a follow-on **second** test layer (LLM-in-the-loop), never the first.

**D1 — How a conflict/pressure generator binds to the simulator (M31.1/M31.2).** EXP-2/EXP-7 need worlds where objectives are forced into tension via a shared limiting precursor with a coupling parameter `κ`. The coupling can be expressed three ways:
- **(A) Rate-multiplier coupling** — `κ` scales the shared reaction's rate so raising V1 throttles V2's supply. *Recommended.* Reuses the existing rate machinery (drafters already vary rates), keeps structure seed-invariant, is the least invasive to the simulator, and is trivially gradable (the drafter knows the Pareto frontier in closed form for the linear case).
- (B) Stoichiometric coupling — the precursor is literally consumed by both routes; tension is mass-conservation. More physically faithful but couples generation to the mass-conservation invariants (C1) and makes the frontier non-closed-form (needs simulation to map).
- (C) Compartment-flow constraint — the precursor is transport-limited across a membrane. Most complex; defers to M28.4 transport machinery.
- **Lean (A)** for M31.1/M31.2; revisit (B) only if an experiment needs strict mass-tension.

**D2 — The `TrialRecord` schema (the M34 unit of observation).** One agent-run against one task must emit a single immutable record the scorers and stats read. Proposed fields: `task_id`, `condition_key` (the dial-vector, opaque), `final_timeline`, `deliberation_trace`, `action_log` (tuple[ActionRecord]), `objective_score` (from the task's grader), plus per-scorer outputs computed lazily. Recommendation: a frozen `TrialRecord` dataclass in a new `suite/trial.py`, `condition_key` a sorted tuple of `(dial_name, level)` pairs so `reliability_grid.aggregate_cells` can bin on it directly. This is low-risk and unblocks M34; **lean: build it early in Phase 2** as the contract the runner and scorers agree on.

**D3 — The agent-loop turn protocol.** The loop is `Observation → Agent.act(obs) → Action → apply → simulate one step → repeat until budget`. Decisions: (a) does the agent see the full `Observation` each turn or a delta; (b) are actions applied to a mutable world copy or a fresh `WorldImpl` per turn (immutability vs cost); (c) how the `DeliberationTrace` is populated — the agent returns `(action, reasoning_steps)` each turn and the runner appends them. Recommendation: full observation each turn (simplest, matches the partial-observability model which already narrows it); fresh immutable `WorldImpl` per turn (consistency > cost at these sizes); agent returns steps the runner threads into the trace. **Lean: as described**; low controversy, flagged for completeness.

**D4 — What plays the "Agent" in the framework's own tests (taint-free determinism).** The framework must be testable without a live LLM. Recommendation: an `Agent` Protocol with two implementations — a **`ScriptedAgent`** (deterministic, seeded, for framework unit/integration tests: it plays a fixed or seed-driven policy) and an **`LLMAgent`** (wraps a real model for actual experiments, via the existing `LLMOp` seam). Framework tests use `ScriptedAgent` exclusively so they stay taint-free and deterministic; `LLMAgent` is exercised only in opt-in experiment runs. **Lean: Protocol + ScriptedAgent first**, LLMAgent as a thin follow-on. This keeps the whole Phase-2 spine CI-green without API calls.

## Phase-2 build sequence (once D1–D4 are settled)

1. **`TrialRecord` + `Agent` Protocol + `ScriptedAgent`** (D2, D4) — the contracts everything else binds to. Pure, testable, no LLM.
2. **`ScenarioRunner`** (D3) — the turn loop producing a `TrialRecord` from `(world, task, agent, dials)`. Integration-tested with `ScriptedAgent` against an existing `build_suite` task end-to-end (the first "live capability" green test).
3. **M31.1 / M31.2 generators** (D1) — conflict-ladder + instrumental-pressure worlds, following the `draft_*_world` pattern, each with a closed-form oracle. Now expressible: EXP-2 and EXP-7 run end-to-end.
4. **M32.1 time-pressure dial** — a budget cap on the runner (turns/steps), graded; trivial once the loop exists.
5. **M34.1 / M34.2 mass-trial** — compose dials, run N seeded trials per condition via the runner, collect `TrialRecord`s, aggregate through `reliability_grid` + `stats_summary` + `effect_size` into a reliability map. This is where the whole stack pays off.
6. **`LLMAgent`** (D4) — wire a real model for actual experiment execution (opt-in, out of CI).

Each step is a coherent PR-sized unit; per the owner's large-PR parameter they accumulate onto one Phase-2 integration branch and open as one PR when substantial.

## Why this is paused here (not built overnight)

The Phase-1 pure-primitive space is exhausted — every remaining capability is either a **generator** (D1, simulator-binding) or **integration** (D2–D4, agent-loop shape). Those choices are load-bearing: they become the substrate all downstream trials run on, so a wrong unsupervised guess would have to be unwound after trials were built on it. Turning them into ratified recommendations here — rather than committing them fast and unsupervised — is the higher-value overnight move. With D1–D4 answered (the recommendations are all low-controversy), Phase 2 is a clean, mostly-mechanical build the same workflow cadence can drive.

## See also
- [[ABIO Experiment Catalog]] — EXP-2 (§ prohibition erosion) and EXP-7 (§ forced tradeoff) are the concrete drivers for the M31 generators; every EXP needs the ScenarioRunner to run.
- [[ABIO Capability Dimensions]] — the 🟡 rows become ✅ when their primitive is consumed by the live runner.
- [[ABIO Roadmap]] § M31 / M32.1 / M34 — the milestones this brief sequences.
