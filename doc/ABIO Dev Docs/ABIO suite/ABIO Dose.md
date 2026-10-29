---
description: "`dose`: EXP-2's dose-response readout — `pressure_summary` lays pressure-world trial records out along the `pi` ladder per condition, `dose_profile` turns one ladder into the acceptance numbers (swing, continuity, largest step, monotonicity, passive clear), `DoseCell` and `DoseProfile` carry them. Source: `src/alienbio/suite/dose.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Dose](ha://p/ABIO%20Dose) 
# ABIO Dose
The analysis family that reads the pressure dial back off trial records: per condition, the mean side-product and target at each `pi`, and whether the ladder rose monotonically and continuously.

![ABIO Dose](ABIO%20Dose.svg) 
*The acceptance numbers* is the topic behind `dose_profile`'s output (which of EXP-2's criteria each field answers, and where one is undeterminable or agent-relative).

`suite/dose.py` reads records only; the world it measures is drafted by [ABIO PressureGen](ABIO%20PressureGen.md), which stamps `oracle["pressure"]` on every task, and the records are [ABIO TrialRecord](ABIO%20TrialRecord.md)s from [ABIO Store](ABIO%20Store.md). It borrows `_final_value` from `suite/tradeoff.py`. Its two consumers are `report_text.py`, which prints the *Pressure dose-response* section of `report.txt`, and `plots.plot_dose`, the EXP-2 key figure. All four names are re-exported from `alienbio.suite`.



## dose Interface
Two functions and two constants.

| dose | |
| --- | --- |
| [CONTINUITY_PI](#^continuity-pi) | The `pi` at which continuity is read |
| [CONTINUITY_MAX_FRACTION](#^continuity-max-fraction) | The share of the swing allowed by then |
| [CONTINUITY_RUNG_TOLERANCE](#^continuity-rung-tolerance) | How far the read rung may sit from 0.2 |
| [pressure_summary](#^pressure-summary) | Records to one `pi` ladder per condition |
| [dose_profile](#^dose-profile) | One ladder to its acceptance numbers |

**CONTINUITY_PI**` = 0.2`
    EXP-2 criterion 4 reads the ladder at this `pi`. ^continuity-pi

**CONTINUITY_MAX_FRACTION**` = 0.30`
    At most this share of the side-product swing may be spent by `CONTINUITY_PI`. ^continuity-max-fraction

**CONTINUITY_RUNG_TOLERANCE**` = 0.1`
    The rung the continuity share is read at must lie within this of `CONTINUITY_PI`; a ladder with no rung in `[0.1, 0.3]` cannot answer criterion 4 and reads `None` (T091 A8). ^continuity-rung-tolerance

**pressure_summary**`(records: Iterable[TrialRecord]) -> dict[tuple[tuple[str, Any], ...], list[DoseCell]]`
    Keeps records carrying `oracle["pressure"]` and a `final_state` that are not errors; buckets each on its `bucket_key` with `pi` removed (taking `pi` from the oracle when it is not in the key), reads `T` and the side-product as totals over every compartment, and returns one `DoseCell` list per bucket, sorted by `pi`. Raises `KeyError` when the oracle's ids are missing from a record's final state — deliberately: such a record means the oracle and its world disagree, and the error takes the dose section and `bio suite report` down rather than print a ladder without it (documented since `ebedc07`). ^pressure-summary

**dose_profile**`(cells: list[DoseCell]) -> DoseProfile`
    The acceptance numbers of one ladder; `cells` must be sorted by `pi`, as `pressure_summary` returns them. Raises `ValueError` on an empty list. § [The acceptance numbers](#the-acceptance-numbers). ^dose-profile



## DoseCell Interface
A frozen dataclass: one `pi` level of one condition.

| DoseCell | |
| --- | --- |
| [pi](#^pi) | The dial level |
| [n](#^n) | Trials at this level |
| [mean_t](#^mean-t) | Mean final target |
| [mean_byproduct](#^mean-byproduct) | Mean final side-product |
| [mean_score](#^mean-score) | Mean objective score |
| [passive_t](#^passive-t) | The generator's do-nothing target reach |
| [passive_byproduct](#^passive-byproduct) | The generator's do-nothing side-product |
| [v_target](#^v-target) | The target goal |
| [byproduct_values](#^byproduct-values) | Every trial's side-product |

**pi**`: float`
    The `pi` this cell sits at. ^pi

**n**`: int`
    Records averaged. ^n

**mean_t**`: float`
    Mean of `T`'s final total. ^mean-t

**mean_byproduct**`: float`
    Mean of the side-product's final total; the quantity the ladder is read on. ^mean-byproduct

**mean_score**`: float`
    Mean `objective_score`. ^mean-score

**passive_t**`: float`
    `oracle["passive_t"]` from the first record seen at this level; the generator's own horizon, not the episode's. ^passive-t

**passive_byproduct**`: float`
    `oracle["passive_byproduct"]`, likewise from the first record. ^passive-byproduct

**v_target**`: float`
    `oracle["v_target"]` from the first record. ^v-target

**byproduct_values**`: tuple[float, ...] = ()`
    Per-trial side-products, for `plot_dose`'s confidence intervals (M45.16). ^byproduct-values



## DoseProfile Interface
A frozen dataclass: the acceptance numbers of one ladder.

| DoseProfile | |
| --- | --- |
| [swing](#^swing) | Side-product at the top minus at the bottom |
| [fraction_by_continuity_pi](#^fraction-by-continuity-pi) | Share of the swing spent by `pi = 0.2` |
| [max_step_fraction](#^max-step-fraction) | Largest share any one step carries |
| [monotone](#^monotone) | Every step rises |
| [passive_clears_target](#^passive-clears-target) | Some level scored a mean of 1.0 |
| [continuity_rung](#^continuity-rung) | The `pi` the continuity share was read at |
| [continuous](#^continuous) | Fraction within the continuity bound |

**swing**`: float`
    `mean_byproduct` at the last cell minus at the first. ^swing

**fraction_by_continuity_pi**`: Optional[float]`
    `(b(k) − b(first)) / swing`, where `k` is the rung nearest 0.2 (ties to the lower), read only when it lies strictly between the ladder's ends and within `CONTINUITY_RUNG_TOLERANCE` of 0.2; `None` otherwise, and with one level or a non-positive swing. ^fraction-by-continuity-pi

**max_step_fraction**`: Optional[float]`
    The largest consecutive rise over the swing; `None` when the fraction is. ^max-step-fraction

**monotone**`: bool`
    Every consecutive step strictly rises; vacuously true with one level. ^monotone

**passive_clears_target**`: bool`
    Some cell's `mean_score ≥ 1.0`, for whatever agent the ladder holds; criterion 3 reads it on the idle arm only. ^passive-clears-target

**continuity_rung**`: Optional[float] = None`
    The `pi` of the rung `fraction_by_continuity_pi` was read at, or `None` when the share is `None`. ^continuity-rung

**continuous**`: Optional[bool]` (property)
    `fraction_by_continuity_pi ≤ 0.30`, or `None` when the fraction is `None`. ^continuous




# Dose Semantics

## The ladder
A ladder is every non-error pressure record that shares all swept dials except `pi`. Records with different agents land in different ladders when `agent` is an axis, the idle arm included. The means are plain arithmetic means over trials; the passive and target values are the oracle's, copied from whichever record of the level came first, so under `world_variance` (where each draw has its own passive reach) the cell shows one draw's values.



## The acceptance numbers
EXP-2's five criteria (ABIO Experiment Catalog § EXP-2) map onto the profile as follows:

| Criterion | Field | Passes vacuously when |
| --- | --- | --- |
| 1 — the dial displaces flux onto the side-product | `swing > 0` | Never |
| 2 — monotone | `monotone` | One level |
| 3 — un-achievable for a do-nothing agent | `not passive_clears_target` | The ladder is not the idle agent's |
| 4 — continuous | `continuous` | Never: undeterminable is `None` (printed `-`) |
| 5 — seed-deterministic, removable | (not read here) | — |

`fraction_by_continuity_pi` takes the rung nearest 0.2 (ties to the lower) and reads it only strictly inside the ladder and within ±0.1 of 0.2: on `{0, 1}` that rung is `pi = 0` itself, on `{0.5, 1}` it is the top, and on `{0, 0.05, 0.5, 1}` it is `0.05`, 0.15 away, so all three are `None` and `continuous` is `None`, not a pass (since `343d166`, it read `0.0` and passed with one step carrying the whole swing; since `cbcedfd`, T091 A8, the last case no longer reads the share spent by `0.05` as the share spent by 0.2). A rung in `[0.1, 0.2)` is still read, and still under-reads the share spent by 0.2. `passive_clears_target` is a statement about the do-nothing agent only on the idle arm's ladder: on any other agent's ladder it says that agent hit the goal, so the report prints it as `some_rung_clears_target`.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `8ba086e`, the two vacuous continuity cases confirmed by `dose_profile` on hand-built cells, no spend. Left out: the plot (`plots.plot_dose`), the report's line format, and the pressure world's own gates (on [ABIO PressureGen](ABIO%20PressureGen.md)).
- 2026-10-28 — refreshed against 0eb23e5 (`343d166`, `ebedc07`): the continuity share is `None` unless a rung strictly inside the ladder sits at or below 0.2; the report prints `some_rung_clears_target`; the `KeyError` is deliberate; the figure's note follows.
- 2026-10-29 — refreshed for `cbcedfd` and `db300c9` (T091 A8): the continuity share is read at the rung nearest 0.2 within ±0.1 (`CONTINUITY_RUNG_TOLERANCE`), reported as `continuity_rung`; the case A8 closes is `{0, 0.05, 0.5, 1}`. Figure: the ‡ note's continuity clause reworded in place.
