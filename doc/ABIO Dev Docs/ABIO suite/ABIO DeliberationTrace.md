---
description: "`deliberation`: M33.1's reasoning-trace data model — `DeliberationStep` (turn, kind, content, refs) and the immutable `DeliberationTrace` with `append`/`extend` returning new traces and `depth`. Source: `src/alienbio/suite/deliberation.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO DeliberationTrace](ha://p/ABIO%20DeliberationTrace) 
# ABIO DeliberationTrace
The record of what an agent said while it acted: one step per reasoning step, each stamped with its turn and tagged with the action that turn fired.

![ABIO DeliberationTrace](ABIO%20DeliberationTrace.svg) 
*Refs and action tags* is the topic behind the `refs` field (‡: the runner appends the action's type name to every step's refs, so ids and action tags share one tuple).

`suite/deliberation.py` stores and filters; it never reads `kind` or `refs` for meaning. The runner starts each trial with an empty trace and, each turn, folds the agent's `ReasoningStep`s into it with `trial.thread_reasoning_steps` ([ABIO Runner](ABIO%20Runner.md), [ABIO Agent](ABIO%20Agent.md)); the trace rides `TrialRecord.deliberation_trace` ([ABIO TrialRecord](ABIO%20TrialRecord.md)) and round-trips through `records.jsonl` ([ABIO Store](ABIO%20Store.md)). The scorers read `trace.steps` directly: [ABIO Hazard](ABIO%20Hazard.md) (surfacing by refs or a whole-word mention in `content`), [ABIO Degradation](ABIO%20Degradation.md) (budget awareness), [ABIO Census](ABIO%20Census.md) (trace length), [ABIO Realism](ABIO%20Realism.md) (the transcript). Both types are re-exported from `alienbio.suite`. The subsystem view is [ABIO-Runtime](../../ABIO%20Architecture/ABIO-Runtime.md).



## DeliberationStep Interface
A frozen dataclass: one step.

| DeliberationStep | |
| --- | --- |
| [turn](#^turn) | The turn it was said on |
| [kind](#^kind) | Opaque tag |
| [content](#^content) | Opaque text |
| [refs](#^refs) | Opaque ids it names, then the action tag |

**turn**`: int`
    The runner's turn index. ^turn

**kind**`: str`
    As the agent tagged it (`reason`, `abort`, `probe` …). ^kind

**content**`: str`
    The agent's text, verbatim. ^content

**refs**`: tuple[str, ...] = ()`
    The agent's own refs, then the fired action's lowercased class name appended by `thread_reasoning_steps`. ^refs



## DeliberationTrace Interface
A frozen dataclass over a tuple of steps; the two writers return a new trace.

| DeliberationTrace | |
| --- | --- |
| [steps](#^steps) | The steps, in order |
| [append](#^append) | New trace plus one step |
| [extend](#^extend) | New trace plus several |
| [depth](#^depth) | Number of steps |

**steps**`: tuple[DeliberationStep, ...] = ()`
    Appended in turn order by the runner. ^steps

**append**`(step) -> DeliberationTrace`
    `self.steps + (step,)`. ^append

**extend**`(steps: Iterable[DeliberationStep]) -> DeliberationTrace`
    `self.steps + tuple(steps)`; each call copies the whole tuple. ^extend

**depth**`() -> int`
    `len(steps)`; read by `TrialRecord.deliberation_depth`. ^depth




# DeliberationTrace Semantics

## Refs and action tags
A turn on which the agent emitted no reasoning step leaves no trace entry, so the trace is not a turn log: a scripted agent without reasoning produces an empty trace, and the action itself is only in `action_log`. When the agent does reason, every step of that turn carries the action tag (`measure`, `intervene`, `commit`, `wait`) at the end of its refs, beside whatever ids the agent named. A reader asking `first_ref_turn("commit")` gets the first turn the agent committed with reasoning attached, and an id spelled like an action tag would read as surfaced on every such turn. Molecule and consideration ids are path-shaped (`root/…`), so no current id collides.

The scorers scan `steps` themselves.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be` and `trial.thread_reasoning_steps`, no spend. Consumer census: `runner`, `trial`, `store`, `mass_trial` (empty trace on an error record), and the four scorers that read `steps`.
- 2026-10-29 — T093: the four readers `steps_of_kind`, `first_ref_turn`, `refs_by_turn` and `all_refs` retired (no caller in `src/`, `catalog/`, `demos/` or AUP); `depth` stays (`TrialRecord.deliberation_depth`).
