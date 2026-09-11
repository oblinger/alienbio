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
import hashlib
import functools
import inspect
import warnings
import json
import math
import platform
import re
import statistics
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, NamedTuple, Optional, Protocol, Sequence, Union, cast

import yaml

from .. import __version__
from ..bio.world import WorldImpl
from ..bio.world_state import WorldStateImpl
from .agent import Action, Agent, Commit, Intervene, Measure, ReasoningStep, ScriptedAgent, Wait
from ..expr.registry import Head, fn as _head, registry as _registry
from .archetypes import identify_pathway as identify_pathway_archetype
from .brief import Affordances, TaskBrief
from .conflict_gen import draft_conflict_world
from .delta_gen import draft_delta_pair
from .delta import delta_summary
from .deliberation import DeliberationStep, DeliberationTrace
from .dist import Constant, Seed
from .info_seeking import ActionRecord
from .effect_size import cohens_d, welch_t
from .hazard import DEPTHS, OBJECTIVE_TYPES, blindspot_summary, consideration_summary, hazard_surfacing_summary
from .tradeoff import conflict_summary, precedence_ladder
from .dose import dose_profile, pressure_summary
from .caution import CAUTION_AXES, appropriate_caution, caution_factorial, caution_summary, caution_trend
from .degradation import degradation_ladder, degradation_summary
from .faking import monitoring_divergence, monitoring_summary
from .census import census_summary, outcome_distribution
from .llm_agent import DEFAULT_DIRECTIVE, PINNED_MODEL, PROVIDER_FIXED_SAMPLING, cost_usd, load_models_snapshot, model_created_at, price_for
from .power import PowerDesign, bonferroni_alpha
from .mass_trial import AgentFactory, MassTrialRunner, ReliabilityMap, aggregate_records
from .observation import Observation
from .pipeline import build_suite
from .phase1_gen import (
    PHASE1_DOWN_VARIANTS,
    PHASE1_VARIANTS,
    draft_phase1_world,
    phase1_chemistry_note,
)
from .pressure_gen import FEED_MAX_RATE, control_surface, draft_pressure_world, passive_reach
from .runner import run
from .trial import ProbeRecord, TrialRecord, final_state_dict
from .verify import SimConfig
from .types import (
    Answer,
    AnswerObjective,
    CarveResult,
    GraderSpec,
    Motif,
    Objective,
    OutcomeObjective,
    Question,
    SuiteSpec,
    TaskInstance,
    Timeline,
)

from .registration import REGISTRY_RELPATH, Registration, resolve_registration

_REPO_ROOT = Path(__file__).resolve().parents[3]

# ── T058: the module is the facade over spec / drafters / agents / store / guards / report_text —
#    every name the old 3.3k-line experiment.py defined is importable from here unchanged.
# ruff: noqa: F401
from .spec import (  # noqa: F401
    CostEstimate,
    ExperimentSpec,
    _DATED_MODEL_RE,
    _default_expected_turns,
    _require_pinned_model,
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
    GUARDED_DIALS,
    GUARDED_DRAFTERS,
    WORLD_INVARIANT_DIALS,
    _DISCOVER_GATE_SIM,
    _Drafters,
    _FACTORY_DIALS,
    _GUARDED_BRIEF_DIALS,
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
    _brief_from_json,
    _brief_to_json,
    _build_manifest,
    _canonical_json,
    _decode_float,
    _encode_float,
    _git_info,
    _json_safe,
    _trials_planned,
    _utc_now_iso,
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
) -> ReliabilityMap:
    """Run (or resume) ``spec`` into ``out_dir``, persisting as it goes.

    Writes ``manifest.json`` once at the start (updated at the end),
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
    :func:`~alienbio.suite.llm_agent.cost_usd`) before each fresh trial; once
    reached the grid stops cleanly (``manifest["stopped_reason"] ==
    "cost_ceiling"``) rather than overspending. The manifest also carries the
    dry-run ``cost_estimate`` (pinned at the start) and the actual
    ``cost_usd_spent``/``usage_totals`` (written at the end).

    Raises:
        ValueError: ``spec`` pairs agent ``"llm"`` with a non-neutral drafter
            (the no-peeking rule) — checked before anything is drafted.
        FileExistsError: ``out_dir`` already holds ``records.jsonl`` and
            ``resume`` is ``False`` (never silently overwrite a paid run).
    """
    # T057 — every guard in one place, in one order, shared with `--dry`.
    flight = preflight(spec, out_dir=out_dir, resume=resume)
    if flight.refusal is not None:
        raise flight.refusal
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
        with records_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                record = record_from_json(d)
                if record.error and record.error.startswith("TaintError") and not retry_taint:
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
                        retried_model = d.get("model") or spec.model or PINNED_MODEL
                        retried_usd += cost_usd(
                            record.usage.get("input_tokens", 0),
                            record.usage.get("output_tokens", 0),
                            price_for(retried_model, spec.price_usd_per_mtok),
                            cache_read_tokens=record.usage.get("cache_read_tokens", 0),
                            cache_write_tokens=record.usage.get("cache_write_tokens", 0),
                        )
                    continue
                clean_lines.append(line)
                existing_by_key[(d["label"], d["index"])] = record
        if retried_lines:
            with (resolved_out / "records.retried.jsonl").open("a") as f:
                for line in retried_lines:
                    f.write(line + "\n")
            rewritten = records_path.with_name("records.jsonl.tmp")
            rewritten.write_text("".join(line + "\n" for line in clean_lines))
            rewritten.replace(records_path)
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
    if resume and manifest_path.exists():
        # Drift already refused in preflight; only the start time is carried.
        try:
            prior_manifest = json.loads(manifest_path.read_text())
        except (OSError, ValueError):
            prior_manifest = {}
        started_at = prior_manifest.get("started_at", started_at)

    trials_planned = _trials_planned(spec)
    manifest = _build_manifest(spec, trials_planned, started_at)
    manifest_path.write_text(json.dumps(manifest, indent=2))

    def drafter(seed: Seed, dials: Mapping[str, Any]) -> tuple[WorldImpl, TaskInstance]:
        merged = {**spec.fixed_dials, **dials}
        return DRAFTERS[spec.drafter](seed, merged, **dict(spec.drafter_kwargs))

    agent_factory = _agent_factory_for(spec)

    # M45.5 — a running USD total over every landed record's real usage (both
    # freshly-run and resumed/``skip``-reused), fed to `stop` below so a
    # sweep with a `cost_ceiling_usd` halts cleanly rather than overspending.
    spent_state = {"usd": retried_usd}

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
            payload["memory"] = spec.memory
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
        if record.usage:
            cost_model = cond.get("model") or spec.model or PINNED_MODEL
            price = price_for(cost_model, spec.price_usd_per_mtok)
            spent_state["usd"] += cost_usd(
                record.usage.get("input_tokens", 0),
                record.usage.get("output_tokens", 0),
                price,
                cache_read_tokens=record.usage.get("cache_read_tokens", 0),
                cache_write_tokens=record.usage.get("cache_write_tokens", 0),
            )
        if progress is not None:
            progress(f"{label}#{i} {record.terminal_reason} score={record.objective_score}")

    def stop() -> bool:
        return spec.cost_ceiling_usd is not None and spent_state["usd"] >= spec.cost_ceiling_usd

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
    manifest_path.write_text(json.dumps(manifest, indent=2))

    (resolved_out / "report.txt").write_text(render_report(rmap, manifest))
    from .plots import write_key_figure

    write_key_figure(rmap, resolved_out, readout=spec.key_readout)

    return rmap


def aggregate(out_dir: Union[str, Path]) -> ReliabilityMap:
    """Rebuild a :class:`~alienbio.suite.mass_trial.ReliabilityMap` from
    ``records.jsonl`` + ``manifest.json`` alone — no world is re-drafted, no
    trial is re-run.

    Raises:
        FileNotFoundError: ``out_dir`` has no ``manifest.json``.
    """
    base = Path(out_dir)
    manifest_path = base / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"aggregate: no manifest.json in {base}")
    manifest = json.loads(manifest_path.read_text())
    spec = spec_from_dict(manifest["spec"])

    records: list[TrialRecord] = []
    records_path = base / "records.jsonl"
    if records_path.exists():
        with records_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                records.append(record_from_json(json.loads(line)))

    return aggregate_records(records, spec.axes, Seed(spec.base_seed), spec.trials_per_condition)
