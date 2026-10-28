---
description: "`store`: the on-disk record store of a run — the `records.jsonl` line codec with its only-when-set keys, the brief codec, the `manifest.json` builder and the model/memory/axis helpers it shares with `bio suite run --dry`, and the run directory every writer and reader meets in. Source: `src/alienbio/suite/store.py`."
---
:>>
# ABIO Store
The run's own evidence on disk: one canonical-JSON line per trial in `records.jsonl`, appended as each trial lands, and a `manifest.json` that pins the spec, code, model, licence and spend the lines were drawn under, so a run can be re-aggregated, resumed and audited from its directory alone.

![ABIO Store](ABIO%20Store.svg) 
*The record line* is the topic that governs `records.jsonl` (†): a field an experiment did not declare leaves no key, so the golden hashes stay byte-identical; *Resume and retries* governs the `originals` edge into `records.retried.jsonl`.

`suite/store.py` has no primary class and no `__all__`: its two public names are the line codec `record_to_json`/`record_from_json`, and the rest are underscore helpers that other modules import by name — `experiment.py` re-exports every one, `commands/suite_cmd.py` takes `_single_model`/`_model_axis_levels` for `--dry`, and tests import the brief codec and `_build_manifest`. This page covers those, and the run directory as a whole, because the store's files are written from four modules. Who writes when is `run_experiment` and `aggregate` in `suite/experiment.py`; the record the line encodes is [ABIO TrialRecord](ABIO%20TrialRecord.md); the spec the manifest pins is [ABIO ExperimentSpec](ABIO%20ExperimentSpec.md); the resume refusal that reads the manifest is [ABIO Guards](ABIO%20Guards.md); `map.json` comes from [ABIO MassTrialRunner](ABIO%20MassTrialRunner.md)'s `ReliabilityMap`. The subsystem view is [ABIO-Experiment](../../ABIO%20Architecture/ABIO-Experiment.md); the operator's view of the run directory is [ABIO Suite Runtime](../../ABIO%20Architecture/ABIO%20Suite%20Runtime.md).



## store Interface
Module-level functions only. The codecs are pure; `run_experiment` decides when each file is written, and the three writers here (`_write_manifest`, `_atomic_write_text`, `_append_retried`) do the writing. The manifest builder is the other impure member — it shells out to `git` and reads the clock, the platform and the models snapshot. Nothing here may import `guards` at module level (`guards` imports this module), so `_build_manifest` resolves `registration_admission` late.

| store | |
| --- | --- |
| [record_to_json](#^record-to-json) | One record → one `records.jsonl` dict |
| [record_from_json](#^record-from-json) | One line's dict → a `TrialRecord` |
| [_brief_to_json](#^brief-to-json) | The brief inside a line |
| [_brief_from_json](#^brief-from-json) | Its inverse |
| [_canonical_json](#^canonical-json) | Sorted-key compact JSON, the line's bytes |
| [_json_safe](#^json-safe) | Sets to sorted lists, recursively |
| [_encode_float](#^encode-float) | `inf`/`-inf`/`nan` as JSON strings |
| [_decode_float](#^decode-float) | Their inverse |
| [_encode_nonfinite](#^encode-nonfinite) | `_encode_float` at every depth |
| [_decode_nonfinite](#^decode-nonfinite) | Its inverse, on the numeric fields |
| [manifest_model_label](#^manifest-model-label) | What a manifest says ran |
| [_write_manifest](#^write-manifest) | `manifest.json`, atomically |
| [_atomic_write_text](#^atomic-write-text) | Temp file + `os.replace` |
| [_append_retried](#^append-retried) | Retried lines, never twice |
| [_build_manifest](#^build-manifest) | The start-of-run `manifest.json` dict |
| [_single_model](#^single-model) | The one model a run uses, or `None` |
| [_model_axis_levels](#^model-axis-levels) | The `model` axis levels, as strings |
| [_axis_levels](#^axis-levels) | Any axis's levels, as declared |
| [_trials_planned](#^trials-planned) | Grid size × trials per condition |
| [_git_info](#^git-info) | Commit and dirty flag, never raising |
| [_utc_now_iso](#^utc-now-iso) | The timestamp format of the manifest |

**record_to_json**`(record: TrialRecord, label: str, index: int) -> dict[str, Any]`
    The record as one line's dict, with `label` and `index` (the cell label and trial index the resume keys on) first. `final_timeline` is summarised to `final_time` (the last time, or `None`) and `final_state` — the record's own `final_state`, or, when that is empty, the last timeline state through `final_state_dict`. `oracle`/`answer` go through `_json_safe`, the whole dict through `_encode_nonfinite` (every non-finite float, at any depth, as `"inf"`/`"-inf"`/`"nan"`), and seven keys are written only when set ([The record line](#the-record-line)). Does not add `agent`, `model`, `memory`, `temperature`, `top_p` or `registration`; `run_experiment` stamps those on the dict before dumping it. ^record-to-json

**record_from_json**`(d: Mapping[str, Any]) -> TrialRecord`
    The inverse, lossy where the line is: `final_timeline` comes back as `Timeline(times=(final_time,), states=())`, a JSON list wherever a tuple went in, and the line-only keys are ignored ([Reload and its limits](#reload-and-its-limits)). The always-written keys are read with `d[...]` and raise `KeyError` when missing; every only-when-set key, and `taint_hits`, `usage`, `wall_time_s`, `oracle`, `final_state`, `name_map`, `answer` and an action's `target`/`value`/`delta`, are read with `.get` and default. The numeric fields — `objective_score`, `spent`, `usage`, condition levels, `final_state`, `oracle`, an action's `value`/`delta`, `compaction`/`forgetting`/`monitor` — go through `_decode_nonfinite`; `answer`, `name_map` and prose do not, so a non-finite float inside an `answer` reloads as its string. ^record-from-json

**_brief_to_json**`(brief: TaskBrief) -> dict[str, Any]`
    Every `TaskBrief` field: `question` and `monitoring` through `_json_safe`, `budget_total` through `_encode_float`, the affordances as lists. Six later keys are written only when set: `affordances.max_rates` (sorted, when non-empty; T023), `context_padding` (T027), `constitution_in_history` (when true; T029), `protocol` (T032), `monitor` (T060), `task_note` (T061). ^brief-to-json

**_brief_from_json**`(d: Mapping[str, Any]) -> TaskBrief`
    The inverse. Requires `question`, the three kinds, `constitution`, `affordances.probes`/`levers`, the budget pair, `action_costs`, `max_turns`, `sim_steps` and `sim_dt`; every other key defaults when absent. ^brief-from-json

**_canonical_json**`(payload: Any) -> str`
    `json.dumps(_encode_nonfinite(payload), sort_keys=True, separators=(",", ":"), default=repr, allow_nan=False)`: the exact bytes of a `records.jsonl` line and the input to `spec_sha256`. `default=repr` turns an unknown leaf into its repr string rather than raising. Every line is strict JSON: non-finite floats are spelled as strings first, and `allow_nan=False` refuses any that slipped past. `suite/render.py` defines its own function of the same name. ^canonical-json

**_json_safe**`(value: Any) -> Any`
    A dumps-safe copy: a set or frozenset becomes a list sorted by `repr`, a dict, list or tuple recurses (tuples become lists), anything else passes through unchanged — floats included; `_encode_nonfinite` spells the non-finite ones. ^json-safe

**_encode_float**`(value: float) -> Any`
    `"inf"`, `"-inf"` or `"nan"` for a non-finite float, the value otherwise — the store's one spelling. Applied directly to `budget`, `remaining`, `brief.budget_total` and every `readout_series` value, and through `_encode_nonfinite` to everything else. ^encode-float

**_decode_float**`(value: Any) -> float`
    `"inf"`/`"-inf"`/`"nan"` back to the floats, anything else through `float()`. ^decode-float

**_encode_nonfinite**`(value: Any) -> Any`
    `value` with every float through `_encode_float`; dict, list and tuple recurse, each keeping its type. A finite tree comes back equal, so its bytes do not move (the goldens prove it). ^encode-nonfinite

**_decode_nonfinite**`(value: Any) -> Any`
    The strings `"inf"`/`"-inf"`/`"nan"` back to floats, dict and list recursing. Used only on fields that carry numbers ([record_from_json](#^record-from-json)). ^decode-nonfinite

**manifest_model_label**`(manifest: Mapping[str, Any]) -> Optional[str]`
    The manifest's `model`, else its `models` levels joined with `", "`, else `None`. `render_report`'s `Model:` line and `bio report`'s run table (kind and model column) both read it. ^manifest-model-label

**_write_manifest**`(path: Path, manifest: Mapping[str, Any]) -> None`
    `json.dump(indent=2)` into `manifest.json.tmp` beside `path`, fsync, `os.replace`; on any failure the temp file is removed and the old manifest stands. ^write-manifest

**_atomic_write_text**`(path: Path, text: str) -> None`
    The same temp-file + `os.replace` for text; a resume's `records.jsonl` rewrite. ^atomic-write-text

**_append_retried**`(path: Path, lines: list[str]) -> None`
    Appends to `records.retried.jsonl` every line not already in it byte for byte, so a resume replayed after a crash adds nothing; a trial that fails again on a later press writes a different line and is kept. ^append-retried

**_build_manifest**`(spec: ExperimentSpec, trials_planned: int, started_at: str) -> dict[str, Any]`
    The manifest as `run_experiment` writes it before the grid: the spec and its sha256, provenance, the model and memory in force, sampling, the resolved registration, the directive hash, the counters at zero and the dry-run `cost_estimate` ([The manifest](#the-manifest)). Calls `estimate_cost(spec)` and `registration_admission(spec)`, so it raises whatever they raise; `preflight` has already run both. ^build-manifest

**_single_model**`(spec: ExperimentSpec) -> Optional[str]`
    `None` under a `model` axis. Otherwise `spec.model or PINNED_MODEL` when any agent kind in play is `llm` (`agent_kinds_in_play`, so an `agent` axis with an `llm` level counts — round 5), else `spec.model`. What the manifest's `model` and `bio suite run --dry`'s `model:` line both say. ^single-model

**_model_axis_levels**`(spec: ExperimentSpec) -> list[str]`
    The `model` axis's levels in declared order, each through `str`; `[]` when `model` is not swept. Feeds the manifest's `models` and `--dry`. ^model-axis-levels

**_axis_levels**`(spec: ExperimentSpec, axis: str) -> list[Any]`
    The named axis's levels as declared, not stringified; `[]` when unswept. Used for `memory`/`memories` only (`d53605e`). ^axis-levels

**_trials_planned**`(spec: ExperimentSpec) -> int`
    `trials_per_condition` times the product of every axis's level count — the manifest's `trials_planned`. An `idle_baseline` arm is already an `agent` axis level (`ExperimentSpec.__post_init__` adds it), so it counts. ^trials-planned

**_git_info**`(repo_root: Path) -> tuple[str, bool]`
    `(git rev-parse HEAD, non-empty git status --porcelain)` at `repo_root`, each with a 10 s timeout. Any failure of the first call gives `("unknown", False)`; a failure of the second gives the commit and `False`. Provenance never fails a run. The root is `_REPO_ROOT`, three parents above this file — the checkout, or a `site-packages` parent when installed. ^git-info

**_utc_now_iso**`() -> str`
    `datetime.now(timezone.utc).isoformat()`, the form of `started_at` and `finished_at`. ^utc-now-iso




# Store Semantics

## The run directory
`out_dir` is the spec's `out_dir` or `runs/<spec.name>`, resolved by `preflight`. `manifest.json` and a resume's `records.jsonl` rewrite go through a temp file and `os.replace`, so neither is ever torn; the other whole files use `write_text`, and the two `.jsonl` files are appended.

| File | Written by | When | Read by |
| --- | --- | --- | --- |
| `manifest.json` | `run_experiment` via `_build_manifest` | before the grid (counts = the lines a resume kept), rewritten if the grid raises (counts and spend so far, `finished_at` null) and at the end with finish time, counts and spend | `preflight`'s `resume` check; `aggregate`; `bio suite resume` (the spec to run) and `bio suite report` (the header); `bio report`'s run table |
| `records.jsonl` | `run_experiment`'s `on_trial`: `record_to_json` + line extras → `_canonical_json` | one line appended per fresh trial, as it lands; rewritten whole (temp file + `replace`) by a resume that retries | `aggregate`, a resume, the golden test, `preflight`'s `out_dir` check (existence only) |
| `records.retried.jsonl` | `run_experiment` on a resume | appended before the grid, when error lines are retried, before `records.jsonl` is rewritten; a line already there is not appended again | nothing in the package; it is evidence |
| `map.json`, `map.csv` | `ReliabilityMap.to_json`/`to_csv`, from `run_experiment` or `bio suite aggregate` | after the grid | nothing in the package |
| `report.txt` | `render_report(rmap, manifest)`, from `run_experiment` or `bio suite report` | after the final manifest write | `bio report` (the spend figure, by regex) |
| `key.png`, `key.json` | `plots.write_key_figure` (`savefig` + readout and caption) | last; absent when nothing applies | `bio report` § 4 |

Because the line is appended in `on_trial` the moment its trial returns, before its price is looked up, a crash, a kill or a pricing failure loses no landed trial. A run that raised leaves a manifest with `finished_at: null` and `trials_completed`/`failed_trials`/`cost_usd_spent` as of the crash; one killed outright (SIGKILL, power) keeps the start-of-run counts — the lines a resume kept, or 0. The records beside it are complete for what ran, and `bio suite resume` continues it.



## The record line
A line is `record_to_json`'s dict plus the extras `run_experiment` stamps, dumped by `_canonical_json` — sorted keys, no spaces — and terminated by `\n`.

| Keys | On the line |
| --- | --- |
| `label`, `index` | always; the resume key |
| the `TrialRecord` core (`task_id` … `name_map`, `action_log`, `deliberation_trace`, `brief`) | always; any non-finite float as `"inf"`/`"-inf"`/`"nan"`, so the line is strict JSON |
| `final_time`, `final_state` | always; the summarised timeline |
| `probes`, `certainty_schedule` | only when non-empty |
| `compaction`, `forgetting`, `monitor`, `readout_series` | only when not `None` |
| `action_log[].value`, `.delta` | only when not `None` |
| `agent`, `model`, `memory`, `temperature`, `top_p` | always, stamped by `run_experiment`<br>`model`, `temperature`, `top_p` null unless the trial's kind is `llm` |
| `registration` | stamped only when the spec claims one |

`memory` is the cell's own level under a `memory` axis (round 4), `model` the cell's level under a `model` axis. The golden contract: `tests/suite/test_golden_experiments.py` runs every scripted catalog zero and pins the sha256 of its `records.jsonl`, each line re-dumped as sorted-key compact JSON with `wall_time_s` removed — the one wall-clock field. A key added after the zeros were pinned is written only when its feature is declared, so the zeros keep their bytes and the hashes prove the addition inert; a change meant to move records re-pins with `GOLDEN_UPDATE=1`, and the commit names which zeros moved. The field-by-field reading of the line is [ABIO TrialRecord](ABIO%20TrialRecord.md) § Only-when-set serialization and the golden contract.



## The manifest
The run's own proof, written by `_build_manifest` before any trial and updated in place by `run_experiment` at the end. Written with `json.dumps(indent=2)`, not canonically.

| Keys | What it proves | Written |
| --- | --- | --- |
| `name`, `spec`, `spec_sha256` | the spec the records were drawn under (`spec_to_dict`) and the sha256 of its canonical JSON | start |
| `alienbio_version`, `git_commit`, `git_dirty`, `python_version`, `platform`, `hostname` | the code and machine | start |
| `model`, `models` | the one model in force (`_single_model`); under a `model` axis `model` is null and `models` lists the levels (T066) | start |
| `model_created_at` | the generation behind the id, from `suite/models_snapshot.json` (T016); null under a `model` axis, with no model, or for an id the snapshot lacks | start |
| `memory`, `memories` | the memory policy; under a `memory` axis null, with the levels in `memories` | start |
| `temperature`, `top_p` | the sampling regime every live call ran under (M45.18) | start |
| `registration` | the resolved licence — `id`, `osf`, `filed`, sorted `dials` and `drafters` — or null (T030) | start |
| `directive_sha256` | sha256 of `DEFAULT_DIRECTIVE`, the system-prompt preamble — not the directive in force, equal today because `agents.py` passes no other | start |
| `design` | the power design, stated before the spend (M46.9), or null | start |
| `cost_estimate`, `cost_ceiling_usd` | the dry-run projection, pinned so actual spend can be compared (M45.5) | start |
| `started_at`, `trials_planned` | the start, and the grid size | start |
| `finished_at`, `trials_completed`, `failed_trials` | null at start, with the lines a resume kept (0 on a fresh run); after a crash, what landed; at the end the count of records on the map, error records included, and of those the error count | start, crash, end |
| `cost_usd_spent`, `usage_totals`, `stopped_reason` | priced usage of every landed record<br>summed token counts<br>`"cost_ceiling"` on an early stop | end |
| `cost_usd_retried` | the priced usage of the error lines a resume retried, already inside `cost_usd_spent` | end only |

The `models`/`memories` keys are absent, not empty, when nothing is swept, so `model` and `memory` stay one-type for every reader.



## Reload and its limits
`aggregate(out_dir)` rebuilds a `ReliabilityMap` from `manifest.json` (its `spec`, through `spec_from_dict`) and every non-blank `records.jsonl` line through `record_from_json`, then `aggregate_records`; no world is drafted, no trial run. Error lines ride `records` and are excluded from the cells there, as in the live run. The reload loses:

- **The timeline** — `final_timeline` is `Timeline(times=(final_time,), states=())`. Scores are frozen on the line, and `final_state` survives as a mapping, so every scorer in the report reads the same; code that indexes `final_timeline.states` does not.
- **Tuples** — a tuple condition level, oracle value or answer reloads as a list, so a reloaded `condition_key` can differ from the live one; `bucket_key` freezes both to the same key.
- **The line extras** — `agent`, `model`, `memory`, sampling and `registration` stay in the file and are not on the rebuilt record.
- **The early stop** — `aggregate_records` cannot know the grid stopped at the ceiling, so its provenance says `stopped_early: false`; the manifest's `stopped_reason` keeps the fact.



## Resume and retries
`run_experiment(spec, resume=True)` — `bio suite resume <DIR>`, with the manifest's own spec — first passes `preflight`, whose `resume` check refuses an unreadable manifest, one with no spec, or a spec that drifted beyond widening (more trials, new levels on an existing axis; `6d82c8b`, [ABIO Guards](ABIO%20Guards.md)). It then reads `records.jsonl` line by line:

| Line | What happens |
| --- | --- |
| clean | kept; its `(label, index)` is skipped by the grid |
| error, `TaintError`, `retry_taint=False` | kept in place and skipped — a taint is deterministic and would fail again |
| any other error | appended to `records.retried.jsonl`, dropped from `records.jsonl`, its priced usage added to the running spend; the trial re-runs |

When anything was retried, the error lines are appended to `records.retried.jsonl` first (skipping any already there), then `records.jsonl` is rewritten from the kept lines through a temp file, so `aggregate` never sees an error line next to its replacement: one line per `(label, index)`. A crash between the two leaves the error lines in `records.jsonl`; the next resume retries them again and appends nothing twice. Seeds are keyed by `(label, index)`, so a retried trial re-draws the same world. The manifest is then rebuilt from the current spec, carrying `started_at` from the old one and counting the kept lines, and the grid appends the missing trials.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD 057a6c1 (`store.py` last changed at `d53605e`); every member traced to `suite/store.py`, the writers and readers to `experiment.py` (`run_experiment` ~251–488, `aggregate` ~491–518), `guards.py` (`_resume` ~823, `_resume_spec_drift` ~650), `mass_trial.py` (`to_json`, `_aggregate`), `plots.py` (`write_key_figure`), `report_text.py` (`render_report`), `registration.py` (`to_dict`), `commands/suite_cmd.py`, `report.py` (`run_rows`), and the golden, round-trip, resume, round 4/5 and leftovers tests. There is no `tests/suite/test_store*.py`; the codec's round trip is `test_experiment.py::test_record_json_round_trip`. Left out as members: the alias `_final_state_dict` (= `trial.final_state_dict`, unused) and `_REPO_ROOT` (the same constant is defined in seven suite modules), both named in prose. The figure folds the codecs into the `append` and `lines` edges and the CLI verbs into the note beside `aggregate`; it draws the golden test on the left, beside the writers, so no read edge crosses the directory.
- Drift and defect hypotheses, not fixed (no code changes in this box):
  - The module docstring (`store.py` 1) says the module holds "resume drift"; `_resume_spec_drift` lives in `guards.py` ~650.
  - `report_text.render_report` (~37) prints `Model: {manifest['model']}`, which is `None` under a `model` axis; it never reads `models`. `report.py` `run_rows` (~286–300) does the same and lists a paid model-axis sweep as `scripted`, model `—`.
  - `bio suite aggregate` (`suite_cmd.py` ~173) rewrites `map.json` from the reload, whose provenance always says `stopped_early: false` (`mass_trial.py` ~375), overwriting the live map's `true` after a ceiling stop.
  - Non-finite floats outside the encoded fields (`objective_score`, `spent`, `final_state`, `oracle`, an action's `value`/`delta`, `usage`) and NaN anywhere are dumped as bare `NaN`/`Infinity` (`_canonical_json`, `store.py` 354), which strict JSON readers refuse; `w2_gen.py` ~603 guards one such case at the source.
  - `manifest.json` is written non-atomically (`experiment.py` 383, 483); a crash mid-write leaves a manifest that `preflight` now refuses to resume from and `aggregate` cannot parse, with the spec lost. `records.jsonl` gets temp-file + `replace`, the manifest does not.
  - On a resume, the retried lines are appended to `records.retried.jsonl` (~355) before `records.jsonl` is replaced (~359); a crash between the two re-appends the same lines on the next resume.
  - A resumed run that crashes leaves its manifest at `trials_completed: 0`, `finished_at: null` though `records.jsonl` holds every earlier line; `bio suite report` and `bio report` then print zero completed.
  - `directive_sha256` hashes `DEFAULT_DIRECTIVE` (`store.py` 389), not the directive in force; true today because `agents.py` never passes another, latent if one becomes a dial.
- The bare `:>>` line the daemon adds on write is left to it, as on the sibling suite docs.
- 2026-10-28 — fixed from the hypotheses above (alienbio `420b0cc` non-finite floats, `36ca296` atomic manifest + crash-safe retries, `002a936` resume/crash counts, `bce6629` the `model`-axis readers + docstring): every section above now states the fixed behaviour; tests in `tests/suite/test_moddoc_findings_store.py`. The retried-line skip keys on the whole line, not `(label, index)`, so a genuine second failure is still kept. The `stopped_early` reload item was fixed separately (`dbbfce1`).
