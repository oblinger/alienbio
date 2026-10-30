---
description: "`census`: the M45.16 per-condition census B2's pre-registration reports — `census_summary` gives engagement per condition (accepted intervenes, the disengaged rate, turns, trace length, illegal actions), `outcome_distribution` gives the distribution of one scalar per condition (quantiles, dispersion, CI, delta against the idle twin), `pressure_byproduct` is the default scalar. Source: `src/alienbio/suite/census.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Census](ha://p/ABIO%20Census) 
# ABIO Census
The analysis family that reports how engaged each arm was and how its outcome was spread, not only its mean: the census B2's pre-registration asks of every experiment.

![ABIO Census](ABIO%20Census.svg) 
*Engagement* is the topic behind the dagger on `disengaged_rate` (only trials offered a lever count); *The idle twin* governs the dotted match between an arm and its idle condition.

`suite/census.py` reads [ABIO TrialRecord](ABIO%20TrialRecord.md)s only, so it reads the same on a reloaded store. The idle twin exists because `ExperimentSpec(idle_baseline=True)` adds an `agent` axis `(agent, "idle")` under matched world seeds ([ABIO ExperimentSpec](ABIO%20ExperimentSpec.md)). The confidence interval is `stats_summary.mean_confidence_interval`. Its one consumer is `report_text.py`, which prints the *Census* and *Outcome distribution* sections of every run's `report.txt`. Nothing here is re-exported from `alienbio.suite`.



## census Interface
Three functions.

| census | |
| --- | --- |
| [census_summary](#^census-summary) | Engagement per condition |
| [outcome_distribution](#^outcome-distribution) | One scalar's distribution per condition |
| [pressure_byproduct](#^pressure-byproduct) | The default scalar: the side-product |

**census_summary**`(records: Iterable[TrialRecord]) -> dict[ConditionKey, CensusCell]`
    Every non-error record bucketed on `bucket_key`; no oracle filter, so every run gets a census. ^census-summary

**outcome_distribution**`(records: Iterable[TrialRecord], read: Callable[[TrialRecord], Optional[float]] = pressure_byproduct) -> dict[ConditionKey, OutcomeDistribution]`
    Applies `read` to every non-error record, keeps the values that are not `None`, and summarizes them per condition; a condition with no readable record is absent. The idle twin of a condition is the one with the same dials and `agent == "idle"`. ^outcome-distribution

**pressure_byproduct**`(record: TrialRecord) -> Optional[float]`
    `None` without `oracle["pressure"]` or a final state; else the side-product's final value in the one compartment Dose reads (`dose.pressure_final_value`: the compartment `oracle["pressure"]["compartments"]` names, else the record's only one); a multi-compartment record naming none refuses (T091 Y5). ^pressure-byproduct



## CensusCell Interface
A frozen dataclass: one condition's engagement.

| CensusCell | |
| --- | --- |
| [n](#^n) | Records |
| [mean_intervenes](#^mean-intervenes) | Accepted intervenes per trial |
| [disengaged_rate](#^disengaged-rate) | Share with no accepted intervene |
| [mean_turns](#^mean-turns) | Turns executed |
| [mean_trace_steps](#^mean-trace-steps) | Deliberation-trace length |
| [mean_illegal](#^mean-illegal) | Illegal actions per trial |

**n**`: int`
    Non-error records. ^n

**mean_intervenes**`: float`
    Mean count of accepted `intervene` actions over the whole log. ^mean-intervenes

**disengaged_rate**`: float`
    Share with none, over the trials whose brief offered a lever; `nan` when none did. A disengaged trial is its own category, never counted as refraining. § [Engagement](#engagement). ^disengaged-rate

**mean_turns**`: float`
    Mean `turns`. ^mean-turns

**mean_trace_steps**`: float`
    Mean number of deliberation steps; zero for scripted agents that record none. ^mean-trace-steps

**mean_illegal**`: float`
    Mean `illegal_actions`. ^mean-illegal



## OutcomeDistribution Interface
A frozen dataclass: one condition's distribution of the read scalar.

| OutcomeDistribution | |
| --- | --- |
| [n](#^outcome-n) | Readable records |
| [mean](#^mean) | Mean value |
| [std](#^std) | Population standard deviation |
| [quantiles](#^quantiles) | Min, p25, median, p75, max |
| [ci](#^ci) | Confidence interval on the mean |
| [idle_delta](#^idle-delta) | Mean minus the idle twin's mean |

**n**`: int`
    Records `read` returned a value for. ^outcome-n

**mean**`: float`
    Arithmetic mean. ^mean

**std**`: float`
    `pstdev`, `0.0` for one value; at fixed seeds it is the run's repeatability. ^std

**quantiles**`: tuple[float, float, float, float, float]`
    `statistics.quantiles(n=4, method="inclusive")` between the min and max; one value repeats five times. ^quantiles

**ci**`: tuple[float, float]`
    `mean_confidence_interval`, or `(mean, mean)` for one value. ^ci

**idle_delta**`: Optional[float]`
    `mean − twin mean` for a non-idle agent whose idle twin was read; `None` for the idle arm itself, without an `agent` axis, or without a twin. ^idle-delta




# Census Semantics

## Engagement
Engagement is counted in accepted interventions, which fits the pressure family, where the agent's only levers are feeds. On a task with no levers it would be meaningless: the `delta`, `diagnose`, `predict` and `discover` drafters ask for an answer and specs such as EXP-8 declare `levers=[]`. So `disengaged_rate` counts only trials whose brief offered a lever (a record without a brief counts as offering one), and is `nan` — printed `-` in the census — when no trial in the condition was offered one (since `343d166`).



## The idle twin
`outcome_distribution` keys twins by every swept dial except `agent`, so the match is exact only when the idle arm and the agent share every other dial; `idle_baseline` builds exactly that grid. `pressure_byproduct` reads the side-product through [ABIO Dose](ABIO%20Dose.md)'s `pressure_final_value`, the same one-compartment read the dose table uses, so the two agree on any world (since `343d166`; it read the first compartment before, then a sum, and since `113029c` the compartment the oracle names or the only one). Every shipped pressure-family world is one compartment.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `6609ed2`, by reading `census.py`, its one caller in `report_text.py` and the idle-arm construction in `spec.py`; nothing was run. Left out: `mean_confidence_interval`'s method (`stats_summary.py`) and the report's line format.
- 2026-10-28 — refreshed against 0eb23e5 (`343d166`): `disengaged_rate` is over lever-offered trials (`nan` when none), `pressure_byproduct` sums compartments; figure labels follow.
- 2026-10-29 — refreshed for `113029c` (T091 Y5): `pressure_byproduct` reads the one compartment Dose reads (`dose.pressure_final_value`) and refuses a multi-compartment record naming none; the summed reading is gone. Figure still true.
