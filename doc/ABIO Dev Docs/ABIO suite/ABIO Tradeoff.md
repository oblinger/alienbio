---
description: "`tradeoff`: EXP-7's conflict-resolution readout — `conflict_oracle` builds the oracle the `conflict` drafter stamps (targets, supply, closed-form frontier, priority), `component_scores` reads per-target attainment off a record, `conflict_summary` gives one `ConflictCell` per condition (mean attainment, dominant target, precedence, Pareto distance), `precedence_ladder` reads consistency across rungs. Source: `src/alienbio/suite/tradeoff.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Tradeoff](ha://p/ABIO%20Tradeoff) 
# ABIO Tradeoff
The analysis family between the conflict ladder and the record store: what the drafter puts on a conflict task's oracle, and, per condition, how far each target was reached, which one won, whether the declared priority held, and how far the achieved point sits from the frontier.

![ABIO Tradeoff](ABIO%20Tradeoff.svg) 
*Dominance and ties* is the topic behind `ConflictCell`'s `dominant` field; *The frontier distance* governs the dagger on `pareto_distance`.

`suite/tradeoff.py` is the seam between [ABIO ConflictGen](ABIO%20ConflictGen.md), which drafts the world, and M33.6's closed-form scorers in `suite/score_conflict.py` (`dominant_objective`, `favors`, `pareto_distance`, `precedence_consistency`). It writes once, at draft time, through `conflict_oracle`, which the `conflict` drafter in `drafters.py` calls; everything else reads [ABIO TrialRecord](ABIO%20TrialRecord.md)s. `_final_value` is borrowed by [ABIO Dose](ABIO%20Dose.md). Consumers: `report_text.py`'s *Conflict resolution* section and `plots.plot_conflict`. Every public name is re-exported from `alienbio.suite`.



## tradeoff Interface
Four functions and one private helper other modules import.

| tradeoff | |
| --- | --- |
| [conflict_oracle](#^conflict-oracle) | The conflict oracle for a drafted rung |
| [component_scores](#^component-scores) | Per-target attainment of one record |
| [conflict_summary](#^conflict-summary) | One `ConflictCell` per condition |
| [precedence_ladder](#^precedence-ladder) | Top-target consistency across rungs |
| [_final_value](#^final-value) | A molecule's total in a record's final state |

**conflict_oracle**`(objective: OutcomeObjective, rung: str, priority: Optional[Sequence[str]] = None) -> dict[str, Any]`
    Reads the targets off `objective.target` (`(id, goal)` or a tuple of them), recomputes the supply as `ConflictGen`'s multiplier times the sum of goals (`_SINGLE_MARGIN` for one target), samples the closed-form frontier for two targets, and returns `{rung, targets, supply, frontier, priority}`. `priority` defaults to the targets' own order and must be a permutation of their ids, else `ValueError`. ^conflict-oracle

**component_scores**`(record: TrialRecord) -> dict[str, float]`
    `min(final / goal, 1.0)` per target, `0.0` for a non-positive goal; `{}` without a conflict oracle or a final state. Raises `KeyError` when a target id is not in the final state. ^component-scores

**conflict_summary**`(records: Sequence[TrialRecord]) -> dict[ConditionKey, ConflictCell]`
    Non-error records carrying `oracle["conflict"]`, bucketed on `bucket_key`. The oracle (targets, priority, frontier) is read from the bucket's first record. ^conflict-summary

**precedence_ladder**`(summary: Mapping[ConditionKey, ConflictCell]) -> dict[ConditionKey, tuple[tuple[str, ...], float]]`
    Groups two-target cells that differ only in `rung`, orders them by `RUNGS`, ranks each cell's targets best-first by mean attainment (ties by id), and returns the rungs present and `precedence_consistency` of those rankings: the share of adjacent rung pairs with the same top target. A single rung is vacuously `1.0`. ^precedence-ladder

**_final_value**`(record: TrialRecord, molecule_id: str) -> Optional[float]`
    The molecule summed over every compartment of `final_state`, or `None` when no compartment carries it. ^final-value



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
    Mean `pareto_distance` of the achieved `(V1, V2)` to the oracle's frontier; `None` without a frontier. ^mean-pareto-distance




# Tradeoff Semantics

## Attainment
Two measures of one target live side by side. The world's own objective (ConflictGen § The objective) scores a target `1/(1 + deficit)` below its goal, in absolute units, and the trial's `objective_score` is the min over targets. `component_scores` here is the ratio `final / goal`, capped at 1. A target 2 short of a goal of 10 is `0.33` to the objective and `0.8` here. The report's per-target columns and the dominance read use the ratio; `objective_score` on the same records uses the falloff.



## Dominance and ties
Per record, the winner is `dominant_objective`'s argmax, kept only when `favors` says it beats every rival strictly; otherwise the record is a tie. A balanced split that meets both targets, or misses both by the same amount, is a tie and expresses no preference, so on `compatible` (both met) and on the default `latent` split every record is a tie. `precedence_ladder` ranks by mean attainment and breaks ties by id, so a rung where both targets average `1.0` contributes `root/crux/sink_a_in` as its top target by spelling, and its consistency with the neighbouring rungs depends on that.



## The frontier distance
`pareto_distance` is the minimum Euclidean distance to any of the frontier's points, and `conflict_oracle` stores 11 samples of the line `V1 + V2 = S`, not the segment. A point on the line between two samples reads the distance to the nearer sample: on `compatible` (`S = 80`, samples 8 apart) `(36, 44)` lies exactly on the frontier and reads `5.66`; `(40, 40)` reads `0`. The quantization error is up to `S/10 · √2 / 2`, so `mean_pareto_distance` carries a floor that depends on where the agent's split lands relative to the sample grid.

The supply in the oracle is recomputed from `ConflictGen`'s private constants, not read off the world, so the frontier is right only while the two modules agree on `_S_MULTIPLIER` and `_SINGLE_MARGIN`.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `84a0776`. The frontier distances were computed with `pareto_distance` on `closed_form_frontier(80)`, no spend; the rest is by reading `tradeoff.py`, `score_conflict.py` and the `conflict` drafter. Left out: the four M33.6 scorers' own interface, the report's line format and `plots.plot_conflict`.
