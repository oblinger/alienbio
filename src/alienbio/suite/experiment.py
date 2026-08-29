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
``tests/suite/test_no_peeking_lint.py``): agent ``"llm"`` may only be paired
with a :data:`NEUTRAL_DRAFTERS` entry — :func:`run_experiment` refuses any
other pairing before a single trial runs, let alone touches the network.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Protocol, Sequence, Union, cast

import yaml

from .. import __version__
from ..bio.world import WorldImpl
from ..bio.world_state import WorldStateImpl
from .agent import Action, Agent, Commit, Measure, ReasoningStep, ScriptedAgent, Wait
from .archetypes import identify_pathway
from .brief import Affordances, TaskBrief
from .conflict_gen import draft_conflict_world
from .deliberation import DeliberationStep, DeliberationTrace
from .dist import Constant, Seed
from .info_seeking import ActionRecord
from .llm_agent import DEFAULT_DIRECTIVE, PINNED_MODEL
from .mass_trial import AgentFactory, MassTrialRunner, ReliabilityMap, aggregate_records
from .observation import Observation
from .pipeline import build_suite
from .pressure_gen import draft_pressure_world
from .trial import TrialRecord
from .types import (
    Answer,
    CarveResult,
    Motif,
    OutcomeObjective,
    Question,
    SuiteSpec,
    TaskInstance,
    Timeline,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]


# ═══════════════════════════════════════════════════════════════════════════
# ExperimentSpec — the declared shape of one experiment (M46.5)
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ExperimentSpec:
    """One declared experiment: axes to sweep, how to draft + how to act, and
    what to hold fixed. Loaded from YAML by :func:`load_spec`.

    ``axes`` and ``fixed_dials`` are both dial-vector mappings — ``axes``
    entries are SWEPT (one condition-cell per level combination, on
    :class:`~alienbio.suite.trial.TrialRecord.condition_key`); ``fixed_dials``
    apply identically to every condition and never appear in a condition key
    (e.g. ``max_turns``, ``sim_steps``, ``budget``, ``levers``).
    """

    name: str
    axes: tuple[tuple[str, tuple[Any, ...]], ...]
    drafter: str
    agent: str
    trials_per_condition: int
    base_seed: int
    drafter_kwargs: Mapping[str, Any] = field(default_factory=dict)
    model: Optional[str] = None
    memory: Union[str, int] = "full"
    token_ceiling: Optional[int] = None
    fixed_dials: Mapping[str, Any] = field(default_factory=dict)
    out_dir: Optional[str] = None


#: Keys ``load_spec``/``spec_from_dict`` will not build a spec without.
_REQUIRED_KEYS: frozenset[str] = frozenset(
    {"name", "axes", "drafter", "agent", "trials_per_condition", "base_seed"}
)

#: Every other recognised top-level key — everything else is a typo (M46.5:
#: an unknown key must not silently become a no-op).
_OPTIONAL_KEYS: frozenset[str] = frozenset(
    {"drafter_kwargs", "model", "memory", "token_ceiling", "fixed_dials", "out_dir"}
)

_ALL_KEYS: frozenset[str] = _REQUIRED_KEYS | _OPTIONAL_KEYS


def spec_to_dict(spec: ExperimentSpec) -> dict[str, Any]:
    """``ExperimentSpec`` -> a JSON-able dict (round-trips through :func:`spec_from_dict`).

    ``axes``/``fixed_dials`` render as plain mappings (dict insertion order
    preserves ``axes``' declared sweep order) — the same shape a YAML spec
    file uses.
    """
    return {
        "name": spec.name,
        "axes": {name: list(levels) for name, levels in spec.axes},
        "drafter": spec.drafter,
        "drafter_kwargs": dict(spec.drafter_kwargs),
        "agent": spec.agent,
        "model": spec.model,
        "memory": spec.memory,
        "token_ceiling": spec.token_ceiling,
        "trials_per_condition": spec.trials_per_condition,
        "base_seed": spec.base_seed,
        "fixed_dials": dict(spec.fixed_dials),
        "out_dir": spec.out_dir,
    }


def spec_from_dict(d: Mapping[str, Any]) -> ExperimentSpec:
    """A dict (as produced by :func:`spec_to_dict`, or a validated YAML load)
    -> :class:`ExperimentSpec`. Optional keys default exactly as the class does."""
    axes_raw = d["axes"]
    axes = tuple((name, tuple(levels)) for name, levels in axes_raw.items())
    return ExperimentSpec(
        name=d["name"],
        axes=axes,
        drafter=d["drafter"],
        agent=d["agent"],
        trials_per_condition=d["trials_per_condition"],
        base_seed=d["base_seed"],
        drafter_kwargs=dict(d.get("drafter_kwargs") or {}),
        model=d.get("model"),
        memory=d.get("memory", "full"),
        token_ceiling=d.get("token_ceiling"),
        fixed_dials=dict(d.get("fixed_dials") or {}),
        out_dir=d.get("out_dir"),
    )


def load_spec(path: Union[str, Path]) -> ExperimentSpec:
    """Load + validate a YAML :class:`ExperimentSpec` file.

    Raises:
        ValueError: the file is not a YAML mapping, names an unknown
            top-level key, or is missing a required one — a typo must never
            silently become a no-op.
    """
    with open(path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"load_spec: {path} must be a YAML mapping")

    unknown = sorted(set(raw) - _ALL_KEYS)
    if unknown:
        raise ValueError(f"load_spec: unknown experiment spec key(s): {unknown}")

    missing = sorted(_REQUIRED_KEYS - set(raw))
    if missing:
        raise ValueError(f"load_spec: missing required experiment spec key(s): {missing}")

    return spec_from_dict(raw)


# ═══════════════════════════════════════════════════════════════════════════
# DRAFTERS — registered world/task builders (M46.5)
# ═══════════════════════════════════════════════════════════════════════════


class DrafterFn(Protocol):
    """A registered :data:`DRAFTERS` entry: ``(seed, dials, **drafter_kwargs)
    -> (world, task)``, the exact shape :func:`~alienbio.suite.mass_trial.MassTrialRunner`
    threads a ``WorldDrafter`` through."""

    def __call__(
        self, seed: Seed, dials: Mapping[str, Any], **kwargs: Any
    ) -> tuple[WorldImpl, TaskInstance]: ...


def _draft_pressure(seed: Seed, dials: Mapping[str, Any], **kwargs: Any) -> tuple[WorldImpl, TaskInstance]:
    """``"pressure"`` — M31.2 emergent-instrumental-pressure world (``pi``/``complexity``).

    Wraps :func:`~alienbio.suite.pressure_gen.draft_pressure_world`'s
    ``(world, skeleton, objective)`` into a :class:`~alienbio.suite.types.TaskInstance`
    the same way ``tests/suite/test_mass_trial.py::_drafter`` does (a no-carve
    :class:`~alienbio.suite.types.CarveResult`), except the question names the
    real, JSON-serialisable target id the objective scores on
    (``objective.target[0]``) rather than an empty placeholder.
    """
    pi = dials["pi"]
    complexity = dials.get("complexity", 0)
    world, _skeleton, objective = draft_pressure_world(seed, pi=pi, complexity=complexity, **kwargs)
    assert isinstance(objective, OutcomeObjective)
    t_id = objective.target[0]
    task = TaskInstance(
        archetype=f"pressure_pi={pi}_c={complexity}",
        world="world0",
        skeleton=CarveResult(motif=Motif(roles=(), edges=()), binding={}),
        objective=objective,
        question=Question(structured={"kind": "outcome", "target": t_id}, kind="json"),
        setup={},
    )
    return world, task


def _draft_conflict(seed: Seed, dials: Mapping[str, Any], **kwargs: Any) -> tuple[WorldImpl, TaskInstance]:
    """``"conflict"`` — M31.1 conflict-ladder world (``rung``). Same wrapping as
    :func:`_draft_pressure`."""
    rung = dials["rung"]
    world, _skeleton, objective = draft_conflict_world(seed, rung=rung, **kwargs)
    assert isinstance(objective, OutcomeObjective)
    t_id = objective.target[0]
    task = TaskInstance(
        archetype=f"conflict_{rung}",
        world="world0",
        skeleton=CarveResult(motif=Motif(roles=(), edges=()), binding={}),
        objective=objective,
        question=Question(structured={"kind": "outcome", "target": t_id}, kind="json"),
        setup={},
    )
    return world, task


def _draft_identify_pathway(
    seed: Seed, dials: Mapping[str, Any], **kwargs: Any
) -> tuple[WorldImpl, TaskInstance]:
    """``"identify_pathway"`` — the neutral capability substrate (M27.1): the
    only :data:`DRAFTERS` entry a live model may run on (see :data:`NEUTRAL_DRAFTERS`)."""
    pathway_length = dials.get("pathway_length", 3)
    distractor_count = dials.get("distractor_count", 1)
    spec = SuiteSpec(
        archetype_mix=Constant(identify_pathway(pathway_length=pathway_length)),
        per_archetype={},
        seed=0,
    )
    suite = build_suite(spec, seed, n_tasks=1, distractor_count=distractor_count, **kwargs)
    return suite.worlds[0], suite.tasks[0]


#: Registered world/task drafters, by name — the ``drafter`` an :class:`ExperimentSpec` names.
DRAFTERS: Mapping[str, DrafterFn] = {
    "pressure": _draft_pressure,
    "conflict": _draft_conflict,
    "identify_pathway": _draft_identify_pathway,
}

#: Drafters a live model ("agent": "llm") may run on — the no-peeking rule
#: (ABIO Experiment Catalog § The no-peeking rule): every conflict/pressure/
#: delta substrate is off-limits to a live model until Alignment Under
#: Pressure has published. Membership, not exclusion, so a future non-neutral
#: drafter is guarded by default.
NEUTRAL_DRAFTERS: frozenset[str] = frozenset({"identify_pathway"})


# ═══════════════════════════════════════════════════════════════════════════
# AGENTS — registered agent factories (M46.5)
# ═══════════════════════════════════════════════════════════════════════════


class AgentFactoryBuilder(Protocol):
    """A registered :data:`AGENTS` entry: ``(spec) -> AgentFactory`` — resolves
    the spec's own ``model``/``memory``/``token_ceiling`` once, then hands back
    the per-trial ``(seed, dials) -> Agent`` builder."""

    def __call__(self, spec: ExperimentSpec) -> AgentFactory: ...


def _idle_policy(observation: Observation, seed: Seed) -> tuple[Action, tuple[ReasoningStep, ...]]:
    """``"idle"``'s policy: always ``Wait`` — the do-nothing baseline (AUP's idle baseline, M45.7)."""
    del observation, seed
    return Wait(duration=1.0), ()


def _idle_agent_factory(seed: Seed, dials: Mapping[str, Any]) -> Agent:
    del dials
    return ScriptedAgent(_idle_policy, seed=seed)


def _make_measure_commit_policy() -> Callable[[Observation, Seed], tuple[Action, tuple[ReasoningStep, ...]]]:
    """A fresh closure-counted policy for one trial: measure the first visible
    probe on turn 0, then commit on every subsequent call.

    Commits ``Answer(value=[], kind="json")`` — an empty, iterable, opaque
    "nothing submitted" sentinel that grades to ``0.0`` under every
    :func:`~alienbio.suite.grade.grade_answer` kind this registry's drafters
    exercise (``ordered_path`` via ``identify_pathway``) without raising —
    unlike a bare ``None``, which crashes ``ordered_path``/``node_set``
    grading (``list(None)``) before the "empty answer" case is even reached.
    """
    fired = [False]

    def policy(observation: Observation, seed: Seed) -> tuple[Action, tuple[ReasoningStep, ...]]:
        del seed
        if not fired[0]:
            fired[0] = True
            for compartment in observation:
                for probe in compartment:
                    return Measure(probe=probe), ()
        return Commit(answer=Answer(value=[], kind="json")), ()

    return policy


def _measure_commit_agent_factory(seed: Seed, dials: Mapping[str, Any]) -> Agent:
    del dials
    return ScriptedAgent(_make_measure_commit_policy(), seed=seed)


def _llm_agent_factory_builder(spec: ExperimentSpec) -> AgentFactory:
    """``"llm"`` — a real-model :class:`~alienbio.suite.llm_agent.LLMAgent`.

    Importing/constructing ``LLMAgent`` is lazy (inside the returned
    factory), so a spec naming ``"llm"`` only fails once a trial is actually
    about to run without a key (``default_anthropic_llm_fn`` raises then).
    """

    def factory(seed: Seed, dials: Mapping[str, Any]) -> Agent:
        del dials
        from .llm_agent import LLMAgent, default_anthropic_llm_fn

        model = spec.model or PINNED_MODEL
        return LLMAgent(
            default_anthropic_llm_fn(model),
            seed,
            memory=spec.memory,
            token_ceiling=spec.token_ceiling,
        )

    return factory


#: Registered agent factories, by name — the ``agent`` an :class:`ExperimentSpec` names.
AGENTS: Mapping[str, AgentFactoryBuilder] = {
    "idle": lambda spec: _idle_agent_factory,
    "measure-commit": lambda spec: _measure_commit_agent_factory,
    "llm": _llm_agent_factory_builder,
}


# ═══════════════════════════════════════════════════════════════════════════
# Record store — records.jsonl (M46.5)
# ═══════════════════════════════════════════════════════════════════════════


def _encode_float(value: float) -> Any:
    """``inf``/``-inf`` as the JSON string ``"inf"``/``"-inf"``; else the float verbatim."""
    if value == float("inf"):
        return "inf"
    if value == float("-inf"):
        return "-inf"
    return value


def _decode_float(value: Any) -> float:
    if value == "inf":
        return float("inf")
    if value == "-inf":
        return float("-inf")
    return float(value)


def _json_safe(value: Any) -> Any:
    """Recursively convert ``value`` into a ``json.dumps``-safe tree.

    Sets become sorted lists (``repr``-ordered, for a stable key sort);
    dict/list/tuple recurse. Anything else passes through verbatim — a
    caller still dumps with ``default=repr`` as the final safety net for any
    genuinely exotic leaf this function doesn't know about.
    """
    if isinstance(value, (set, frozenset)):
        return sorted((_json_safe(v) for v in value), key=repr)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _final_state_dict(state: WorldStateImpl) -> dict[str, dict[str, float]]:
    """``{compartment_id: {molecule_id: value}}`` read off a self-describing
    ``WorldStateImpl`` — ``{}`` for a pure-int state (no id axes to read)."""
    comp_ids = state.compartment_ids
    mol_ids = state.molecule_ids
    if comp_ids is None or mol_ids is None:
        return {}
    return {
        comp_ids[ci]: {mol_ids[mj]: state.get(ci, mj) for mj in range(len(mol_ids))}
        for ci in range(len(comp_ids))
    }


def _brief_to_json(brief: TaskBrief) -> dict[str, Any]:
    return {
        "question": _json_safe(brief.question),
        "question_kind": brief.question_kind,
        "objective_kind": brief.objective_kind,
        "answer_kind": brief.answer_kind,
        "constitution": brief.constitution,
        "affordances": {
            "probes": list(brief.affordances.probes),
            "levers": list(brief.affordances.levers),
        },
        "budget_total": _encode_float(brief.budget_total),
        "budget_unit": brief.budget_unit,
        "action_costs": dict(brief.action_costs),
        "max_turns": brief.max_turns,
        "sim_steps": brief.sim_steps,
        "sim_dt": brief.sim_dt,
    }


def _brief_from_json(d: Mapping[str, Any]) -> TaskBrief:
    aff = d["affordances"]
    return TaskBrief(
        question=d["question"],
        question_kind=d["question_kind"],
        objective_kind=d["objective_kind"],
        answer_kind=d["answer_kind"],
        constitution=d["constitution"],
        affordances=Affordances(probes=tuple(aff["probes"]), levers=tuple(aff["levers"])),
        budget_total=_decode_float(d["budget_total"]),
        budget_unit=d["budget_unit"],
        action_costs=dict(d["action_costs"]),
        max_turns=d["max_turns"],
        sim_steps=d["sim_steps"],
        sim_dt=d["sim_dt"],
    )


def record_to_json(record: TrialRecord, label: str, index: int) -> dict[str, Any]:
    """One :class:`~alienbio.suite.trial.TrialRecord` -> a JSON-able dict (one
    ``records.jsonl`` line). The final timeline is SUMMARISED: only the last
    ``(time, state)`` snapshot survives, as ``final_time`` + ``final_state``
    (``{compartment_id: {molecule_id: value}}``) — :func:`record_from_json`
    documents the corresponding loss.
    """
    times = record.final_timeline.times
    states = record.final_timeline.states
    final_time = times[-1] if times else None
    final_state = _final_state_dict(cast(WorldStateImpl, states[-1])) if states else {}

    return {
        "label": label,
        "index": index,
        "task_id": record.task_id,
        "condition_key": [[name, value] for name, value in record.condition_key],
        "objective_score": record.objective_score,
        "terminal_reason": record.terminal_reason,
        "budget": _encode_float(record.budget),
        "spent": record.spent,
        "remaining": _encode_float(record.remaining),
        "illegal_actions": record.illegal_actions,
        "turns": record.turns,
        "error": record.error,
        "action_log": [
            {"kind": a.kind, "destructive": a.destructive, "accepted": a.accepted, "reason": a.reason}
            for a in record.action_log
        ],
        "deliberation_trace": [
            {"turn": s.turn, "kind": s.kind, "content": s.content, "refs": list(s.refs)}
            for s in record.deliberation_trace.steps
        ],
        "brief": _brief_to_json(record.brief) if record.brief is not None else None,
        "final_time": final_time,
        "final_state": final_state,
    }


def record_from_json(d: Mapping[str, Any]) -> TrialRecord:
    """The inverse of :func:`record_to_json`.

    The store keeps only the SUMMARISED final timeline (the last snapshot),
    so the rebuilt ``final_timeline`` is ``Timeline(times=(final_time,),
    states=())`` — every intermediate turn's state is gone, and ``states`` is
    always empty; only the final time survives (``final_state`` is not
    reattached to ``final_timeline`` — it has no ``WorldState`` to become).
    """
    condition_key = tuple((name, value) for name, value in d["condition_key"])
    action_log = tuple(
        ActionRecord(kind=a["kind"], destructive=a["destructive"], accepted=a["accepted"], reason=a["reason"])
        for a in d["action_log"]
    )
    trace = DeliberationTrace(
        steps=tuple(
            DeliberationStep(turn=s["turn"], kind=s["kind"], content=s["content"], refs=tuple(s["refs"]))
            for s in d["deliberation_trace"]
        )
    )
    brief_d = d.get("brief")
    brief = _brief_from_json(brief_d) if brief_d is not None else None

    final_time = d.get("final_time")
    final_timeline = Timeline(times=(final_time,), states=()) if final_time is not None else Timeline(times=(), states=())

    return TrialRecord(
        task_id=d["task_id"],
        condition_key=condition_key,
        final_timeline=final_timeline,
        deliberation_trace=trace,
        action_log=action_log,
        objective_score=d["objective_score"],
        terminal_reason=d["terminal_reason"],
        budget=_decode_float(d["budget"]),
        spent=d["spent"],
        remaining=_decode_float(d["remaining"]),
        illegal_actions=d["illegal_actions"],
        turns=d["turns"],
        brief=brief,
        error=d["error"],
    )


# ═══════════════════════════════════════════════════════════════════════════
# Manifest (M46.7)
# ═══════════════════════════════════════════════════════════════════════════


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_info(repo_root: Path) -> tuple[str, bool]:
    """``(git_commit, git_dirty)`` — ``("unknown", False)`` if git is unavailable
    (never fails the run over provenance)."""
    try:
        commit = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout.strip()
    except Exception:
        return "unknown", False
    try:
        status = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout
        dirty = bool(status.strip())
    except Exception:
        dirty = False
    return commit, dirty


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=repr)


def _build_manifest(spec: ExperimentSpec, trials_planned: int, started_at: str) -> dict[str, Any]:
    spec_dict = spec_to_dict(spec)
    spec_sha256 = hashlib.sha256(_canonical_json(spec_dict).encode("utf-8")).hexdigest()
    git_commit, git_dirty = _git_info(_REPO_ROOT)
    directive_sha256 = hashlib.sha256(DEFAULT_DIRECTIVE.encode("utf-8")).hexdigest()
    return {
        "name": spec.name,
        "spec": spec_dict,
        "spec_sha256": spec_sha256,
        "alienbio_version": __version__,
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "hostname": platform.node(),
        "model": spec.model,
        "memory": spec.memory,
        "directive_sha256": directive_sha256,
        "started_at": started_at,
        "finished_at": None,
        "trials_planned": trials_planned,
        "trials_completed": 0,
        "failed_trials": 0,
    }


def _trials_planned(spec: ExperimentSpec) -> int:
    total = spec.trials_per_condition
    for _name, levels in spec.axes:
        total *= len(levels)
    return total


# ═══════════════════════════════════════════════════════════════════════════
# run_experiment / aggregate / render_report (M46.5/M46.7/M46.11)
# ═══════════════════════════════════════════════════════════════════════════


def _guard_no_peeking(spec: ExperimentSpec) -> None:
    if spec.agent == "llm" and spec.drafter not in NEUTRAL_DRAFTERS:
        raise ValueError(
            "run_experiment: the no-peeking rule (ABIO Experiment Catalog "
            f"§ The no-peeking rule) forbids agent 'llm' on drafter {spec.drafter!r}; "
            f"only {sorted(NEUTRAL_DRAFTERS)} may run a live model"
        )


def run_experiment(
    spec: ExperimentSpec,
    *,
    out_dir: Optional[str] = None,
    resume: bool = False,
    on_error: str = "record",
    progress: Optional[Callable[[str], None]] = None,
) -> ReliabilityMap:
    """Run (or resume) ``spec`` into ``out_dir``, persisting as it goes.

    Writes ``manifest.json`` once at the start (updated at the end),
    ``records.jsonl`` incrementally (one line per fresh trial), and, on
    completion, ``map.json``/``map.csv``/``report.txt``.

    Raises:
        ValueError: ``spec`` pairs agent ``"llm"`` with a non-neutral drafter
            (the no-peeking rule) — checked before anything is drafted.
        FileExistsError: ``out_dir`` already holds ``records.jsonl`` and
            ``resume`` is ``False`` (never silently overwrite a paid run).
    """
    _guard_no_peeking(spec)

    resolved_out = Path(out_dir or spec.out_dir or f"runs/{spec.name}")
    resolved_out.mkdir(parents=True, exist_ok=True)
    records_path = resolved_out / "records.jsonl"
    manifest_path = resolved_out / "manifest.json"

    if records_path.exists() and not resume:
        raise FileExistsError(
            f"run_experiment: {resolved_out} already holds records.jsonl "
            "(pass resume=True to continue, or choose a different out_dir)"
        )

    existing_by_key: dict[tuple[str, int], TrialRecord] = {}
    if resume and records_path.exists():
        with records_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                existing_by_key[(d["label"], d["index"])] = record_from_json(d)

    def skip(label: str, i: int) -> Optional[TrialRecord]:
        return existing_by_key.get((label, i))

    started_at = _utc_now_iso()
    if resume and manifest_path.exists():
        try:
            started_at = json.loads(manifest_path.read_text()).get("started_at", started_at)
        except (OSError, ValueError):
            pass

    trials_planned = _trials_planned(spec)
    manifest = _build_manifest(spec, trials_planned, started_at)
    manifest_path.write_text(json.dumps(manifest, indent=2))

    def drafter(seed: Seed, dials: Mapping[str, Any]) -> tuple[WorldImpl, TaskInstance]:
        merged = {**spec.fixed_dials, **dials}
        return DRAFTERS[spec.drafter](seed, merged, **dict(spec.drafter_kwargs))

    agent_factory = AGENTS[spec.agent](spec)

    def on_trial(label: str, i: int, record: TrialRecord) -> None:
        if (label, i) not in existing_by_key:
            line = _canonical_json(record_to_json(record, label, i))
            with records_path.open("a") as f:
                f.write(line + "\n")
        if progress is not None:
            progress(f"{label}#{i} {record.terminal_reason} score={record.objective_score}")

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
    )

    (resolved_out / "map.json").write_text(rmap.to_json())
    (resolved_out / "map.csv").write_text(rmap.to_csv())

    manifest["finished_at"] = _utc_now_iso()
    manifest["trials_completed"] = len(rmap.records)
    manifest["failed_trials"] = rmap.provenance.failed_trials
    manifest_path.write_text(json.dumps(manifest, indent=2))

    (resolved_out / "report.txt").write_text(render_report(rmap, manifest))

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


def _condition_label(key: Sequence[tuple[str, Any]]) -> str:
    return "&".join(f"{name}={value}" for name, value in key)


def render_report(rmap: ReliabilityMap, manifest: Mapping[str, Any]) -> str:
    """A plain-text report: header + per-condition table + failure census +
    interaction/contrast lines (when present). No third-party formatting."""
    lines: list[str] = []
    lines.append(f"Experiment: {manifest.get('name')}")
    lines.append(f"Commit: {manifest.get('git_commit')} (dirty={manifest.get('git_dirty')})")
    lines.append(f"Model: {manifest.get('model')}")
    lines.append(f"Started: {manifest.get('started_at')}   Finished: {manifest.get('finished_at')}")
    lines.append(
        f"Trials planned: {manifest.get('trials_planned')}   "
        f"completed: {manifest.get('trials_completed')}   "
        f"failed: {manifest.get('failed_trials')}"
    )
    lines.append("")

    lines.append("Conditions:")
    axis_names = [name for name, _ in rmap.provenance.axes]
    header = ", ".join(axis_names) if axis_names else "(condition)"
    lines.append(f"  {header:<40} {'n':>4} {'mean':>10} {'std':>10} {'ci_low':>10} {'ci_high':>10}")
    for key, summary in sorted(rmap.cells.items(), key=lambda kv: str(kv[0])):
        label = _condition_label(key)
        lines.append(
            f"  {label:<40} {summary.stats.n:>4} {summary.stats.mean:>10.4f} "
            f"{summary.stats.std:>10.4f} {summary.ci[0]:>10.4f} {summary.ci[1]:>10.4f}"
        )
    lines.append("")

    lines.append("Failure census:")
    terminal_counts: dict[str, int] = {}
    illegal_total = 0
    error_count = 0
    abort_counts: dict[str, int] = {}
    for record in rmap.records:
        terminal_counts[record.terminal_reason] = terminal_counts.get(record.terminal_reason, 0) + 1
        illegal_total += record.illegal_actions
        if record.error:
            error_count += 1
        for step in record.deliberation_trace.steps:
            if step.kind != "abort":
                continue
            for tag in ("parse_exhausted", "token_ceiling"):
                if tag in step.content:
                    abort_counts[tag] = abort_counts.get(tag, 0) + 1
    for reason, count in sorted(terminal_counts.items()):
        lines.append(f"  terminal_reason={reason!r}: {count}")
    lines.append(f"  illegal_actions (total): {illegal_total}")
    lines.append(f"  records with error: {error_count}")
    for tag, count in sorted(abort_counts.items()):
        lines.append(f"  aborted={tag!r}: {count}")

    if rmap.interactions or rmap.contrasts:
        lines.append("")
        lines.append("Interactions / contrasts:")
        for pair, value in sorted(rmap.interactions.items()):
            lines.append(f"  {pair[0]} x {pair[1]} interaction: {value:.4f}")
        for pair, contrast in sorted(rmap.contrasts.items()):
            lines.append(
                f"  {pair[0]} x {pair[1]} contrast: cohens_d={contrast.cohens_d:.4f} "
                f"welch_t={contrast.welch_t:.4f}"
            )

    lines.append("")
    return "\n".join(lines)
