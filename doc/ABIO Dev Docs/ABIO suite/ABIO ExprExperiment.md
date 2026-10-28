---
description: "`expr_experiment`: layers 3–6 of the Expr head catalog and the experiment-file front end — the pattern, carve and objective heads, `task`, the suite heads, `brief` and `episode` (the brief-side and episode-side dial vectors), `power`, the nine agent heads, the `experiment` head that turns quoted `task`/`brief`/`episode` calls into an `ExperimentSpec`, `load_experiment`, and its inverse `spec_to_text`. Source: `src/alienbio/suite/expr_experiment.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO ExprExperiment](ha://p/ABIO%20ExprExperiment) 
# ABIO ExprExperiment
The page for how an experiment file becomes an `ExperimentSpec`: which heads build tasks and objectives by hand, how the `experiment` head reads its quoted calls so that free names are axes and every other keyword is a fixed dial, how a file is loaded, and how a spec is written back.

![ABIO ExprExperiment](ABIO%20ExprExperiment.svg) 
*Free names are axes* is the topic behind `_split_call`, the one reader of every quoted call; *Writing a spec back* governs the dotted return edge, which quotes every scalar field it writes (‡).

The result of this module is the spec of [ABIO ExperimentSpec](ABIO%20ExperimentSpec.md), built by `spec_from_dict`; the drafter heads a `task:` call names, with their declared dials and guards, are [ABIO Drafters](ABIO%20Drafters.md), and the `AGENTS` registry and live-model factory the agent heads wrap are [ABIO Agents](ABIO%20Agents.md). The heads below layer 3 (blocks, worlds, constructors) are [ABIO ExprHeads](ABIO%20ExprHeads.md); the language, loader and registry are [ABIO Interp](../ABIO%20expr%20Modules/ABIO%20Interp.md), [ABIO YamlTags](../ABIO%20expr%20Modules/ABIO%20YamlTags.md) and [ABIO Registry](../ABIO%20expr%20Modules/ABIO%20Registry.md). `suite/spec.load_spec` decides trust (a file under `catalog/` loads trusted) and calls `load_experiment`. The experiment form as a user writes it is in [ABIO Expr Spec](../../ABIO%20Guides/ABIO%20Expr%20Spec.md); the runtime it feeds is [ABIO Suite Runtime](../../ABIO%20Architecture/ABIO%20Suite%20Runtime.md).



## Objective and task heads
Layer 3. Hand-built tasks: a pattern carved into a host, an objective over it, a task wrapping both. An objective head returns `{question, objective, skeleton}`, which `task` accepts whole.

| Objective and task heads | |
| --- | --- |
| [pattern](#^pattern) | A `Motif`: roles, edges, constraints |
| [carve](#^carve) | Carve a pattern into a host chemistry |
| [identify](#^identify) | Identify-the-pathway objective |
| [diagnose_q](#^diagnose-q) | Diagnose-the-perturbation objective |
| [predict_q](#^predict-q) | Predict-the-response objective |
| [intervene_q](#^intervene-q) | Design-an-intervention objective |
| [grader](#^grader) | A `GraderSpec` |
| [answer](#^answer) | An `AnswerObjective` |
| [question](#^question) | A `Question` |
| [outcome](#^outcome) | An `OutcomeObjective` |
| [task](#^task) | A `TaskInstance` |

**pattern**`(roles: Mapping[str, str], edges=(), constraints=None, params=None) -> Motif` (constructor)
    Refuses empty roles, a constraint or edge naming an unknown role, and an edge that is not `[from, to, relation]`. A constraint is a head name or a callable. ^pattern

**carve**`(host, pattern: Motif, allow_add=True) -> CarveResult`
    Carves into the host's chemistry (a world or a chemistry) under the node's seed; a `CarveFail` becomes an `ExprError` with its reason. ^carve

**identify**`(world, roles, skeleton=None, binding=None, verb="identify")`
    `IdentifyPathwayRecipe` over the roles. With no skeleton, `binding` names the roles directly (`{target: glucose}`); giving both refuses. ^identify

**diagnose_q**`(world, skeleton=None, binding=None, target_role=…, verb="diagnose")`
    `DiagnosePerturbationRecipe`. ^diagnose-q

**predict_q**`(world, reaction_id, target_id, skeleton=None, factor=…, sim=None, verb="predict")`
    `PredictResponseRecipe`: up, down or same by re-simulation under the node's seed. ^predict-q

**intervene_q**`(world, target_value, skeleton=None, binding=None, role=…, verb="intervene")`
    `DesignInterventionRecipe`, outcome-scored. ^intervene-q

**grader**`(kind: str, **config) -> GraderSpec` (constructor)
    The grader kind with its free-form config. ^grader

**answer**`(key, grader: GraderSpec, kind=None) -> AnswerObjective` (constructor)
    Wraps a bare key in an `Answer` of the grader's kind. ^answer

**question**`(structured, kind="json") -> Question` (constructor)
    A question's structured content and its kind. ^question

**outcome**`(scorer, target) -> OutcomeObjective` (constructor)
    `scorer` is a head name or a callable. ^outcome

**task**`(objective, question=None, skeleton=None, archetype="task", world="world0", setup=None) -> TaskInstance` (constructor)
    Unpacks an objective head's pair; refuses an objective that is neither kind and a missing question; an absent skeleton is an empty `CarveResult`. ^task



## Suite heads
Layer 5.

| Suite heads | |
| --- | --- |
| [suite](#^suite) | Build a `Suite` from an archetype or a Dist of them |
| [cover](#^cover) | Partition feature sets into containers |
| [vocabulary](#^vocabulary) | An opaque vocabulary over a world's ids |

**suite**`(tasks, n_tasks=1, distractor_count=0, sim=None, max_redraws=8) -> Suite`
    `build_suite` under the node's seed; `tasks` is a `TaskArchetype` or a Dist over them (a quoted `choice(...)`). ^suite

**cover**`(features, aggressiveness=0.5, admissible=None) -> Cover`
    Each feature is a `FeatureSet` or a mapping of name to predicate (a head name or callable). ^cover

**vocabulary**`(world, extra_tokens=()) -> Vocabulary`
    `build_vocabulary` under the node's seed. ^vocabulary



## Agent-side heads
Layer 6. `brief` and `episode` are dial vectors: evaluated, each returns the mapping of the keywords given; quoted inside an experiment, their keywords are the dials the experiment reads.

| Agent-side heads | |
| --- | --- |
| [brief](#^brief) | The brief-side dials |
| [episode](#^episode) | The episode-side dials |
| [power](#^power) | A `PowerDesign` |
| [idle … pursue_target](#^scripted-agents) | The eight scripted agent heads |
| [llm](#^llm) | A live-model agent factory |
| [agent_registry_name](#^agent-registry-name) | The `AGENTS` key for either spelling |
| [BRIEF_GUARDED](#^brief-guarded) | The brief's guarded dials |

**brief**`(*, constitution, monitoring, framing, observability, observation_noise, stakes, reversibility, irreversible_levers, levers, assays, assay_kill, bury_commitment, constitution_in_history, protocol, probes, monitor_coverage, monitor_sham, monitor_salience, task_note) -> dict`
    Keyword-only, every default `None`; returns the non-`None` keywords. These reach the `TaskBrief` or the observation narrowing, never the drafted world. Declares `guarded_params=BRIEF_GUARDED`. ^brief

**episode**`(*, max_turns, budget, sim_steps, sim_dt, sample_every) -> dict`
    The runner's turn budget and integration parameters, same contract. ^episode

**power**`(target_effect_d, primary_contrast=None, multiple_comparison="none", alpha=0.05, power=0.8) -> PowerDesign` (constructor)
    The statistical design a run commits to. ^power

**idle, measure_commit, survey_commit, heuristic_commit, knockout_commit, act_commit, assay_commit, pursue_target** (agent)
    One head per scripted `AGENTS` entry, named with underscores; each returns the registry builder's factory (scripted builders ignore the spec) and carries `meta["registry_name"]` with the hyphenated key. ^scripted-agents

**llm**`(model=None, memory="full", token_ceiling=None) -> AgentFactory` (agent)
    `llm_agent_factory` after `require_pinned_model`; the same factory the `AGENTS["llm"]` entry builds. Takes no sampling arguments. ^llm

**agent_registry_name**`(name, env=None) -> str`
    `survey-commit` as given, or the `registry_name` of an agent head (`survey_commit`); anything else raises (`ExprError` with an env, `ValueError` without). ^agent-registry-name

**BRIEF_GUARDED**`: frozenset[str]`
    The same object as `drafters.GUARDED_BRIEF_DIALS`, so the head's declaration and the guard's set cannot drift (T066). ^brief-guarded



## Experiment Interface
The experiment head and the front end.

| Experiment | |
| --- | --- |
| [experiment](#^experiment) | Quoted calls, axes and options to an `ExperimentSpec` |
| [SIDE_HEADS](#^side-heads) | `brief`, `episode` |
| [EXPERIMENT_AXES](#^experiment-axes) | Axes the experiment sweeps with no binding |
| [load_experiment](#^load-experiment) | An experiment file to a spec |
| [spec_to_text](#^spec-to-text) | A spec to an experiment file |

**experiment**`(*, name, task, agent, trials_per_condition, base_seed, brief=None, episode=None, axes=None, drafter_kwargs=None, model=None, memory="full", …, registration=None) -> ExperimentSpec` (experiment)
    Refuses an axis whose levels are not a list. Splits `task` against the named drafter's declared dials (it must be a `drafter` head), then `brief` and `episode` against their own (each must be a call of that name); refuses a dial given on two calls and an axis no call reads (factory dials excepted). Maps `agent` and the `agent` axis to registry keys, gathers the optional fields that are set, and returns `spec_from_dict(...)`, whose `ValueError` becomes an `ExprError`. § [Free names are axes](#free-names-are-axes). ^experiment

**SIDE_HEADS**` = ("brief", "episode")`
    The agent-side calls; `spec_to_text` places a dial on one of these before the drafter. ^side-heads

**EXPERIMENT_AXES**` = FACTORY_DIALS`
    `agent`, `model`, `memory`, `compact_at`, `compact_budget`, `history_token_limit`, `max_tokens`, `output_schedule`: read by the agent factory from the trial's dials, so they sweep as plain axes with no free name. ^experiment-axes

**load_experiment**`(path, *, text=None, trusted=False) -> ExperimentSpec`
    Under `Env.standard(seed=0, trusted=...)`: a document that is an `!experiment` call evaluates at `experiment`; a mapping is loaded with `Env.load`, every binding forced, and exactly one must be a spec. Refuses the pre-M47.4 flat form (`drafter:` with no `task:`) naming the new one. ^load-experiment

**spec_to_text**`(spec, *, header="") -> str`
    Writes the `!experiment` form: each fixed dial and swept axis on the call that declares it (brief, then episode, then the drafter), the agent with underscores, the optional fields that differ from their defaults, the idle-baseline flag instead of its added agent level, the design as `!power`. Raises when no head declares a dial. § [Writing a spec back](#writing-a-spec-back). ^spec-to-text




# ExprExperiment Semantics

## Free names are axes
`_split_call` reads one quoted call. It refuses positional arguments and a keyword the head does not declare. A keyword whose value is a bare name listed in `axes` is swept, and must be swept under its own name (`monitoring=monitoring`; `monitoring=m` refuses). A bare name not in `axes` is looked up in the quoted form's scope and becomes a fixed dial with that value, so reusable text bound at the top of the file can be named. Any other value must be a literal; a negated number (`pi=-1.5`, which parses as `op:neg`) is read as the negative literal, and any other nested call or name inside it refuses. A required parameter of the head that is neither fixed nor swept refuses. Which call a dial appears in is what makes it world-side, brief-side or episode-side; the guard does not consult a list.



## Writing a spec back
`spec_to_text` promises `load_experiment(text=spec_to_text(spec)) == spec`. Dials and axes go through `_yaml_literal` and `_yaml_inline`, which quote strings, and so do `name`, `key_readout` and `out_dir` since `64988be` (‡): a spec named `no`, `null` or `a: b` reloads under that name. The agent is written raw (a registry key, always safe). An infinite dial is written `1e999` / `-1e999` (`inf` would read back as a name); a NaN dial has no inline spelling and refuses to render.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `0304b1f` (read with `git show`; `expr_experiment.py` last changed at `01fee6a`). Run against an export of that tree: `exp04.yaml` round-trips through `spec_to_text`; the same spec renamed `no`, `null` and `a: b` reloads named `False`, `None`, and refuses with a YAML error. Findings filed on T088.
- 2026-10-28 — refreshed against 0eb23e5 (`64988be`, `13298f0`): `name`/`key_readout`/`out_dir` are quoted on the way back, infinite dials write `1e999`, NaN refuses, a negative literal dial loads; the figure's dagger follows.
