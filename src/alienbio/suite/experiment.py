"""Declarative experiment sweeps — spec, run, resume, aggregate, report (M46.5/M46.7/M46.11).

Every experiment run so far has been an ad-hoc script outside the repo, and
:class:`~alienbio.suite.mass_trial.MassTrialRunner` keeps its records only in
memory: nothing pins the code/model/prompt that produced a number, and a
crashed grid starts over from scratch. This module closes that gap:

- :class:`ExperimentSpec` + :func:`load_spec` — one YAML file names a dial
  sweep (``axes``), a world :data:`DRAFTERS` entry, an agent :data:`AGENTS`
  entry, and the fixed dials/trial count/seed everything else needs.
- :func:`run_experiment` — drives :class:`~alienbio.suite.mass_trial.MassTrialRunner`
  over the spec's condition grid, persisting every :class:`~alienbio.suite.trial.TrialRecord`
  to ``records.jsonl`` as it lands (:func:`record_to_json`) and a
  ``manifest.json`` pinning the code/model/spec that produced them, so a run
  directory is a reviewable, diffable, re-runnable artifact — resumable
  (``resume=True``) if it crashed partway.
- :func:`aggregate` / :func:`render_report` — rebuild the
  :class:`~alienbio.suite.mass_trial.ReliabilityMap` / text report from the
  on-disk record store alone, with no re-run.

**The no-peeking rule** (owner ruling 2026-08-27; see ``ABIO Experiment
Catalog`` § *The no-peeking rule*, and the static guard in
``tests/suite/test_no_peeking_lint.py``): agent ``"llm"`` is refused on any
conflict/pressure/delta drafter (:data:`GUARDED_DRAFTERS`) and on any world
carrying an alignment-bearing dial (:data:`GUARDED_DIALS` — hazard,
constitution, monitoring, framing, ...). "Neutral" is a property of the
world, not of the drafter's name: a plain ``diagnose`` / ``predict`` /
``intervene`` world is a capability substrate and may host a live model.
:func:`no_peeking_violation` is the one place the rule is encoded;
:func:`run_experiment` refuses before a single trial runs, let alone touches
the network.

**Layout (T058, 2026-09-10).** This module keeps :func:`run_experiment` and
:func:`aggregate` and re-exports everything else, so every import that ever
worked against it still does. The bands live in their own modules now:
``suite.spec`` (the spec, validators, ``load_spec``, the cost estimate),
``suite.drafters`` (the drafter heads, ``DRAFTERS``, the dial registry and the
guarded sets), ``suite.agents`` (the scripted factories, ``AGENTS``),
``suite.store`` (record/brief JSON, the manifest), ``suite.guards`` (the five
guards and :func:`preflight`) and ``suite.report_text`` (:func:`render_report`).
The ``expr_experiment`` <-> ``experiment`` import cycle is gone:
``expr_experiment`` imports ``spec`` / ``drafters`` / ``agents`` directly
(``_Drafters.__missing__`` stays — it serves drafters registered after
import by a catalog file's ``_includes_``).
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence, Union

from ..bio.world import WorldImpl
from .dist import Seed
from .llm_agent import PINNED_MODEL, cost_usd, price_for
from .mass_trial import MassTrialRunner, ReliabilityMap, aggregate_records, grid_positions
from .trial import TrialRecord
from .types import TaskInstance
from .spec import REPO_ROOT as _REPO_ROOT  # noqa: F401 — the old name

# ── T058: the module is the facade over spec / drafters / agents / store / guards / report_text —
#    every name the old 3.3k-line experiment.py defined is importable from here unchanged.
from .spec import (  # noqa: F401
    CostEstimate,
    ExperimentSpec,
    _DATED_MODEL_RE,
    default_expected_turns as _default_expected_turns,
    require_pinned_model as _require_pinned_model,
    _validate_cost_ceiling,
    _validate_design,
    _validate_key_readout,
    _validate_matched_dials,
    _validate_positive_int,
    _validate_price_override,
    _validate_registration_id,
    _validate_sampling,
    _validate_unit_float,
    agent_kinds_in_play,
    estimate_cost,
    load_spec,
    resolve_source_path,
    spec_from_dict,
    spec_to_dict,
)
from .drafters import (  # noqa: F401
    CATALYST_ID,
    CONFLICT_FREE_ADMITTED_DIALS,
    CONFLICT_FREE_DRAFTERS,
    DEFAULT_CATALYST_K,
    DEFAULT_CATALYST_LEVEL,
    DEFAULT_HAZARD_THRESHOLD,
    DELTA_ARMS,
    DRAFTERS,
    Draft,
    DrafterFn,
    EPISTEMIC_DISCLOSURE,
    WORLD_INVARIANT_DIALS,
    _DISCOVER_GATE_SIM,
    _Drafters,
    FACTORY_DIALS as _FACTORY_DIALS,
    GUARDED_BRIEF_DIALS as _GUARDED_BRIEF_DIALS,
    _adapt,
    _check_epistemic_access,
    _correlational_evidence,
    _generative_suite,
    _intermediate_branches,
    _no_carve,
    _pressure_pools,
    _unknown_dials_message,
    _with_oracle,
    commit_the_link,
    conflict,
    delta,
    describe_the_world,
    diagnose,
    dial_params,
    discover,
    drafter_heads,
    guarded_dials,
    guarded_drafters,
    identify_pathway,
    intervene,
    phase1_pressure,
    predict,
    pressure,
    runtime_dials,
    unknown_dials,
    unknown_spec_dials,
)
from .agents import (  # noqa: F401
    ACT_VALUE,
    AGENTS,
    AgentFactoryBuilder,
    PURSUE_RATE,
    _ActCommitAgent,
    _AssayCommitAgent,
    _HeuristicCommitAgent,
    _KnockoutCommitAgent,
    _PursueTargetAgent,
    _act_commit_agent_factory,
    _agent_factory_for,
    _assay_commit_agent_factory,
    _heuristic_commit_agent_factory,
    _idle_agent_factory,
    _idle_policy,
    _knockout_commit_agent_factory,
    _llm_agent_factory_builder,
    _make_measure_commit_policy,
    _make_survey_commit_policy,
    _measure_commit_agent_factory,
    _pursue_target_agent_factory,
    _survey_commit_agent_factory,
)
from .store import (  # noqa: F401
    RETRIED_FILENAME,
    directory_spend_usd,
    _append_retried,
    _atomic_write_text,
    _brief_from_json,
    _brief_to_json,
    _build_manifest,
    _canonical_json,
    _decode_float,
    _encode_float,
    _git_info,
    _json_safe,
    _trials_planned,
    _usage_usd,
    _utc_now_iso,
    _write_manifest,
    read_manifest,
    read_records,
    record_from_json,
    record_to_json,
)
from .guards import (  # noqa: F401
    PREFLIGHT_CHECKS,
    Preflight,
    _phase1_variants_in_play,
    _resume_spec_drift,
    declared_surface_violation,
    dials_in_play,
    no_peeking_violation,
    preflight,
    registration_admission,
    sampling_violation,
    unknown_dials_violation,
)
from .report_text import (  # noqa: F401
    _condition_label,
    idle_baseline_comparison,
    primary_contrast_result,
    render_report,
)


def run_experiment(
    spec: ExperimentSpec,
    *,
    out_dir: Optional[str] = None,
    resume: bool = False,
    on_error: str = "record",
    progress: Optional[Callable[[str], None]] = None,
    retry_taint: bool = False,
    notes: Optional[Callable[[str], None]] = None,
) -> ReliabilityMap:
    """Run (or resume) ``spec`` into ``out_dir``, persisting as it goes.

    Writes ``manifest.json`` at the start (updated if the grid raises and at the end),
    ``records.jsonl`` incrementally (one line per fresh trial), and, on
    completion, ``map.json``/``map.csv``/``report.txt``.

    ``resume=True`` reuses completed trials and RETRIES error records —
    the record a dead provider call leaves behind is the hole a resume
    exists to fill, not a result. Retried lines are preserved in
    ``records.retried.jsonl``, removed from ``records.jsonl`` (so the
    fresh replacement is the only line for its ``(label, index)``), and
    the count is announced through ``progress``. The seeds are keyed by
    ``(label, index)``, so a retried trial re-draws the same world.

    ``spec.cost_ceiling_usd`` (M45.5), when set, is checked against a running
    ``spent_usd`` total (every landed record's ``usage``, priced via
    :func:`~alienbio.suite.llm_agent.price_for` /
    :func:`~alienbio.suite.llm_agent.cost_usd`) before each fresh trial. The
    ceiling is the DIRECTORY's budget, not a press's: a resume starts the
    total from :func:`~alienbio.suite.store.directory_spend_usd` (``records.jsonl``
    plus every line earlier resumes moved to ``records.retried.jsonl``); once
    reached the grid stops cleanly (``manifest["stopped_reason"] ==
    "cost_ceiling"``) rather than overspending. The manifest also carries the
    dry-run ``cost_estimate`` (pinned at the start) and the actual
    ``cost_usd_spent``/``usage_totals`` (written at the end).

    Raises:
        ValueError: any :func:`~alienbio.suite.guards.preflight` check
            refuses (the first, in :data:`~alienbio.suite.guards.PREFLIGHT_CHECKS`
            order): the registration claim, the no-peeking rule, unknown or
            misplaced dials, the declared surface, the sampling regime, the
            W2 chain lag, the brief-side and agent dials, an unpriced model
            level, a condition whose world or brief refuses to draft, or a
            resume against an unreadable or drifted manifest — all before
            anything is drafted for the run or spent.
        FileExistsError: ``out_dir`` already holds ``records.jsonl`` and
            ``resume`` is ``False`` (never silently overwrite a paid run).
    """
    # T057 — every guard in one place, in one order, shared with `--dry`.
    flight = preflight(spec, out_dir=out_dir, resume=resume)
    if flight.refusal is not None:
        raise flight.refusal
    # T091 Y7 — ``notes`` (default: ``progress``) takes what a passing check
    # wants said (the re-drafted pre-stamp store), so the CLI can print it
    # without ``-v``.
    say_note = notes if notes is not None else progress
    if say_note is not None:
        for note in flight.notes:
            say_note(note)
    resolved_out = flight.out_dir
    resolved_out.mkdir(parents=True, exist_ok=True)
    records_path = resolved_out / "records.jsonl"
    manifest_path = resolved_out / "manifest.json"

    existing_by_key: dict[tuple[str, int], TrialRecord] = {}
    retried_usd = 0.0
    if resume and records_path.exists():
        # AUP 2026-09-09 — an error record is a hole, not a result: the common
        # reason a sweep dies partway (provider 400/429/500, an expired key, an
        # empty credit balance) is exactly what writes error records, so a
        # resume that reuses them re-reports the same failures in a second and
        # the log reads clean. A resume RETRIES error lines: they are moved to
        # records.retried.jsonl (the evidence survives), dropped from the
        # store (one line per (label, index) — aggregate must never see both
        # the old error and its fresh replacement), and announced.
        clean_lines: list[str] = []
        retried_lines: list[str] = []
        kept_taint = 0
        for line, d, record in read_records(records_path):
            if record.error_class == "TaintError" and not retry_taint:
                # T054 #2: a taint is framework-deterministic (same brief,
                # same leak), so retrying it re-spends the whole tainted
                # set on every press and lands the same error again. It
                # stays in place; `retry_taint=True` opts in once the leak
                # is fixed.
                kept_taint += 1
                clean_lines.append(line)
                existing_by_key[(d["label"], d["index"])] = record
                continue
            if record.error:
                retried_lines.append(line)
                # T051 box 4 — a retried line's real usage still counts
                # against the ceiling: before, every resume re-armed the
                # full ceiling with the prior press's error spend dropped
                # (three presses of a $4 ceiling spent $18, each manifest
                # reporting $6).
                if record.usage:
                    retried_usd += _usage_usd(record.usage, d.get("model"), spec)
                continue
            clean_lines.append(line)
            existing_by_key[(d["label"], d["index"])] = record
        if retried_lines:
            # Evidence first, then the store: a crash between the two leaves
            # the error lines in records.jsonl, the next resume reads them
            # again, and `_append_retried` skips the copies already kept — no
            # duplicate, and no retried line lost (T084, ABIO Store).
            _append_retried(resolved_out / RETRIED_FILENAME, retried_lines)
            _atomic_write_text(records_path, "".join(line + "\n" for line in clean_lines))
            if progress is not None:
                progress(
                    f"resume: retrying {len(retried_lines)} error record(s) "
                    "(originals kept in records.retried.jsonl)"
                )
        if kept_taint and progress is not None:
            progress(
                f"resume: keeping {kept_taint} TaintError record(s) in place — a taint is "
                "deterministic; fix the leak and pass retry_taint=True to re-run them"
            )

    def skip(label: str, i: int) -> Optional[TrialRecord]:
        return existing_by_key.get((label, i))

    started_at = _utc_now_iso()
    ceiling_history: list[Optional[float]] = [spec.cost_ceiling_usd]
    if resume and manifest_path.exists():
        # Preflight already refused an unreadable, spec-less or drifted
        # manifest; the start time and the ceiling history are carried.
        prior = read_manifest(manifest_path)
        started_at = prior.get("started_at", started_at)
        # T091 B3 — the ceiling may change on a resume; the manifest keeps
        # every value the run ran under, in order (a manifest from before
        # the field starts from its spec's own ceiling).
        ceiling_history = list(prior.get("cost_ceiling_history") or [prior["spec"].get("cost_ceiling_usd")])
        if ceiling_history[-1] != spec.cost_ceiling_usd:
            ceiling_history.append(spec.cost_ceiling_usd)

    trials_planned = _trials_planned(spec)
    manifest = _build_manifest(spec, trials_planned, started_at)
    manifest["cost_ceiling_history"] = ceiling_history
    # T084 (ABIO Store) — every landed line, keyed (label, index) -> is_error,
    # so the manifest's counts describe the store on disk at every write: a
    # resume starts from the lines it kept, not from 0, and a run that dies
    # mid-grid still says how many trials landed.
    landed: dict[tuple[str, int], bool] = {key: bool(r.error) for key, r in existing_by_key.items()}

    def _count_landed() -> None:
        manifest["trials_completed"] = len(landed)
        manifest["failed_trials"] = sum(landed.values())

    _count_landed()
    _write_manifest(manifest_path, manifest)

    def drafter(seed: Seed, dials: Mapping[str, Any]) -> tuple[WorldImpl, TaskInstance]:
        merged = {**spec.fixed_dials, **dials}
        return DRAFTERS[spec.drafter](seed, merged, **dict(spec.drafter_kwargs))

    agent_factory = _agent_factory_for(spec)

    # M45.5 — a running USD total, fed to `stop` below so a sweep with a
    # `cost_ceiling_usd` halts cleanly rather than overspending. A resume
    # seeds it from everything the directory already spent (T091 D: the
    # reused lines, this press's retried lines and every earlier press's —
    # the one total the resume guard checks); `on_trial` then adds only the
    # trials this press runs.
    spent_state = {"usd": directory_spend_usd(resolved_out, spec) if resume else 0.0}

    def on_trial(label: str, i: int, record: TrialRecord) -> None:
        cond = dict(record.condition_key)
        kind = str(cond.get("agent", spec.agent))
        # M45.11: the persisted "model" field means "this trial ran a live
        # model" — still gated on kind == "llm" so a scripted arm's line
        # keeps reading "model": null (unchanged pre-M45.5 contract).
        persisted_model = (cond.get("model") or spec.model or PINNED_MODEL) if kind == "llm" else None
        # M45.5: cost accounting keys off USAGE, not kind — a "scripted arm"
        # (record.usage is None) skips the price lookup entirely, but any
        # agent that DOES expose usage is priced under the model in force
        # for this trial (falling back to spec.model / PINNED_MODEL).
        if (label, i) not in existing_by_key:
            payload = record_to_json(record, label, i)
            # M45.11: the model and memory policy in force ride on EVERY line,
            # not only the manifest, so a record store can be read alone.
            payload["agent"] = kind
            payload["model"] = persisted_model
            # Round 4: the level in force — a ``memory`` axis runs per level
            # (T066) and every line used to say ``spec.memory``.
            payload["memory"] = cond.get("memory", spec.memory)
            # M45.18: the sampling in force on a live line (null on a scripted one).
            payload["temperature"] = spec.temperature if kind == "llm" else None
            payload["top_p"] = spec.top_p if kind == "llm" else None
            if spec.registration is not None:
                # T030 — a licensed line names its license; unregistered
                # runs' lines (and golden hashes) stay byte-unchanged.
                payload["registration"] = spec.registration
            line = _canonical_json(payload)
            with records_path.open("a") as f:
                f.write(line + "\n")
        # T051 box 4 — the price lookup runs AFTER the line is on disk: a
        # paid trial's usage is never lost to a pricing failure (which
        # ``estimate_cost`` now refuses before spend anyway).
        if record.usage and (label, i) not in existing_by_key:
            spent_state["usd"] += _usage_usd(record.usage, cond.get("model"), spec)
        landed[(label, i)] = bool(record.error)
        if progress is not None:
            progress(f"{label}#{i} {record.terminal_reason} score={record.objective_score}")

    def stop() -> bool:
        return spec.cost_ceiling_usd is not None and spent_state["usd"] >= spec.cost_ceiling_usd

    try:
        rmap = MassTrialRunner().run(
            list(spec.axes),
            drafter,
            agent_factory,
            spec.trials_per_condition,
            Seed(spec.base_seed),
            on_error=on_error,
            extra_dials=spec.fixed_dials,
            on_trial=on_trial,
            skip=skip,
            matched_dials=tuple(WORLD_INVARIANT_DIALS) + tuple(spec.matched_dials),
            concurrency=spec.concurrency,
            stop=stop,
        )
    except BaseException:
        # The grid died (a raised trial, a kill, Ctrl-C): record what landed
        # and the spend so far; ``finished_at`` stays null — the run did not
        # finish, and ``bio suite resume`` continues it.
        _count_landed()
        manifest["cost_usd_spent"] = spent_state["usd"]
        manifest["cost_usd_retried"] = retried_usd
        _write_manifest(manifest_path, manifest)
        raise

    (resolved_out / "map.json").write_text(rmap.to_json())
    (resolved_out / "map.csv").write_text(rmap.to_csv())

    usage_totals = {
        "calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
    }
    for record in rmap.records:
        if record.usage:
            for key in usage_totals:
                usage_totals[key] += record.usage.get(key, 0)

    manifest["finished_at"] = _utc_now_iso()
    manifest["trials_completed"] = len(rmap.records)
    manifest["failed_trials"] = rmap.provenance.failed_trials
    manifest["cost_usd_spent"] = spent_state["usd"]
    manifest["cost_usd_retried"] = retried_usd
    manifest["cost_ceiling_usd"] = spec.cost_ceiling_usd
    manifest["stopped_reason"] = "cost_ceiling" if rmap.provenance.stopped_early else None
    manifest["usage_totals"] = usage_totals
    _write_manifest(manifest_path, manifest)

    (resolved_out / "report.txt").write_text(render_report(rmap, manifest))
    from .plots import write_key_figure

    write_key_figure(rmap, resolved_out, readout=spec.key_readout)

    return rmap


def spec_from_manifest(manifest: Mapping[str, Any], *, current: bool = False) -> ExperimentSpec:
    """The spec a run directory's manifest describes (T091 E1, Y2).

    ``current=False`` (aggregate, report — the read-only verbs) returns the
    spec the records were drawn under — the manifest's own, rebuilt with
    ``validation="recorded"``: a rule that exists to stop a RUN and has
    tightened since the run was written (fixed-and-swept, a published price
    in the override mapping, …; :data:`~alienbio.suite.spec.RECORDED_NOTE_RULES`)
    lands on ``spec.recorded_warnings`` instead of refusing, so a finished
    run still reads. The recorded ``helper_modules`` (K E1) are executed
    directly — their ``_includes_`` decorators register the run's drafter
    and agents, which the manifest's spec names but cannot rebuild — and the
    experiment file itself is never re-read, so a run whose yaml was since
    deleted, moved or edited still aggregates. A helper that no longer
    exists, or lies outside the trusted ``catalog/`` root, refuses, naming it.

    ``current=True`` (resume) returns the file as it is NOW, strictly
    validated, so the resume's drift check compares the edited file against
    the manifest (drift is what a resume checks); a recorded file that no
    longer exists refuses, naming the path. A manifest without
    ``spec_path`` (a Python-built or replaced spec) is read from its
    ``spec`` alone either way, strictly on a resume."""
    if not current:
        _run_recorded_helpers(manifest.get("helper_modules") or ())
        return spec_from_dict(manifest["spec"], validation="recorded")
    recorded = manifest.get("spec_path")
    if recorded is None:
        return spec_from_dict(manifest["spec"])
    path = resolve_source_path(str(recorded))
    if not path.is_file():
        raise FileNotFoundError(
            f"the run's manifest names spec_path {recorded!r} ({path}), which does not exist — "
            "restore the experiment file (a resume compares it against the manifest)"
        )
    return load_spec(path)


def _run_recorded_helpers(helpers: Sequence[Any]) -> None:
    """Execute each recorded helper module (T091 Y2): a trusted load's
    ``_includes_`` registrations, without re-reading the experiment file.
    Only a file under the trusted ``catalog/`` root runs — the manifest is a
    file on disk, and only a catalog spec could have recorded a helper."""
    from ..expr.include import run_python_file

    trusted_root = (_REPO_ROOT / "catalog").resolve()
    for recorded in helpers:
        path = resolve_source_path(str(recorded)).resolve()
        if trusted_root not in path.parents:
            raise ValueError(
                f"the run's manifest names helper module {recorded!r} ({path}) outside the trusted "
                f"catalog root {trusted_root} — a recorded helper is executed only from there"
            )
        if not path.is_file():
            raise FileNotFoundError(
                f"the run's manifest names helper module {recorded!r} ({path}), which does not exist — "
                "restore it (it registers the run's drafter and agents)"
            )
        run_python_file(path)


def aggregate(out_dir: Union[str, Path], *, spec: Optional[ExperimentSpec] = None) -> ReliabilityMap:
    """Rebuild a :class:`~alienbio.suite.mass_trial.ReliabilityMap` from
    ``records.jsonl`` + ``manifest.json`` alone — no world is re-drafted, no
    trial is re-run. ``Provenance.stopped_early`` is read back from the
    manifest's ``stopped_reason``. ``spec`` is the recorded spec when the
    caller already loaded it (:func:`spec_from_manifest`, to print its
    ``recorded_warnings``); else it is loaded here, in recorded mode.

    Raises:
        FileNotFoundError: ``out_dir`` has no ``manifest.json``.
    """
    base = Path(out_dir)
    manifest_path = base / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"aggregate: no manifest.json in {base}")
    manifest = read_manifest(manifest_path)
    if spec is None:
        spec = spec_from_manifest(manifest)

    records_path = base / "records.jsonl"
    rows = [(d, record) for _line, d, record in read_records(records_path)] if records_path.exists() else []
    # T088 (mass_trial 4): a resume keeps the lines it reuses and appends the
    # re-run ones, so file order is not run order; the live map aggregates in
    # run order (grid position, then trial index). Sort back to it, so a
    # reloaded cell's float sums are taken in the same order as the live one's.
    # Stable: a line whose label the spec does not know keeps its file place
    # after every known one.
    positions = grid_positions(spec.axes)

    def run_order(row: tuple[dict[str, Any], TrialRecord]) -> tuple[int, int]:
        pos = positions.get(str(row[0].get("label")))
        return (len(positions), 0) if pos is None else (pos, int(row[0].get("index", 0)))

    rows.sort(key=run_order)
    records = [record for _d, record in rows]

    rmap = aggregate_records(records, spec.axes, Seed(spec.base_seed), spec.trials_per_condition)
    # The early stop is a fact about the run, not the records: the manifest
    # carries it (``stopped_reason``), and a reload that left the default
    # rewrote a ceiling-stopped run's map.json as complete (T084 B).
    stopped_early = manifest.get("stopped_reason") is not None
    return dataclasses.replace(rmap, provenance=dataclasses.replace(rmap.provenance, stopped_early=stopped_early))


def __getattr__(name: str) -> object:
    """``GUARDED_DRAFTERS`` / ``GUARDED_DIALS`` read through to
    :mod:`.drafters`, which computes them from the registry on every read
    (T088 drafters 3)."""
    if name in ("GUARDED_DRAFTERS", "GUARDED_DIALS"):
        from . import drafters

        return getattr(drafters, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
