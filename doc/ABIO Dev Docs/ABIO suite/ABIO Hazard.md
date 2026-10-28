---
description: "`hazard`: the EXP-4/5/6 surfacing family — `hazard_oracle` and `assert_hazard_gate` (when an injected, unmentioned byproduct crosses its threshold, refused at draft time if never), `hazard_surfacing_turn` and its summary, the graded `Consideration` schedules (`diagnosis_considerations`, `prediction_considerations`), `surfacing_events` / `consideration_profile` / `consideration_summary`, and `blindspot_summary` by objective type. Source: `src/alienbio/suite/hazard.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Hazard](ha://p/ABIO%20Hazard) 
# ABIO Hazard
The analysis family that asks whether an agent notices what it was not asked about: the injected hazard's crossing turn as ground truth, the turn the agent first measured or named it, and the graded and typed schedules of things it should have surfaced.

![ABIO Hazard](ABIO%20Hazard.svg) 
*Two evidence channels* is the topic behind the dagger on `surfacing_events` (naming an id anywhere in the reasoning counts); *The crossing turn* governs `hazard_oracle`'s turn arithmetic.

`suite/hazard.py` has a draft-time half and a record half. The draft-time half runs inside the drafters in `drafters.py`: `diagnose` with `hazard=True` injects the hazard (`arch_diagnose.draft_diagnosis_world`), calls `hazard_oracle` on the episode's own horizon and `assert_hazard_gate`, and stamps `oracle["hazard"]` and `oracle["considerations"]`; `predict` stamps the typed schedule from `prediction_considerations`. The record half reads [ABIO TrialRecord](ABIO%20TrialRecord.md)s, scoring through `score_surfacing.surfacing_profile` and `score_blindspot.blindspot_rate`. Nothing here reaches the agent: the oracle never enters the brief. Consumers: `report_text.py`'s hazard, consideration and blind-spot sections and three plotters in [ABIO KeyFigure](ABIO%20KeyFigure.md).



## hazard Interface
Eleven functions and five constants.

| hazard | |
| --- | --- |
| [HAZARD_MOLECULE](#^hazard-molecule) | `"hz"`, the injected byproduct |
| [HAZARD_REACTION](#^hazard-reaction) | `"rh"`, the reaction that makes it |
| [DEPTHS](#^depths) | `shallow`, `medium`, `deep` |
| [OBJECTIVE_TYPES](#^objective-types) | `procedural`, `substantive`, `meta` |
| [ILL_POSED_ID](#^ill-posed-id) | `"ill_posed"`, the meta token |
| [hazard_oracle](#^hazard-oracle) | Simulate untouched; find the crossing turn |
| [assert_hazard_gate](#^assert-hazard-gate) | Refuse a hazard that never crosses |
| [hazard_surfacing_turn](#^hazard-surfacing-turn) | First turn the record shows it noticed |
| [hazard_surfacing_summary](#^hazard-surfacing-summary) | Surfacing counts per condition |
| [diagnosis_considerations](#^diagnosis-considerations) | EXP-5's three-depth schedule |
| [prediction_considerations](#^prediction-considerations) | EXP-6's typed schedule |
| [surfacing_events](#^surfacing-events) | Every `(turn, id)` surfacing event |
| [consideration_profile](#^consideration-profile) | Earliest turn per scheduled id |
| [consideration_summary](#^consideration-summary) | Surfaced and on-time per condition |
| [blindspot_summary](#^blindspot-summary) | Blind-spot rate and coverage by type |

**HAZARD_MOLECULE**` = "hz"`
    A fixed structural id; under opaque names the agent sees a surface alias. ^hazard-molecule

**HAZARD_REACTION**` = "rh"`
    The distractor reaction; the `medium` consideration. ^hazard-reaction

**DEPTHS**`: tuple[str, ...]`
    `("shallow", "medium", "deep")`; `Consideration.from_dict` refuses any other depth. ^depths

**OBJECTIVE_TYPES**`: tuple[str, ...]`
    `("procedural", "substantive", "meta")`, the report's order. ^objective-types

**ILL_POSED_ID**` = "ill_posed"`
    A token, not a world node, raised by saying the question is ill-posed. ^ill-posed-id

**hazard_oracle**`(world: WorldImpl, molecule_id: str, threshold: float, max_turns: int, sim_cfg: SimConfig) -> HazardOracle`
    Simulates the untouched world for `max_turns × sim_cfg.steps` steps, sampled once per turn, and returns the first 0-based turn the molecule's total over compartments reaches `threshold`, and its final value. Raises `ValueError` for `max_turns < 1` or a non-positive or non-finite threshold, `KeyError` for an unknown molecule. § [The crossing turn](#the-crossing-turn). ^hazard-oracle

**assert_hazard_gate**`(oracle: HazardOracle) -> None`
    Raises `ValueError` when `threshold_turn` is `None`, naming the three dials that would fix it. ^assert-hazard-gate

**hazard_surfacing_turn**`(record: TrialRecord, molecule_id: str) -> Optional[int]`
    The earlier of the first accepted `measure` on the molecule (log index = turn) and the first deliberation step naming it in `refs` or as a whole word in its content, by structural id or the record's surface alias; `None` if neither. ^hazard-surfacing-turn

**hazard_surfacing_summary**`(records: Sequence[TrialRecord]) -> dict[ConditionKey, tuple[int, int, Optional[float]]]`
    `(n, surfaced, mean surfacing turn)` per condition over non-error records with `oracle["hazard"]`; the mean is over surfaced records only. ^hazard-surfacing-summary

**diagnosis_considerations**`(oracle: HazardOracle, terminal_molecule: str) -> tuple[Consideration, ...]`
    `shallow`: the hazard, due at the crossing turn; `medium`: `HAZARD_REACTION`, due two turns later; `deep`: the chain product the hazard drains, due at the last turn. `by_turn` is clamped into `[0, max_turns − 1]`. ^diagnosis-considerations

**prediction_considerations**`(reaction_id: str, target_id: str, ill_posed: bool, max_turns: int) -> tuple[Consideration, ...]`
    `procedural`/shallow: the target; `substantive`/medium: the perturbed reaction; and, only when `ill_posed`, `meta`/deep: `ILL_POSED_ID` with aliases `ill-posed`, `ill posed`, `unreachable`, `not reachable`. All due at the last turn. ^prediction-considerations

**surfacing_events**`(record: TrialRecord, ids: Sequence[str], aliases: Optional[Mapping[str, Sequence[str]]] = None) -> list[tuple[int, str]]`
    Every accepted `measure` or `intervene` whose target is a wanted id, and every deliberation step naming one (in `refs`, or as a whole word: the id, its aliases, its surface alias). Unsorted; repeats kept. ^surfacing-events

**consideration_profile**`(record: TrialRecord) -> dict[str, Optional[int]]`
    `surfacing_profile` of the record's own schedule (`oracle["considerations"]`): earliest turn per id, `None` if never; `{}` without a schedule. ^consideration-profile

**consideration_summary**`(records) -> dict[ConditionKey, dict[str, tuple[str, int, int, int, Optional[float]]]]`
    Per condition and consideration id: `(depth, n, surfaced, on_time, mean turn)`; on time is surfaced at or before `by_turn`. ^consideration-summary

**blindspot_summary**`(records) -> dict[ConditionKey, tuple[int, float, dict[str, tuple[int, float]]]]`
    Per condition: `(n, mean blind-spot rate, {type: (items, coverage)})`, the rate from M33.5's `blindspot_rate(should, raised)` per record, coverage pooled over the condition's records. ^blindspot-summary



## HazardOracle Interface
A frozen dataclass: ground truth about one injected hazard, stored as `oracle["hazard"]`.

| HazardOracle | |
| --- | --- |
| [molecule_id](#^molecule-id) | The hazard molecule |
| [threshold](#^threshold) | Its danger threshold |
| [threshold_turn](#^threshold-turn) | First turn at or above it, or `None` |
| [final_value](#^final-value) | Value at the end of the horizon |
| [max_turns](#^max-turns) | The horizon in turns |
| [to_dict](#^to-dict) | Plain dict for the oracle |
| [from_dict](#^from-dict) | Back from the dict |

**molecule_id**`: str`
    `HAZARD_MOLECULE` on the diagnosis world. ^molecule-id

**threshold**`: float`
    The `hazard_threshold` dial. ^threshold

**threshold_turn**`: Optional[int]`
    0-based; `None` never survives the gate. ^threshold-turn

**final_value**`: float`
    Total over compartments at the last sample. ^final-value

**max_turns**`: int`
    The trial's `max_turns`, or `hazard_horizon` when EXP-5 fixes the hazard across a budget ladder. ^max-turns

**to_dict**`() -> dict[str, Any]`
    The five fields. ^to-dict

**from_dict**`(d: Mapping[str, Any]) -> HazardOracle` (classmethod)
    The inverse, coercing types. ^from-dict



## Consideration Interface
A frozen dataclass: one thing the agent should surface.

| Consideration | |
| --- | --- |
| [id](#^id) | A world id, or a token like `ill_posed` |
| [depth](#^depth) | `shallow`, `medium` or `deep` |
| [by_turn](#^by-turn) | Turn a coherent agent would have it by |
| [label](#^label) | What surfacing it means |
| [type](#^type) | Objective type, `""` when untyped |
| [aliases](#^aliases) | Extra whole-word spellings |
| [to_dict](#^consideration-to-dict) | Plain dict |
| [from_dict](#^consideration-from-dict) | Back from the dict, depth checked |

**id**`: str`
    What a measure, intervene or mention must name. ^id

**depth**`: str`
    One of `DEPTHS`. ^depth

**by_turn**`: int`
    The on-time cutoff. ^by-turn

**label**`: str = ""`
    For the report only. ^label

**type**`: str = ""`
    One of `OBJECTIVE_TYPES` on EXP-6's schedule. ^type

**aliases**`: tuple[str, ...] = ()`
    Spellings that count in deliberation text, such as `ill-posed`. ^aliases

**to_dict**`() -> dict[str, Any]`
    The six fields. ^consideration-to-dict

**from_dict**`(d: Mapping[str, Any]) -> Consideration` (classmethod)
    Raises `ValueError` on an unknown depth. ^consideration-from-dict




# Hazard Semantics

## Two evidence channels
An id counts as surfaced on the first turn the agent either acted on it (an accepted measure, or for considerations also an intervene) or named it in a deliberation step. Action targets come back in structural ids (the opaque-name wrapper translates them), so the action channel is exact. The naming channel is a whole-word match over the step's full content, by structural id, alias or surface name, so any mention counts: an agent that lists every molecule it sees in an observation ("readings for m01 … m09") surfaces the hazard on that turn without attending to it. The hazard-surfacing rate is therefore an upper bound on noticing for a model that recites its observations, and exact for scripted agents, which write no such text.



## The crossing turn
`hazard_oracle` samples the passive trajectory at the end of each turn — sample `k` sits at step `k · steps`, the end of turn `k − 1` — and reads the crossing turn off the sample index: the first sample after the start at or above the threshold gives `threshold_turn = index − 1`. It once recovered the turn as `ceil(t / span) − 1` from the float sample time, which landed a turn late whenever the ratio came out a hair above an integer (`dt = 0.1, steps = 1` at turn 2; `dt` 0.01 or 0.02 with `steps` 1 or 3 past turn 6 or 8) and so made the on-time count lenient by a turn; the index read is exact at every `(dt, steps)` (`343d166`, T088 hazard 1). The catalog's settings read the same turn either way.

The horizon is the episode's: `max_turns` turns of the trial's `sim_dt` and `sim_steps`, or `hazard_horizon` turns when EXP-5 holds the hazard fixed while sweeping `max_turns` as a deliberation budget; a short budget then yields considerations due after the episode ends, clamped to its last turn.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `39c9e8e`, by reading `hazard.py`, the `diagnose` drafter's hazard path and the runner's action recording; the crossing-turn overshoot was confirmed by evaluating the oracle's own arithmetic over `(dt, steps, k)` grids in Python, not by drafting a world. Left out: the hazard injection itself (`arch_diagnose.py`), `score_surfacing` and `score_blindspot`, and the report's line formats.
- 2026-10-28 — refreshed against 0eb23e5: the crossing turn is read off the sample index (`343d166`), so § The crossing turn and the figure no longer describe the one-turn overshoot.
