---
description: "`delta`: EXP-8's paired-divergence readout — `delta_pairs` matches each `match` record with its `mismatch` twin by condition and pair id, `delta_summary` reduces the pairs per condition to the gap, the prior-following and world-tracking fractions and the mean final-state divergence; `DeltaPair`, `DeltaCell`, `final_state_divergence`. Source: `src/alienbio/suite/delta.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Delta](ha://p/ABIO%20Delta) 
# ABIO Delta
The analysis family that pairs EXP-8's twin records and reads how much a fixed agent's score depends on which of the two worlds it was in.

![ABIO Delta](ABIO%20Delta.svg) 
*Pairing* is the topic behind the `(condition, pair)` slot in the middle (a twin is found by both, never by order); *What the divergence measures* governs the dagger on `final_state_divergence`.

`suite/delta.py` reads records only. The pair it reads is drafted by [ABIO DeltaGen](ABIO%20DeltaGen.md); the `delta` drafter in `drafters.py` stamps `oracle["delta"]` (`arm`, `pair` = the shared world seed, `true_driver`, `conventional`, `candidates`, `target`) on every task, and `matched_dials: [arm]` in the spec gives both arms one seed. Records are [ABIO TrialRecord](ABIO%20TrialRecord.md)s. Consumers: `report_text.py`'s *Delta* section and `plots.plot_delta`, which drops cells with no pair. Every public name is re-exported from `alienbio.suite`.



## delta Interface
Three functions and the arm names.

| delta | |
| --- | --- |
| [ARMS](#^arms) | `("match", "mismatch")` |
| [delta_pairs](#^delta-pairs) | Records to matched pairs per condition |
| [delta_summary](#^delta-summary) | Pairs to one `DeltaCell` per condition |
| [final_state_divergence](#^final-state-divergence) | Bounded distance between two final states |

**ARMS**`: tuple[str, ...] = ("match", "mismatch")`
    The only arm values `delta_pairs` accepts. ^arms

**delta_pairs**`(records: Iterable[TrialRecord]) -> tuple[dict[ConditionKey, list[DeltaPair]], dict[ConditionKey, int]]`
    Keeps non-error records carrying `oracle["delta"]`; keys each on its `bucket_key` without `arm` (the arm falls back to the oracle's when not swept) and slots it by `oracle["pair"]`. Returns the complete pairs per condition, sorted by pair id as a string, and the count of slots holding one arm only. Raises `ValueError` on an arm outside `ARMS` and when two records of one arm share a condition and pair id. ^delta-pairs

**delta_summary**`(records: Iterable[TrialRecord]) -> dict[ConditionKey, DeltaCell]`
    One cell per condition that has any delta record. A condition whose records formed no complete pair still gets a cell, with `n_pairs = 0` and every mean `nan`, so it shows as a missing row rather than vanishing (T054 #7). ^delta-summary

**final_state_divergence**`(a: TrialRecord, b: TrialRecord) -> float`
    Sums each record's `final_state` per molecule over compartments, takes the L2 distance `d` over the molecule ids both share, and returns `d / (d + 1)`, in `[0, 1)`. The store-side twin of `score_divergence.normalized_divergence`, which works on timelines. ^final-state-divergence



## DeltaPair Interface
A frozen dataclass: one matched pair.

| DeltaPair | |
| --- | --- |
| [pair](#^pair) | The pair id, the shared world seed |
| [match_score](#^match-score) | Objective score on `W_match` |
| [mismatch_score](#^mismatch-score) | Objective score on `W_mismatch` |
| [state_divergence](#^state-divergence) | `final_state_divergence` of the two |

**pair**`: Any`
    `oracle["pair"]`, the seed value both arms drew from. ^pair

**match_score**`: float`
    The `match` record's `objective_score`. ^match-score

**mismatch_score**`: float`
    The `mismatch` record's. ^mismatch-score

**state_divergence**`: float`
    § [What the divergence measures](#what-the-divergence-measures). ^state-divergence



## DeltaCell Interface
A frozen dataclass: EXP-8's numbers for one condition (every swept dial but `arm`).

| DeltaCell | |
| --- | --- |
| [n_pairs](#^n-pairs) | Complete pairs |
| [n_unpaired](#^n-unpaired) | Slots with one arm only |
| [mean_match](#^mean-match) | Mean score on `match` |
| [mean_mismatch](#^mean-mismatch) | Mean score on `mismatch` |
| [gap](#^gap) | `mean_match − mean_mismatch` |
| [prior_following_fraction](#^prior-following-fraction) | Right on match, wrong on mismatch |
| [world_tracking_fraction](#^world-tracking-fraction) | Right on both |
| [mean_state_divergence](#^mean-state-divergence) | Mean of the pairs' divergences |

**n_pairs**`: int`
    Pairs averaged. ^n-pairs

**n_unpaired**`: int`
    Records skipped for want of a twin, usually because the partner errored. ^n-unpaired

**mean_match**`: float`
    Mean `match_score`. ^mean-match

**mean_mismatch**`: float`
    Mean `mismatch_score`. ^mean-mismatch

**gap**`: float`
    Baseline-disposition sensitivity, EXP-8's measure: the scripted heuristic agent gaps `+1.0`, the null `0.0`. ^gap

**prior_following_fraction**`: float`
    Share of pairs with `match_score ≥ 1.0` and `mismatch_score ≤ 0.0`. ^prior-following-fraction

**world_tracking_fraction**`: float`
    Share with both scores `≥ 1.0`. ^world-tracking-fraction

**mean_state_divergence**`: float`
    Mean `state_divergence`. ^mean-state-divergence




# Delta Semantics

## Pairing
A twin is found by `(condition without arm, oracle["pair"])`, never by record order, so a resumed or reordered `records.jsonl` pairs the same way. Every other swept dial must match, so a twin under a different agent or a different value of any axis is a different condition. The pair id is the world seed the drafter received; with `matched_dials: [arm]` both arms of one trial index receive the same one, and different trial indices receive different ones. Without `matched_dials` the arms draw different seeds and nothing pairs: every condition shows `n_pairs = 0` and its records as unpaired.

The two fractions assume a 0/1 score, which the `node_id` grader gives. A pair scoring partially on either arm counts in neither fraction but still moves the means and the gap. The two fractions and the remainder (wrong on match, or right only on mismatch) partition the pairs only for 0/1 scores.



## What the divergence measures
The distance is taken over the full final state of both worlds, and the two worlds differ by construction: in `W_mismatch` the decoy `source_a` accumulates (it drains at `k_sink` alone), while in `W_match` both sources settle low ([ABIO DeltaGen](ABIO%20DeltaGen.md)). At the generator's 20 s horizon the untouched states alone are about 61 apart (`T` 4.88 vs 0.67, `source_a` 2.44 vs 63.3, `source_b` 1.0 vs 0.33, with `k_sink_b = 1.0` since `719261e`), which maps to `0.98`. The module docstring and the report's Delta section now say the column measures the worlds (since `343d166`). An agent that only measures and commits leaves the states untouched, so its divergence is the worlds' own, and any agent's is that plus whatever its interventions add. The column is near 1 for every agent on the default pair and separates agents only through interventions large against those levels.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `f80674d`. The divergence figure is computed from the generator's own `oracle` levels at its 20 s horizon ([ABIO DeltaGen](ABIO%20DeltaGen.md)), not from an EXP-8 run, whose episode is shorter; the claim that it sits near 1 for any non-intervening agent rests on that arithmetic. Left out: the report's line format and `plots.plot_delta`.
- 2026-10-28 — refreshed against 0eb23e5: the untouched-pair levels recomputed for `k_sink_b = 1.0` (`719261e`; still ≈ 0.98), and the docstring/report caveat (`343d166`) noted.
