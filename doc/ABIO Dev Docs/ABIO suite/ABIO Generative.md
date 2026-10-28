---
description: "`generative`: M29's three wiring functions — `generative_diagnose`, `generative_predict`, `generative_intervene` take each archetype's bare factory and attach a seed-driven `drafter` (and predict's `up`/`down`/`same` tokens) so `build_suite` can materialize it; the `diagnose`/`predict`/`intervene` experiment drafters call them. Source: `src/alienbio/suite/generative.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Generative](ha://p/ABIO%20Generative) 
# ABIO Generative
The glue that turns the three M29 archetypes, whose ground truth is chosen by a generator rather than carved, into `TaskArchetype`s `build_suite` can draft from a seed.

![ABIO Generative](ABIO%20Generative.svg) 
*The horizon of the goal* is the topic behind the intervene drafter's `sim_cfg` (‡: the goal is the passive reach at `SimConfig()`, 20 s, whatever the episode runs).

`suite/generative.py` reuses each family's bare factory for the recipe and motif (`arch_diagnose.diagnose_perturbation`, `arch_predict.predict_response`, `arch_intervene.design_intervention`) and attaches a `drafter` with `dataclasses.replace`, so each recipe has one source. The drafters it attaches are the families' own `draft_*_world` functions. Its callers are the `diagnose`, `predict` and `intervene` heads in `drafters.py` ([ABIO Drafters](ABIO%20Drafters.md)), which run the archetype through `build_suite` and then add the EXP oracles (hazard, perturbation, ill-posed, intervene). The types are [ABIO Types](ABIO%20Types.md)'s `TaskArchetype`, `CarveResult` and `Objective`. All three functions are re-exported from `alienbio.suite`. The subsystem view is [ABIO Suite Construction](../../ABIO%20Architecture/ABIO%20Suite%20Construction.md).



## generative Interface
Three factories, each returning a `TaskArchetype` with `drafter` set.

| generative | |
| --- | --- |
| [generative_diagnose](#^generative-diagnose) | Diagnose the perturbed molecule |
| [generative_predict](#^generative-predict) | Predict up, down or same |
| [generative_intervene](#^generative-intervene) | Drive the sink to a goal |

**generative_diagnose**`(*, n_nodes=4, distractor_count=3, hazard=False, hazard_rate=DEFAULT_HAZARD_RATE, perturbation=None) -> TaskArchetype`
    The drafter calls `draft_diagnosis_world(seed, …)`, which picks the perturbed molecule per seed and binds it on the skeleton; the recipe reads it there, so one recipe serves every seed. Answer-scored: the drafter returns no objective. ^generative-diagnose

**generative_predict**`(*, n_nodes=4, factor=DEFAULT_FACTOR, ill_posed=False) -> TaskArchetype`
    Fixes the perturbed reaction `m0_m1` and the target `m{n−1}` in the recipe, which is correct only because the drafted structure is seed-invariant; the drafter `assert`s the drafted reaction id equals `m0_m1`. Adds `extra_answer_tokens = ("up", "down", "same")`. Raises `ValueError` for `n_nodes < 2`. ^generative-predict

**generative_intervene**`(*, n_nodes=4, target_value=None, sim_cfg=SimConfig()) -> TaskArchetype`
    The drafter calls `draft_intervention_world(seed, n_nodes, target_value, sim_cfg)` and returns `make_intervention_objective(target_id, goal)`: the goal is a per-world value, so the drafter, not the recipe, builds the outcome objective. The recipe's own `target_value` is a `0.0` placeholder that only feeds the unused answer key. § [The horizon of the goal](#the-horizon-of-the-goal). ^generative-intervene




# Generative Semantics

## Structural invariance
Each drafter varies only rate constants, never the molecule or reaction set, so ids the recipe holds stay valid across seeds. Diagnose chooses its perturbed node per seed but records the choice on the skeleton; predict hard-codes its ids and checks one of them with `assert`, which `python -O` removes.



## The horizon of the goal
With `target_value=None`, `draft_intervention_world` sets the goal to the sink's concentration at the end of `simulate(world, sim_cfg)`. The `intervene` drafter calls `generative_intervene(n_nodes=…)` without `sim_cfg`, so the goal and the `passive` value it stamps on the oracle are read at `SimConfig()`: 200 steps of 0.1 s, 20 s. An episode runs `max_turns × sim_steps × sim_dt` instead; exp09's is 12 turns × 10 steps × 0.1 s, 12 s. On a five-node chain the 20 s reach was 99.99, 86.44 and 98.30 at seeds 9, 10, 11 against 98.93, 57.22 and 83.32 at 12 s, so a do-nothing agent scores 0.48, 0.03 and 0.06 against a goal the oracle calls its own passive reach. `target_margin = 0.2` then lifts a 99.99 goal to 120, above the 100 units the chain holds. The same mismatch on phase 1 was T055's fix (derive on the episode's own horizon).




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be`, the three `draft_*_world` functions and the drafter heads in `drafters.py`; the 20 s versus 12 s reaches measured with `draft_intervention_world` on the HEAD export (seeds 9–11 directly, not through `build_suite`'s child seeds), no spend. Not determined: what an exp09 trial's own seeds give (T088 § suite/generative).
