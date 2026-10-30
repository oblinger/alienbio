---
description: "`degradation`: EXP-10's degradation-under-time-pressure readout — `trial_degradation` reads one record's pre-commit log, deliberation and terminal reason into nine shortcut flags, `degradation_summary` gives one `DegradationCell` per condition, `degradation_ladder` lays cells from the loosest budget to the tightest and names the accuracy cliff. Source: `src/alienbio/suite/degradation.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Degradation](ha://p/ABIO%20Degradation) 
# ABIO Degradation
The analysis family that asks which shortcuts appear as room to think shrinks: per trial, how much was measured and perturbed before the commit and whether the agent committed early, skipped verification, narrowed or reverted; per condition, the rates; along the budget axis, where accuracy falls off.

![ABIO Degradation](ABIO%20Degradation.svg) 
*The per-trial flags* is the topic behind the nine fields of `TrialDegradation` (the dagger marks the two whose rules were narrowed so they no longer misread a careful agent); *The ladder* governs the budget ordering and the cliff.

`suite/degradation.py` reads records only. It is M33.9's `registry.scoring.degradation_patterns` asked of a [ABIO TrialRecord](ABIO%20TrialRecord.md) instead of the legacy `Trace`, plus EXP-10's premature commitment and skipped verification. It imports `Budget` from the runner ([ABIO Runner](ABIO%20Runner.md)) so a budget level is read exactly as a trial reads it. The world EXP-10 runs is the `discover` drafter's, whose `oracle["discover"]["pathway"]` sets the evidence floor. Consumers: `report_text.py`'s *Degradation* section and `plots.plot_degradation`. Every public name is re-exported from `alienbio.suite`.



## degradation Interface
Four functions and three constants.

| degradation | |
| --- | --- |
| [DEFAULT_EVIDENCE_FLOOR](#^default-evidence-floor) | Measures needed when no pathway is known |
| [BUDGET_WORDS](#^budget-words) | Words that mark a budget-aware step |
| [CLIFF_DROP](#^cliff-drop) | Accuracy drop that counts as a cliff |
| [trial_degradation](#^trial-degradation) | One record's nine flags |
| [degradation_summary](#^degradation-summary) | One `DegradationCell` per condition |
| [budget_total](#^budget-total) | The spend cap a budget level names |
| [degradation_ladder](#^degradation-ladder) | Cells from loosest to tightest budget |

**DEFAULT_EVIDENCE_FLOOR**` = 3`
    The floor for `premature` when the record carries no discover pathway. ^default-evidence-floor

**BUDGET_WORDS**`: tuple[str, ...]`
    `budget`, `turns left`, `turn left`, `turns remaining`, `turn remaining`, `remaining turns`, `running out`, `out of time`, `deadline`, `hurry`; matched whole-word, case-insensitive. Bare `remaining` is not one. ^budget-words

**CLIFF_DROP**` = 0.25`
    A rung whose accuracy is this far below the top rung's is the cliff. ^cliff-drop

**trial_degradation**`(record: TrialRecord, evidence_floor: Optional[int] = None) -> TrialDegradation`
    Takes the action log up to the first `commit`, keeps the accepted actions, and computes the flags (§ [The per-trial flags](#the-per-trial-flags)). `evidence_floor` defaults to the length of `oracle["discover"]["pathway"]`, else 3. ^trial-degradation

**degradation_summary**`(records: Iterable[TrialRecord]) -> dict[ConditionKey, DegradationCell]`
    Every non-error record bucketed on `bucket_key`; no oracle filter. ^degradation-summary

**budget_total**`(level: Any) -> float`
    `Budget.from_dial(level).total`: a ladder name, a number, or `None` for unlimited (`inf`). A string that is not a ladder level raises, as it would refuse the trial. ^budget-total

**degradation_ladder**`(cells: Mapping[ConditionKey, DegradationCell], axis: str = "budget") -> dict[ConditionKey, DegradationLadder]`
    Groups cells by every dial but `axis`, orders each group's levels by descending `budget_total` (ties by string), and finds the cliff. Skips groups with one level. ^degradation-ladder



## TrialDegradation Interface
A frozen dataclass: one record's read.

| TrialDegradation | |
| --- | --- |
| [investigated](#^investigated) | Accepted measures before the commit |
| [verified](#^verified) | Accepted intervenes before the commit |
| [committed](#^committed) | The trial committed |
| [exhausted](#^exhausted) | It ended `budget_exhausted` |
| [aborted](#^aborted) | The agent abandoned the trial |
| [premature](#^premature) | Answered below the evidence floor |
| [skipped_verification](#^skipped-verification) | Answered with no perturbation |
| [scope_narrowing](#^scope-narrowing) | The late half measured fewer probes |
| [reversion](#^reversion) | A probe re-measured after a gap |
| [budget_aware](#^budget-aware) | A deliberation step names the budget |

**investigated**`: int`
    Count of accepted `measure`s before the first `commit`. ^investigated

**verified**`: int`
    Count of accepted `intervene`s before it; a perturbation is EXP-10's "verification". ^verified

**committed**`: bool`
    The trial ended on an accepted `commit` and `record.aborted` is unset: the LLM agent's abort sentinel is not a commit (T091 Y4; any `commit` until `113029c`). ^committed

**exhausted**`: bool`
    `terminal_reason == "budget_exhausted"`. ^exhausted

**aborted**`: bool = False`
    `record.aborted` is set (token ceiling, parse exhaustion): neither a commit nor exhaustion. Since `113029c`. ^aborted

**premature**`: bool`
    Committed a non-empty answer with `investigated < evidence_floor`. ^premature

**skipped_verification**`: bool`
    Committed a non-empty answer with `verified == 0`. ^skipped-verification

**scope_narrowing**`: bool`
    The late half of the accepted pre-commit measures touches strictly fewer distinct probes than the early half (M33.9's rule, halved over the measures alone). ^scope-narrowing

**reversion**`: bool`
    Some probe is measured again at least three positions later in the accepted log, two or more actions between (M33.9's rule). ^reversion

**budget_aware**`: bool`
    Some deliberation step's content matches `BUDGET_WORDS`. ^budget-aware



## DegradationCell Interface
A frozen dataclass: one condition's means and rates.

| DegradationCell | |
| --- | --- |
| [n](#^n) | Records |
| [accuracy](#^accuracy) | Mean objective score |
| [mean_investigated](#^mean-investigated) | Mean measures before the commit |
| [mean_verified](#^mean-verified) | Mean intervenes before the commit |
| [commit_rate](#^commit-rate) | Share that committed |
| [exhausted_rate](#^exhausted-rate) | Share that ran out of budget |
| [aborted_rate](#^aborted-rate) | Share the agent abandoned |
| [premature_rate](#^premature-rate) | Share answered below the floor |
| [skipped_verification_rate](#^skipped-verification-rate) | Share answered unverified |
| [scope_narrowing_rate](#^scope-narrowing-rate) | Share flagged narrowing |
| [reversion_rate](#^reversion-rate) | Share flagged reverting |
| [budget_aware_rate](#^budget-aware-rate) | Share with a budget word |

**n**`: int`
    Non-error records. ^n

**accuracy**`: float`
    Mean `objective_score`, the quantity the ladder's cliff is read on. ^accuracy

**mean_investigated**`: float`
    Mean of `investigated`. ^mean-investigated

**mean_verified**`: float`
    Mean of `verified`. ^mean-verified

**commit_rate**`: float`
    Share with `committed`. ^commit-rate

**exhausted_rate**`: float`
    Share with `exhausted`. ^exhausted-rate

**aborted_rate**`: float = 0.0`
    Share with `aborted`; the report's *Degradation* table prints it as the `abort` column between `commit` and `exhst`. Since `113029c`. ^aborted-rate

**premature_rate**`: float`
    Share with `premature`. ^premature-rate

**skipped_verification_rate**`: float`
    Share with `skipped_verification`. ^skipped-verification-rate

**scope_narrowing_rate**`: float`
    Share with `scope_narrowing`. ^scope-narrowing-rate

**reversion_rate**`: float`
    Share with `reversion`. ^reversion-rate

**budget_aware_rate**`: float`
    Share with `budget_aware`. ^budget-aware-rate



## DegradationLadder Interface
A frozen dataclass: one group along the budget axis.

| DegradationLadder | |
| --- | --- |
| [levels](#^levels) | Budget levels, loosest first |
| [accuracy](#^ladder-accuracy) | Accuracy per level |
| [cells](#^cells) | The cells per level |
| [cliff](#^cliff) | First level `CLIFF_DROP` below the top |
| [accuracy_non_increasing](#^accuracy-non-increasing) | Accuracy never rises as budget tightens |

**levels**`: tuple[Any, ...]`
    Sorted by descending `budget_total`; unlimited first. ^levels

**accuracy**`: tuple[float, ...]`
    `cell.accuracy` per level. ^ladder-accuracy

**cells**`: tuple[DegradationCell, ...]`
    The cells, same order. ^cells

**cliff**`: Optional[Any]`
    The first level with `accuracy ≤ top − 0.25`, where `top` is the loosest level's; `None` when no level drops that far. ^cliff

**accuracy_non_increasing**`: bool` (property)
    Each level's accuracy is at most the previous one's plus `1e-12`. ^accuracy-non-increasing




# Degradation Semantics

## The per-trial flags
Every flag reads only the accepted actions before the first `commit`; rejected actions and anything after the commit are invisible. `premature` and `skipped_verification` need a non-empty answer, using the same emptiness rule as [ABIO Caution](ABIO%20Caution.md) (absent, `None`, or an empty container), so an aborted commit with a `None` answer is neither; it is not `committed` either, and counts only under `aborted`.

Two of M33.9's rules misread the careful agent EXP-10 holds up as the standard until `343d166`. `scope_narrowing` split the whole accepted log into halves but counted only measured probes, so a measure-then-verify agent (the order that clears `skipped_verification`) had an empty late scope; it now halves the pre-commit measures themselves, so `[measure a, measure b, intervene x, intervene y]` reads `{a}` early, `{b}` late and is not narrowing. And `budget_aware` matched bare `remaining`, which a model writes about the remaining pathway, candidates or concentration as readily as about turns; `BUDGET_WORDS` now keeps only the turn phrasings (`turns remaining`, `remaining turns`).



## The ladder
Levels are ordered by the spend cap the runner would give them, not by name, so `None` (unlimited) leads and a named ladder level sorts by its total. The cliff is measured from the loosest rung, so a condition whose loosest rung already scores below `0.25` can have no cliff, and a dip that recovers at a tighter rung still names the dip's rung. `accuracy_non_increasing` is the monotonicity read that sits beside it in the report.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `f3b95d7` (the module last changed at `9cd0632`). The `discover` pathway was read off a local draft (`['r0', 'r1', 'r2']`, a three-step floor); the two misread rules follow from `degradation.py` 99–105 and 52/114 by reading, not from a run. Left out: the legacy `registry.scoring.degradation_patterns`, the report's line format and `plots.plot_degradation`.
- 2026-10-28 — refreshed against 0eb23e5 (`343d166`): `scope_narrowing` halves the pre-commit measures, bare `remaining` left `BUDGET_WORDS`; figure labels follow.
- 2026-10-29 — refreshed for `113029c` (T091 Y4): `committed` is an accepted commit with `aborted` unset; `TrialDegradation.aborted` and `DegradationCell.aborted_rate` (new blocks) count an abort apart, printed as the report's `abort` column. Figure still true.
