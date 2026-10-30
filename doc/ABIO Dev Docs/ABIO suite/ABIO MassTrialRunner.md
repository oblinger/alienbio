---
description: "`MassTrialRunner` and `ReliabilityMap`: the condition grid, the seeded trial sweep under concurrency and a stop hook, error isolation, and the reducer that turns records into cell statistics, 2×2 contrasts and provenance. Source: `src/alienbio/suite/mass_trial.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO MassTrialRunner](ha://p/ABIO%20MassTrialRunner) 
# ABIO MassTrialRunner
The sweep engine: it crosses the swept dials into a grid of cells, runs a fixed number of seeded trials per cell through `runner.run`, and reduces every `TrialRecord` into one frozen `ReliabilityMap`.

![ABIO MassTrialRunner](ABIO%20MassTrialRunner.svg) 
*Errors and resume* is the topic that governs the `_aggregate` node and the dotted resume path: an error record rides `records` but never a cell, and a resume moves error lines to `records.retried.jsonl` and re-runs them on the same seeds.

This page covers `suite/mass_trial.py`: the grid, the runner, the reducer and the four frozen result types. The module introduces no statistics of its own; every number comes from `reliability_grid` (`CellStats`, `aggregate_cells`, `two_way_interaction`), `stats_summary` (`mean_confidence_interval`) and `effect_size` (`cohens_d`, `welch_t`). Its one production caller is `run_experiment` in `suite/experiment.py`, which supplies the drafter, the agent factory, the persistence hook, the resume seam and the cost-ceiling hook; the spec it reads is [ABIO ExperimentSpec](ABIO%20ExperimentSpec.md), the per-trial loop is [ABIO Runner](ABIO%20Runner.md), the record and its `bucket_key`/`is_error` are [ABIO TrialRecord](ABIO%20TrialRecord.md), the checks that run before any of this are [ABIO Guards](ABIO%20Guards.md). The subsystem view is [ABIO-Experiment](../../ABIO%20Architecture/ABIO-Experiment.md); the operator's view is [ABIO Suite Runtime](../../ABIO%20Architecture/ABIO%20Suite%20Runtime.md) § Sweeps.



## MassTrialRunner Interface
A stateless class with one method; `run_experiment` builds a fresh one per run (`MassTrialRunner().run(...)`). It is axis-agnostic: it never inspects a dial name or level, only threads the cell's dials to the drafter, the agent factory and `runner.run`. Every `(cell, trial)` unit is a pure function of its own derived seed, which is what makes the thread pool, resume and widening an axis safe.

| MassTrialRunner | |
| --- | --- |
| [run](#^run) | Run every cell × trial and reduce to a map |

**run**`(axes: Sequence[Axis], drafter: WorldDrafter, agent_factory: AgentFactory, trials_per_condition: int, base_seed: Seed, on_error: str = "record", extra_dials: Mapping[str, Any] = {}, on_trial: Optional[Callable[[str, int, TrialRecord], None]] = None, skip: Optional[Callable[[str, int], Optional[TrialRecord]]] = None, matched_dials: Collection[str] = (), stop: Optional[Callable[[], bool]] = None, concurrency: int = 1) -> ReliabilityMap`
    Builds the grid with [condition_grid](#^condition-grid), sorts the keys by `str(key)`, and enumerates `trials_per_condition` units per key in that order. Per unit: `skip(label, i)` first — a returned record lands as-is, nothing drafted; then `stop()` — once true the grid ends and `stopped_early` is set; then the unit drafts with `drafter(trial_seed.child("draft"), dials)`, builds the agent with `agent_factory(trial_seed.child("agent"), dials)` and runs `runner.run(..., trial_seed.child("run"), swept=<axis names>)`, where `dials` is `{**extra_dials, **dict(key)}`. The returned record's `condition_key` is reset to the swept key alone, so `extra_dials` widens what a trial sees and never what it is binned on. `on_trial(label, i, record)` fires as each record lands, fresh or reused; its exceptions propagate. `on_error` and `concurrency` are [Running under the ceiling](#running-under-the-ceiling) and [Errors and resume](#errors-and-resume); `matched_dials` is [The grid and seeding](#the-grid-and-seeding). Ends with `_aggregate` over every landed record. `ValueError` for an `on_error` other than `"record"`/`"raise"`, a `concurrency` that is not an int ≥ 1 (a `bool` is refused), or two cells sharing a label ([The grid and seeding](#the-grid-and-seeding)). ^run



## ReliabilityMap Interface
The frozen result of a sweep, built only by `_aggregate` (directly from `run`, or from a store through [aggregate_records](#^aggregate-records)). Cells and contrasts hold statistics over the scored records; `records` keeps every record, error records included, for the per-record readers. The last field defaults to `()` so a hand-built fixture constructs without records.

| ReliabilityMap | |
| --- | --- |
| [cells](#^cells) | One `CellSummary` per swept condition with scored records |
| [interactions](#^interactions) | 2×2 interaction contrast per eligible axis pair |
| [contrasts](#^contrasts) | Diagonal effect size per eligible axis pair |
| [provenance](#^provenance) | Axes, seed, trial count, failures, early stop |
| [records](#^records) | Every record, in landing order |
| [to_json](#^to-json) | The `map.json` payload |
| [to_csv](#^to-csv) | The `map.csv` per-cell table |

**cells**`: Mapping[ConditionKey, CellSummary]`
    Keyed by each record's `bucket_key` (the condition key with list and mapping levels frozen to tuples). A cell exists only when at least one non-error record landed in it: an all-error or never-run cell is absent, not `n = 0`. ^cells

**interactions**`: Mapping[tuple[str, str], float]`
    For each pair of swept axes that both have exactly two levels and all four marginal combinations observed, `two_way_interaction` over the 2×2 marginal of cell means; see [Interactions and contrasts](#interactions-and-contrasts). Pairs are in `provenance.axes` order. ^interactions

**contrasts**`: Mapping[tuple[str, str], ContrastResult]`
    The same axis pairs, each with Cohen's d and Welch's t of the high diagonal against the low one; a pair is absent when either diagonal has fewer than two scored records or the pooled variance is zero. ^contrasts

**provenance**`: Provenance`
    What produced the map; see [Provenance Interface](#provenance-interface). ^provenance

**records**`: tuple[TrialRecord, ...] = ()`
    Every record `run` landed, in the sorted unit order, reused and error records included — the input of every analysis family and the failure census. From [aggregate_records](#^aggregate-records), the order it is given; `experiment.aggregate` sorts the stored lines back to run order first ([grid_positions](#^grid-positions), then index), so a resumed run reloads in the live order. ^records

**to_json**`() -> str`
    Indented JSON with `provenance` (axes, `base_seed` value, `trials_per_condition`, `failed_trials`, `stopped_early`), `cells` (condition key as pairs, `n`, `mean`, `std`, `ci_low`, `ci_high`, sorted by `str(key)`), `interactions` and `contrasts` (sorted by pair). `records` is not serialized; `records.jsonl` carries them. ^to-json

**to_csv**`() -> str`
    One header row (each swept axis name in `provenance.axes` order, then `n`, `mean`, `std`, `ci_low`, `ci_high`) and one row per cell, sorted by `str(key)`. A frozen list level prints as its tuple. ^to-csv



## CellSummary Interface
One cell's statistics: the shared `CellStats` record from `reliability_grid` plus a confidence interval for its mean. Frozen.

| CellSummary | |
| --- | --- |
| [stats](#^stats) | `n`, mean, sample standard deviation |
| [ci](#^ci) | Normal-approximation interval for the mean |

**stats**`: CellStats`
    `n` (scored records in the cell), `mean` (`sum / n`) and `std` (sample, `n − 1`; `0.0` when `n < 2`). ^stats

**ci**`: tuple[float, float]`
    `mean ± 1.96 · std / √n` from `mean_confidence_interval` (a two-sided ~95 % normal multiplier, not Student's t); `(mean, mean)` when `n < 2`. See [Cell statistics](#cell-statistics). ^ci



## ContrastResult Interface
A pairwise effect size between two pooled groups of raw scores, both numbers computed high minus low. Frozen.

| ContrastResult | |
| --- | --- |
| [cohens_d](#^cohens-d) | Standardized mean difference |
| [welch_t](#^welch-t) | Welch's t statistic |

**cohens_d**`: float`
    `(mean(high) − mean(low)) / pooled_sd`, the pooled sample standard deviation of the two groups. ^cohens-d

**welch_t**`: float`
    `(mean(high) − mean(low)) / √(s₁²/n₁ + s₂²/n₂)`. ^welch-t



## Provenance Interface
What produced a map. Frozen; the two counters default so a hand-built fixture constructs with three arguments. `run_experiment` copies `failed_trials` and `stopped_early` into the manifest (`failed_trials`, `stopped_reason: "cost_ceiling"`).

| Provenance | |
| --- | --- |
| [axes](#^axes) | The swept axes, levels as tuples |
| [base_seed](#^base-seed) | The seed every trial seed derives from |
| [trials_per_condition](#^trials-per-condition) | The fixed per-cell trial count |
| [failed_trials](#^failed-trials) | Error records the map was built over |
| [stopped_early](#^stopped-early) | Did the stop hook end the grid? |

**axes**`: tuple[tuple[str, tuple[Any, ...]], ...]`
    The axes as `run` was given them, normalised to tuples, in the caller's order (not the sorted cell order); `to_csv` takes its columns from it and the contrasts their pairs. ^axes

**base_seed**`: Seed`
    The root of every `base_seed.child(f"{label}/{i}")`; `to_json` writes its `value`. ^base-seed

**trials_per_condition**`: int`
    The planned count per cell (a fixed floor, not a power-driven top-up); a cell's `n` can be lower after errors or an early stop. ^trials-per-condition

**failed_trials**`: int = 0`
    `len(records)` minus the scored records — the error records the reducer skipped, counted by `_aggregate` itself so a live run and a reload agree. Always `0` under `on_error="raise"`. ^failed-trials

**stopped_early**`: bool = False`
    `True` when `stop()` returned true before the last unit, or a worker found it true as it started; set by `run` after the reduce. [aggregate_records](#^aggregate-records) alone leaves `False`; `experiment.aggregate` reads it back from the manifest's `stopped_reason` (T084 B, 2026-10-28 — before that `bio suite aggregate` rewrote a ceiling-stopped run's `map.json` with `stopped_early: false`). ^stopped-early



## mass_trial Interface
`suite/__init__.py` re-exports `Axis`, `CellSummary`, `ConditionKey`, `ContrastResult`, `MassTrialRunner`, `Provenance`, `ReliabilityMap`, `aggregate_records` and `condition_grid`. `AgentFactory` and `WorldDrafter` are imported from the module directly (`agents.py`, `experiment.py`, `expr_experiment.py`); `guards.py` also imports the private `_condition_label` so its `draft` check uses the run's own seed labels.

| mass_trial | |
| --- | --- |
| [condition_grid](#^condition-grid) | The orthogonal product of the axes, one key per cell |
| [aggregate_records](#^aggregate-records) | Rebuild a map from stored records |
| [grid_positions](#^grid-positions) | Each cell label's place in run order |
| [label_collision](#^label-collision) | Two cells sharing one label, if any |
| [SEED_SCHEME_VERSION](#^seed-scheme-version) | The version of the per-trial seed derivation |
| [ConditionKey](#^conditionkey) | One cell's sorted `(dial, level)` pairs |
| [Axis](#^axis) | A dial name and its levels |
| [WorldDrafter](#^worlddrafter) | `(seed, dials)` → world and task |
| [AgentFactory](#^agentfactory) | `(seed, dials)` → agent |

**condition_grid**`(axes: Sequence[Axis]) -> list[ConditionKey]`
    `itertools.product` over the axes' levels in the order given, each combination normalised by `trial.condition_key` (sorted by dial name). Empty `axes` yields `[()]`, one cell with no dials. No dedupe: a level repeated on one axis enumerates its cell twice; `ExperimentSpec` refuses a repeated level, an empty axis and a repeated axis name at construction (T091 B1). `run` re-sorts the result by `str(key)`; callers that need the run's order must do the same. ^condition-grid

**aggregate_records**`(records: Sequence[TrialRecord], axes: tuple[tuple[str, tuple[Any, ...]], ...], base_seed: Seed, trials_per_condition: int) -> ReliabilityMap`
    The public name for `_aggregate`, the reducer `run` itself ends with: no drafting, no re-running. `experiment.aggregate(out_dir)` reads `records.jsonl` and the manifest's spec, calls it, and sets `stopped_early` from the manifest's `stopped_reason`; `bio suite aggregate` and `bio suite report` go through that. ^aggregate-records

**grid_positions**`(axes: Sequence[Axis]) -> dict[str, int]`
    Each condition label's position in the order `run` enumerates and lands its units (the grid's keys sorted by `str`). `experiment.aggregate` sorts reloaded lines by it, then by index, so a reloaded cell's float sums are taken in the live order; a line whose label the spec does not know keeps its file place after every known one. ^grid-positions

**label_collision**`(axes: Sequence[Axis]) -> Optional[str]`
    The problem when two distinct cells render the same condition label (`1` and `"1"`, a level carrying `&b=`), else `None`. Exact duplicate levels (equal `repr`) are not this check's: `ExperimentSpec` refuses them first. `run` raises it before any unit and `guards.label_collision_violation` is preflight's `labels` check ([The grid and seeding](#The%20grid%20and%20seeding)). ^label-collision

**SEED_SCHEME_VERSION**`: int = 1`
    The version of the per-trial seed derivation this module owns: `base_seed.child(f"{seed_label}/{i}")`, then `.child("draft")`/`("agent")`/`("run")`. Half of the manifest's `world_scheme` stamp (`store.world_scheme`; the other half is the matched dials the spec sweeps), which a resume compares so a store never mixes worlds drawn under two schemes in one cell. Its comment carries the bump rule: bump it whenever the derivation changes (the label format, a child path, how matched dials are projected out) or a drafter starts drawing a different world from the same seed and dials; a change to `WORLD_INVARIANT_DIALS` moves the stamp by itself, but only for a spec that sweeps the dial (`1e08068`, `b6d1607`, T091 R2, X1). Defined below the imports. ^seed-scheme-version

**ConditionKey**` = tuple[tuple[str, Any], ...]`
    One cell: `(dial, level)` pairs sorted by dial name, the shape `trial.condition_key` produces. Levels stay raw here; `bucket_key` is the hashable form. ^conditionkey

**Axis**` = tuple[str, Sequence[Any]]`
    One swept dial and its ordered levels; `ExperimentSpec.axes` is a tuple of these. ^axis

**WorldDrafter**` = Callable[[Seed, Mapping[str, Any]], tuple[WorldImpl, TaskInstance]]`
    Builds one world and task for a trial. `run_experiment`'s closure merges `spec.fixed_dials` under the dials again and calls `DRAFTERS[spec.drafter](seed, merged, **spec.drafter_kwargs)`. ^worlddrafter

**AgentFactory**` = Callable[[Seed, Mapping[str, Any]], Agent]`
    Builds one agent for a trial; `run_experiment` takes it from `agents._agent_factory_for(spec)`, which reads `agent`, `model`, `memory` and the other agent dials off the trial's dials. ^agentfactory




# MassTrialRunner Semantics

## The grid and seeding
A cell is one combination of swept levels; a unit is one `(cell, trial index)`. The cell's label is `"&".join(f"{name}={value}")` over its sorted key (`level=a&rung=2`), and the unit's seed is `base_seed.child(f"{seed_label}/{i}")`, a SHA-256 of the parent value and the string. `seed_label` is the cell label with every `matched_dials` entry removed, so cells that differ only in matched dials draw identical world, agent and run seeds. A seed depends only on the cell's own key and index, never on the grid's size or order: widening an axis adds cells without moving an existing cell's worlds, and a re-run unit draws the same world. Levels render through `str`, so two distinct levels can share a label (`1` and `"1"`, or a level containing `&b=`) and with it a seed and a resume key; `label_collision` refuses such a grid — in `run` before any unit, and as preflight's `labels` check before spend — rather than re-rendering, which would move every stored seed (T084 C, 2026-10-28).

| Dial kind | Where `run_experiment` puts it | In the cell key | In the seed label |
| --- | --- | --- | --- |
| Swept axis | `spec.axes` → `axes` | yes | yes |
| Swept and matched | an axis named in `WORLD_INVARIANT_DIALS` or `spec.matched_dials` | yes | no |
| Idle arm | `idle_baseline: true` appends `("agent", (<agent>, "idle"))` at load | yes | no (`agent` is world-invariant) |
| Fixed | `spec.fixed_dials` → `extra_dials` | no | no |
| Generator kwarg | `spec.drafter_kwargs`, closed over by the drafter | no | no |

`run_experiment` passes `matched_dials = WORLD_INVARIANT_DIALS + spec.matched_dials`: the brief-, agent-, observation- and episode-side dials (`agent`, `model`, `monitoring`, `framing`, `constitution`, `max_turns`, `budget`, `memory`, `levers`, `probes`, `max_tokens`, the monitor dials, `task_note`, `observability`, `observation_noise`, `sample_every`, the forgetting dials and the rest in `drafters.py`; the `sim_steps`/`sim_dt` clock stays out, since drafters read it), so a control arm and a live arm, or the rungs of a budget ladder, run on byte-identical worlds. The label handed to `skip` and `on_trial` and stored as each line's `label` is always the full cell label, matched dials included. Any change to this derivation bumps [SEED_SCHEME_VERSION](#^seed-scheme-version), so an older store refuses to resume rather than mixing two schemes' worlds in one cell ([ABIO Guards](ABIO%20Guards.md) § Resume and the seed scheme).



## Running under the ceiling
With `concurrency = 1` units run in order on the calling thread. With `concurrency > 1` they run on a `ThreadPoolExecutor` of that many workers, but results land in submission order, so `records`, the `on_trial` sequence, `records.jsonl` and the map are byte-identical to a serial run. Threads buy wall time for live-model trials, which wait on the network; the simulator is CPU-bound Python, so a scripted sweep gains little.

The `stop` hook is consulted at three points. In the submitting loop, after every finished unit at the head of the queue has landed (so `on_trial` has already added its spend); by each worker as it picks a unit up, which then returns nothing and spends nothing; and never before a `skip` hit, so a resumed unit always replays. The overshoot past a ceiling is therefore at most the units genuinely running when it tripped (≤ `concurrency`). `run_experiment`'s hook is `spent_usd ≥ cost_ceiling_usd`, where `on_trial` prices each landed record's `usage` after writing its line, and a resume seeds the total with the spend of the error lines it retries.



## Errors and resume
Under `on_error="record"` (the default) an exception from the drafter, the agent factory or `runner.run` ends that unit only. If the exception carries the trial's own record (`TaintError`, `TrialError`), that record lands with `terminal_reason="error"` and `error` naming the underlying cause, so its brief, oracle and real usage survive; otherwise a bare record lands with `objective_score = 0.0`, an empty timeline, `task_id` = the drafted world or the cell label, and the agent's `usage` if the agent was built. Under `on_error="raise"` the first exception propagates and nothing is reduced. An exception out of landing (an `on_trial` that raised) or a `run_one` under `on_error="raise"` at `concurrency > 1` first lands every unit still pending, each through `on_trial` (a unit not yet started is cancelled: it has spent nothing), and then propagates the first failure, so no paid record is dropped (`01fee6a`).

`_aggregate` is the one place error records leave the statistics: it keeps every record on `records` and bins only those with `is_error` false (`terminal_reason == "error"` or a non-empty `error`), and `failed_trials` is the difference. Before `63b3f7e` (2026-10-28) `run` filtered error records itself and counted them as they landed, while a reload through `aggregate_records` folded each error line into its cell as a score of 0 — one good and one error line reloaded to `n = 2` at half the live mean. Both paths now run the same reducer, so a reloaded map's cells and `failed_trials` equal the live one's.

| Line on disk at resume | What `run_experiment` does | Reaches `run` as |
| --- | --- | --- |
| Clean record | kept in `records.jsonl` | a `skip` hit, landed unchanged, not rewritten |
| Error record | appended to `records.retried.jsonl`, removed from `records.jsonl`, its spend counted | a fresh unit on the same seed |
| `TaintError` record | kept in place (deterministic) unless `retry_taint=True` | a `skip` hit, counted in `failed_trials` |
| Missing `(label, index)` | — | a fresh unit |

Resume is keyed by `(label, index)` only; `preflight`'s `resume` check refuses a spec that drifted from the manifest before any of this runs.



## Cell statistics
`n` counts the scored records in the cell — landed, not error — so it is at most `trials_per_condition` and falls below it after errors or an early stop. `mean` and `std` come from `aggregate_cells`; the interval is a normal approximation with z = 1.96, which is narrower than a Student's t interval at the small `n` typical of a live arm (at `n = 3` the t multiplier is 4.30). A singleton cell reports `std = 0.0` and a zero-width interval rather than raising. The score is `TrialRecord.objective_score`; nothing else on the record enters a cell.



## Interactions and contrasts
Computed for each pair of swept axes in which both axes have exactly two levels, so an idle arm (`agent` × 2) crossed with any two-level dial qualifies. The interaction is `m[a1,b1] − m[a1,b0] − m[a0,b1] + m[a0,b0]` over the 2×2 marginal, each marginal mean the unweighted average of the matching cells' means across every other swept axis; it is skipped when a combination has no cell. The contrast pools raw scores, not means: every record at `(a1, b1)` against every record at `(a0, b0)`, other axes pooled, with `a0`/`b0` the lower level under `sorted` (a mapping level, which has no order, by its canonical JSON). Every lookup in this path — the marginal's cells, the pooled levels, the sort — runs on levels frozen to the `bucket_key` form, so a list or mapping axis (`levers`, `output_schedule`) yields interactions and contrasts like any other; before the 2026-10-28 fix (T084 A) the marginal looked cells up by the raw key and raised `TypeError: unhashable` after the paid grid. A zero pooled variance (a deterministic scripted sweep) leaves the pair out rather than raising. The report's `primary_contrast` (a declared design) is a separate one-axis contrast computed in `report_text.py` from `records`.



## What reads the map

| Reader | Reads |
| --- | --- |
| `run_experiment` | `to_json` → `map.json`, `to_csv` → `map.csv`<br>`records` → `usage_totals`, `trials_completed`<br>`provenance` → `failed_trials`, `stopped_reason` |
| `render_report` | `provenance.axes`, `cells` → the Conditions table<br>`records` → census, analysis sections, idle twins<br>`interactions`, `contrasts` → the Bonferroni count |
| Analysis families (`hazard`, `tradeoff`, `caution`, `faking`, `degradation`, `delta`, `dose`, `census`) | `records` only, each bucketing on `bucket_key` and skipping `is_error` |
| `plots.key_figure` | `records` → every readout figure<br>`cells` → the fallback means-with-CI figure<br>`provenance.axes` → the ladder and hazard axes |
| `bio suite aggregate` / `report` | a map rebuilt by `experiment.aggregate`, written back to `map.json` / `report.txt` |




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD 4d625e5 (`mass_trial.py` last changed at `63b3f7e`, whose diff — error filtering moved into `_aggregate`, `failed_trials` derived there — the page describes). Every member traced to `suite/mass_trial.py`; the seams checked against `experiment.py` (`run_experiment`, `aggregate`), `spec.py` (`spec_from_dict`'s idle arm, `matched_dials`), `drafters.py` (`WORLD_INVARIANT_DIALS`), `store.py` (`record_to_json`, `_trials_planned`), `trial.py` (`bucket_key`, `is_error`, `hashable_condition_key`), `report_text.py`, `plots.py`, `guards.py`, `dist.py` (`Seed.child`), `reliability_grid.py`, `stats_summary.py`, `effect_size.py`, `commands/suite_cmd.py`, and the tests `test_mass_trial.py`, `test_bucketing_keys.py`, `test_moddoc_findings_suite2.py` (B), `test_experiment.py` (resume, retries, ceiling). Left out as members: the private helpers `_condition_label`, `_levels_of`, `_marginal_cell_means`, `_pooled_raw_scores` and `_aggregate` (described in prose where they decide behavior), `run`'s inner `run_one`/`land`/`drain`, and `CellStats` (it lives in `reliability_grid.py`). The figure folds the drafter and agent factory into `runner.run`'s sub-label and shows `stop()` and `aggregate(out_dir)`, which live in `experiment.py`, as nodes because they are the two callers that close the loop.
- Divergences found, not fixed (reported to the caller): `_marginal_cell_means` looks cells up by the raw `condition_key` (line 268–269) while `cells` is keyed by `bucket_key`, so a two-level axis with list or mapping levels (`levers`, `output_schedule`) crossed with another two-level axis raises `TypeError: unhashable` after the grid has been paid for (reproduced with `aggregate_records`); `sorted(_levels_of(...))` at line 358 would raise on mapping levels too. `experiment.aggregate` (experiment.py line 518) cannot restore `stopped_early`, so `bio suite aggregate` rewrites `map.json` of a ceiling-stopped run with `stopped_early: false`. `_condition_label` stringifies levels, so `1` and `"1"` on one axis share a seed label and a resume key. The module and class docstrings (lines 3, 18, 385) still call the runner sequential, and line 462 states the old `terminal_reason == "error"` test where the reducer now uses `is_error`. [ABIO Suite Runtime](../../ABIO%20Architecture/ABIO%20Suite%20Runtime.md) § Sweeps says dial vectors come from `suite.conditions` (the run path never calls it), lists eight matched dials (the tuple has 24) and shows `run` without its seven later keywords; [ABIO-Experiment](../../ABIO%20Architecture/ABIO-Experiment.md)'s hypotheses table still lists "resume after an edited axis" as unchecked, which `preflight`'s resume-drift check now refuses.
- 2026-10-28 — the divergences above fixed (T084): `e8a9ef2` the interactions/contrasts path looks cells up, pools and sorts on the frozen `bucket_key` form (list and mapping axes aggregate; `test_bucketing_keys.py` lints `mass_trial.py` for a bare `condition_key(` lookup); `dbbfce1` `experiment.aggregate` reads `stopped_early` back from the manifest's `stopped_reason`; `1d46b37` a grid whose levels share a condition label is refused (`label_collision`, in `run` and as preflight's `labels` check) rather than re-rendered, so no stored seed moves; the stale docstrings, [ABIO Suite Runtime](../../ABIO%20Architecture/ABIO%20Suite%20Runtime.md) § Sweeps and [ABIO-Experiment](../../ABIO%20Architecture/ABIO-Experiment.md)'s resume-drift row corrected in the same pass. Tests: `tests/suite/test_moddoc_findings_mass_trial.py`.
- 2026-10-28 — refreshed against 0eb23e5: `grid_positions` (new, `01fee6a`) and `label_collision` given blocks; a reload sorts back to run order; an exception at `concurrency > 1` lands every in-flight unit before it propagates.
- 2026-10-29 — refreshed for `e5ea4d0` (T091 B1): `condition_grid` does not dedupe, and `label_collision` leaves exact duplicate levels to `ExperimentSpec`, which refuses them at construction.
- 2026-10-29 — refreshed for `1e08068` and `b6d1607` (T091 R2, X1): `SEED_SCHEME_VERSION` given a block with its bump rule; the seeding section points to the resume's scheme check.
