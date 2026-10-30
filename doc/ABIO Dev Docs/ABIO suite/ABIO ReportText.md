---
description: "`report_text`: the plain-text `report.txt` over a `ReliabilityMap` — `render_report` prints the header, condition table, failure census, design block and one section per analysis family that has records; `idle_baseline_comparison` and `primary_contrast_result` are its two own reads. Source: `src/alienbio/suite/report_text.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO ReportText](ha://p/ABIO%20ReportText) 
# ABIO ReportText
The renderer of `report.txt`: a fixed header and condition table, then one section for each analysis family whose oracle the records carry, then the idle-baseline lines.

![ABIO ReportText](ABIO%20ReportText.svg) 
*Section order* is the topic behind the column of sections (each prints only when its summary returns rows; ‡ the two reads this module computes itself).

`suite/report_text.py` was split out of `experiment.py` in T058 and is re-exported from `alienbio.suite` and the `experiment` facade. Its one caller is `bio suite run|report` (`commands/suite_cmd.py`, [ABIO SuiteCmd](../ABIO%20alienbio/ABIO%20SuiteCmd.md)), which writes the string to `report.txt`. The map is [ABIO MassTrialRunner](ABIO%20MassTrialRunner.md)'s `ReliabilityMap`, the manifest is [ABIO Store](ABIO%20Store.md)'s. Every family section delegates to that family's module: [ABIO Hazard](ABIO%20Hazard.md), [ABIO Tradeoff](ABIO%20Tradeoff.md), [ABIO Caution](ABIO%20Caution.md), [ABIO Faking](ABIO%20Faking.md), [ABIO Degradation](ABIO%20Degradation.md), [ABIO Delta](ABIO%20Delta.md), [ABIO Dose](ABIO%20Dose.md), [ABIO Census](ABIO%20Census.md). The statistics are `effect_size.py` and `power.py`. The subsystem view is [ABIO-Analysis](../../ABIO%20Architecture/ABIO-Analysis.md).



## report_text Interface
Three functions; the private `_condition_label` writes a key as `name=value&name=value`.

| report_text | |
| --- | --- |
| [render_report](#^render-report) | The whole report as one string |
| [idle_baseline_comparison](#^idle-baseline-comparison) | Each live arm beside its idle twin |
| [primary_contrast_result](#^primary-contrast-result) | Cohen's d and Welch t for the declared contrast |

**render_report**`(rmap: ReliabilityMap, manifest: Mapping[str, Any], realism=None) -> str`
    Builds the report line by line, ending in a newline. `realism` is a `realism.realism_win_rates` result the caller already judged; when given, a *Realism* section is appended through `realism.realism_lines` ([ABIO Realism](ABIO%20Realism.md)). Nothing passes it yet: the report never calls the judge, which spends (since `113029c`). Reads only `rmap.records`, `rmap.cells`, `rmap.interactions`, `rmap.contrasts`, `rmap.provenance.axes` and manifest keys, each with a default, so an old manifest renders. Sorts every table by `str(key)`. § [Section order](#section-order). ^render-report

**idle_baseline_comparison**`(rmap: ReliabilityMap) -> list[tuple[str, str, float, float, int]]`
    Drops error records, removes `agent` from each `bucket_key`, groups scores per remaining condition and agent, and for each condition with an `idle` arm returns `(label, live_agent, live_mean, idle_mean, n)` per other agent. `n` is `min(len(live), len(idle))`: with five live trials and one idle it reads 1. Records with no `agent` on their key are skipped. ^idle-baseline-comparison

**primary_contrast_result**`(rmap: ReliabilityMap, contrast: Mapping[str, Any]) -> Optional[dict[str, Any]]`
    Pools every non-error record whose `bucket_key` has `axis == low` against every one with `axis == high`, all other dials pooled and the idle twin excluded unless `axis` is `agent` (T088), and returns `{cohens_d, welch_t, n_low, n_high}` (high minus low). `None` when a side has fewer than two scores or `cohens_d` raises on zero pooled variance. § [The design block](#the-design-block). ^primary-contrast-result




# ReportText Semantics

## Section order
Fixed, top to bottom; a family section prints only when its summary returns rows.

| Section | Source | Printed when |
| --- | --- | --- |
| Header (name, commit, model, times, trials, cost, usage) | manifest, `wall_time_s` summed | Always |
| Conditions (n, mean, std, CI per cell) | `rmap.cells` | Always |
| Failure census (terminal reasons, illegal, errors by class, aborts, records with `grade_error`, records with `parse_failures` and the parse-failure total, `records with taint_exempt: N (ids: …)`) | records | Always |
| Interactions / contrasts | `rmap.interactions`, `rmap.contrasts` | Either is non-empty |
| Design | manifest `design` | Declared |
| Hazard surfacing, Objective surfacing by depth, Blind spots | `hazard` | Hazard / schedule / typed rows |
| Conflict resolution + precedence ladder | `tradeoff` | Conflict oracle |
| Caution (an `abort` column after `commit`) + trends + factorial + reference | `caution` | A stakes/reversibility key or a discover oracle |
| Monitoring divergence | `faking` | Monitoring rows |
| Degradation (an `abort` column between `commit` and `exhst`) + budget ladder | `degradation` | A `budget` in some key |
| Delta | `delta` | Delta oracle |
| Pressure dose-response (an unread `by_pi0.2` prints `- (<reason>)` from `dose.continuity_unread_reason`) | `dose` | Pressure oracle |
| Census, Side-product distribution | `census` | Rows |
| Idle baseline | `idle_baseline_comparison` | An idle arm |
| Realism | `realism.realism_lines` | `realism=` passed (never, today) |



## The design block
Printed when the manifest carries `design` (`power.PowerDesign.to_dict`). The verdict is `ok` when the spec's `trials_per_condition` is at least `required_trials_per_condition`, and `UNDERPOWERED` otherwise, including when either is missing. `alpha_used` is `alpha / len(rmap.contrasts)` under `bonferroni`; it is printed and compared with nothing, since no p-value is computed anywhere in the report.

The primary contrast pools every other swept dial but drops records with `agent == "idle"` from both sides unless the contrast's axis is `agent` (T088 report_text 1). Every catalog spec that declares one also sets `idle_baseline: true`; before the fix the idle twin sat on both sides: two live trials per side at scores 0/0.1 and 1/0.9 give `d = 12.7`, and adding two idle zeros per side read `d = 1.15` from the same live arm.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be`; the idle pooling in `primary_contrast_result` and the `min` n of `idle_baseline_comparison` confirmed on duck-typed records against the HEAD export, the catalog's `idle_baseline` + `primary_contrast` pairing by `git grep`, no spend. Left out: each family's own columns (on its module doc) and the figure and `bio report` pages (`plots.py`, `report.py`).
- 2026-10-28 — refreshed against `abb5796`: `primary_contrast_result` excludes the idle twin unless the axis is `agent`.
- 2026-10-29 — refreshed for `e5ea4d0` (T091 B13): the failure census also counts `grade_error` records, `parse_failures` records and the parse-failure total, so a grid of wrong-shaped commits no longer reads as plain zeros.
- 2026-10-29 — refreshed for `113029c` (T091 Y4, Y6, Y8): the census lists `records with taint_exempt: N (ids: …)`; Caution and Degradation gain an `abort` column; an unread continuity share says why; `render_report(realism=…)` appends a Realism section no caller passes yet. Figure still true.
