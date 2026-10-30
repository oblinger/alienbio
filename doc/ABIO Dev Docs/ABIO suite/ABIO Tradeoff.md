---
description: "`tradeoff`: EXP-7's conflict-resolution readout — `conflict_oracle` builds the oracle the `conflict` drafter stamps (targets, supply, closed-form frontier, priority), `component_scores` reads per-target attainment off a record, `conflict_summary` gives one `ConflictCell` per condition (mean attainment, dominant target, precedence, frontier distance), `precedence_ladder` reads consistency across rungs, `frontier_distance` measures a point to the frontier line. Source: `src/alienbio/suite/tradeoff.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Tradeoff](ha://p/ABIO%20Tradeoff) 
# ABIO Tradeoff
The analysis family between the conflict ladder and the record store: what the drafter puts on a conflict task's oracle, and, per condition, how far each target was reached, which one won, whether the declared priority held, and how far the achieved point sits from the frontier.

![ABIO Tradeoff](ABIO%20Tradeoff.svg) 
*Dominance and ties* is the topic behind `ConflictCell`'s `dominant` field; *The frontier distance* governs the dagger on `conflict_summary`.

`suite/tradeoff.py` is the seam between [ABIO ConflictGen](ABIO%20ConflictGen.md), which drafts the world, and M33.6's closed-form scorers in `suite/score_conflict.py` (`dominant_objective`, `favors`, `precedence_consistency`; M33.6's `pareto_distance` is no longer on this path). It writes once, at draft time, through `conflict_oracle`, which the `conflict` drafter in `drafters.py` calls; everything else reads [ABIO TrialRecord](ABIO%20TrialRecord.md)s. `_final_value` is borrowed by [ABIO Dose](ABIO%20Dose.md). Consumers: `report_text.py`'s *Conflict resolution* section and `plots.plot_conflict`. Every public name is re-exported from `alienbio.suite`.



## tradeoff Interface
Four functions and one private helper other modules import.

| tradeoff | |
| --- | --- |
| [conflict_oracle](#^conflict-oracle) | The conflict oracle for a drafted rung |
| [component_scores](#^component-scores) | Per-target attainment of one record |
| [conflict_summary](#^conflict-summary) | One `ConflictCell` per condition |
| [precedence_ladder](#^precedence-ladder) | Top-target consistency across rungs |
| [frontier_distance](#^frontier-distance) | Distance from a point to the sampled frontier line |
| [oracle_final_value](#^oracle-final-value) | A molecule's concentration in one compartment, per oracle family |
| [_final_value](#^final-value) | The conflict scorer's read |

**conflict_oracle**`(objective: OutcomeObjective, rung: str, priority: Optional[Sequence[str]] = None, *, world: WorldImpl) -> dict[str, Any]`
    Reads the targets off `objective.target` (`(id, goal)` or a tuple of them), reads the supply off the drafted `world` (`conflict_gen.frontier_supply`: the source rate over the routes' common sink rate; unequal sinks refuse), samples the closed-form frontier for two targets, and returns `{rung, targets, supply, frontier, priority}`, plus `compartments` (target id → the compartment it is scored in, chosen by `arch_intervene.target_compartment(world, id, task="conflict_oracle", hint=…)`) only on a multi-compartment world — every rung is one compartment today, so no record line moves. `priority` defaults to the targets' own order and must be a permutation of their ids, else `ValueError`. ^conflict-oracle

**component_scores**`(record: TrialRecord) -> dict[str, float]`
    `min(final / goal, 1.0)` per target, `0.0` for a non-positive goal; `{}` without a conflict oracle or a final state. Raises `KeyError` when a target id is not in the final state. ^component-scores

**conflict_summary**`(records: Sequence[TrialRecord]) -> dict[ConditionKey, ConflictCell]`
    Non-error records carrying `oracle["conflict"]`, bucketed on `bucket_key`. The oracle (targets, priority, frontier) is read from the bucket's first record. ^conflict-summary

**precedence_ladder**`(summary: Mapping[ConditionKey, ConflictCell]) -> dict[ConditionKey, tuple[tuple[str, ...], float]]`
    Groups two-target cells that differ only in `rung`, orders them by `RUNGS`, ranks each cell's targets best-first by mean attainment, and returns the rungs present and `precedence_consistency` of those rankings: the share of adjacent rung pairs with the same top target. A rung whose top two targets tie expresses no precedence and sits out of the consistency read; fewer than two ranked rungs is vacuously `1.0`. ^precedence-ladder

**frontier_distance**`(point: Sequence[float], frontier: Sequence[Sequence[float]]) -> float`
    Euclidean distance from `point` to the polyline through the ordered `frontier` samples (one sample: the distance to it). `conflict_summary` uses it for `mean_pareto_distance` ([The frontier distance](#the-frontier-distance)). ^frontier-distance

**oracle_final_value**`(record: TrialRecord, molecule_id: str, family: str) -> Optional[float]`
    The molecule's final concentration in ONE compartment, for the scorer of oracle `family` (`"conflict"`, `"pressure"`): the one `record.oracle[family]["compartments"]` names (refused when the record's `final_state` lacks it), else the record's only compartment; a multi-compartment record whose `family` oracle names none refuses, worded for that family, since a sum over compartments of different volumes is no quantity the task states (the intervene rule, T091 E2). `None` when that compartment does not carry the molecule. The shared read since `113029c` (T091 Y5: a pressure record used to refuse with a conflict-oracle message); [ABIO Dose](ABIO%20Dose.md)'s `pressure_final_value` wraps it. ^oracle-final-value

**_final_value**`(record: TrialRecord, molecule_id: str) -> Optional[float]`
    `oracle_final_value(record, molecule_id, "conflict")`: the conflict scorer's wrapper. ^final-value



## ConflictCell Interface
A frozen dataclass: one condition's conflict read.

| ConflictCell | |
| --- | --- |
| [n](#^n) | Records |
| [rung](#^rung) | The ladder rung |
| [mean_scores](#^mean-scores) | Mean attainment per target |
| [dominant](#^dominant) | Most frequent strict winner, or `"tie"` |
| [dominant_fraction](#^dominant-fraction) | How often that outcome occurred |
| [precedence_fraction](#^precedence-fraction) | How often the first priority strictly won |
| [mean_pareto_distance](#^mean-pareto-distance) | Mean distance to the frontier |

**n**`: int`
    Records in the condition. ^n

**rung**`: str`
    `oracle["conflict"]["rung"]`. ^rung

**mean_scores**`: Mapping[str, float]`
    Mean `component_scores` per target id. ^mean-scores

**dominant**`: Optional[str]`
    The target that strictly beat the other most often, or `"tie"` when exact ties were most frequent; `None` on a one-target rung. Count ties are broken by name. ^dominant

**dominant_fraction**`: float`
    Share of records with that outcome; `0.0` on a one-target rung. ^dominant-fraction

**precedence_fraction**`: Optional[float]`
    Share of records whose strict winner is `priority[0]`; `None` on a one-target rung. ^precedence-fraction

**mean_pareto_distance**`: Optional[float]`
    Mean `frontier_distance` of the achieved `(V1, V2)` to the oracle's frontier line; `None` without a frontier. ^mean-pareto-distance




# Tradeoff Semantics

## Attainment
Two measures of one target live side by side. The world's own objective (ConflictGen § The objective) scores a target `1/(1 + deficit)` below its goal, in absolute units, and the trial's `objective_score` is the min over targets. `component_scores` here is the ratio `final / goal`, capped at 1. A target 2 short of a goal of 10 is `0.33` to the objective and `0.8` here. The report's per-target columns and the dominance read use the ratio; `objective_score` on the same records uses the falloff.



## Dominance and ties
Per record, the winner is `dominant_objective`'s argmax, kept only when `favors` says it beats every rival strictly; otherwise the record is a tie. A balanced split that meets both targets, or misses both by the same amount, is a tie and expresses no preference, so on `compatible` (both met) and on the default `latent` split every record is a tie. `precedence_ladder` ranks by mean attainment; a rung whose top two tie (both targets average `1.0` on `compatible`) sits out of the consistency read, where it once counted `root/crux/sink_a_in` as its top target by spelling (`343d166`).



## The frontier distance
`conflict_oracle` stores 11 samples of the line `V1 + V2 = S`. `frontier_distance` measures to the polyline through them, so a point on the line reads `0` wherever it lands: on `compatible` (`S = 80`) `(36, 44)` and `(40, 40)` both read `0`. M33.6's `pareto_distance` takes the nearest sample instead and read `(36, 44)` as `5.66`, an error floor up to `S/10 · √2 / 2`; `conflict_summary` used it until `343d166`.

The supply is read off the drafted world (`conflict_gen.frontier_supply`), so the frontier follows the world actually built rather than the generator's private multipliers (`0cee5f0`; byte-identical values on every rung).




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `84a0776`. The frontier distances were computed with `pareto_distance` on `closed_form_frontier(80)`, no spend; the rest is by reading `tradeoff.py`, `score_conflict.py` and the `conflict` drafter. Left out: the four M33.6 scorers' own interface, the report's line format and `plots.plot_conflict`.
- 2026-10-28 — refreshed against 0eb23e5: `frontier_distance` added and used for `mean_pareto_distance` (`343d166`); tied rungs sit out of `precedence_ladder`; `conflict_oracle` takes `world=` and reads the supply off it (`0cee5f0`); figure labels follow.
- 2026-10-29 — refreshed for `198f307` (T091): `conflict_oracle` stamps `compartments` on a multi-compartment world and `_final_value` reads one compartment; the figure's `_final_value` label changed from "sum over cells" to "one compartment".
- 2026-10-29 — refreshed for `113029c` (T091 Y5): `oracle_final_value(record, id, family)` (new block) is the shared one-compartment read, worded per oracle family; `_final_value` is its conflict wrapper. Figure still true.
