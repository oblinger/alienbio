# Agent loop — brief, session memory, contained failure

*Four agents on one tiny world: recovery through the brief after a rejection, the illegal-action limit containing a confused agent, an empty taint audit, a $0 dry run — and a pinned-memory live arm CI never runs.*

One neutral chain (`A -> B -> C`, fed and drained) under an outcome task (raise `C` to a target), swept across an `agent` axis: the framework's `act_commit` and `idle` beside two example-owned session agents. `retry_commit` is the loop working as intended — its first probe is illegal, the runner rejects it AS DATA and says so via `notice`, and the agent recovers by reading its `begin` brief (turn memory) before committing. `clumsy_commit` is the loop's containment — an unknown lever every turn until `illegal_action_limit` stops the trial with reason `illegal_limit`, one burned trial and nothing else. Every scripted record carries `usage: None`, an empty taint audit, and the whole grid dry-runs at $0.

`live.yaml` is the LLM arm — run by hand (`--dry` first), never by CI. **AUP condition (2026-08-31):** with a live model the `memory` window stays FIXED — never sweep memory with an LLM (a memory sweep is a retention curve, AUP measure 2's territory). The test asserts `live.yaml` keeps `memory` a scalar and sweeps nothing; scripted arms are unrestricted.

## Run it

    bio suite run catalog/examples/agent_loop/agent_loop.yaml --dry
    bio suite run catalog/examples/agent_loop/agent_loop.yaml
    bio suite run catalog/examples/agent_loop/live.yaml --dry   # the LLM arm, by hand

## What it covers

| Capability dimension | Where |
|---|---|
| `TaskBrief` + `begin`/`notice` session memory (M46.1/M46.2) | `retry_commit` |
| rejection-as-data + the illegal-action limit (M46.3) | `retry_commit`, `clumsy_commit` |
| an `agent` axis beside example-owned registered agents (M46.8) | `axes: {agent: [...]}` |
| the taint audit clean on a whole scripted grid | `test_scripted_trials_carry_no_usage...` |
| the $0 dry-run estimate for an all-scripted grid (M45.5) | `estimate_cost` |
| a live arm shape: pinned model dial, fixed memory, temperature/top_p, cost ceiling, no-peeking pass | `live.yaml` |

Deliberately absent: every AI-safety dial (roadmap M48.9); the memory-sweep restriction above.

## Test

`tests/expr/test_agent_loop_example.py`.
