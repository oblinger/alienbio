---
description: "`agents`: the agent registry an experiment names — `AGENTS` (eight scripted control agents and `llm`), `AgentFactoryBuilder`, the scripted policies (`idle`, `measure-commit`, `survey-commit`, `heuristic-commit`, `knockout-commit`, `act-commit`, `assay-commit`, `pursue-target`), `llm_agent_factory` (the one real-model factory both the spec path and the Expr `llm` head build through), and `_agent_factory_for`, which resolves the agent per trial so `agent` and `model` sweep as axes. Source: `src/alienbio/suite/agents.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Agents](ha://p/ABIO%20Agents) 
# ABIO Agents
The page for how an experiment's `agent` becomes an agent in a trial: the registry of named builders, what each scripted control does turn by turn, how the live-model factory reads the spec and the trial's dials, and how one grid can mix agents over the same worlds.

![ABIO Agents](ABIO%20Agents.svg) 
*Agents as axes* is the topic behind `_agent_factory_for` (the agent kind is read per trial, the builder once per kind); *The scripted controls* governs the eight policy boxes, each an extreme an instrument must expose.

`agents.py` was split out of `experiment.py` (T058), which re-exports it. The `Agent` protocol, `ScriptedAgent` and the action types are [ABIO Agent](ABIO%20Agent.md); the real-model agent the `llm` entry builds, its memory and forgetting triggers, is [ABIO LLMAgent](ABIO%20LLMAgent.md); the brief a stateful agent reads in `begin` is [ABIO TaskBrief](ABIO%20TaskBrief.md); the runner that calls `begin`/`act`/`notice` is [ABIO Runner](ABIO%20Runner.md); the grid that calls the per-trial factory is [ABIO MassTrialRunner](ABIO%20MassTrialRunner.md). The Expr agent heads (`survey_commit`, `llm`, …) that name these entries are in [ABIO ExprExperiment](ABIO%20ExprExperiment.md); `FACTORY_DIALS`, the dials a factory reads, is in [ABIO Drafters](ABIO%20Drafters.md).



## agents Interface
The registry, the live-model factory and the per-trial resolver.

| agents | |
| --- | --- |
| [AgentFactoryBuilder](#^agentfactorybuilder) | `(spec) -> AgentFactory` |
| [AGENTS](#^agents) | Name to builder |
| [AGENT_DIALS](#^agent-dials) | The factory dials each kind reads |
| [llm_agent_factory](#^llm-agent-factory) | The one real-model factory |
| [_agent_factory_for](#^agent-factory-for) | The per-trial factory for a spec |
| [ACT_VALUE](#^act-value) | `act-commit`'s intervention value |
| [PURSUE_RATE](#^pursue-rate) | `pursue-target`'s lever setting |

**AgentFactoryBuilder** (Protocol)`(spec: ExperimentSpec) -> AgentFactory`
    Resolves the spec's own fields once and returns the per-trial `(seed, dials) -> Agent`. ^agentfactorybuilder

**AGENTS**`: Mapping[str, AgentFactoryBuilder]`
    `idle`, `measure-commit`, `survey-commit`, `heuristic-commit`, `knockout-commit`, `act-commit`, `assay-commit`, `pursue-target` (each a builder that ignores the spec) and `llm`. The keys are the hyphenated names a spec stores; the Expr heads use underscores. ^agents

**AGENT_DIALS**`: Mapping[str, frozenset[str]]`
    The factory dials (`drafters.FACTORY_DIALS` less `agent`) each kind reads off its trial's dials: only `llm`, which reads `model`, `memory`, `compact_at`, `compact_budget`, `history_token_limit`, `max_tokens` and `output_schedule`. A kind absent here reads none. `guards.inert_arm_violation` refuses an axis over one of these dials when no agent kind in the grid reads it (T091 B11). ^agent-dials

**llm_agent_factory**`(*, model, temperature=None, top_p=None, memory="full", token_ceiling=None, compact_at=None, compact_budget=None, history_token_limit=None, max_tokens=None, output_schedule=None) -> AgentFactory`
    The returned factory, per trial: picks `dials["model"]`, else `model`, else `PINNED_MODEL`, and refuses an unpinned one; builds one `UsageMeter` shared by the provider function and the agent; returns an `LLMAgent` whose `memory`, `compact_at`, `compact_budget`, `history_token_limit`, `max_tokens` and `output_schedule` are the trial's dial when present, else the argument. `temperature`, `top_p` and `token_ceiling` come from the arguments only. `LLMAgent` and the provider are imported inside the factory, so naming `llm` fails only when a trial is about to run without a key. ^llm-agent-factory

**_agent_factory_for**`(spec: ExperimentSpec) -> AgentFactory`
    Per trial: the kind is `dials["agent"]` when swept, else `spec.agent`; an unknown kind raises `ValueError`; the builder is resolved once per kind and cached for the grid. § [Agents as axes](#agents-as-axes). ^agent-factory-for

**ACT_VALUE**` = 10.0`
    The setpoint `act-commit` writes. ^act-value

**PURSUE_RATE**` = 10.0`
    The setting `pursue-target` pulls every declared lever to, AUP's own "pull hard" probe value. ^pursue-rate




# Agents Semantics

## The scripted controls
Zero model calls and deterministic. Each commits `Answer(value=[], kind="json")`, an empty sentinel that grades 0 under every answer kind without raising, unless its rule says otherwise. The stateful ones read the brief in `begin`.

| Agent | Turn 0 | After |
| --- | --- | --- |
| `idle` | `Wait` | `Wait`, forever: the do-nothing baseline (M45.7) |
| `measure-commit` | measure the first visible probe | commit the sentinel |
| `survey-commit` | measure each visible probe once, sorted, one per turn | commit the sentinel; the scripted zero for hazard surfacing (M36.1) |
| `heuristic-commit` | measure the first candidate (the brief's question when it is a set, else every visible probe) | commit the candidate with the largest summed reading: right on the matched arm, wrong on the mismatched (M36.6) |
| `knockout-commit` | `Intervene` the first declared irreversible lever to 0, or measure once if none | commit the sentinel: the incautious extreme (M36.7) |
| `act-commit` | `Intervene` the first declared lever to `ACT_VALUE` | commit the sentinel; destructive or not by the reversibility tag alone (M36.8) |
| `assay-commit` | run the destructive assay on the first assayable reaction, or measure once if none | commit the sentinel: the tempted extreme (M36.10) |
| `pursue-target` | pull the next declared lever to `PURSUE_RATE` | keep cycling the levers until the target reads at or above the goal, then commit; wait when no lever is declared (M45.20) |

`pursue-target` never reads the side-product, which makes it the feasibility test for an aligned agent at `pi = 0`, the upper bound every live curve is read against, and the engagement reference for the census. Its stop rule reads the target summed over every compartment that shows it, the reading the dose readout scores (`dose._final_value`).



## Agents as axes
`agent` and `model` are factory dials: a spec may sweep them, and because they are world-invariant, every arm shares the world seeds — a scripted control and a live model see the same worlds by construction (M46.8). The builder for each kind is created on the kind's first trial and reused, so the spec-level `llm` settings (temperature, token ceiling) are fixed for the grid while the trial-level dials (model, memory, forgetting, output budget) vary per trial. The scripted builders discard their dials.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `721500f` (read with `git show`; `agents.py` last changed at `01fee6a`, after the T066 memory-axis fix). No run; the behaviours are read from the policies. Findings filed on T088.
- 2026-10-28 — refreshed against 0eb23e5: `pursue-target`'s stop rule sums the target over compartments (`64988be`).
- 2026-10-29 — refreshed for `e5ea4d0` (T091 B11): `AGENT_DIALS` declares which factory dials each kind reads (only `llm`), read by the `inert-arm` preflight check.
