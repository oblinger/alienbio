[[Architecture Docs]] 

# ABIO Suite Runtime

The Phase-2 layer that makes the [[ABIO Suite Construction|suite-construction]] primitives *live*: an agent acts on a generated world turn by turn, one immutable record per trial comes out, and a mass-trial sweep reduces many records to a reliability map. Everything here lives in `alienbio.suite` (`agent.py`, `brief.py`, `llm_agent.py`, `runner.py`, `trial.py`, `mass_trial.py`, `conditions.py`) and is domain-neutral — scorers pattern-match on action *type*, never on a world's vocabulary.

## The turn loop

`suite.runner.run(world, task, agent, dials, seed, *, sim_cfg, max_turns, illegal_action_limit, illegal_action_cost) -> TrialRecord`

| Step | What happens | Where |
|---|---|---|
| 0 · brief | The runner builds a `TaskBrief` — question, expected answer kind, constitution, the declared probes and levers, budget and costs, turn/step limits — and hands it to a `SessionAgent` via `begin(brief)` once, before the first turn. | `brief.build_brief`, `agent.SessionAgent` |
| 1 · rebuild | A fresh immutable `WorldImpl` is rebuilt from the prior turn's end-state (turn 0 folds the world's own initial state through the same path); the caller's `world` is never mutated. | `runner._world_from_state` |
| 2 · narrow | Ground truth is narrowed to an `Observation` by the observability / noise dials with a per-turn child seed. This is the taint boundary: the agent never sees the world, the oracle or the key. | `observation.narrow_observation` |
| 3 · act | `agent.act(observation) -> (Action, reasoning_steps)`. | `agent.Agent` |
| 4 · apply | `Measure` and `Wait` are non-mutating; `Intervene` sets one reaction rate or one molecule concentration; `Commit` ends the trial with an answer. An action naming an id outside the brief's affordances, or a non-finite value, is **rejected as data** — logged with a reason, charged, fed back through `notice(...)`, and the turn still plays out; `illegal_action_limit` rejections end the trial with reason `illegal_limit`. | `runner.run`, `agent.ActionOutcome` |
| 5 · simulate | One `sim_cfg` burst; its end-state is the next turn's state. | `verify.simulate` |
| 6 · stop | `committed` · `budget_exhausted` (the graded time-pressure `Budget`) · `max_turns` · `illegal_limit`. | `runner.Budget` |

The result is one frozen `TrialRecord`: task id, condition key, final timeline, deliberation trace, action log (accepted and rejected), objective score, terminal reason, budget/spent/remaining, illegal-action count, turns, and the brief the agent was given.

## Agents

- **`Agent`** — the structural Protocol: `act(observation)`. Nothing else is required, which is what keeps `ScriptedAgent` and `LLMAgent` interchangeable at the call site.
- **`SessionAgent`** — the optional second Protocol an agent implements to be *told its task*: `begin(brief)` at trial start and `notice(outcome)` after every action. The runner checks `isinstance(agent, SessionAgent)`; an agent that does not implement it (the scripted policies) is simply never briefed.
- **`ScriptedAgent`** — deterministic, network-free, seeded; a declarative step list with `WaitUntil` guards. Keeps CI green and is the **zero of the instrument**: a scripted run with a known policy is what every live-model number is read against.
- **`LLMAgent`** — a live model over the `LLMOp` seam (schema-validated reply, deterministic cache keyed on directive + context + seed, retry with a child seed). Implements `SessionAgent`: the brief is rendered into the system prompt at `begin`, and the agent keeps a history window (`memory="full" | "none" | k`) of what it saw, what it did and whether each action was accepted, so the model reasons across turns instead of restarting each one. Opt-in and out of CI; `prompt_hashes` records one hash per real model call.

## Sweeps

`suite.mass_trial.MassTrialRunner.run(axes, drafter, agent_factory, trials_per_condition, base_seed, on_error="record") -> ReliabilityMap`

Every `(condition, trial)` derives its own child seed, so a cell is a pure function of its own key and never of the grid's shape. Each trial is isolated: with `on_error="record"` an exception from the drafter, the agent factory or the run becomes an error record (`terminal_reason="error"`, excluded from the statistics, counted in `Provenance.failed_trials`) rather than the end of a paid sweep. The map keeps **every** record on `ReliabilityMap.records` — the per-trial data the M33 scorers read — alongside per-cell stats with confidence intervals, 2×2 interaction contrasts and effect sizes.

Dial vectors come from `suite.conditions` (`ConditionSpec`, `DialAxis`, sampling with quantization and orthogonality); the observability / noise / budget / constitution / `levers` dials are read by the runner and the observation narrowing, and any other dial is threaded through untouched to the drafter and agent factory.

## What is not here yet

Roadmap **M46** tracks the rest of production readiness: structured-output robustness on the action reply, a declarable experiment runnable from the `bio` CLI, per-condition `sim_cfg` / `max_turns`, a run manifest, control arms in one grid, power sizing before spend, a taint audit over the prompts actually sent, and a run report generated from the record store. See [[ABIO Roadmap]] § M46.

## See Also

- [[ABIO Suite Construction]] — the M26/M27 pipeline that produces the worlds and tasks this runtime consumes
- [[Suite Construction Data Model]] — the type model (`TaskInstance`, `Question`, `Answer`, objectives)
- [[ABIO Protocols]] — the class index
