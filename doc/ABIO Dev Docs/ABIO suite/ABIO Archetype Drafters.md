---
description: "`arch_diagnose` + `arch_intervene` + `arch_predict`: the three M29 generated-truth archetypes, one page because they share one shape — a `draft_*_world` that builds a seeded chain and a hand-made `CarveResult`, a frozen recipe dataclass, and a factory returning the `TaskArchetype`. Diagnose names the perturbed node, predict the response token (`up`/`down`/`same`), intervene drives the sink to a goal. Sources: `src/alienbio/suite/arch_diagnose.py`, `arch_intervene.py`, `arch_predict.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Archetype Drafters](ha://p/ABIO%20Archetype%20Drafters) 
# ABIO Archetype Drafters
The three task families whose ground truth is a generation choice or a simulation, each a chain world, a hand-built binding and a recipe that reads its key off that binding.

![ABIO Archetype Drafters](ABIO%20Archetype%20Drafters.svg) 
*What the key depends on* is the topic behind the three key boxes (‡: the predict key is the same token on every seed).

The three modules are documented together because each has the same three parts: a `draft_*_world(seed, …)` that builds an `n_nodes` chain `m0 → … → m{n−1}` with `m0` at 100 and returns a `CarveResult` constructed by hand (no carve), a frozen `*Recipe` dataclass implementing `ObjectiveRecipe`, and a factory returning the `TaskArchetype`. [ABIO Generative](ABIO%20Generative.md) attaches each drafter to its factory, and the `diagnose`, `predict` and `intervene` heads add the EXP oracles ([ABIO Drafters](ABIO%20Drafters.md)); catalog runs are exp03–exp06 and exp09. The hazard injected into diagnose worlds is [ABIO Hazard](ABIO%20Hazard.md)'s; `perturbed_reaction` and the assay oracle serve [ABIO Faking](ABIO%20Faking.md). The factories and recipes are re-exported from `alienbio.suite`. The design is [ABIO Suite Construction](../../ABIO%20Architecture/ABIO%20Suite%20Construction.md).



## arch_diagnose Interface
Name the perturbed molecule among the candidates.

| arch_diagnose | |
| --- | --- |
| [draft_diagnosis_world](#^draft-diagnosis-world) | Chain, distractors, chosen target |
| [perturbed_reaction](#^perturbed-reaction) | The reaction a perturbation lives on |
| [perturb_reaction_rate](#^perturb-reaction-rate) | Scale one reaction's rate |
| [DiagnosePerturbationRecipe](#^diagnoseperturbationrecipe) | Candidates in, node out |
| [diagnose_perturbation](#^diagnose-perturbation) | The factory |

**draft_diagnosis_world**`(seed, *, n_nodes=4, distractor_count=0, hazard=False, hazard_rate=0.01, perturbation=None) -> (WorldImpl, CarveResult)`
    Chain reactions `r0 …` at the default rate 1.0, distractors `d0 …` at 1.0 with no reactions; the target is `m{1 + seed.child("target") draw over n−1}` — never `m0` on a chain (T091 A2). `hazard` adds `rh: m{n−1} → hz` at `hazard_rate` and records both ids on `added`. `perturbation` multiplies the target's `perturbed_reaction` by that factor; `None` applies `DEFAULT_PERTURBATION = 3.0` (T088), so the answer is in the dynamics (§ [What the key depends on](#what-the-key-depends-on)). With `n_nodes = 1` there is no reaction to perturb. ^draft-diagnosis-world

**perturbed_reaction**`(world, target_id) -> Optional[str]`
    The sorted-first reaction producing the target, else the one consuming it, else `None`. ^perturbed-reaction

**perturb_reaction_rate**`(world, reaction_id, factor) -> WorldImpl`
    Rebuilds that reaction with `mk.R` at `rate · factor`, keeping modifiers, and the world through `rebuild_world` (flows and population laws kept, T088); refuses a non-numeric rate and a reaction carrying a `rate_law` (its `rate` is unused, so scaling it would be inert). ^perturb-reaction-rate

**DiagnosePerturbationRecipe**`(target_role="target", verb="diagnose")`
    Question: every molecule not in `added`, as a `node_set`; key: `Answer(binding["target"], "node_id")`; grader `node_id`. ^diagnoseperturbationrecipe

**diagnose_perturbation**`(*, n_nodes=4, archetype_id=…) -> TaskArchetype`
    One molecule-gated `target` role, no edges, empty features. ^diagnose-perturbation



## arch_predict Interface
Predict the terminal sink's response to speeding the chain's first reaction.

| arch_predict | |
| --- | --- |
| [RESPONSE_TOKENS](#^response-tokens) | `up`, `down`, `same` |
| [draft_prediction_world](#^draft-prediction-world) | Chain with seeded rates |
| [predicted_response](#^predicted-response) | Simulate both, compare the target |
| [PredictResponseRecipe](#^predictresponserecipe) | Lever and target in, token out |
| [predict_response](#^predict-response) | The factory |

**RESPONSE_TOKENS**` = ("up", "down", "same")`
    Carried as `node_id` answers; joined to the render vocabulary as `extra_answer_tokens`. ^response-tokens

**draft_prediction_world**`(seed, *, n_nodes=4, factor=3.0, ill_posed=False) -> (WorldImpl, CarveResult, str)`
    Reactions `m_i_m_{i+1}` at seeded rates in `[0.1, 1.0)`; `ill_posed` sets `m1_m2` to rate 0 (needs `n_nodes ≥ 3`). The perturbed reaction is always `m0_m1`, the target always `m{n−1}`. ^draft-prediction-world

**predicted_response**`(world, target_id, reaction_id, factor, sim_cfg=SimConfig(), seed=Seed(0), *, tol=1e-6) -> str`
    Simulates the world and its `perturb_rate` twin and compares the target's final concentration in the first compartment: `up`, `down`, or `same` within `tol`. ^predicted-response

**PredictResponseRecipe**`(reaction_id, target_id, factor=3.0, verb="predict", sim_cfg=SimConfig(), seed=Seed(0), tol=1e-6)`
    Question: `{reaction_id, target_id}` as a `node_set`; key: `predicted_response(...)`; grader `node_id`. ^predictresponserecipe

**predict_response**`(reaction_id, target_id, factor=3.0, *, sim_cfg, seed, archetype_id) -> TaskArchetype`
    Two gated roles (`perturbed` a reaction, `target` a molecule), no edges. ^predict-response



## arch_intervene Interface
Drive the chain's sink to a goal concentration; outcome-scored.

| arch_intervene | |
| --- | --- |
| [draft_intervention_world](#^draft-intervention-world) | Chain and the goal |
| [target_compartment](#^target-compartment) | The one compartment the target is read in |
| [make_target_scorer](#^make-target-scorer) | Closeness of the final level |
| [make_intervention_objective](#^make-intervention-objective) | Scorer as an objective |
| [DesignInterventionRecipe](#^designinterventionrecipe) | Target in, outcome graded |
| [design_intervention](#^design-intervention) | The factory |

**draft_intervention_world**`(seed, *, n_nodes=4, target_value=None, sim_cfg=SimConfig()) -> (WorldImpl, CarveResult, (str, float))`
    Seeded chain rates; target `m{n−1}`; with no `target_value` the goal is the sink's level at the end of `simulate(world, sim_cfg)`, 20 s by default; the `intervene` head passes the episode-horizon `sim_cfg` (T088, [ABIO Drafters](ABIO%20Drafters.md)). ^draft-intervention-world

**target_compartment**`(world, target_id, named=None) -> str`
    The binding's `compartment` entry when given (it must be a compartment of the world), else the only compartment, else the one compartment whose initial concentrations hold the target; several holders or none refuse at draft, naming the compartments and the `compartment:` binding (T091 E2: a sum over compartments of different volumes is no quantity the task states). `DesignInterventionRecipe.build_objective` calls it. ^target-compartment

**make_target_scorer**`(target_mol_id, target_value, compartment=None) -> Callable[[Timeline], float]`
    `1 / (1 + |final − goal|)` on the final state: the target's concentration in the one compartment `target_compartment` picked. `compartment` unset is allowed only on a one-compartment state; on a multi-compartment state, or a compartment the state does not carry, the scorer raises. ^make-target-scorer

**make_intervention_objective**`(target_mol_id, target_value, compartment=None) -> OutcomeObjective`
    The scorer with `target = target_value`. ^make-intervention-objective

**DesignInterventionRecipe**`(target_value: float, role_name="target", verb="intervene")`
    Question: `{target}` as a `node_set`; key: a scalar placeholder; grader kind `outcome`, so `build_suite` requires the drafter's objective. ^designinterventionrecipe

**design_intervention**`(target_value, *, archetype_id=…) -> TaskArchetype`
    One molecule-gated `target` role. ^design-intervention




# Archetype Drafters Semantics

## What the key depends on
**Diagnose**: the reaction feeding the seed-chosen target runs at `perturbation` (default 3.0, T088) times the chain's 1.0, so every seed drafts its own world and the answer is observable. `m0` is never the target (T091 A2): its only reaction `r0` also feeds `m1`, so the two drew byte-identical worlds and about one trial in four had an unidentifiable answer; every target now perturbs a reaction no other target does. Before T088 the default was label-only — one world for every seed, the answer at chance — and exp04, exp05 and exp04-diagnose-zero ran that way; they were re-pinned at `bf91515`.

**Predict**: the lever is always the chain's throttle and the target always the terminal sink, so speeding the throttle always raises it. Over 40 seeds at `n_nodes = 4` the key was `up` every time, and `same` every time with `ill_posed`. A policy that always answers `up` scores 1.0 on every well-posed trial of exp06.

**Intervene**: the scorer's falloff is in absolute concentration units, so the score depends on the world's scale: 10 units off a goal of 100 reads 0.09, while a do-nothing final of 0 against a goal of 0.5 would read 0.67.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the three sources at alienbio HEAD `64988be`; the identical diagnose worlds and the constant predict keys (40 seeds each arm) confirmed on the HEAD export, the catalog usage by `git grep`, no spend. The module docstring of `arch_intervene` still says the agent loop is out of scope; exp09 runs it through the runner.
- 2026-10-28 — refreshed against `bf91515`: diagnose perturbs by default (`DEFAULT_PERTURBATION = 3.0`), `perturb_reaction_rate` keeps flows and refuses a `rate_law` reaction, the intervene head passes the episode-horizon `sim_cfg`.
- 2026-10-29 — refreshed for `e392c11` and `62fdc9a` (T091 A2, E2): the diagnose target is drawn from `m1 … m{n−1}` (the `m0`/`m1` shared-world note deleted), and the intervene scorer reads one compartment through the new `target_compartment` (`compartment=` on the scorer and objective). A concurrent uncommitted edit adds `task=`/`hint=` keywords to `target_compartment`; not documented until it lands. Figure: the diagnose-key note "m0, m1 share r0" now reads "target never m0".
