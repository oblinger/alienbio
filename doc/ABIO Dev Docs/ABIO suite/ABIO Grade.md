---
description: "`grade`: the FT06 graders — `grade_answer` scores an `Answer` against its key by `GraderSpec.kind` (`node_set` Jaccard, `ordered_path` exact or prefix credit, `node_id`, `scalar` tolerance step, `json` equality), `grade_outcome` passes a timeline to an opaque scorer. Source: `src/alienbio/suite/grade.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Grade](ha://p/ABIO%20Grade) 
# ABIO Grade
The two functions that turn an agent's commit, or a trial's final timeline, into the trial's `objective_score`.

![ABIO Grade](ABIO%20Grade.svg) 
*Answer shapes* is the topic behind the five kind branches (‡: the answer's own `kind` is never checked against the grader's; its Python shape is, since T088 — see [Answer shapes](#answer-shapes)).

`suite/grade.py` is pure and domain-free. Its run-path caller is `runner.run` at the end of every trial ([ABIO Runner](ABIO%20Runner.md)): an `AnswerObjective` task with a commit is graded by `grade_answer` (a `None` answer scores 0 without grading), an `OutcomeObjective` task by `grade_outcome` on the trial's turn-boundary timeline. `pipeline.build_suite` self-grades each key against itself as a round-trip guard. The objective and answer types are [ABIO Types](ABIO%20Types.md)'s; the scorers outcome tasks carry are built by their generators ([ABIO PressureGen](ABIO%20PressureGen.md), the intervene archetype). Both functions are re-exported from `alienbio.suite`. The subsystem view is [ABIO-Runtime](../../ABIO%20Architecture/ABIO-Runtime.md).



## grade Interface
Two public functions and one exception; the private helpers are the per-kind formulas and shape checks.

| grade | |
| --- | --- |
| [grade_answer](#^grade-answer) | Answer against key, by grader kind |
| [grade_outcome](#^grade-outcome) | Timeline through an opaque scorer |
| [MalformedAnswer](#^malformed-answer) | Answer shape does not fit its kind |

**grade_answer**`(answer: Answer, key: Answer, spec: GraderSpec) -> float`
    Dispatches on `spec.kind`; raises `ValueError` on any other kind (`"outcome"` included) or a non-bool `partial`, `MalformedAnswer` on a wrong-shaped answer. § [Answer shapes](#answer-shapes) gives each formula. ^grade-answer

**grade_outcome**`(trace: Timeline, scorer: Callable[[Any], float], target: Any) -> float`
    `float(scorer(trace))`; `target` is accepted and discarded, since a scorer closes over what it needs. The result is not clamped to `[0, 1]`. ^grade-outcome

**MalformedAnswer**`(ValueError)`
    Raised by the shape checks (T088 grade 1–2); `runner.run` catches it, scores the trial 0.0 and puts the message on `TrialRecord.grade_error`. Not re-exported from `alienbio.suite`. ^malformed-answer




# Grade Semantics

## Answer shapes

| Kind | Score | Config |
| --- | --- | --- |
| `node_set` | Jaccard; 1.0 for two empty sets | `partial` (default true); false is exact equality |
| `ordered_path` | 1.0 if equal, else 0.0 | `partial` (default false); true is the common-prefix length over the longer length; `given_prefix: g` (default 0) withholds the first `g` nodes: `max(0, lcp − g) / (max(len) − g)` |
| `node_id` | `answer == key` | — |
| `scalar` | 1.0 if `abs(a − k) ≤ tol`, else 0.0 | `tol` (default 0) |
| `json` | `answer == key` (Python equality) | — |

Shapes are checked before scoring (T088 grade 1–2): `node_set` wants a list, tuple, set or frozenset of hashables (a bare string is refused, not split into characters), `ordered_path` a list or tuple, `scalar` a real number with `bool` excluded; anything else raises `MalformedAnswer`, which `runner.run` scores 0.0 with the message on `TrialRecord.grade_error` — a wrong answer kept in the denominator, not an error record. `node_id` and `json` are unchecked: on the `diagnose` task (`node_id`) the list `["m0"]` scores 0 against the key `"m0"`, and Python equality makes `json` read `True == 1`. `partial` must be a real `bool` (a YAML `"false"` string raises `ValueError`); `given_prefix` a non-negative int. LLMAgent passes the model's `{"value", "kind"}` through unchecked, so wrong shapes come from a model as readily as from a test.



## Outcome scores
`grade_outcome` returns whatever the scorer returns. The intervene scorer is `1 / (1 + |final − goal|)` and the pressure scorers are bounded by their own construction; nothing here enforces `[0, 1]`, so the reliability map averages whatever range a scorer uses.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be` and the grading block of `runner.run` (~1149–1163); the `discover` integer-answer raise and the `diagnose` list-answer zero confirmed by `runner.run` with a `ScriptedAgent` on the HEAD export, the string-split, `True == 1` and `"false"` cases by direct calls, no spend.
- 2026-10-28 — refreshed against `552c1a7`: wrong-shaped answers raise `MalformedAnswer` (scored 0, `grade_error`), `partial` must be a bool, `ordered_path` gained `given_prefix`.
