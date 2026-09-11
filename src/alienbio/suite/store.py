"""The record store — record/brief JSON codecs, the manifest, resume drift (T058; split out of ``experiment.py``)."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, cast


from .. import __version__
from ..bio.world_state import WorldStateImpl
from .brief import Affordances, TaskBrief
from .deliberation import DeliberationStep, DeliberationTrace
from .info_seeking import ActionRecord
from .llm_agent import DEFAULT_DIRECTIVE, PINNED_MODEL, model_created_at
from .trial import ProbeRecord, TrialRecord, final_state_dict
from .types import (
    Timeline,
)


_REPO_ROOT = Path(__file__).resolve().parents[3]

from .spec import ExperimentSpec, estimate_cost, spec_to_dict


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


_final_state_dict = final_state_dict


def _brief_to_json(brief: TaskBrief) -> dict[str, Any]:
    out: dict[str, Any] = {
        "question": _json_safe(brief.question),
        "question_kind": brief.question_kind,
        "objective_kind": brief.objective_kind,
        "answer_kind": brief.answer_kind,
        "constitution": brief.constitution,
        "affordances": {
            "probes": list(brief.affordances.probes),
            "levers": list(brief.affordances.levers),
            "assays": list(brief.affordances.assays),
        },
        "budget_total": _encode_float(brief.budget_total),
        "budget_unit": brief.budget_unit,
        "action_costs": dict(brief.action_costs),
        "max_turns": brief.max_turns,
        "sim_steps": brief.sim_steps,
        "sim_dt": brief.sim_dt,
        "monitoring": _json_safe(brief.monitoring),
        "framing": brief.framing,
        "stakes": brief.stakes,
        "reversibility": brief.reversibility,
        "irreversible": list(brief.irreversible),
    }
    if brief.affordances.max_rates:
        # T023 — written only when a cap exists, so an uncapped experiment's
        # records (and golden hashes) stay byte-unchanged.
        out["affordances"]["max_rates"] = {k: v for k, v in sorted(brief.affordances.max_rates.items())}
    if brief.context_padding is not None:
        # T027 — written only when the commitment is buried, same golden rule.
        out["context_padding"] = brief.context_padding
    if brief.constitution_in_history:
        # T029 — written only under displacement, same golden rule.
        out["constitution_in_history"] = True
    if brief.protocol is not None:
        # T032 — written only when a scaffold rides the brief, same golden rule.
        out["protocol"] = brief.protocol
    return out


def _brief_from_json(d: Mapping[str, Any]) -> TaskBrief:
    aff = d["affordances"]
    return TaskBrief(
        question=d["question"],
        question_kind=d["question_kind"],
        objective_kind=d["objective_kind"],
        answer_kind=d["answer_kind"],
        constitution=d["constitution"],
        affordances=Affordances(
            probes=tuple(aff["probes"]),
            levers=tuple(aff["levers"]),
            assays=tuple(aff.get("assays") or ()),
            max_rates=dict(aff.get("max_rates") or {}),
        ),
        budget_total=_decode_float(d["budget_total"]),
        budget_unit=d["budget_unit"],
        action_costs=dict(d["action_costs"]),
        max_turns=d["max_turns"],
        sim_steps=d["sim_steps"],
        monitoring=d.get("monitoring"),
        framing=d.get("framing"),
        stakes=d.get("stakes"),
        reversibility=d.get("reversibility"),
        irreversible=tuple(d.get("irreversible") or ()),
        sim_dt=d["sim_dt"],
        context_padding=d.get("context_padding"),
        constitution_in_history=bool(d.get("constitution_in_history", False)),
        protocol=d.get("protocol"),
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
    final_state = dict(record.final_state) or (_final_state_dict(cast(WorldStateImpl, states[-1])) if states else {})

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
        "taint_hits": list(record.taint_hits),
        "turns": record.turns,
        "error": record.error,
        "usage": dict(record.usage) if record.usage is not None else None,
        "wall_time_s": record.wall_time_s,
        "action_log": [
            {
                "kind": a.kind,
                "destructive": a.destructive,
                "accepted": a.accepted,
                "reason": a.reason,
                "target": a.target,
                # T046 — only-when-set, so non-Intervene lines are unchanged.
                **({"value": a.value} if a.value is not None else {}),
                **({"delta": a.delta} if a.delta is not None else {}),
            }
            for a in record.action_log
        ],
        "deliberation_trace": [
            {"turn": s.turn, "kind": s.kind, "content": s.content, "refs": list(s.refs)}
            for s in record.deliberation_trace.steps
        ],
        "brief": _brief_to_json(record.brief) if record.brief is not None else None,
        "final_time": final_time,
        "final_state": final_state,
        "oracle": _json_safe(dict(record.oracle)),
        "answer": _json_safe(record.answer),
        "name_map": dict(record.name_map),
        **(
            {
                "probes": [
                    {"turn": pr.turn, "timing": pr.timing, "text": pr.text, "answer": pr.answer, "error": pr.error}
                    for pr in record.probes
                ]
            }
            if record.probes
            else {}
        ),
        **(
            {"certainty_schedule": [bool(x) for x in record.certainty_schedule]}
            if record.certainty_schedule
            else {}
        ),
        **(
            {"compaction": _json_safe(dict(record.compaction))}
            if record.compaction is not None
            else {}
        ),
        **(
            {"forgetting": _json_safe(dict(record.forgetting))}
            if record.forgetting is not None
            else {}
        ),
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
        ActionRecord(
            kind=a["kind"],
            destructive=a["destructive"],
            accepted=a["accepted"],
            reason=a["reason"],
            target=a.get("target", ""),
            value=a.get("value"),
            delta=a.get("delta"),
        )
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
        taint_hits=tuple(d.get("taint_hits", ())),
        turns=d["turns"],
        brief=brief,
        error=d["error"],
        usage=d.get("usage"),
        wall_time_s=d.get("wall_time_s", 0.0),
        oracle=dict(d.get("oracle") or {}),
        final_state=dict(d.get("final_state") or {}),
        name_map=dict(d.get("name_map") or {}),
        answer=d.get("answer"),
        probes=tuple(
            ProbeRecord(
                turn=pr["turn"], timing=pr["timing"], text=pr["text"],
                answer=pr.get("answer"), error=pr.get("error", ""),
            )
            for pr in d.get("probes") or ()
        ),
        certainty_schedule=tuple(bool(x) for x in d.get("certainty_schedule") or ()),
        compaction=d.get("compaction"),
        forgetting=d.get("forgetting"),
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
    from .guards import registration_admission  # guards imports this module; resolve late

    registration = registration_admission(spec)
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
        # The model actually in force: a live run without an explicit model
        # uses PINNED_MODEL, and the manifest must say so, not "None".
        "model": (spec.model or PINNED_MODEL) if spec.agent == "llm" else spec.model,
        # T016: the generation behind an undated id, from the recorded
        # models.list snapshot — what makes two runs naming it comparable.
        "model_created_at": model_created_at((spec.model or PINNED_MODEL) if spec.agent == "llm" else spec.model),
        "memory": spec.memory,
        # M45.18 — the sampling every live call ran under.
        "temperature": spec.temperature,
        "top_p": spec.top_p,
        # T030 — the resolved license (None when no registration is claimed):
        # the manifest proves the run's own admission.
        "registration": registration.to_dict() if registration is not None else None,
        "directive_sha256": directive_sha256,
        "started_at": started_at,
        "finished_at": None,
        "trials_planned": trials_planned,
        "trials_completed": 0,
        "failed_trials": 0,
        # M45.5 — the dry-run projection, pinned at start so a run's actual
        # spend (written at the end) can be compared against what it expected.
        "cost_estimate": asdict(estimate_cost(spec)),
        "cost_ceiling_usd": spec.cost_ceiling_usd,
        "cost_usd_spent": 0.0,
        "stopped_reason": None,
        "usage_totals": None,
        # M46.9 — the statistical design, stated before the spend.
        "design": spec.design.to_dict() if spec.design is not None else None,
    }


def _trials_planned(spec: ExperimentSpec) -> int:
    total = spec.trials_per_condition
    for _name, levels in spec.axes:
        total *= len(levels)
    return total
