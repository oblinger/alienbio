---
description: "`types`: the suite's neutral value types, in layers — `Timeline`; the M27 construction chain `Motif`/`RoleSlot` → `CarveResult` → `TaskArchetype` (+ `ObjectiveRecipe`, `Drafter`) → `TaskInstance` → `Suite`; the question/answer/objective family (`Question`, `Answer`, `GraderSpec`, `AnswerObjective`, `OutcomeObjective`); `Op`/`ScriptedOp`. Source: `src/alienbio/suite/types.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Types](ha://p/ABIO%20Types) 
# ABIO Types
The value types every other suite module passes around: a simulated trajectory, the M27 chain from an abstract motif to a materialized suite, and the question, answer and objective a task is graded by.

![ABIO Types](ABIO%20Types.svg) 
*Frozen, not immutable* is the topic behind every box (‡: the dataclasses are frozen, but the dict and list fields inside them are not).

`suite/types.py` holds no logic: domain meaning lives in opaque `Tags` the module never reads. Two families matter at run time. `Timeline` is what `verify.simulate` returns and every generator's oracle reads. `TaskInstance`, `Question`, `Answer`, `GraderSpec` and the two objectives are what a drafter returns and the runner, the brief and the grader consume ([ABIO Runner](ABIO%20Runner.md), [ABIO TaskBrief](ABIO%20TaskBrief.md), [ABIO Drafters](ABIO%20Drafters.md)). The motif chain (`Motif`, `RoleSlot`, `FeatureSet`, `CarveResult`, `TaskArchetype`, `ObjectiveRecipe`, `SuiteSpec`, `Suite`) is M27's construction pipeline, whose design is [ABIO Suite Construction Data Model](../../ABIO%20Architecture/ABIO%20Suite%20Construction%20Data%20Model.md); `ScriptedOp` is [ABIO LLMOp](ABIO%20LLMOp.md)'s pure-code sibling. Every public name is re-exported from `alienbio.suite`.



## Run-time types Interface
The types a run carries from drafter to grader.

| Run-time types | |
| --- | --- |
| [Timeline](#^timeline) | Timestamps and world states |
| [TaskInstance](#^taskinstance) | One drafted task |
| [Question](#^question) | Structured question tagged by kind |
| [Answer](#^answer) | A value tagged by kind |
| [GraderSpec](#^graderspec) | Which grader, with what knobs |
| [AnswerObjective](#^answerobjective) | Grade an answer against a key |
| [OutcomeObjective](#^outcomeobjective) | Score an outcome against a target |
| [Objective](#^objective) | Either objective |

**Timeline**`(times: tuple[float, ...], states: tuple[WorldState, ...])`
    `states[k]` at `times[k]` seconds. The lengths are not checked against each other. ^timeline

**TaskInstance**`(archetype: str, world: str, skeleton: CarveResult, objective: Objective, question: Question, setup: Any)`
    `world` is a name, not the world; `setup` is the drafter's free mapping (`hidden_ids`, `lever_caps`, `probe_vocab`, `brief_defaults` …). ^taskinstance

**Question**`(structured: Any, kind: str)`
    `kind` matches a render kind of `render.py`. ^question

**Answer**`(value: Any, kind: str)`
    Documented kinds `node_set`, `ordered_path`, `node_id`, `scalar`, `json`; not validated. ^answer

**GraderSpec**`(kind: str, config: Tags = {})`
    Tolerance and partial-credit knobs live in `config`. ^graderspec

**AnswerObjective**`(grader: GraderSpec, key: Answer)`
    Graded by `grade.grade_answer`. ^answerobjective

**OutcomeObjective**`(scorer: Callable, target: Any)`
    The scorer reads the final state or timeline; graded by `grade.grade_outcome`. ^outcomeobjective

**Objective**` = Union[AnswerObjective, OutcomeObjective]`
    What a task is scored by. ^objective



## Construction types Interface
The M27 chain from an abstract pattern to a suite.

| Construction types | |
| --- | --- |
| [RoleSlot](#^roleslot) | A named, typed role with constraints |
| [Motif](#^motif) | Roles and tagged edges |
| [CarveResult](#^carveresult) | Roles bound to host nodes |
| [FeatureSet](#^featureset) | Named predicates a world must meet |
| [ObjectiveRecipe](#^objectiverecipe) | Question, key and grader from a carve |
| [Drafter](#^drafter) | Seed to world, carve and objective |
| [TaskArchetype](#^taskarchetype) | Motif, verb, features, recipe |
| [SuiteSpec](#^suitespec) | The archetype mix |
| [Suite](#^suite) | Worlds and task instances |

**RoleSlot**`(name: str, type_tag: str, constraints: tuple[Predicate, ...] = ())`
    `Predicate = Callable[[Any], bool]`, only ever called. ^roleslot

**Motif**`(roles: tuple[RoleSlot, ...], edges: tuple[tuple[str, str, str], ...], params: Tags = {})`
    Edges are `(role, role, tag)`. ^motif

**CarveResult**`(motif: Motif, binding: Mapping[str, NodeId], added: tuple = (), removed: tuple = ())`
    The ground truth a recipe reads; generator drafters build it directly instead of carving. ^carveresult

**FeatureSet**`(features: frozenset[tuple[str, Predicate]] = frozenset())`
    Read by `cover.py`. ^featureset

**ObjectiveRecipe**` (Protocol)`
    `build_question(skeleton, world) -> Question`, `build_key(skeleton, world) -> Answer`, `grader_spec() -> GraderSpec`. Not `runtime_checkable`. ^objectiverecipe

**Drafter**` = Callable[[Seed], tuple[WorldImpl, CarveResult, Optional[Objective]]]`
    The M27 generator seam; an outcome archetype returns its own objective, an answer archetype `None`. Distinct from the experiment registry's drafters ([ABIO Drafters](ABIO%20Drafters.md)). ^drafter

**TaskArchetype**`(id, motif, verb, feature_reqs: FeatureSet, recipe: ObjectiveRecipe, drafter: Optional[Drafter] = None, extra_answer_tokens: tuple[str, ...] = ())`
    With a `drafter`, `build_suite` uses it instead of carving; `extra_answer_tokens` (`up`/`down`/`same`) join the vocabulary. ^taskarchetype

**SuiteSpec**`(archetype_mix: Dist[TaskArchetype])`
    The docstring still says "per-archetype schemas + seed"; the class has only the mix. ^suitespec

**Suite**`(worlds: tuple[WorldImpl, ...], tasks: tuple[TaskInstance, ...])`
    What `pipeline.build_suite` returns. ^suite



## types Interface
Aliases and protocols.

| types | |
| --- | --- |
| [NodeId](#^nodeid) | A node name |
| [Tags](#^tags) | Opaque key-value bag |
| [Directive](#^directive) | An op's instruction text |
| [Op](#^op) | Callable over a context |
| [ScriptedOp](#^scriptedop) | An `Op` backed by a function |
| [Unused names](#^unused) | Declared, read nowhere |

**NodeId**` = str`
    A molecule or reaction name in a host world. ^nodeid

**Tags**` = dict[str, str | float | bool]`
    At run time a value may be any JSON value (LLMAgent passes the model's `params` through). ^tags

**Directive**` = str`
    The fixed instruction an `LLMOp` carries; LLMAgent's system prompt. ^directive

**Op**` (Protocol, runtime_checkable)`
    `__call__(context) -> T_co`. ^op

**ScriptedOp**`(fn: Callable[[Any], T])`
    Calls `fn(context)`; constructed nowhere in `src/`. ^scriptedop

**Renderable, Difficulty**
    A `render(vocabulary)` protocol and `dict[str, float]`; no module reads either. ^unused




# Types Semantics

## Frozen, not immutable
Every class is `@dataclass(frozen=True)`, and frozen is shallow (stated in the module docstring since T088 types 1): fields typed `Tags`, `Mapping` or `Any` hold the caller's object, uncopied: `GraderSpec("x").config["tol"] = 1` succeeds and shows in the instance. The generated `__hash__` then fails on those fields: `GraderSpec`, `Motif` and `CarveResult` raise `TypeError: unhashable type: 'dict'`, and an `Answer` with a list value raises on `list`. Nothing in `src/` hashes them or mutates a held collection. Deep-freezing is not done because the payloads compare by `==` (the render round trip) and serialize as plain JSON.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be`; hashability and the mutable `config` confirmed on the HEAD export, the consumer census by `git grep -w` per name over `src/` (`Renderable`, `Difficulty` and `ScriptedOp` have no reader). Left out: what each recipe builds (the archetype and pipeline docs).
- 2026-10-28 — refreshed against `0377846`: the module docstring now calls frozen shallow and says why it is not deep; no behaviour change.
