---
description: "`NameMap` and `OpaqueAgent`: the opaque `m01`/`r01` names a model agent sees, translated at the runner boundary in both directions, and `token_pattern`, the one token boundary the surfacing and the taint audit share. Source: `src/alienbio/suite/naming.py`."
---
:>> [[ABIO]] → [[ABIO Dev Docs]] → [ABIO NameMap](ha://p/ABIO%20NameMap) 
# ABIO NameMap
The opaque-names boundary: a seed-shuffled map from a world's structural ids to `m01…`/`r01…` surface names, the agent wrapper that translates every crossing through it, and the token boundary the taint audit reads it by.

![[ABIO NameMap.svg|2400]] 
*The token boundary* is the topic that governs `token_pattern`'s node: the surfacing and the taint audit spell one boundary, so they cannot disagree about what a whole id is.

This page covers `suite/naming.py`: the map, how it is built, what crosses it in each direction, and the boundary regex. The turn loop that builds the map, wraps the agent, stores the map and runs `audit_prompts` is [[ABIO Runner]]; the brief's fields are [[ABIO TaskBrief]]; the shared-id rule the builder mirrors is [[ABIO ChemistryImpl]]; where the boundary sits in the live loop is [[ABIO-Runtime]], and the operator-facing account is [[ABIO Suite Runtime]] § Opaque names.



## NameMap Interface
An injective structural → surface map over one world's ids, with its inverse. A frozen dataclass whose two maps are public and whose two compiled patterns (`_pattern`, `_back_pattern`) are private, excluded from `repr` and from equality, so two maps compare by their entries alone. Build one with `of`, which compiles the patterns; calling the dataclass constructor directly means passing compiled patterns by hand. Every lookup passes an unmapped string through unchanged, so a key the map never saw — the monitor's `auditor:coverage` compartment, an action-cost verb — crosses as itself.

| NameMap | |
| --- | --- |
| [[#^to-surface\|to_surface]] | Structural id → surface name |
| [[#^to-structural\|to_structural]] | Surface name → structural id |
| [[#^of\|of]] | Build from a mapping; refuse colliding surface names |
| [[#^surface\|surface]] | One id to its surface name |
| [[#^structural\|structural]] | One surface name to its id |
| [[#^surface-text\|surface_text]] | Surface every whole id in free text |
| [[#^structural-text\|structural_text]] | Restore every whole surface name in free text |
| [[#^surface-value\|surface_value]] | Surface every string in a JSON-ish value |
| [[#^structural-value\|structural_value]] | Restore every string in a JSON-ish value |

**to_surface**`: Mapping[str, str]`
    Structural id → surface name, a plain `dict` copy of the mapping `of` was given. This is what the runner writes onto `TrialRecord.name_map` (as `dict(name_map.to_surface)`) and what `audit_prompts` takes as the set of every structural id ([[#The taint audit]]). ^to-surface

**to_structural**`: Mapping[str, str]`
    The inverse, built by `of` from `to_surface`'s items. ^to-structural

**of**`(mapping: Mapping[str, str]) -> "NameMap"` (static)
    Build a map from `mapping`, inverting it and compiling one pattern per direction (longest id first, under [[#The token boundary]]). Raises `ValueError("NameMap: the surface names collide")` when two structural ids share a surface name. It does not check that no surface name is also a structural id. `realism.render_transcript` rebuilds a map from a stored record this way. ^of

**surface**`(structural: str) -> str`
    The surface name of `structural`, or `structural` itself when it is not in the map. ^surface

**structural**`(surface: str) -> str`
    The structural id of `surface`, or `surface` itself when it is not in the map. ^structural

**surface_text**`(text: str) -> str`
    `text` with every structural id that appears as a whole token replaced by its surface name; `text` unchanged when the map is empty. An id inside a longer id is not a whole token and is left as written; a `.` is never part of an id, so `id.rate` surfaces as `m01.rate` ([[#The token boundary]]). ^surface-text

**structural_text**`(text: str) -> str`
    The inverse of `surface_text`: every whole surface name replaced by its structural id. Used on a probe's answer. ^structural-text

**surface_value**`(value: Any) -> Any`
    A copy of `value` with `surface_text` applied to every string inside it, dict keys included, through dicts (any `Mapping`, rebuilt as `dict`), lists, tuples, sets and frozensets; any other value — numbers, `None`, dataclasses — is returned as is. ^surface-value

**structural_value**`(value: Any) -> Any`
    `surface_value` in the other direction, with `structural_text`. Used on a committed answer's value. ^structural-value



## OpaqueAgent Interface
The wrapper that lets any agent see and speak surface names while the runner sees structural ids. `runner.run` wraps the trial's agent in it once, right after building the brief, when [[#^opaque-names-requested|opaque_names_requested]] says so; from then on every crossing goes through it. It implements `SessionAgent` and `ProbeAgent` structurally whether or not the wrapped agent does, and passes a call through only when the inner agent can take it. Every other attribute the runner reads off an agent — `usage`, `prompt_texts`, `parse_failures`, `aborted`, `compaction`, `forgetting` — is forwarded untouched by `__getattr__`, so the taint audit reads the inner agent's own prompts.

| OpaqueAgent | |
| --- | --- |
| [[#^opaqueagent\|OpaqueAgent]] | Wrap an agent with a name map |
| [[#^inner\|inner]] | The wrapped agent |
| [[#^name-map\|name_map]] | The map every crossing goes through |
| [[#^begin\|begin]] | Hand the inner agent the surfaced brief |
| [[#^notice\|notice]] | Hand it the turn's outcome in surface names |
| [[#^probe\|probe]] | Ask a probe in surface names; answer in ids |
| [[#^act\|act]] | Surface the observation; return the action in ids |

**OpaqueAgent**`(agent: Any, name_map: NameMap) -> None`
    Store `agent` as `inner` and `name_map`. Validates nothing. ^opaqueagent

**inner**`: Any`
    The wrapped agent: an `LLMAgent`, a scripted agent, anything with `act`. ^inner

**name_map**`: NameMap`
    The trial's map. ^name-map

**begin**`(brief: TaskBrief) -> None`
    When the inner agent is a `SessionAgent`, call its `begin` with `surface_brief(brief, name_map)`; otherwise do nothing. The runner keeps the structural brief, and that is the brief stored on the record. ^begin

**notice**`(outcome: ActionOutcome) -> None`
    When the inner agent is a `SessionAgent`, call its `notice` with a copy of `outcome` whose `action` is `surface_action`'s and whose `reason` is surfaced with `surface_text`, so the agent hears its own names back, rejection reasons included. `turn`, `accepted` and `result` (a destructive assay's revealed rate, a float) are passed as they are. ^notice

**probe**`(text: str) -> Optional[str]`
    `None` when the inner agent has no `probe`. Otherwise asks it `surface_text(text)` and returns the answer through `structural_text`, or the answer unchanged when it is not a string. The probe's text arrives structural because the runner substitutes `{placeholder}` tokens from the drafter's `probe_vocab` first. ^probe

**act**`(observation: Observation) -> tuple[Action, tuple[ReasoningStep, ...]]`
    Call the inner agent's `act` with `surface_observation(observation, name_map)`, then return `structural_action` of its action and its reasoning steps with each entry of `refs` mapped through `structural`. A step's `content` is returned verbatim, so the trace holds the model's own words in surface names ([[#What crosses, in which direction]]). ^act



## naming Interface
The module-level functions. `__all__` lists `NameMap`, `OpaqueAgent`, `build_name_map`, `opaque_names_requested`, `structural_action`, `surface_action`, `surface_brief`, `surface_observation` and `token_pattern` (imported by `suite/runner.py`). Private: `_BOUNDARY_L` and `_BOUNDARY_R` (the boundary regexes), `_id_pattern` (the longest-first alternation over a map's keys; a pattern that matches nothing for an empty map) and `_map_value` (the recursive walk behind the `_value` methods).

| naming | |
| --- | --- |
| [[#^token-pattern\|token_pattern]] | One token as a whole id in free text |
| [[#^build-name-map\|build_name_map]] | The trial's map from a chemistry and a seed |
| [[#^opaque-names-requested\|opaque_names_requested]] | Whether a trial runs under opaque names |
| [[#^surface-brief\|surface_brief]] | The brief in surface names |
| [[#^surface-observation\|surface_observation]] | An observation in surface names |
| [[#^structural-action\|structural_action]] | An agent's action back in structural ids |
| [[#^surface-action\|surface_action]] | An action in surface names |

**token_pattern**`(token: str) -> "re.Pattern[str]"`
    A compiled regex matching `token` only as a whole id: `_BOUNDARY_L + re.escape(token) + _BOUNDARY_R`. `audit_prompts` scans every prompt with it, and exempts secrets that a question leaf or a declared probe text names with it ([[#The token boundary]]). ^token-pattern

**build_name_map**`(chemistry: "ChemistryImpl", seed: Seed) -> NameMap`
    `m01…` for every molecule and `r01…` for every reaction of `chemistry`, each kind sorted and then shuffled by its own child seed ([[#The surface vocabulary]]). Raises `ValueError` naming the sorted ids when any id is both a molecule and a reaction ([[#The shared-id refusal]]). Deterministic in the id sets and `seed`. ^build-name-map

**opaque_names_requested**`(task_setup: Any, dials: Mapping[str, Any]) -> bool`
    The `opaque_names` dial when it is given and not `None` (truthiness, so `False` turns opaque names off even on a world that asks for them); otherwise the truthiness of `task_setup["opaque_names"]` when `task_setup` is a mapping; otherwise `False`. The guarded drafters set the setup key. ^opaque-names-requested

**surface_brief**`(brief: TaskBrief, nm: NameMap) -> TaskBrief`
    A copy of `brief` with `question` and `monitoring` through `surface_value`; `constitution`, `context_padding`, `protocol`, `framing`, `monitor`, `stakes`, `reversibility` and `task_note` through `surface_text` when non-empty; the affordances' `probes`, `levers`, `assays` and `max_rates` keys and `irreversible` through `surface`. That is every field `render_brief` prints; the rest are copied as is ([[#What is never translated]]). ^surface-brief

**surface_observation**`(observation: Observation, nm: NameMap) -> Observation`
    A tuple with each compartment dict's keys through `surface`; values untouched. ^surface-observation

**structural_action**`(action: Action, nm: NameMap) -> Action`
    A `Measure`'s `probe` and an `Intervene`'s `lever` through `structural`; a `Commit`'s answer rebuilt as `Answer(value=structural_value(value), kind=kind)`; a `Wait`, or anything else, returned as is. `params` and an `Intervene`'s `value` are never translated. ^structural-action

**surface_action**`(action: Action, nm: NameMap) -> Action`
    The mirror of `structural_action`, with `surface` and `surface_value`. Used by `OpaqueAgent.notice`. ^surface-action




# NameMap Semantics

## The surface vocabulary
A generated world's ids say what their parts are (`root/crux/sink_byproduct_in`, `route_clean/rxn`); a model shown them has the answer before it has measured anything. So a molecule is `m` and a reaction `r`, followed by a 1-based index zero-padded to `max(2, digits in the count)` — `m01…m07` for seven molecules, `m001` once there are a hundred. The two kinds are numbered independently, so `m01` and `r01` coexist. Each kind's ids are sorted, then shuffled by `random.Random(seed.child("names/molecules").value)` or `…("names/reactions")`, so the surface name carries neither the structure nor the generator's ordering, and the map depends on the id sets and the seed, not on dict order. The runner passes `seed.child("names")` of the trial seed: one map per trial, the same map on every replay of that trial. Every molecule and reaction is mapped, including `hidden_ids` pools the agent never observes.



## The token boundary
An id is matched only as a whole token. `_BOUNDARY_L` is `(?<![A-Za-z0-9_/-])` and `_BOUNDARY_R` is `(?![A-Za-z0-9_/-])`: an id character (letter, digit, `_`, `/`, `-`) on either side means the match is inside a longer id. Anything else is a boundary, a `.` included on either side, whether it ends a sentence or continues into a word (`m01` matches in `m01.` and in `m01.rate`); no shipped id carries a dot. Maps match longest id first, since one id may prefix another.

The dot rule took two fixes. T066 (deep scan round 2): the right boundary used to exclude `.` outright, so `surface_text("Never drain root/harm_in.")` returned the structural id unchanged, and the taint audit, which spelled the same boundary, read the prompt as clean — a structural id reached a live model with `taint_hits == ()`. `token_pattern` is now the one spelling, and both `NameMap`'s compiled patterns and `audit_prompts` are built from `_BOUNDARY_L` and `_BOUNDARY_R`, so the two cannot disagree about what a whole id is. T066 still refused a `.` that continued into a word, so `root/x_in.rate` escaped both sides the same way; the module-doc pass (2026-10-27) made a dot a boundary on either side. `tests/suite/test_t066_guard_holes.py` pins the sentence-ending case, `m01.rate`, and the negative `xm01`; `tests/suite/test_moddoc_findings_suite.py` pins both sides and the audit hit.



## What crosses, in which direction

| Crossing | Direction | Function | Translated |
| --- | --- | --- | --- |
| Brief, at `begin` | out | `surface_brief` | question, every printed text field, affordances, irreversible levers |
| Observation, each turn | out | `surface_observation` | compartment keys |
| Outcome, at `notice` | out | `surface_action`, `surface_text` | the action, the reason |
| Probe question | out | `surface_text` | the whole text |
| Action, from `act` | in | `structural_action` | probe, lever, answer value |
| Reasoning steps | in | `structural` | each `refs` entry |
| Probe answer | in | `structural_text` | the whole text |

Everything inbound lands structural, so the runner, the graders and every scorer work on the world's own names, and the action log, the answer, the probe records and the deliberation `refs` on the record are structural. The one inbound value kept in surface names is a reasoning step's `content`: it is the model's words. Scorers that scan it read the surface alias off `TrialRecord.name_map` — `hazard` adds `name_map[id]` to the names it looks for — and `realism.render_transcript` rebuilds a `NameMap` with `of` to show the whole session in the vocabulary the agent spoke.



## What is never translated
The runner itself never holds a surface name: the brief it builds, the world, the oracle, `task.setup` (with `hidden_ids`) and the answer key stay structural, and the brief stored on the record is the structural one. `hidden_ids` pools are projected out of every observation before the agent sees it, so their surface names never reach a prompt even though the map holds them.

Inside the crossing, `surface_brief` surfaces every field `render_brief` prints, `protocol`, `monitor`, `monitoring` and `context_padding` included (the last three carry no ids by construction, and are surfaced anyway so the rule is the printed set, not a per-field judgement); the fields it leaves are ones the prompt never shows. An action's `params` and an `Intervene`'s `value` are not translated, nor is an outcome's `result`.



## The shared-id refusal
`build_name_map` writes molecules and then reactions into one dict, so an id naming both would lose its molecule entry: the reaction would win the surface name and `structural_text` would map it back to the wrong entity. It refuses any id in both key sets with `ValueError` (`build_name_map: id(s) [...] name both a molecule and a reaction; one surface name cannot stand for two entities`), as a backstop beside `ChemistryImpl`'s own construction-time refusal ([[ABIO ChemistryImpl]] § Ids and the shared-id refusal, T054 #1). `tests/suite/test_naming.py` checks it with a stub chemistry that bypasses the constructor.



## The taint audit
`audit_prompts` (in `suite/runner.py`) scans the prompts an agent actually sent — `prompt_texts`, forwarded through `OpaqueAgent` — after the loop. It forms its secrets in structural ids (hidden molecules, reaction ids the brief did not hand over, answer-key tokens, minus what the question and the declared probes name, matched with `token_pattern`). Under a name map it then replaces them with `{surface(s) for s in secrets} | set(to_surface)`: a secret leaks in its surface form, and any structural id in a prompt is itself a leak. Each secret is searched with `token_pattern`; hits land on `TrialRecord.taint_hits` and raise `TaintError` carrying the record. A scripted agent has no `prompt_texts` and audits clean.




# BRIEF
- 2026-10-19 — written as an ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD 84f8190; the dot boundary, the per-kind padding and `protocol` passing through `surface_brief` unsurfaced were confirmed by running them against the venv, not inferred. Left out: `__getattr__` as a member block (its block id would be `^--getattr--`; the forwarding is in the OpaqueAgent paragraph), `NameMap`'s dataclass constructor (it takes the private compiled patterns; `of` is the way in), and `TrialRecord.name_map` and the store's `name_map` key as members (they belong to the trial and store docs). The figure omits `brief.py` and `llm_agent.py` as nodes, for density.
