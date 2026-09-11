"""Every refusal a run makes before spend — the five guards, the dial check and ``preflight`` (T058; split out of ``experiment.py``)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional


from ..expr.registry import registry as _registry
from .phase1_gen import (
    PHASE1_DOWN_VARIANTS,
)

from .registration import REGISTRY_RELPATH, Registration, resolve_registration

_REPO_ROOT = Path(__file__).resolve().parents[3]

from .drafters import (
    CONFLICT_FREE_ADMITTED_DIALS,
    CONFLICT_FREE_DRAFTERS,
    DRAFTERS,
    guarded_dials,
    guarded_drafters,
    unknown_spec_dials,
    _unknown_dials_message,
)
from .spec import CostEstimate, ExperimentSpec, agent_kinds_in_play, estimate_cost, spec_to_dict


def declared_surface_violation(spec: ExperimentSpec) -> Optional[str]:
    """M45.2 — why ``spec`` has no declared control surface: a guarded drafter
    (conflict / pressure / delta and the controls on them) with no ``levers``
    dial, fixed or swept. ``None`` otherwise. The default for those worlds is
    *no levers until declared*, failing visibly — never every reaction id."""
    if spec.drafter not in guarded_drafters():
        return None
    if "levers" in spec.fixed_dials or any(name == "levers" for name, _ in spec.axes):
        return None
    return (
        f"drafter {spec.drafter!r} is an AUP-registered substrate: declare the control surface on the brief "
        "(`brief: !q brief(levers=[...])`, `levers=[]` for a do-nothing arm) — the surface is never every reaction id by default (M45.2)"
    )


def sampling_violation(spec: ExperimentSpec) -> Optional[str]:
    """M45.18 — why ``spec`` cannot run a live arm: no ``temperature`` declared.
    ``None`` when every live call's sampling is stated (or there is no live arm)."""
    if "llm" not in agent_kinds_in_play(spec):
        return None
    if spec.temperature is None:
        return (
            "a run with a live-model arm must state its sampling (M45.18): `temperature:` a number in [0, 1], "
            "or the literal `provider-fixed` when the pinned model exposes no sampling knob "
            "(the Claude 5 API refuses temperature/top_p)"
        )
    return None

def unknown_dials_violation(spec: ExperimentSpec) -> Optional[str]:
    """Why ``spec`` carries a dial nobody reads — ``None`` when it does not.
    Checked before spend (``run_experiment``, ``bio suite run --dry``) so a
    misplaced key refuses the run instead of becoming N error records."""
    unknown = unknown_spec_dials(spec)
    if not unknown:
        return None
    if spec.drafter in _registry:
        return _unknown_dials_message(_registry.get(spec.drafter), unknown)
    return f"{spec.drafter}: unknown dial(s) {unknown}"


def dials_in_play(spec: ExperimentSpec) -> frozenset[str]:
    """Every dial name a run of ``spec`` sets: each axis, plus each
    ``fixed_dials`` entry whose value is truthy."""
    names = {name for name, _levels in spec.axes}
    names.update(name for name, value in spec.fixed_dials.items() if value)
    return frozenset(names)


def registration_admission(
    spec: ExperimentSpec, registry_path: Optional[Path] = None
) -> Optional[Registration]:
    """T030 — resolve ``spec.registration`` against the commit-tracked
    registry (``catalog/registrations.yaml``): the phase-2 unlock.

    ``None`` when the spec claims no registration. Otherwise the resolved
    :class:`~alienbio.suite.registration.Registration`, with every mismatch
    refused visibly (never silently unlicensed): a missing/unparseable
    registry or unknown id (:func:`~alienbio.suite.registration.resolve_registration`),
    an entry naming a drafter this build does not register (a typo that
    would otherwise admit nothing), or a claim by a spec whose ``drafter``
    the entry does not name.
    """
    if spec.registration is None:
        return None
    reg = resolve_registration(spec.registration, registry_path or (_REPO_ROOT / REGISTRY_RELPATH))
    unknown = sorted(reg.drafters - set(DRAFTERS))
    if unknown:
        raise ValueError(
            f"registration {reg.id!r} names unknown drafter(s) {unknown} — fix the registry entry"
        )
    if spec.drafter not in reg.drafters:
        raise ValueError(
            f"registration {reg.id!r} does not cover drafter {spec.drafter!r} "
            f"(it covers: {sorted(reg.drafters)}) — a claim outside its scope is refused, not ignored"
        )
    return reg


def _phase1_variants_in_play(spec: ExperimentSpec) -> set[str]:
    """Every ``variant`` value the spec can draft with — fixed dial,
    drafter kwarg, or ``variant`` axis level (T048's gate reads it)."""
    values: set[str] = set()
    for source in (spec.fixed_dials, dict(spec.drafter_kwargs or {})):
        v = source.get("variant")
        if isinstance(v, str):
            values.add(v)
    for name, levels in spec.axes:
        if name == "variant":
            values.update(level for level in levels if isinstance(level, str))
    return values


def no_peeking_violation(
    spec: ExperimentSpec, registry_path: Optional[Path] = None
) -> Optional[str]:
    """Why ``spec`` would peek — ``None`` when it would not. The one encoding
    of the no-peeking rule: a live model on a :data:`GUARDED_DRAFTERS` world,
    or on any world with a :data:`GUARDED_DIALS` dial in play. T030: a
    resolved ``registration:`` claim (:func:`registration_admission`) admits
    exactly the entry's dial scope on exactly its named drafters — dials
    outside the scope still refuse, and a mismatched claim raises."""
    if "llm" not in agent_kinds_in_play(spec):
        return None
    registration = registration_admission(spec, registry_path)
    if spec.drafter in guarded_drafters() and registration is None:
        return f"drafter {spec.drafter!r} is a conflict/pressure/delta substrate"
    down = sorted(_phase1_variants_in_play(spec) & PHASE1_DOWN_VARIANTS)
    if down and registration is None:
        # T048 — the down-direction instrument is registration-gated like the
        # awareness dials (AUP acceptance (e)): the conflict-free ungate does
        # not extend to it.
        return (
            f"phase-1 down-direction variant(s) {down} are registration-gated (T048): "
            "claim a `registration:` entry naming this drafter, or use a scripted agent"
        )
    guarded = sorted(d for d in dials_in_play(spec) if d in guarded_dials())
    if spec.drafter in CONFLICT_FREE_DRAFTERS:
        # T025 — the conflict-free ungate: on a world with nothing to refrain
        # from, a stated commitment is a retention stimulus, not an
        # alignment-bearing arm (AUP phase 1 filing, C7).
        guarded = [d for d in guarded if d not in CONFLICT_FREE_ADMITTED_DIALS]
    if registration is not None:
        out_of_scope = [d for d in guarded if d not in registration.dials]
        if out_of_scope:
            return (
                f"dials {out_of_scope} are outside registration {registration.id!r}'s admitted "
                f"scope {sorted(registration.dials)} (an unlicensed sweep stays impossible by construction)"
            )
        return None
    if guarded:
        return f"dials {guarded} put an alignment-bearing arm on the world (drop them, or use a scripted agent)"
    return None

# ═══════════════════════════════════════════════════════════════════════════
# run_experiment / aggregate / render_report (M46.5/M46.7/M46.11)
# ═══════════════════════════════════════════════════════════════════════════


def _resume_spec_drift(prior: Any, spec: ExperimentSpec) -> list[str]:
    """T051 box 4 — the spec fields a ``resume=True`` call changed against the
    run's manifest, empty when the resume is legitimate. A resume keyed
    records by ``(label, index)`` alone, so an edited ``base_seed``,
    ``max_turns``, ``drafter_kwargs`` or model re-labelled every stale line
    as the new spec's cell (zero re-drafts) and the rebuilt manifest then
    asserted a spec the records were never drawn under. The two legitimate
    edits are widening: more ``trials_per_condition``, or new levels on an
    existing axis (per-label seeds make both additive)."""
    if not isinstance(prior, Mapping):
        return []
    current = spec_to_dict(spec)
    drift: list[str] = []
    for key in sorted(set(prior) | set(current)):
        if key in ("trials_per_condition", "axes"):
            continue
        if prior.get(key) != current.get(key):
            drift.append(key)
    if int(current.get("trials_per_condition", 0)) < int(prior.get("trials_per_condition", 0)):
        drift.append("trials_per_condition")
    old_axes = dict(prior.get("axes") or {})
    new_axes = dict(current.get("axes") or {})
    for name, levels in old_axes.items():
        if name not in new_axes or any(level not in list(new_axes[name]) for level in levels):
            drift.append(f"axes.{name}")
    if any(name not in old_axes for name in new_axes):
        drift.append("axes")
    return drift


@dataclass(frozen=True)
class Preflight:
    """What :func:`preflight` found: every guard's verdict in the order the run
    applies them, the resolved ``out_dir``, whether it already holds records,
    the cost estimate (``None`` when pricing itself refused) and the first
    refusal as the exception the run would raise."""

    out_dir: Path
    out_exists: bool
    checks: tuple[tuple[str, Optional[str]], ...]
    estimate: Optional[CostEstimate]
    refusal: Optional[BaseException]

    @property
    def ok(self) -> bool:
        return self.refusal is None

    def lines(self) -> list[str]:
        """The verdicts as ``bio suite run --dry`` prints them."""
        out = [f"out_dir exists: {'yes (run refuses without resume)' if self.out_exists else 'no'}"]
        for name, why in self.checks:
            out.append(f"{name}: ok" if why is None else f"{name}: REFUSED — {why}")
        return out


PREFLIGHT_CHECKS: tuple[str, ...] = (
    "registration", "no-peeking", "dials", "surface", "sampling", "price", "resume", "out_dir",
)


def preflight(spec: ExperimentSpec, *, out_dir: Optional[str] = None, resume: bool = False) -> Preflight:
    """Every refusal a run can make before spend, in one place (T051 box 5 /
    T057 proposal 3). :func:`run_experiment` raises the first; ``bio suite
    run --dry`` prints them all. Before this, ``--dry`` ran two of the guards
    and the run the rest — a spec with a bogus ``registration:`` printed
    all-ok and refused on the run — and the per-model price check and the
    resume-drift check (box 4) had been added to one side only.

    Order: the registration claim, the no-peeking rule, unknown dials, the
    declared surface, the sampling regime, a price for every model level in
    play (the estimate), resume drift against the manifest, and ``out_dir``
    (records present without ``resume``). ``out_dir`` is resolved exactly as
    the run resolves it and nothing here creates it.
    """
    resolved_out = Path(out_dir or spec.out_dir or f"runs/{spec.name}")
    records_path = resolved_out / "records.jsonl"
    manifest_path = resolved_out / "manifest.json"
    out_exists = records_path.exists()
    checks: list[tuple[str, Optional[str]]] = []
    refusal: Optional[BaseException] = None
    estimate: Optional[CostEstimate] = None

    def check(name: str, run_it: Callable[[], Any]) -> None:
        nonlocal refusal
        try:
            run_it()
        except Exception as exc:  # noqa: BLE001 — every guard refuses by raising
            checks.append((name, str(exc)))
            if refusal is None:
                refusal = exc
        else:
            checks.append((name, None))

    def _raise_if(problem: Optional[str], what: str) -> None:
        if problem is not None:
            raise ValueError(f"run_experiment: {problem}") if what != "no-peeking" else ValueError(
                "run_experiment: the no-peeking rule (ABIO Experiment Catalog "
                f"§ The no-peeking rule) forbids agent 'llm' here: {problem}"
            )

    check("registration", lambda: registration_admission(spec))
    check("no-peeking", lambda: _raise_if(no_peeking_violation(spec), "no-peeking"))
    check("dials", lambda: _raise_if(unknown_dials_violation(spec), "dials"))
    check("surface", lambda: _raise_if(declared_surface_violation(spec), "surface"))
    check("sampling", lambda: _raise_if(sampling_violation(spec), "sampling"))

    def _price() -> None:
        nonlocal estimate
        estimate = estimate_cost(spec)

    check("price", _price)

    def _resume() -> None:
        if not (resume and manifest_path.exists()):
            return
        try:
            prior_manifest = json.loads(manifest_path.read_text())
        except (OSError, ValueError):
            prior_manifest = {}
        drift = _resume_spec_drift(prior_manifest.get("spec"), spec)
        if drift:
            raise ValueError(
                f"run_experiment: resume=True but the spec differs from the run's manifest on {drift} — "
                "a resume continues the SAME experiment (only more trials_per_condition or added axis "
                f"levels may change); start a new out_dir for a new spec ({resolved_out})"
            )

    check("resume", _resume)

    def _out_dir() -> None:
        if out_exists and not resume:
            raise FileExistsError(
                f"run_experiment: {resolved_out} already holds records.jsonl "
                "(pass resume=True to continue, or choose a different out_dir)"
            )

    check("out_dir", _out_dir)
    return Preflight(resolved_out, out_exists, tuple(checks), estimate, refusal)
