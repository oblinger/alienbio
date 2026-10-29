# Agent loop — brief, session memory, contained failure

*Four agents on one tiny world: recovery through the brief after a rejection, the illegal-action limit containing a confused agent, an empty taint audit, a $0 dry run — and a pinned-memory live arm CI never runs.*

One neutral chain (`A -> B -> C`, fed and drained) under an outcome task (raise `C` to a target), behind the **passive gate** — `helpers.passive_gate` integrates the untouched world over the episode's horizon and refuses it when `C`'s do-nothing reach is within half of the goal — and scored at that horizon (`setup["score_horizon_turns"]`, so an early commit is integrated passively to it, the `intervene` drafter's shape). The control surface is the feed's rate alone (`brief(levers=["root/feed/rxn"])`), swept across an `agent` axis: the framework's `act_commit` and `idle` beside two example-owned session agents. `retry_commit` is the loop working as intended — its first probe is illegal, the runner rejects it AS DATA and says so via `notice`, and the agent recovers by reading its `begin` brief (turn memory) before committing. `clumsy_commit` is the loop's containment — an unknown lever every turn until `illegal_action_limit` stops the trial with reason `illegal_limit`, one burned trial and nothing else. Every scripted record carries `usage: None`, an empty taint audit, and the whole grid dry-runs at $0.

`live.yaml` is the LLM arm — run by hand (`--dry` first), never by CI. **AUP condition (2026-08-31):** with a live model the `memory` window stays FIXED — never sweep memory with an LLM (a memory sweep is a retention curve, AUP measure 2's territory). The test asserts `live.yaml` keeps `memory` a scalar and sweeps nothing; scripted arms are unrestricted.

## Before and after the passive gate (T096)

Before, the target sat at the passive reach (feed 0.5, drain 0.1: `C` = 2.90 at 15 turns against the goal 3.0), the drain was the first default lever, and the score was read at the commit — so doing nothing won. Now the drain is 3.0 and the feed 0.25 (passive `C` = 0.083, on `setup["oracle"]["loop"]`), and `act_commit`'s one pull sets the feed to 10.

| Agent (base seed 21, 2 trials) | before | after |
|---|---|---|
| `act_commit` | 0.251 | **0.888** |
| `retry_commit` (feed 2.0) | 0.258 | 0.295 |
| `clumsy_commit` | 0.511 | 0.255 |
| `idle` | 0.912 | 0.255 |

The gameability red-team's three findings here (idle, commit-now, random beat or tie `act_commit`) are closed: idle 0.255, commit-now 0.255, random 0.501 / 0.408 (seeds 1 / 2), max-pull 0.034, all below 0.888.

## Run it

    bio suite run catalog/examples/agent_loop/agent_loop.yaml --dry
    bio suite run catalog/examples/agent_loop/agent_loop.yaml
    bio suite run catalog/examples/agent_loop/live.yaml --dry   # the LLM arm, by hand

## What it covers

| Capability dimension | Where |
|---|---|
| `TaskBrief` + `begin`/`notice` session memory (M46.1/M46.2) | `retry_commit` |
| rejection-as-data + the illegal-action limit (M46.3) | `retry_commit`, `clumsy_commit` |
| a passive gate on a neutral world, the outcome scored at the horizon (rung 3) | `helpers.passive_gate`, `loop_world` |
| an `agent` axis beside example-owned registered agents (M46.8) | `axes: {agent: [...]}` |
| the taint audit clean on a whole scripted grid | `test_scripted_trials_carry_no_usage...` |
| the $0 dry-run estimate for an all-scripted grid (M45.5) | `estimate_cost` |
| a live arm shape: pinned model dial, fixed memory, temperature/top_p, cost ceiling, no-peeking pass | `live.yaml` |

Deliberately absent: every AI-safety dial (roadmap M48.9); the memory-sweep restriction above.

## Test

`tests/expr/test_agent_loop_example.py`.
