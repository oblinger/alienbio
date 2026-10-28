---
description: "`grade`: the FT06 graders — `grade_answer` scores an `Answer` against its key by `GraderSpec.kind` (`node_set` Jaccard, `ordered_path` exact or prefix credit, `node_id`, `scalar` tolerance step, `json` equality), `grade_outcome` passes a timeline to an opaque scorer. Source: `src/alienbio/suite/grade.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Grade](ha://p/ABIO%20Grade) 
# ABIO Grade
The two functions that turn an agent's commit, or a trial's final timeline, into the trial's `objective_score`.

![ABIO Grade](ABIO%20Grade.svg) 
*Answer shapes* is the topic behind the five kind branches (‡: the answer's own `kind` and Python type are never checked against the grader's).

`suite/grade.py` is pure and domain-free. Its run-path caller is `runner.run` at the end of every trial ([ABIO Runner](ABIO%20Runner.md)): an `AnswerObjective` task with a commit is graded by `grade_answer` (a `None` answer scores 0 without grading), an `OutcomeObjective` task by `grade_outcome` on the trial's turn-boundary timeline. `pipeline.build_suite` self-grades each key against itself as a round-trip guard. The objective and answer types are [ABIO Types](ABIO%20Types.md)'s; the scorers outcome tasks carry are built by their generators ([ABIO PressureGen](ABIO%20PressureGen.md), the intervene archetype). Both functions are re-exported from `alienbio.suite`. The subsystem view is [ABIO-Runtime](../../ABIO%20Architecture/ABIO-Runtime.md).



## grade Interface
Two public functions; the three private helpers are the per-kind formulas.

| grade | |
| --- | --- |
| [grade_answer](#^grade-answer) | Answer against key, by grader kind |
| [grade_outcome](#^grade-outcome) | Timeline through an opaque scorer |

**grade_answer**`(answer: Answer, key: Answer, spec: GraderSpec) -> float`
    Dispatches on `spec.kind`; raises `ValueError` on any other kind (`"outcome"` included). § [Answer shapes](#answer-shapes) gives each formula. ^grade-answer

**grade_outcome**`(trace: Timeline, scorer: Callable[[Any], float], target: Any) -> float`
    `float(scorer(trace))`; `target` is accepted and discarded, since a scorer closes over what it needs. The result is not clamped to `[0, 1]`. ^grade-outcome




# Grade Semantics

## Answer shapes

| Kind | Score | Config |
| --- | --- | --- |
| `node_set` | Jaccard; 1.0 for two empty sets | `partial` (default true); false is exact equality |
| `ordered_path` | 1.0 if equal, else 0.0 | `partial` (default false); true is the common-prefix length over the longer length |
| `node_id` | `answer == key` | — |
| `scalar` | 1.0 if `abs(a − k) ≤ tol`, else 0.0 | `tol` (default 0) |
| `json` | `answer == key` (Python equality) | — |

Each formula coerces the answer value with `set(...)`, `list(...)` or `float(...)` and trusts its shape. Measured through `runner.run` with a scripted commit: on the `discover` task (`ordered_path`) an integer answer raised `TypeError: 'int' object is not iterable` out of `run` itself, after the trial's last turn, so the trial becomes an error record rather than a score; on the `diagnose` task (`node_id`) the list `["m0"]` scored 0 against the key `"m0"`. A bare string on a `node_set` or `ordered_path` task is split into characters (`"m0"` reads as `{"m", "0"}`). LLMAgent passes the model's `{"value", "kind"}` through unchecked, so these shapes come from a model as readily as from a test. Python equality makes `json` read `True == 1`, and `partial` is read with `bool(...)`, so a YAML string `"false"` turns partial credit on.



## Outcome scores
`grade_outcome` returns whatever the scorer returns. The intervene scorer is `1 / (1 + |final − goal|)` and the pressure scorers are bounded by their own construction; nothing here enforces `[0, 1]`, so the reliability map averages whatever range a scorer uses.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be` and the grading block of `runner.run` (~1149–1163); the `discover` integer-answer raise and the `diagnose` list-answer zero confirmed by `runner.run` with a `ScriptedAgent` on the HEAD export, the string-split, `True == 1` and `"false"` cases by direct calls, no spend.
