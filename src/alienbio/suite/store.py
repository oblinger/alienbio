"""The record store — record/brief JSON codecs, the manifest and its atomic writers (T058; split out of ``experiment.py``; resume drift lives in ``guards.py``)."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional, cast


from .. import __version__
from ..bio.world_state import WorldStateImpl
from .brief import Affordances, TaskBrief
from .deliberation import DeliberationStep, DeliberationTrace
from .info_seeking import ActionRecord
from .llm_agent import DEFAULT_DIRECTIVE, PINNED_MODEL, cost_usd, model_created_at, price_for
from .trial import ProbeRecord, TrialRecord, final_state_dict
from .types import (
    Timeline,
)



from .spec import REPO_ROOT, ExperimentSpec, agent_kinds_in_play, estimate_cost, spec_to_dict


# ═══════════════════════════════════════════════════════════════════════════
# Record store — records.jsonl (M46.5)
# ═══════════════════════════════════════════════════════════════════════════


#: The one spelling of a non-finite float in the store: a JSON string, so
#: every line is strict JSON (``_canonical_json`` dumps with
#: ``allow_nan=False``) and a strict reader never meets ``NaN``/``Infinity``.
_NONFINITE: dict[str, float] = {"inf": float("inf"), "-inf": float("-inf"), "nan": float("nan")}

#: A STRING leaf that would read as a non-finite spelling — ``"nan"``,
#: ``"inf"``, ``"-inf"``, or one of those behind any number of backslashes —
#: is written with one more leading backslash, so the bare spelling on disk
#: is only ever a float and a prose dial ``"nan"`` reads back as the string
#: it was (T091 B7: ``read_manifest`` turned a ``task_note: "inf"`` into a
#: float and a resume of the unchanged spec refused as drift).
_ESCAPED = re.compile(r"\\*(?:nan|inf|-inf)")


def _encode_float(value: float) -> Any:
    """A non-finite float as the JSON string ``"inf"``/``"-inf"``/``"nan"``; else the float verbatim."""
    if isinstance(value, float) and not math.isfinite(value):
        return "nan" if math.isnan(value) else ("inf" if value > 0 else "-inf")
    return value


def _decode_float(value: Any) -> float:
    """One float field of a DECODED tree (:func:`_decode_nonfinite` already ran)."""
    return float(value)


def _encode_nonfinite(value: Any) -> Any:
    """``value`` as the store spells it, at any depth: every non-finite float
    through :func:`_encode_float`, every string that could be mistaken for
    one escaped with one more leading backslash (:data:`_ESCAPED`).

    Applied exactly ONCE per write — by :func:`_canonical_json` (a record
    line, the spec hash) and :func:`_write_manifest`; the codecs above them
    return plain trees. (It is not idempotent: an escaped string escapes
    again.) Dict/list/tuple recurse (each keeps its type); every other leaf
    passes through. A finite tree with no such string comes back equal, so
    its dumped bytes are unchanged.
    """
    if isinstance(value, float):
        return _encode_float(value)
    if isinstance(value, str):
        return "\\" + value if _ESCAPED.fullmatch(value) else value
    if isinstance(value, dict):
        return {k: _encode_nonfinite(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_encode_nonfinite(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_encode_nonfinite(v) for v in value)
    return value


def _decode_nonfinite(value: Any) -> Any:
    """The inverse of :func:`_encode_nonfinite`, over a whole parsed tree:
    a bare ``"inf"``/``"-inf"``/``"nan"`` is the writer's float, an escaped
    one loses one backslash and stays a string. Applied once, to the whole
    line (:func:`record_from_json`) or manifest (:func:`read_manifest`) —
    since the writer escapes every string it could collide with, there is
    no field the decode must skip."""
    if isinstance(value, str):
        if value in _NONFINITE:
            return _NONFINITE[value]
        if value.startswith("\\") and _ESCAPED.fullmatch(value):
            return value[1:]
        return value
    if isinstance(value, dict):
        return {k: _decode_nonfinite(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode_nonfinite(v) for v in value]
    return value


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
        "budget_total": brief.budget_total,
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
    if brief.monitor is not None:
        # T060 — written only under a monitor arm, same golden rule.
        out["monitor"] = brief.monitor
    if brief.task_note is not None:
        # T061 — written only when a task note rides the brief, same golden rule.
        out["task_note"] = brief.task_note
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
        monitor=d.get("monitor"),
        task_note=d.get("task_note"),
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
        "budget": record.budget,
        "spent": record.spent,
        "remaining": record.remaining,
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
        **(
            {"monitor": _json_safe(dict(record.monitor))}
            if record.monitor is not None
            else {}
        ),
        # T088 — written only when set, so goldens are byte-unchanged.
        **({"parse_failures": int(record.parse_failures)} if record.parse_failures else {}),
        **({"aborted": record.aborted} if record.aborted is not None else {}),
        **({"grade_error": record.grade_error} if record.grade_error is not None else {}),
        # T091 A1 — only when a run-out ran.
        **({"runout": _json_safe(dict(record.runout))} if record.runout is not None else {}),
        # T091 K3 — only when the audit exempted an id the agent named.
        **({"taint_exempt": {str(k): int(v) for k, v in sorted(record.taint_exempt.items())}} if record.taint_exempt else {}),
        **(
            # T062 — written only when the drafter declares readouts.
            {"readout_series": {rid: list(vals) for rid, vals in record.readout_series.items()}}
            if record.readout_series is not None
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
    # T091 B7: the whole line is decoded once (the writer escapes every
    # string a non-finite spelling could collide with), so a string level
    # ``"nan"`` in ``condition_key`` stays a string and a float NaN a float.
    d = _decode_nonfinite(dict(d))
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
        monitor=d.get("monitor"),
        parse_failures=int(d.get("parse_failures", 0)),
        aborted=d.get("aborted"),
        grade_error=d.get("grade_error"),
        runout=d.get("runout"),
        taint_exempt={str(k): int(v) for k, v in (d.get("taint_exempt") or {}).items()},
        readout_series=(
            {rid: tuple(_decode_float(v) for v in vals) for rid, vals in d["readout_series"].items()}
            if d.get("readout_series") is not None
            else None
        ),
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
    """Sorted-key compact strict JSON: every non-finite float is spelled by
    :func:`_encode_nonfinite`, and ``allow_nan=False`` refuses any that
    slipped past (a ``default=repr`` leaf cannot be one)."""
    return json.dumps(
        _encode_nonfinite(payload), sort_keys=True, separators=(",", ":"), default=repr, allow_nan=False
    )


def _atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` through a temp file in the same directory and
    ``os.replace``: a reader sees the old file or the new one, never a torn one."""
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("w") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _write_manifest(path: Path, manifest: Mapping[str, Any]) -> None:
    """``manifest.json`` written atomically (temp file + ``os.replace``).

    A crash mid-dump used to leave a torn manifest that ``preflight`` refuses
    to resume from and ``aggregate`` cannot parse — with the spec, the only
    copy of what the records were drawn under, lost. Now the old manifest
    stands until the new one is whole.

    The manifest is strict JSON like every record line (T088 leftovers): a
    non-finite float anywhere — a spec carrying ``inf`` in a dial, a ceiling
    or a level — is spelled ``"inf"``/``"-inf"``/``"nan"`` by
    :func:`_encode_nonfinite`, and :func:`read_manifest` decodes it back. A
    finite manifest's bytes are unchanged.
    """
    text = json.dumps(_encode_nonfinite(manifest), indent=2, allow_nan=False)
    _atomic_write_text(path, text)


def read_manifest(path: Path) -> dict[str, Any]:
    """``manifest.json`` parsed, with the store's non-finite spellings
    decoded back (:func:`_decode_nonfinite`, over the whole manifest) — the
    one reader every resume, aggregate and report goes through, so a spec
    carrying ``inf`` round-trips equal, and a string dial ``"inf"`` stays a
    string (T091 B7).

    Raises whatever ``json.loads`` / the read raises (callers that must
    word an unreadable manifest catch ``OSError``/``ValueError``).
    """
    return _decode_nonfinite(json.loads(path.read_text()))


class StoreError(ValueError):
    """A record store that cannot be read as written: a line that is not
    JSON, named by file and 1-based line number (T091 B4)."""


def read_records(path: Path) -> Iterator[tuple[str, dict[str, Any], TrialRecord]]:
    """Every ``records.jsonl`` line as ``(line, parsed dict, record)``, blank
    lines skipped — the one reader the resume and :func:`aggregate` share
    (the line is kept verbatim so a resume can rewrite the store from it;
    the dict is decoded like the record).

    Raises:
        StoreError: a line does not parse — named by file and line number,
            and called out as a crash artifact when it is the last line
            with no newline (an append torn mid-write). Nothing is dropped
            silently: the line is evidence, and which repair is right
            (delete the torn tail, or restore it) is the operator's call.
    """
    text = path.read_text()
    lines = text.split("\n")
    for number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except ValueError as exc:
            torn = number == len(lines) and not text.endswith("\n")
            where = (
                "the last line, with no trailing newline — an append torn by a crash or a full disk; "
                "delete that line (or restore it) and resume"
                if torn
                else "edit or restore it before reading the store"
            )
            raise StoreError(f"{path}: line {number} is not valid JSON ({exc}) — {where}") from None
        yield line, _decode_nonfinite(raw), record_from_json(raw)


def _usage_usd(usage: Mapping[str, Any], model: Optional[str], spec: ExperimentSpec) -> float:
    """USD for one record's provider ``usage`` under the model in force for
    its trial (``model``, else ``spec.model``, else :data:`PINNED_MODEL`) —
    the one pricing of a landed or retried line against the cost ceiling."""
    return cost_usd(
        usage.get("input_tokens", 0),
        usage.get("output_tokens", 0),
        price_for(model or spec.model or PINNED_MODEL, spec.price_usd_per_mtok),
        cache_read_tokens=usage.get("cache_read_tokens", 0),
        cache_write_tokens=usage.get("cache_write_tokens", 0),
    )


#: Where a resume keeps the error lines it retried (beside ``records.jsonl``).
RETRIED_FILENAME = "records.retried.jsonl"


def records_spend_usd(path: Path, spec: ExperimentSpec, *, exclude: frozenset[str] = frozenset()) -> float:
    """What the lines of one record file spent, priced as the run prices
    them; a line in ``exclude`` (verbatim) is skipped, a missing file is 0."""
    if not path.exists():
        return 0.0
    return sum(
        _usage_usd(record.usage, d.get("model"), spec)
        for line, d, record in read_records(path)
        if record.usage and line not in exclude
    )


def directory_spend_usd(out_dir: Path, spec: ExperimentSpec) -> float:
    """Every dollar a run directory has spent: ``records.jsonl`` plus the
    error lines earlier resumes moved to ``records.retried.jsonl`` (T091 D).

    The cost ceiling is a DIRECTORY budget, not a press budget: the resume
    guard refuses a ceiling below this total, and a resumed run's spend
    counter starts from it — so three presses of a $4 ceiling stop at $4,
    whatever the presses retried. A retried line still byte-identical to a
    ``records.jsonl`` line (a resume that crashed between keeping the
    evidence and rewriting the store) counts once.
    """
    records = out_dir / "records.jsonl"
    live = frozenset(line for line, _d, _r in read_records(records)) if records.exists() else frozenset()
    return records_spend_usd(records, spec) + records_spend_usd(out_dir / RETRIED_FILENAME, spec, exclude=live)


def _append_retried(path: Path, lines: list[str]) -> None:
    """Append retried error lines to ``records.retried.jsonl``, skipping any
    line already there byte for byte.

    A resume appends here BEFORE it rewrites ``records.jsonl``, so a crash
    between the two loses no evidence; the next resume reads the same error
    lines again and this skip keeps them from landing twice. A trial that
    fails again on a later press writes a different line (its own usage,
    wall time and error), so a genuine second failure is still kept.
    """
    seen: set[str] = set()
    if path.exists():
        text = path.read_text()
        if text and not text.endswith("\n"):
            # T091 M4 — appending onto a torn tail glued the new evidence
            # into the unparseable line; preflight's records-readable check
            # refuses first, this is the store's own guard.
            raise StoreError(
                f"{path}: the last line has no trailing newline — an append torn by a crash or a "
                "full disk; delete that line (or restore it) before a resume appends to it"
            )
        seen = {line.strip() for line in text.splitlines() if line.strip()}
    fresh = [line for line in lines if line not in seen]
    if not fresh:
        return
    with path.open("a") as f:
        for line in fresh:
            f.write(line + "\n")


def _model_axis_levels(spec: ExperimentSpec) -> list[str]:
    """The ``model`` axis's levels, in declared order — empty when unswept."""
    for name, levels in spec.axes:
        if name == "model":
            return [str(level) for level in levels]
    return []


def manifest_model_label(manifest: Mapping[str, Any]) -> Optional[str]:
    """What a manifest says ran: its one ``model``, else the ``models`` levels
    of a ``model`` axis joined with ``", "``, else ``None`` (no live model).

    The one reading of the pair ``_build_manifest`` writes from
    :func:`_single_model` / :func:`_model_axis_levels`; ``render_report`` and
    ``bio report``'s run table both go through it, so a paid sweep never
    reads ``Model: None`` or ``scripted``.
    """
    model = manifest.get("model")
    if model:
        return str(model)
    levels = manifest.get("models") or []
    return ", ".join(str(level) for level in levels) if levels else None


def _axis_levels(spec: ExperimentSpec, axis: str) -> list[Any]:
    """``axis``'s levels as declared — empty when it is not swept."""
    for name, levels in spec.axes:
        if name == axis:
            return list(levels)
    return []


def _single_model(spec: ExperimentSpec) -> Optional[str]:
    """The one model id this run uses, or ``None`` when it sweeps several."""
    if _model_axis_levels(spec):
        return None
    # Round 5: every kind in play, not ``spec.agent`` alone — an ``agent``
    # axis ``[idle, llm]`` on a scripted spec ran its llm cells on
    # PINNED_MODEL while the header said ``model: null`` (and no
    # ``model_created_at``), as the record lines did not.
    return (spec.model or PINNED_MODEL) if "llm" in agent_kinds_in_play(spec) else spec.model


def _build_manifest(spec: ExperimentSpec, trials_planned: int, started_at: str) -> dict[str, Any]:
    spec_dict = spec_to_dict(spec)
    spec_sha256 = hashlib.sha256(_canonical_json(spec_dict).encode("utf-8")).hexdigest()
    git_commit, git_dirty = _git_info(REPO_ROOT)
    # DEFAULT_DIRECTIVE, not the directive in force: equal today (agents.py never passes another); latent if one becomes a dial.
    directive_sha256 = hashlib.sha256(DEFAULT_DIRECTIVE.encode("utf-8")).hexdigest()
    from .guards import registration_admission  # guards imports this module; resolve late

    registration = registration_admission(spec)
    return {
        "name": spec.name,
        "spec": spec_dict,
        "spec_sha256": spec_sha256,
        # T091 E1 — the file the spec was loaded from and the helper modules
        # its trusted ``_includes_`` executed, so ``bio suite
        # resume|aggregate|report`` reload the file (registering the helpers'
        # drafters and agents) and a resume compares the file as it is now
        # against the spec the records were drawn under. Absent for a
        # Python-built spec.
        **(
            {
                "spec_path": spec.source.get("spec_path"),
                "helper_modules": list(spec.source.get("helper_modules") or ()),
            }
            if spec.source
            else {}
        ),
        "alienbio_version": __version__,
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "hostname": platform.node(),
        # The model actually in force: a live run without an explicit model
        # uses PINNED_MODEL, and the manifest must say so, not "None".
        # T066: with a ``model`` AXIS this named ``spec.model`` — a generation
        # no cell runs. ``estimate_cost`` was taught about the axis in T051
        # box 4 and this was not, so the header said "claude-sonnet-5" while
        # the estimate said "mixed(...)" and every record line carried its
        # own, correct id.
        "model": _single_model(spec),
        # T066: with a ``model`` axis there is no single id, so ``model`` is
        # null and the swept levels ride their own field — rather than the
        # header naming one generation while every cell ran another. Kept a
        # separate key so ``model`` stays a string-or-null for every reader.
        **({"models": _model_axis_levels(spec)} if _model_axis_levels(spec) else {}),
        # T016: the generation behind an undated id, from the recorded
        # models.list snapshot — what makes two runs naming it comparable.
        # Absent for a swept axis: there is no single generation to date.
        "model_created_at": model_created_at(_single_model(spec)),
        # Round 4/5 leftover (2026-10-27): as ``model`` / ``models`` above —
        # under a ``memory`` axis no single window ran, so ``memory`` is null
        # and the swept levels ride ``memories``; every record line carries
        # its own cell's value (round 4).
        "memory": None if _axis_levels(spec, "memory") else spec.memory,
        **({"memories": _axis_levels(spec, "memory")} if _axis_levels(spec, "memory") else {}),
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
        # T091 B3 — a resume may change the ceiling (never below what the
        # records spent); every value the run has run under, in order.
        "cost_ceiling_history": [spec.cost_ceiling_usd],
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
