---
description: "`guards`: every refusal a run makes before spend — `preflight` and its 19 ordered checks, the no-peeking rule and the registration licence, the declared surface, unknown and misplaced dials, the price check and one drafted world per condition. Source: `src/alienbio/suite/guards.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Guards](ha://p/ABIO%20Guards) 
# ABIO Guards
The gate in front of every paid run: `preflight` puts an `ExperimentSpec` through nineteen checks in a fixed order and returns every verdict, so `run_experiment` can raise the first refusal and `bio suite run --dry` can print them all, before a single world is simulated or a model is called.

![ABIO Guards](ABIO%20Guards.svg) 
*The no-peeking rule and the registration licence* is the topic that governs the licence group; *The draft check* governs group 5, skipped once anything above it refused.

`suite/guards.py` has no primary class: its exports are `preflight`, the `Preflight` result it returns, the check-name tuple, and one `*_violation` function per check, each returning `None` or the refusal's text. This page covers those. The dial sets the guards read live in `suite/drafters.py` (`DRAFTERS`, `guarded_drafters()`, `guarded_dials()`, `EPISODE_DIALS`, `WORLD_INVARIANT_DIALS`, `runtime_dials()`, `FACTORY_DIALS`, `CONFLICT_FREE_DRAFTERS`); the registry parser and `REGISTRY_RELPATH` in `suite/registration.py`; `ExperimentSpec`, `agent_kinds_in_play` and `estimate_cost` in `suite/spec.py`; the certainty slice rule `certainty_slice_problem` in `suite/runner.py`. The brief-side refusals the `draft` check reaches by calling `build_brief` are [ABIO TaskBrief](ABIO%20TaskBrief.md)'s; the trial a passing spec then runs is [ABIO Runner](ABIO%20Runner.md). The subsystem view is [ABIO-Experiment](../../ABIO%20Architecture/ABIO-Experiment.md); the operator's list is [ABIO Suite Runtime](../../ABIO%20Architecture/ABIO%20Suite%20Runtime.md) § Every refusal happens before spend, which matches the source's order.



## Preflight Interface
A frozen dataclass: what one `preflight` call found. `checks` holds every check's verdict in [PREFLIGHT_CHECKS](#^preflight-checks) order, whether or not an earlier one refused; `refusal` is the first refusal as the exception the run raises. Built only by `preflight`; `run_experiment` reads `refusal` and `out_dir`, `bio suite run --dry` reads `lines()` and `estimate`.

| Preflight | |
| --- | --- |
| [out_dir](#^out-dir) | The run's output folder, resolved as the run resolves it |
| [out_exists](#^out-exists) | Whether it already holds `records.jsonl` |
| [checks](#^checks) | Every check's name and verdict, in order |
| [skipped](#^skipped) | Checks not run because an earlier one refused |
| [resume](#^resume) | Whether the call was a resume |
| [estimate](#^estimate) | The dry-run cost estimate |
| [refusal](#^refusal) | The first refusal, as the exception |
| [ok](#^ok) | Whether nothing refused |
| [lines](#^lines) | The verdicts as `--dry` prints them |

**out_dir**`: Path`
    `Path(out_dir or spec.out_dir or f"runs/{spec.name}")`. `preflight` never creates it; `run_experiment` does, after a clean preflight. ^out-dir

**out_exists**`: bool`
    `records.jsonl` exists under `out_dir` at the moment of the call; the `out_dir` check refuses on it unless `resume`. ^out-exists

**checks**`: tuple[tuple[str, Optional[str]], ...]`
    One `(name, verdict)` pair per check: `None` for a pass (or a skip), else `str(exc)` of the refusal. A refusing check does not stop later ones ([The preflight order](#the-preflight-order)). ^checks

**skipped**`: tuple[str, ...] = ()`
    Names of the checks marked `only_if_clean` that did not run because something earlier refused; today only `draft`. Their `checks` entry carries `None`, so read this before reading a `None` as a pass. ^skipped

**resume**`: bool = False`
    The `resume` argument. When false, the `resume` check had nothing to compare and `lines()` prints it as skipped. ^resume

**estimate**`: Optional[CostEstimate]`
    `estimate_cost(spec)` from the `price` check; `None` when pricing itself refused. ^estimate

**refusal**`: Optional[BaseException]`
    The first exception any check raised: a `ValueError` whose text starts `run_experiment:` for the violation checks, the bare `ValueError` of `registration_admission` / `resolve_registration` for the claim, `FileExistsError` for `out_dir`. ^refusal

**ok**`: bool` (property)
    `refusal is None`. ^ok

**lines**`() -> list[str]`
    `out_dir exists: yes (run refuses without resume)` or `no`, then one line per check: `<name>: ok`, `<name>: REFUSED — <why>`, or `<name>: skipped (an earlier check refused)`; off a resume, `resume: skipped (not a resume)` (it used to print `resume: ok` for a check with nothing to compare). ^lines



## guards Interface
The module-level exports, in the order a run meets them. `experiment.py` re-exports `PREFLIGHT_CHECKS`, `Preflight`, `preflight`, `registration_admission`, `no_peeking_violation`, `unknown_dials_violation`, `declared_surface_violation`, `sampling_violation` and `dials_in_play` (plus the private `_phase1_variants_in_play` and `_resume_spec_drift`), and `commands/suite_cmd.py` imports `preflight` through it; `store.py` calls `registration_admission` to stamp the resolved licence on the manifest. Each `*_violation` function is pure over the spec except `registration_admission` (reads the registry file), `agent_construction_violation` (builds scripted agents) and `draft_violation` (drafts worlds); none spends or calls a model. `REGISTRY_RELPATH` is imported here from `registration.py`, and the registration tests monkeypatch it on this module, since this is where `registration_admission` reads it.

| guards | |
| --- | --- |
| [preflight](#^preflight) | Run every check in order; one `Preflight` |
| [PREFLIGHT_CHECKS](#^preflight-checks) | The nineteen check names, in run order |
| [registration_admission](#^registration-admission) | Resolve a `registration:` claim against the registry |
| [no_peeking_violation](#^no-peeking-violation) | A live model on a guarded world or dial, unlicensed |
| [unknown_dials_violation](#^unknown-dials-violation) | A dial name nothing reads |
| [fixed_factory_dials_violation](#^fixed-factory-dials-violation) | An agent-factory dial in `fixed_dials` |
| [misplaced_episode_dials_violation](#^misplaced-episode-dials-violation) | A clock dial in `drafter_kwargs` |
| [declared_surface_violation](#^declared-surface-violation) | A guarded drafter with no `levers` declared |
| [sampling_violation](#^sampling-violation) | A live arm with no `temperature` stated |
| [w2_lag_violation](#^w2-lag-violation) | A W2 depth whose chain lag breaks the bound |
| [brief_dials_violation](#^brief-dials-violation) | A malformed in-world monitor arm |
| [certainty_windows_violation](#^certainty-windows-violation) | Certainty slices that cannot cut the turn |
| [score_window_violation](#^score-window-violation) | A held-score window longer than the episode |
| [intervene_horizon_violation](#^intervene-horizon-violation) | An `intervene` budget ladder with no horizon pin |
| [inert_arm_violation](#^inert-arm-violation) | An arm that can measure nothing |
| [agent_construction_violation](#^agent-construction-violation) | A condition whose agent cannot be built |
| [draft_violation](#^draft-violation) | A condition whose world refuses to draft |
| [dials_in_play](#^dials-in-play) | Every dial name a run sets |

**preflight**`(spec: ExperimentSpec, *, out_dir: Optional[str] = None, resume: bool = False) -> Preflight`
    Resolves `out_dir`, then runs each check of [PREFLIGHT_CHECKS](#^preflight-checks) in order, catching any `Exception` as that check's refusal and keeping the first as `refusal`; `draft` is skipped once anything refused, and `records-readable` and `resume` do nothing off a resume. Never raises for a refusal, creates nothing, spends nothing. `run_experiment` calls it with its own `out_dir` and `resume`; `--dry` passes `resume=False`, the flag `bio suite run` itself passes ([Dry run and real run](#dry-run-and-real-run)). ^preflight

**PREFLIGHT_CHECKS**`: tuple[str, ...]`
    `("registration", "no-peeking", "dials", "labels", "episode-dials", "surface", "sampling", "w2-lag", "brief-dials", "certainty-windows", "score-window", "intervene-horizon", "inert-arm", "agent", "price", "draft", "records-readable", "resume", "out_dir")`: the names `checks` carries, in the order `preflight` runs them. A declaration only; `preflight` spells each name again in its own `check(...)` calls. ^preflight-checks

**registration_admission**`(spec: ExperimentSpec, registry_path: Optional[Path] = None) -> Optional[Registration]`
    `None` when `spec.registration` is unset. Otherwise resolves the id in the registry (`registry_path`, default the repo's `catalog/registrations.yaml`) through `resolve_registration`, which raises on a missing or unparseable file, an unknown id or a malformed entry; then raises `ValueError` when the entry names a drafter this build does not register, or does not name `spec.drafter`. Runs as the `registration` check whatever the agent, so a scripted run with a false claim refuses too ([The registry file](#the-registry-file)). ^registration-admission

**no_peeking_violation**`(spec: ExperimentSpec, registry_path: Optional[Path] = None) -> Optional[str]`
    `None` unless `"llm"` is among `agent_kinds_in_play(spec)` (the spec's `agent` plus any `agent` axis levels). Then, in order: a falsy `opaque_names` in play refuses, licence or not, when the spec's drafter is in `drafters.opaque_by_default_drafters()` (every guarded drafter plus `OPAQUE_SETUP_DRAFTERS`, i.e. `phase1_pressure`), the message naming the drafter and that set (T091 D7: off, a live model reads the world's structural ids, which the taint audit cannot see; on any other drafter `False` is the default it already runs under, K D7); a guarded drafter without a licence refuses; a phase-1 down-direction `variant` without a licence refuses; the guarded dials in play, less `constitution` on a conflict-free drafter, must all sit inside the licence's `dials`, or with no licence there must be none. Calls `registration_admission` itself, so a bad claim also raises here ([The no-peeking rule and the registration licence](#the-no-peeking-rule-and-the-registration-licence)). ^no-peeking-violation

**unknown_dials_violation**`(spec: ExperimentSpec) -> Optional[str]`
    The `fixed_dials` keys and axis names that neither the drafter head's own dials nor `runtime_dials()` read (`drafters.unknown_spec_dials`). The message, for a registered head, names what the head and the runtime do read and, when the head takes `**generator`, says generator overrides belong in `drafter_kwargs`. `drafter_kwargs` is not checked here ([Dials in play](#dials-in-play)). ^unknown-dials-violation

**fixed_factory_dials_violation**`(spec: ExperimentSpec) -> Optional[str]`
    Refuses any of `FACTORY_DIALS` (`agent`, `model`, `memory`, `compact_at`, `compact_budget`, `history_token_limit`, `max_tokens`, `output_schedule`) in `fixed_dials`: the factory reads the merged dial vector, but the guards and `estimate_cost` read the spec field and the axes, so `fixed_dials: {agent: llm}` passed every check, estimated $0.00 and ran a paid trial. Runs inside the `dials` check, after `unknown_dials_violation` (since `c63ad42`). ^fixed-factory-dials-violation

**misplaced_episode_dials_violation**`(spec: ExperimentSpec) -> Optional[str]`
    Refuses `max_turns`, `sim_steps` or `sim_dt` in `drafter_kwargs`: the drafter would size its derivation to that clock while the runner, which reads only the dial vector, ran another (T066: a `sim_dt` the episode never ran cleared the W2 lag bound and was stamped on the oracle). ^misplaced-episode-dials-violation

**declared_surface_violation**`(spec: ExperimentSpec) -> Optional[str]`
    On a guarded drafter, refuses unless `levers` is a `fixed_dials` key or an axis name, and refuses a declared value (fixed, or any axis level) that is not a list, naming it: `levers: null` used to pass ([The declared surface](#the-declared-surface)). `None` on every other drafter. ^declared-surface-violation

**sampling_violation**`(spec: ExperimentSpec) -> Optional[str]`
    With a live arm in play, refuses when `spec.temperature` is `None`: a number in `[0, 1]` or the literal `provider-fixed` must be stated (M45.18; the range and literal are validated at load by `spec.py`). ^sampling-violation

**w2_lag_violation**`(spec: ExperimentSpec) -> Optional[str]`
    On `pressure_w2` only: for every positive int `depth` in play times every `sim_dt` in play (else the runner's default `sim_cfg.dt`), runs `w2_gen.assert_chain_lag(depth, dt, k_harm_hop)` and returns its message on the first failure. `None` at depth 0 only, when `drafter_kwargs` sets `hop_delay_s` (the ledger form, which the instant-read bound does not cover), or when `k_harm_hop` is a non-constant distribution. ^w2-lag-violation

**brief_dials_violation**`(spec: ExperimentSpec) -> Optional[str]`
    Calls `monitor.resolve_monitor(dials)` on each condition's merged dial vector and returns the first exception's text, naming the condition: `monitor_coverage` out of range, a `monitor_sham` without coverage, the in-world monitor beside the told `monitoring` dial. ^brief-dials-violation

**certainty_windows_violation**`(spec: ExperimentSpec) -> Optional[str]`
    When `drafter_kwargs` sets `certainty_windows`: refuses a non-int or `< 1` value, then, per condition, `runner.certainty_slice_problem(sim_steps, windows, sample_every)` with the runner's defaults for an unset dial: `windows` must divide `sim_steps`, and when `windows > 1` each slice must be a multiple or a divisor of `sample_every`, or the recorded sample grid moves with the dial. A malformed `sim_steps` or `sample_every` is skipped here; the runner's own validation owns it. ^certainty-windows-violation

**score_window_violation**`(spec: ExperimentSpec) -> Optional[str]`
    When `drafter_kwargs` sets a positive numeric `score_window`: refuses the first condition whose horizon `max_turns × sim_steps × sim_dt` (runner defaults for unset dials) is shorter, since no window that long exists and `score_read="held"` would score every arm at the trajectory minimum. ^score-window-violation

**inert_arm_violation**`(spec: ExperimentSpec) -> Optional[str]`
    First refuses a factory-dial axis (other than `agent`) that no agent kind in the grid reads, by `agents.AGENT_DIALS`: its cells would differ only by label (T091 B11; only `llm` reads `memory`, the `compact_*` dials, `max_tokens` …). Then refuses the first condition whose `compact_at` (its dial, else `spec.compact_at`) is `>=` that cell's own `max_turns` (else the spec's derived turn count): turns are 0-based, so compaction would never fire and the arm would record `compaction: null`, indistinguishable from its control. ^inert-arm-violation

**intervene_horizon_violation**`(spec: ExperimentSpec) -> Optional[str]`
    On `intervene` only: refuses a `max_turns` axis when no `intervene_horizon` in play is set (an explicit `None` counts as unset, T091 F3). `intervene` derives its goal and passive reach, and scores the outcome, at that horizon, so an unpinned ladder gives every rung its own goal and reads the horizon, not the budget (T091 A4; `diagnose` has the same shape, pinned by `hazard_horizon`). ^intervene-horizon-violation

**agent_construction_violation**`(spec: ExperimentSpec) -> Optional[str]`
    Per condition: refuses an agent kind not in `agents.AGENTS`; for `llm`, calls `llm_agent.validate_agent_config` on the cell's `memory`, `compact_at`, `compact_budget`, `history_token_limit`, `max_tokens` and `output_schedule` (dial, else spec field) without building the agent, so no API key is needed; for any other kind, builds it through the spec's factory at `trial_seed.child("agent")` and checks that its `probe`, if any, binds the runner's `(text, observation)` call (the message names T088, which widened it). That mismatch refuses only on a condition that declares `probes`; elsewhere the run never calls `probe`, so it is a `UserWarning` (T091 B8, G4). ^agent-construction-violation

**draft_violation**`(spec: ExperimentSpec) -> Optional[str]`
    Refuses an unknown drafter. Otherwise drafts one world per condition at the seed its first trial will use, builds that condition's brief with the real `build_brief`, collects every config refusal (`ValueError`) and every fault (any other exception, named by class) from either, and returns them all joined by `; `, each naming its condition ([The draft check](#the-draft-check)). ^draft-violation

**dials_in_play**`(spec: ExperimentSpec) -> frozenset[str]`
    Every axis name, every `fixed_dials` key with a truthy value, and every `drafter_kwargs` key the drafter head declares as a dial, with a truthy value. What the no-peeking rule intersects with `guarded_dials()` ([Dials in play](#dials-in-play)). ^dials-in-play




# Guards Semantics

## The preflight order
`preflight` runs the checks below top to bottom. Each catches its own exception, so `checks` holds a verdict for every one; only `draft` is conditional, skipped once anything above it refused, because drafting every condition is the slowest check and a spec that already refuses will not run. `price` precedes `draft` for the same reason: an unpriced model level is the cheaper verdict. The order and names match [ABIO Suite Runtime](../../ABIO%20Architecture/ABIO%20Suite%20Runtime.md) § Every refusal happens before spend and [ABIO-Experiment](../../ABIO%20Architecture/ABIO-Experiment.md)'s pre-flight table at this source.

| Check | Function | Reads | Refuses when | Since |
| --- | --- | --- | --- | --- |
| `registration` | `registration_admission` | `spec.registration`, the registry file, `DRAFTERS` | the claim does not resolve, or does not cover the drafter | T030 |
| `no-peeking` | `no_peeking_violation` | agent kinds, `guarded_drafters()`, `guarded_dials()`, the licence | a live model meets a guarded drafter, variant or dial unlicensed | 2026-08-27 ruling; T030, T025, T048 |
| `dials` | `unknown_dials_violation`, `fixed_factory_dials_violation` | `fixed_dials` keys, axis names, head `dial_params`, `runtime_dials()` | a name nothing reads; a factory dial in `fixed_dials` | AUP 2026-09-10; round 4 |
| `labels` | `label_collision_violation` | the axes' levels, rendered as `_condition_label` renders them | two distinct cells share a label (`1` and `"1"`, or a level carrying `&b=`) — they would share a seed and a resume key | T088 (mass_trial round), 2026-10-28 |
| `episode-dials` | `misplaced_episode_dials_violation` | `drafter_kwargs`, `EPISODE_DIALS` | a clock dial only the drafter would see | T066 |
| `surface` | `declared_surface_violation` | `guarded_drafters()`, `levers` | a guarded drafter with no `levers`, or a non-list one | M45.2; T084 |
| `sampling` | `sampling_violation` | agent kinds, `temperature` | a live arm with sampling unstated | M45.18 |
| `w2-lag` | `w2_lag_violation` | `depth`, `sim_dt`, `k_harm_hop`, `hop_delay_s` | the instant-read chain lag exceeds the bound | AUP leg 3, 2026-09-15 |
| `brief-dials` | `brief_dials_violation` | each condition's monitor dials | `resolve_monitor` refuses | T066 |
| `certainty-windows` | `certainty_windows_violation` | `certainty_windows`, `sim_steps`, `sample_every` | slices do not divide the turn or miss the sample grid | T066; round 4 |
| `score-window` | `score_window_violation` | `score_window`, each cell's horizon | the window exceeds the episode | T066 |
| `intervene-horizon` | `intervene_horizon_violation` | `drafter`, the axes, `intervene_horizon` | an `intervene` `max_turns` axis with no `intervene_horizon` | T091 A4 |
| `inert-arm` | `inert_arm_violation` | factory-dial axes, `AGENT_DIALS`, `compact_at`, each cell's `max_turns` | a factory axis no agent in the grid reads; compaction can never fire | T066; round 4; T091 B11 |
| `agent` | `agent_construction_violation` | each condition's agent dials and `probe` signature | the agent kind or config refuses; a probe that cannot take `(text, observation)` with probes declared | T066; T091 B8 |
| `price` | `estimate_cost` | model levels, price table, turns, memory | a live model level has no price | T051 box 4 |
| `draft` | `draft_violation` | one drafted world and brief per condition | the drafter or `build_brief` refuses the condition | T066; round 4/5; T084 |
| `records-readable` | inline, `store.read_records` | `records.jsonl` and `records.retried.jsonl` under `out_dir`, each whenever it exists, ceiling or not | `resume=True` and a line of either does not parse (`StoreError`, named by line), so a torn line refuses before the resume moves anything | T091 B4, M4 |
| `resume` | `_resume_spec_drift` | `manifest.json` and `records.jsonl` under `out_dir` | `resume=True` and records exist with no manifest, the manifest is unreadable or spec-less, the ceiling is below the directory's spend (`records.jsonl` + `records.retried.jsonl`), or the spec drifted | T051 box 4; round 5; T084; T091 B2/B3 |
| `out_dir` | inline | `records.jsonl` under `out_dir` | records exist and `resume` is false | M46 |

The condition-wise checks (`brief-dials`, `certainty-windows`, `score-window`, `inert-arm`, `agent`, `draft`) iterate the same units: one merged dial vector `{**fixed_dials, **condition}` per grid cell, paired with `base_seed.child(f"{label}/0")`, where `label` drops `WORLD_INVARIANT_DIALS` and `spec.matched_dials` exactly as `MassTrialRunner` does. Except `draft`, they stop at the first refusing condition.

`resume` refuses any changed spec field except two widenings: more `trials_per_condition`, and added levels on an existing axis. Three fields shape no record and are never drift (`_NON_RECORD_FIELDS`): `concurrency`, `out_dir` and `cost_ceiling_usd`, so a grid the ceiling stopped can be resumed under a raised one (T091 B3); the ceiling is the directory's budget and may not sit below what the directory already spent, `records.jsonl` plus `records.retried.jsonl` (`store.directory_spend_usd`; T091 D). `expected_turns` counts as unchanged when both sides hold their derived value (the largest `max_turns`), so widening a `max_turns` axis resumes. Both sides are compared in the manifest's JSON normal form (tuples as lists, mapping keys as strings, `nan` equal to `nan`; T091 D3), and axis levels by their typed, NaN-equal frozen form (`trial.frozen_value(level, typed=True, nan_equal=True)`, which first reads each level through `trial.plain_value`), so `1 → 1.0` is drift, a dict level in another key order is not, a numpy level (`np.linspace`) equals its JSON read-back and resumes, and a NaN level equals itself (T091 G1, K G1). The manifest is read through `store.read_manifest`. An unreadable `manifest.json`, or one carrying no `spec`, refuses the resume, naming the file. A directory holding `records.jsonl` but no manifest refuses too (T091 B2): with no manifest the records cannot be matched to the spec they were drawn under. An empty directory with neither has nothing to continue and passes. `records-readable` runs first, so a torn last line is named by number before the drift check reads anything.



## The no-peeking rule and the registration licence
No language model runs on a substrate the Alignment Under Pressure paper has a registered question about, or with an alignment-bearing dial in play, unless a filed registration licenses exactly that pairing. The rule binds only when `"llm"` is among the spec's agent kinds; scripted agents characterise the world and pass. `test_no_peeking_lint.py` adds a static guard over `tests/`, `demos/` and the docs tree: no file may name both an LLM entry point and a pressure-family drafter.

| Case | No licence | With a licence covering the drafter |
| --- | --- | --- |
| guarded drafter (`guarded=True` head: `conflict`, `pressure`, `pressure_w2`, `delta`, `commit_the_link`, `describe_the_world`) | refused | admitted, dials checked below |
| `phase1_pressure` down variant (`coupling_down_*`, by fixed dial, kwarg or axis level) | refused | admitted |
| `opaque_names=False` on an opaque-by-default drafter (guarded, or `phase1_pressure`) | refused | refused |
| guarded dial in play (`guarded_dials()`) | refused | admitted only if in the licence's `dials` |
| `constitution` on a `CONFLICT_FREE_DRAFTERS` drafter (`phase1_pressure`) | admitted | admitted |
| any other guarded dial on that drafter (`monitoring`, `framing`, `stakes` …) | refused | admitted only if in the licence's `dials` |

`guarded_dials()` is the brief's guarded set (`constitution`, `monitoring`, `framing`, `stakes`, `reversibility`, `assays`, the three monitor dials, `task_note`), plus every head's `guarded_params`, plus every dial of a guarded head except `EPISODE_DIALS`. Both it and `guarded_drafters()` are recomputed on each call, so a guarded head a trusted `_includes_` file registers after import is refused too. A licence is all-or-nothing on scope: one out-of-scope dial refuses the run, naming the licence and its scope. A claim whose entry does not name the drafter raises rather than admitting nothing.



## The declared surface
On a guarded drafter the agent's levers are never every reaction id by default: the spec must declare them on the brief, `brief(levers=[...])`, or `levers=[]` for a do-nothing arm. The `surface` check tests that `levers` is a `fixed_dials` key or an axis and that every declared value is a list (`[]` allowed); the drafter adapter stamps `require_levers` on the task and `build_brief` enforces the same rule inside the trial. Which levers are legal is the brief's business, not this check's: the readout-molecule refusal, the hidden-pool refusal and the lever-entry shape are [ABIO TaskBrief](ABIO%20TaskBrief.md)'s, and `draft` reaches every one of them before spend by calling `build_brief`.



## Dials in play
A run's dial vector is `{**fixed_dials, **condition}`; the drafter adapter splats `drafter_kwargs` straight into the head as well. So a dial can arrive three ways, and each guard reads all three where it matters (T066: guards that read only `axes` and `fixed_dials` let `drafter_kwargs: {epistemic_access: 2}` draw a guarded brief on a live model with no licence).

| Name class | Who reads it | Where it may be set |
| --- | --- | --- |
| head dial (`dial_params` of the drafter) | the drafter | axis, `fixed_dials`, `drafter_kwargs` (counted in play) |
| generator setting (`feed_max_rate`, `target_margin`, `certainty_windows`, `score_window`, `hop_delay_s`, `sim_cfg` …) | the generator through `**generator` | `drafter_kwargs` only; never registration-checked |
| episode dial (`max_turns`, `sim_steps`, `sim_dt`) | the drafter and the runner | axis or `fixed_dials`; `drafter_kwargs` refused |
| factory dial (`agent`, `model`, `memory`, `compact_at`, `compact_budget`, `history_token_limit`, `max_tokens`, `output_schedule`) | the agent factory | spec field (fixed) or axis; `fixed_dials` refused |
| world-invariant dial (`WORLD_INVARIANT_DIALS`) | brief, episode or factory | anywhere legal; dropped from the seed label, so arms share worlds |

The known set is derived, not listed: a head's `dial_params` (its keyword parameters, less `env`/`ctx` and `**generator`) plus `runtime_dials()`, which reads the `brief` and `episode` heads' signatures in `expr_experiment.py` and adds `WORLD_INVARIANT_DIALS` and `FACTORY_DIALS`. A fixed dial with a falsy value (`hazard: false`, `0`, `""`) is not in play.



## The draft check
For each condition, `draft_violation` calls `DRAFTERS[spec.drafter](trial_seed.child("draft"), dials, **drafter_kwargs)` with the seed and merged dials the run's first trial of that condition will use, so a seed-dependent refusal (the `certainty` floor, which `world_variance` moves per draw) is the run's own verdict. A later trial's seed can still refuse on the run; drafting every seed is the run.

A `ValueError` (including `SkeletonError`) is a configuration refusal, worded `drafts no world`: it is how a generator deliberately refuses a dial vector. Any other exception is a generator fault, worded `generator error <Class>: …`, and refuses too: a drafter is a pure function of seed and dials with no provider call, so the run would crash on the same draft (T084 finding D; `TypeError` and `KeyError` used to read as config, and every other class was skipped as transient). Every refusing condition is named in one joined message; it used to stop at the first, and to return `None` at the first non-config exception, hiding every later refusal.

Each drafted condition's brief is then built by the real `build_brief`, through `_first_brief`, which mirrors `runner.run`'s preamble: the runner's default clock overridden by the cell's `max_turns`/`sim_steps`/`sim_dt`/`sample_every`, the `budget` dial, the turn-0 observation with `hidden_ids` projected out, and the seeds `trial_seed.child("run")` uses. A `ValueError` from it is that condition's refusal (`builds no brief`): `assays` naming no reaction, a lever on the readout or on a `hidden_ids` pool (T066 Q1), a malformed `levers` entry, and any brief refusal added later. No agent is built and nothing is simulated (T084 finding A: only the hidden-pool refusal was pulled forward before, as a hand copy of `build_brief`'s logic).



## Price and the cost ceiling
The `price` check is `estimate_cost(spec)`: zero live trials price at $0.00 with no lookup; otherwise every `model` axis level (or `spec.model`, else the pinned model) must resolve through `price_for`, with `spec.price_usd_per_mtok` as an override, or the check refuses before anything is drafted. Turns default to the largest declared `max_turns`, else the runner's 50; a `memory` axis is priced per level. The estimate is advisory: it rides the manifest and `--dry`'s output, and nothing compares it with `cost_ceiling_usd`. The ceiling is enforced at run time by `run_experiment`'s `stop()`, against the priced usage of every landed record, so it stops a grid after the unit that crossed it, not before.



## Dry run and real run

| | `run_experiment` | `bio suite run --dry` |
| --- | --- | --- |
| calls | `preflight(spec, out_dir=…, resume=…)` | `preflight(spec, out_dir=…, resume=False)` |
| on a refusal | raises `flight.refusal`, the first | prints every `lines()` verdict<br>then `preflight: REFUSED`, exits 1 |
| on success | creates `out_dir`, writes the manifest, runs the grid | prints the plan, the estimate and the ceiling, exits 0 |
| `resume` check | runs when `resume=True` (`bio suite resume <DIR>`) | `resume: skipped (not a resume)`: `bio suite run` never resumes, so neither does its `--dry`; a directory holding records refuses on `out_dir`, as the run does |

A refusal message from a violation check starts `run_experiment:` in both, since the text is the same exception; the no-peeking one adds the rule's name.



## The registry file
`catalog/registrations.yaml` maps a registration id to exactly four keys, `osf`, `filed` (YYYY-MM-DD), `dials` and `drafters`; `registration.py` refuses any other key, a missing one, or an empty list. The file lands only by commit, so every licence has provenance, and `test_registration.py` pins the three filed AUP entries, so deleting one is a red test rather than a refusal discovered at launch.

| Id | OSF | Filed | Drafters | Dials beyond the shared five |
| --- | --- | --- | --- | --- |
| `aup-awareness` | `osf.io/pj7ny` | 2026-09-01 | `pressure` | none |
| `aup-pressure` | `osf.io/ekpd7` | 2026-09-03 | `pressure` | none |
| `aup-exploration` | `osf.io/xnc2p` | 2026-08-31 | `pressure`, `phase1_pressure`, `pressure_w2` | `stakes`, `depth`, `fan_out`, `distractor_depth`, `world_variance`, the three monitor dials, `task_note` |

The shared five are `pi`, `complexity`, `certainty`, `epistemic_access`, `constitution`. A licensed run stamps the claimed id on every record line and the resolved entry on the manifest.




# BRIEF
- 2026-10-27 — written as an ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD 2f32083 (`guards.py` unchanged since `2a7c8ed`; re-checked at `d0a2797`); every member and claim traced to `suite/guards.py`, with the seams checked against `drafters.py` (dial sets, `_adapt`, `runtime_dials`), `registration.py` + `catalog/registrations.yaml`, `spec.py` (`agent_kinds_in_play`, `estimate_cost`, `default_expected_turns`), `experiment.py` (`run_experiment`, the drafter closure, `stop()`), `commands/suite_cmd.py` (`--dry`), `mass_trial.py` (seed labels), `brief.py` (the lever refusals) and the guard, registration, T066, round 4/5 and hidden-pool tests. Left out as members: the private helpers `_head_dials`, `_drafter_kwarg_dials`, `_dial_values_in_play`, `_condition_units`, `_condition_dial_vectors`, `_phase1_variants_in_play`, `_resume_spec_drift` and `preflight`'s inner `check`/`_raise_if`, named in prose where a reader needs them; `guarded_drafters()`/`guarded_dials()`, `REGISTRY_RELPATH` and `certainty_slice_problem` are imported, not defined here, so they are described, not given blocks. The figure groups the sixteen checks into six bands of my choosing; the grouping is not in the source. The `out_dir` check's "Since" is given as M46, the milestone that built the run store; the exact origin commit was not traced.
- Drift found, fixed 2026-10-28 (with findings A–E below): `preflight`'s docstring "Order:" (~694) lists nine of the sixteen checks; `draft_violation`'s docstring (~354) says "at the base seed" where the code drafts at each condition's first-trial seed; the module docstring and `ABIO-Experiment` still say "the five guards", and `ABIO-Experiment`'s pre-flight table has seven rows, attributes the readout-lever refusal to `declared_surface_violation` and gives `guards.py` 307 lines (786 today).
- 2026-10-28 — findings A–E fixed and this page updated with each: the `draft` check builds every condition's brief with the real `build_brief` (the hand-copied hidden-pool check is gone); a non-list `levers` is a `surface` refusal; an unreadable or spec-less manifest refuses a resume; only `ValueError` is a config refusal, any other drafter or brief exception a named generator error that still refuses; `--dry` prints `resume: skipped (not a resume)`. The docstrings and `ABIO-Experiment`'s pre-flight table, modules row and `--dry` list were made true in the same pass.
- 2026-10-28 — refreshed against 0eb23e5 (`01fee6a`): the resume check reads the manifest through `store.read_manifest`; the description's check count corrected to 17.
- 2026-10-29 — refreshed for `e392c11`, `e5ea4d0` and `661005d` (T091 A4, B2–B4, B8, B11, D3, D7, F3, G1, G4): nineteen checks (`intervene-horizon` and `records-readable` added, with a block for `intervene_horizon_violation`); resume refuses records without a manifest and a ceiling below spend, never counts `concurrency`/`out_dir`/`cost_ceiling_usd` as drift, and compares JSON-canonical, typed frozen values; no-peeking refuses a falsy `opaque_names`; `inert-arm` refuses a factory axis no agent reads; `agent` checks the probe signature (warning only without probes). Figure: the check count and two band lines updated in place, nothing redrawn.
- 2026-10-29 — refreshed for `c80cf5f` and `fab20be` (T091 D, K D7, K G1): the resume ceiling is checked against `directory_spend_usd`; `opaque_names=False` refuses only on opaque-by-default drafters; drift compares plain-valued, NaN-equal frozen levels.
- 2026-10-29 — refreshed for `fa72cb8` (T091 M4): `records-readable` reads `records.retried.jsonl` too, whenever it exists, ceiling or not, so a torn tail there refuses before a resume moves its error lines. Figure still true.
