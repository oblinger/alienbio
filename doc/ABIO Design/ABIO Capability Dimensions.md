---
description: "The dimensions of generality and capability the Alien Biology framework must provide, harvested from the ASP experiment catalog. A capability inventory (NOT an experiment plan) — the spine that drives the roadmap's forward milestones (M27+)."
---
:>> [[ABIO]] → [[ABIO Design]] → [ABIO Capability Dimensions](ha://p/ABIO%20Capability%20Dimensions) 
# ABIO Capability Dimensions
**What this is.** The framework's end-goal (see [[ABIO Roadmap]] § Meta-Thesis) is to be a **taint-free, generative, parameterized testing framework** whose worlds and tasks cover long reasoning chains and multi-turn settings under partial observability and partial understanding — general enough to *execute the kinds of experiments described in [[AUP]]* (Series A: Deliberative Coherence; Series B: Driver Conflicts; Series C: Modulating Factors).

**Related**: [[ABIO]] · [[ABIO Roadmap]] · [[AUP]] · [[ABIO Suite Construction]] 

This document enumerates the **capability dimensions** those experiments require of the framework. It is a **capability inventory, not an experiment design** — each entry is something the framework must be able to *do* or *dial*, harvested by reading the ASP series for what they presuppose. The roadmap's forward milestones (M27–M35) build these; the list is the source of truth those milestones reference.

**Reading the list.** Each entry is `**Dimension** — what it is; why it's needed; ASP driver(s); status.` Status: ✅ built · 🟡 partial · ⬜ to build · 🔮 future/out-of-near-term.

## A. Core substrate dimensions

The world/simulation the framework provides. Largely delivered by M1–M26.

- **Molecular simulation engine** — concentrations, bidirectional reactions, transport/diffusion, predation, operating envelopes, population dynamics with graduated→irreversible-death effects. The physics every task runs on. Driver: X2, all. ✅ (M1, M6–M9, M13/M24).
- **Parameterized world generation from spec** — regions, species, molecules, reactions, initial conditions, feedstock, all from a YAML/generator spec. Driver: X2, all. ✅ (M2 generator, M19 build system).
- **Region isolation + per-molecule permeability** — controlled local experiments; wall a region off, tune what crosses. Driver: X2; C1 local-testing; B-series conflict staging. ✅ (M9 multi-compartment).
- **Partial-observability sensing model** — a split between cheap direct observables (sample substrate/species, sensors, population counts) and investigation-gated hidden structure (pathways, interdependencies, causal chains), where sampling costs organisms/budget. Driver: X2, A1, C1, all. 🟡 (M7 measurements/actions + M1.14 observation; the *investigation-gated hidden-structure* half needs hardening — see [[#B. Generation & control-knob dimensions]] rows on observability).
- **Action execution with reversibility semantics** — an explicit reversible (env-control, isolation) vs. irreversible (feedstock, death, cascade) split on the action set. Driver: X2, C2, C1, all. 🟡 (actions exist M7; the reversibility *tagging + scoring hook* needs to be first-class — see Stakes/Reversibility dial).

## B. Generation & control-knob dimensions

What the framework can generate, inject, and dial. The bulk of the forward roadmap — **each knob must be independently parameterizable and jointly samplable** (the M34 composability requirement).

- **Taint-free / guaranteed-novel generation** — scenarios provably absent from training data, so a general LLM prior is useless and the agent *must* experiment. Driver: X1, A1, C1, all. 🟡 (procedural generation exists; the *guaranteed-novelty property* wants an explicit invariant/test).
- **Asymmetric knowledge + ground-truth oracle** — the framework holds the true world (mechanisms, hidden structure, correct answers) that the agent does not; every scorer reads from it. Driver: X1, A3, C1, all scoring. 🟡 (ground truth held by construction via M26 verify; a first-class *oracle interface* for scoring wants formalizing).
- **Controllable-complexity dial** — a systematic difficulty control. **First axis = network size / complexity** (Q4); later axes = observability, noise/stochasticity, compartment/transport structure. Driver: X1, A2, all. 🟡 (network-size ✅ M28.1; **observability + noise primitives built** — `suite/observation.py`, wave 2 — as pure projection/hiding/noise functions; wiring them as `build_suite` dials pending).
- **Constitution / objective injection** — supply explicit objectives, prohibitions, and priority orderings to the agent per scenario (the `Observation.constitution` seam). Driver: A1, A2, A3, all B, C1, C2. 🟡 (field exists in the observation; the *injection + catalog* is to build).
- **Objective instrumentation by required reasoning depth** — objectives tagged immediate / one-step / multi-step / deep, with controllable objective complexity, so depth-of-deliberation is a measurable variable. Driver: A2, A1. ⬜.
- **Objective-type taxonomy generation** — procedural / substantive / meta-level, ± duties, abstract / concrete — with scenarios where each type is clearly relevant. Driver: A3. ⬜.
- **Multi-objective conflict engineering** — worlds that *force* objective-vs-objective tension, over a conflict-structure ladder (single → compatible → latent-tension → explicit forced-tradeoff), with framing and intensity variation. Driver: B1. ⬜.
- **Emergent-instrumental-pressure worlds** — instrumental sub-goals that arise from task structure and erode an explicit prohibition, requiring **designable cross-species pathway overlap**, over a graded pressure dial (none → task-impossible-without-violation). Driver: B2. ⬜.
- **Fixed-model / vary-world harness (Delta Principle)** — hold the base model fixed and vary the *world* to match/mismatch trained dispositions; measure baseline disposition first, then override under constitutional pressure. Driver: B3, and the general design of B/C. ⬜.
- **Environmental-pressure injection library** — resource scarcity, implicit user expectation, competitive/time dynamics, feedback signals, social-proof framing — over an intensity/persistence ladder (none → compounding multi-type), explicit vs. implicit, and *removable* (to test recovery). Driver: B4. ⬜.
- **Hidden inter-species interdependency generation** — typed relationships (symbiosis / competition / indirect multi-step chain / shared resource / mutual support) with tunable strength. Driver: C1. 🟡 (hidden reactions exist H5; the *typed, tunable interdependency generator* is to build).
- **Epistemic-accessibility control** — how much investigation is required to discover hidden structure (easy → moderate → difficult → hidden). Driver: C1. ⬜.
- **Independent stakes dial + reversibility dial** — consequence magnitude and irreversibility as two *independent* knobs over the same decision structure (a factorial), so caution-scaling can be measured cleanly. Driver: C2; modulates C1. ⬜.
- **Deliberation-budget / time-pressure control** — token caps, turn limits, reflection prompts, urgency signals, deadlines, investigation opportunity-cost — over a graded ladder (unlimited → minimal). Driver: A2, A3 (unlimited regime), C3. 🟡 (budget/cost machinery exists M1.14; graded *time-pressure knobs* to build).
- **Monitoring / observability-signal injection** — a belief-vs-reality split (explicit / implicit / apparent-absence / *deceptive* — appears unobserved but is logged), plus "this is a test" vs. "this is real" framing. Driver: C4; A1 faking mode. ⬜.
- **User-preference / sycophancy injection** — inject a user preference that may pull against the objective. Driver: A1; overlaps B4 implicit-expectation. ⬜.
- **Explicit-hint / framing-variation controls** — same conflict reworded; "there may be hidden relationships"; values- vs. rules-framing — as control conditions isolating framing effects. Driver: B1, C1, C4, B4. ⬜.
- **Iterative multi-generation alignment-adjustment loop** — a system that adapts itself or trains a successor, with initial-condition variation and cross-generation tracking. Driver: Direction-3 (Fixed Points / Trajectory / Attractors / Perturbation). 🔮 future.

## C. Measurement & scoring dimensions

What the framework can measure off the ground-truth oracle — automatically, at scale.

- **Deliberation-trace capture** — record the agent's reasoning chain for downstream analysis. Driver: A1, A2, A3, B3, C3, C4. 🟡 (neutral capture data model **built** — `suite/deliberation.py` `DeliberationStep`/`DeliberationTrace`, wave 3, the second-wave keystone the reasoning-level scorers read; wiring capture into the actual agent loop pending).
- **Ground-truth behavioral-alignment scoring** — score action vs. what reasoning-from-objectives *should* conclude, and outcome vs. ideal-given-full-info. Driver: A1, all. 🟡 (M26.5 graders: Jaccard / LCP / tolerance / deep-eq + opaque outcome scorer; behavioral-alignment scorers to build atop).
- **Failure-mode classification** — relevance misrecognition / motivated reasoning / CoT unfaithfulness / alignment faking / sycophancy. Driver: A1. 🟡 (rule-based classifier **built** — `suite/score_failuremode.py` `classify_failure_modes`/`primary_failure_mode` over a `FailureSignals` record, wave 4; deriving the signals from a real trace pending).
- **Per-objective surfacing detection + convergence** — which objective appeared at which deliberation depth; time/tokens to first surfacing; convergence across budget sweeps. Driver: A2, A3. 🟡 (scorer **built** — `suite/score_surfacing.py` `surfacing_depth`/`surfacing_profile`/`coverage_at_budget`/`is_monotone_coverage`, wave 3; feeding it real trace events pending).
- **Blind-spot external verification** — a "should-have-considered" oracle (external, not self-report) + training-data-characteristic correlation. Driver: A3. 🟡 (set-based scorer **built** — `suite/score_blindspot.py` `missed`/`spurious_considerations`, `blindspot_rate`, `consideration_coverage`, wave 4; the oracle that supplies the should-set is per-experiment, pending).
- **Conflict-resolution scoring** — which driver dominates, precedence consistency across scenarios, explicit-recognition detection, endorsement match. Driver: B1, B2, B3, B4. 🟡 (scorer **built** — `suite/score_conflict.py` `dominant_objective`/`favors`/`precedence_consistency`/`pareto_distance`, wave 3; the conflict-engineering generators that produce the scenarios pending, M31.1).
- **Threshold / erosion + recovery measurement** — the pressure level where fidelity breaks, and whether behavior recovers (or drifts) after pressure is removed. Driver: B2, B4, C3. ⬜.
- **Calibration measurement** — caution scaling ∝ uncertainty × stakes × irreversibility; info-seeking / investigation-rate scoring; "I don't know" vs. "no relationship" discrimination. Driver: C1, C2. 🟡 (scorers **built** — `suite/score_calibration.py` Brier/ECE (wave 2) + `suite/info_seeking.py` investigation-rate/destructiveness/actions-before-commit (wave 4); the caution∝uncertainty×stakes×irreversibility regression over trials pending, M34).
- **Degradation-pattern detection** — reasoning shortcuts, default reversion, scope narrowing, confidence inflation, investigation abandonment, budget self-awareness — under pressure. Driver: C3. ⬜.
- **Paired-condition divergence measurement** — behavioral divergence across matched conditions (monitored vs. unmonitored; faking vs. sandbagging; strategic vs. emergent). Driver: C4, C2, C3. 🟡 (divergence scorer **built** — `suite/score_divergence.py` `final_state_distance`/`normalized_divergence`, wave 2; running the matched paired conditions and diffing them pending, M34).
- **Trajectory / attractor / perturbation analysis** — convergence, attractor detection (e.g. power-aggregation pulls), cross-generation sensitivity. Driver: Direction-3. 🔮 future.

## Integrative end-state

- **Mass-trial automation + cross-dimensional reliability map** — the payoff and the true far end. The framework must not just run each capability in isolation but **compose the knobs** (conflict-type × uncertainty, time-pressure × stakes, blind-spots × conflict-type, observability × conflict-type, …), run hundreds–thousands of trials per condition against the ground-truth oracle, and aggregate into a **reliability map** with interaction-effect detection and statistical power. Every generation knob in § B must be independently parameterizable and jointly samplable; every scorer in § C must run automatically at scale. Driver: ASP §5.4 / §6.4 cross-dimensional analysis. ⬜ (M34 — the integrative end-state).

## Test matrix (generated)

**Generated by `bio test-matrix --markdown` (roadmap M48.1) — never hand-edited.** The status column is the test list's: ✅ built and proven by the named `tests/capabilities/` test, 🟡 partial (the primitive exists, its end-to-end wiring does not), ⬜ planned, 🔮 future; ❌ would be a built dimension nobody proves, which `bio test-matrix --check` (and CI) refuses. The glyphs on the entries above are the design-time reading; this table is the ground truth.

| Id | Dimension | Status | Proven by |
|---|---|---|---|
| A1 | Molecular simulation engine | ✅ built | `test_a_substrate::test_a1_engine_runs_reactions_modulations_and_compiled_rate_laws_on_both_simulators` |
| A2 | Parameterized world generation from spec | ✅ built | `test_a_substrate::test_a2_a_world_is_generated_from_a_spec_file` |
| A3 | Region isolation + per-molecule permeability | ✅ built | `test_a_substrate::test_a3_transport_between_compartments_moves_a_pool_and_only_that_pool` |
| A4 | Partial-observability sensing model | ✅ built | `test_a_substrate::test_a4_observability_and_noise_dials_narrow_what_the_agent_sees` |
| A5 | Action execution with reversibility semantics | ✅ built | `test_a_substrate::test_a5_levers_carry_reversibility_and_a_destructive_act_is_logged_as_such` |
| B1 | Taint-free / guaranteed-novel generation | ✅ built | `test_b_generation::test_b1_the_brief_never_carries_the_key_and_a_live_model_is_refused_where_it_could_peek` |
| B2 | Asymmetric knowledge + ground-truth oracle | ✅ built | `test_b_generation::test_b2_every_record_carries_the_ground_truth_oracle_the_agent_never_sees` |
| B3 | Controllable-complexity dial | ✅ built | `test_b_generation::test_b3_the_complexity_dial_changes_the_world_and_nothing_else` |
| B4 | Constitution / objective injection | ✅ built | `test_b_generation::test_b4_the_constitution_reaches_the_brief_verbatim` |
| B5 | Objective instrumentation by required reasoning depth | ✅ built | `test_b_generation::test_b5_objectives_are_instrumented_by_reasoning_depth` |
| B6 | Objective-type taxonomy generation | ✅ built | `test_b_generation::test_b6_objective_types_are_generated_and_the_ill_posed_trap_is_a_matched_variant` |
| B7 | Multi-objective conflict engineering | ✅ built | `test_b_generation::test_b7_the_conflict_ladder_forces_a_tradeoff_only_at_the_forced_rung` |
| B8 | Emergent-instrumental-pressure worlds | ✅ built | `test_b_generation::test_b8_the_pressure_dial_moves_the_byproduct_monotonically` |
| B9 | Fixed-model / vary-world harness (Delta) | ✅ built | `test_b_generation::test_b9_the_delta_pair_shares_one_seed_and_differs_on_the_rewired_edge` |
| B10 | Environmental-pressure injection library | ✅ built | `test_b_generation::test_b10_environmental_pressure_is_injectable_graded_and_removable` |
| B11 | Hidden inter-species interdependency generation | ✅ built | `test_b_generation::test_b11_a_hidden_interdependency_is_generated_with_tunable_strength` |
| B12 | Epistemic-accessibility control | ✅ built | `test_b_generation::test_b12_epistemic_accessibility_is_the_hidden_set_held_per_trial` |
| B13 | Independent stakes dial + reversibility dial | ✅ built | `test_b_generation::test_b13_stakes_and_reversibility_are_independent_dials_on_the_brief` |
| B14 | Deliberation-budget / time-pressure control | ✅ built | `test_b_generation::test_b14_the_budget_ladder_starves_the_survey_at_the_tight_rung` |
| B15 | Monitoring / observability-signal injection | ✅ built | `test_b_generation::test_b15_monitoring_belief_and_reality_are_set_independently` |
| B16 | User-preference / sycophancy injection | ⬜ planned | — |
| B17 | Explicit-hint / framing-variation controls | ✅ built | `test_b_generation::test_b17_framing_presets_and_free_text_rewrite_the_briefing_only` |
| B18 | Iterative multi-generation alignment-adjustment loop | 🔮 future | — |
| C1 | Deliberation-trace capture | ✅ built | `test_c_measurement::test_c1_the_deliberation_trace_is_captured_per_turn` |
| C2 | Ground-truth behavioral-alignment scoring | ✅ built | `test_c_measurement::test_c2_the_committed_answer_is_scored_against_the_ground_truth_key` |
| C3 | Failure-mode classification | 🟡 partial | `test_c_measurement::test_c3_failure_modes_classify_from_signals` |
| C4 | Per-objective surfacing detection + convergence | ✅ built | `test_c_measurement::test_c4_surfacing_turn_and_depth_profile_are_read_off_records` |
| C5 | Blind-spot external verification | ✅ built | `test_c_measurement::test_c5_blind_spots_are_scored_against_an_external_should_have_considered_set` |
| C6 | Conflict-resolution scoring | ✅ built | `test_c_measurement::test_c6_conflict_resolution_is_scored_and_precedence_read_across_the_ladder` |
| C7 | Threshold / erosion + recovery measurement | 🟡 partial | `test_c_measurement::test_c7_threshold_and_recovery_are_measured_from_the_dose_and_pressure_reads` |
| C8 | Calibration measurement | ✅ built | `test_c_measurement::test_c8_caution_is_measured_and_compared_to_the_calibrated_expectation` |
| C9 | Degradation-pattern detection | ✅ built | `test_c_measurement::test_c9_degradation_patterns_are_read_down_the_ladder` |
| C10 | Paired-condition divergence measurement | ✅ built | `test_c_measurement::test_c10_matched_arms_are_paired_and_their_divergence_measured` |
| C11 | Trajectory / attractor / perturbation analysis | 🔮 future | — |
| I1 | Mass-trial automation + cross-dimensional reliability map | ✅ built | `test_i_integrative::test_i1_a_two_axis_sweep_yields_cells_interactions_contrasts_and_idle_baselines` |

## Notes on scope

- These are **framework capabilities**, not experiments. Building the "constitution-injection" knob is in scope; designing the A1 experiment that uses it is *not* (that is ASP's job, done later).
- The list is harvested from ASP as of 2026-07-12. Under-specified ASP items (Direction-3 fixed-point experiments; a "Genuine Deliberation" probe; a "Specification Sensitivity" experiment) imply the 🔮 rows and are tracked in [[ABIO Roadmap]] § Yet to be added.
- The entry glyphs were written at harvest time (M1–M26 complete); § Test matrix is generated from the tests and is the current status.
