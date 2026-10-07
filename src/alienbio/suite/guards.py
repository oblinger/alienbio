"""Every refusal a run makes before spend — the five guards, the dial check and ``preflight`` (T058; split out of ``experiment.py``)."""

from __future__ import annotations

import inspect
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
    EPISODE_DIALS,
    dial_params,
    guarded_dials,
    guarded_drafters,
    unknown_spec_dials,
    _unknown_dials_message,
)
from .spec import (
    CostEstimate,
    ExperimentSpec,
    _default_expected_turns,
    agent_kinds_in_play,
    estimate_cost,
    spec_to_dict,
)


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


def _head_dials(spec: ExperimentSpec) -> frozenset[str]:
    """The dial names the spec's drafter head declares as keywords."""
    if spec.drafter not in _registry:
        return frozenset()
    return frozenset(dial_params(_registry.get(spec.drafter)))


def _drafter_kwarg_dials(spec: ExperimentSpec) -> dict[str, Any]:
    """The entries of ``drafter_kwargs`` that are DIALS of this drafter — the
    head's own declared keywords, as opposed to the generator settings that
    reach it through ``**generator`` (``feed_max_rate``, ``target_margin``,
    ``certainty_windows``, ``hop_delay_s``, ``sim_cfg`` …).

    T066 (deep scan round 2) found this split unguarded in both directions.
    ``_adapt`` splats ``drafter_kwargs`` straight into the head, so a dial
    placed there is fully APPLIED, while every guard read only ``spec.axes``
    and ``spec.fixed_dials`` — so ``drafter_kwargs: {epistemic_access: 2}``
    drew the guarded brief on a live model with no registration at all, and
    ``{world_variance: 0.4}`` scaled the whole rate set without the filing's
    dial scope ever being checked. Two investigators found it independently,
    one through the registration gate and one through the W2 lag bound.
    ``variant`` was already read from here by hand (T048); this generalizes
    that patch to every declared dial, which is also the spelling the
    phase-1 catalog specs use.
    """
    kwargs = dict(spec.drafter_kwargs or {})
    return {name: value for name, value in kwargs.items() if name in _head_dials(spec)}


def dials_in_play(spec: ExperimentSpec) -> frozenset[str]:
    """Every dial name a run of ``spec`` sets: each axis, plus each
    ``fixed_dials`` entry whose value is truthy, plus every declared dial
    the spec passes through ``drafter_kwargs`` (:func:`_drafter_kwarg_dials`
    — applied by the drafter exactly as a fixed dial is)."""
    names = {name for name, _levels in spec.axes}
    names.update(name for name, value in spec.fixed_dials.items() if value)
    names.update(name for name, value in _drafter_kwarg_dials(spec).items() if value)
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


def _dial_values_in_play(spec: ExperimentSpec, name: str) -> list[Any]:
    """Every value dial ``name`` can take in a run of ``spec``: its axis
    levels, else its ``fixed_dials`` value, else its ``drafter_kwargs``
    value (which the drafter applies the same way), else nothing."""
    for axis, levels in spec.axes:
        if axis == name:
            return list(levels)
    if name in spec.fixed_dials:
        return [spec.fixed_dials[name]]
    kwarg_dials = _drafter_kwarg_dials(spec)
    if name in kwarg_dials:
        return [kwarg_dials[name]]
    return []


def misplaced_episode_dials_violation(spec: ExperimentSpec) -> Optional[str]:
    """Why ``spec`` puts an EPISODE dial where only the drafter will see it.

    ``max_turns`` / ``sim_steps`` / ``sim_dt`` are read by BOTH the drafter
    (to size a derivation against the horizon the runner will run) and the
    runner (which actually runs it) — but the runner reads the dial vector
    and never ``drafter_kwargs``. So one in ``drafter_kwargs`` is applied to
    the draft and silently ignored by the episode, and the two then disagree
    about the clock. T066 measured the consequence: ``drafter_kwargs:
    {depth: 2, sim_dt: 0.005}`` cleared ``pressure_w2``'s chain-lag bound
    and stamped ``sim_dt=0.005`` on the oracle while the episode ran at the
    0.1 s default — a 10x violation of the bound, the provoked tracked read
    drifting +16.9 % with depth, every guard green and the record's own
    provenance false. Declared in ``episode(...)`` / ``fixed_dials`` it
    reaches both, which is what every catalog spec does.
    """
    misplaced = sorted(set(dict(spec.drafter_kwargs or {})) & EPISODE_DIALS)
    if not misplaced:
        return None
    return (
        f"{spec.drafter}: {', '.join(misplaced)} in drafter_kwargs reaches the drafter but NOT "
        "the runner, which reads the dial vector — the draft and the episode would disagree "
        f"about the clock. Declare {'it' if len(misplaced) == 1 else 'them'} in episode(...) / "
        "fixed_dials / an axis instead."
    )


def w2_lag_violation(spec: ExperimentSpec) -> Optional[str]:
    """AUP leg 3 (2026-09-15): the same arithmetic the ``pressure_w2`` head
    runs at draft (:func:`~alienbio.suite.w2_gen.assert_chain_lag`), before
    spend, over every ``depth`` x ``sim_dt`` the spec puts in play — so a W2
    grid whose deepest cell would read the tracked pool as a phase artifact
    refuses as a config error, not as N error records. ``None`` off the W2
    head, at ``depth == 0`` only, or when ``k_harm_hop`` is a sampled
    distribution (the draft still checks that case)."""
    if spec.drafter != "pressure_w2":
        return None
    from .dist import Constant
    from .w2_gen import DEFAULT_K_HARM_HOP, assert_chain_lag

    depths = [d for d in _dial_values_in_play(spec, "depth") if isinstance(d, int) and not isinstance(d, bool)]
    if not any(d > 0 for d in depths):
        return None
    kwargs = dict(spec.drafter_kwargs or {})
    if kwargs.get("hop_delay_s") is not None:
        # T063 — the multi-turn form reads harm off the ledger, which the
        # chain's delay does not move; the instant-read bound does not apply.
        return None
    k_hop: Any = kwargs.get("k_harm_hop", DEFAULT_K_HARM_HOP)
    if isinstance(k_hop, Constant):
        k_hop = k_hop.value
    if isinstance(k_hop, bool) or not isinstance(k_hop, (int, float)):
        return None
    from .runner import run

    run_defaults = inspect.signature(run).parameters
    default_dt = float(run_defaults["sim_cfg"].default.dt)
    dts = [float(v) for v in _dial_values_in_play(spec, "sim_dt") if isinstance(v, (int, float))] or [default_dt]
    for depth in sorted(d for d in depths if d > 0):
        for dt in dts:
            try:
                assert_chain_lag(depth, dt, float(k_hop))
            except Exception as exc:  # noqa: BLE001 — the message is the verdict
                return f"pressure_w2: {exc}"
    return None


def _condition_units(spec: ExperimentSpec) -> list[tuple[dict[str, Any], Any]]:
    """One ``(dials, trial_seed)`` pair per grid condition — exactly what the
    run hands the drafter and the agent factory for that condition's FIRST
    trial: the merged dial vector ``{**fixed_dials, **dials}`` and the seed
    ``base_seed.child(f"{label}/0")``.

    The seed matters. The generators' gates are seed-dependent (a world's
    certainty floor moves with its drawn rates, and ``world_variance`` moves
    it per draw), so checking a condition at some other seed can refuse a
    run that would have been fine and pass one that would not. This derives
    the same seed ``MassTrialRunner`` will use, so a refusal here is a
    refusal the run would have hit on its first trial of that condition.
    """
    from .dist import Seed
    from .drafters import WORLD_INVARIANT_DIALS
    from .mass_trial import _condition_label, condition_grid

    axes = tuple((name, tuple(levels)) for name, levels in spec.axes)
    keys = condition_grid(axes) if axes else [()]
    base = Seed(spec.base_seed)
    # Exactly what ``run_experiment`` passes the runner: the world-invariant
    # dials (so an agent / model / budget axis keeps the matched world seed,
    # M46.8) plus the spec's own ``matched_dials``.
    matched = set(WORLD_INVARIANT_DIALS) | set(spec.matched_dials or ())
    units: list[tuple[dict[str, Any], Any]] = []
    for key in keys:
        label = _condition_label(key)
        seed_label = (
            _condition_label(tuple((n, v) for n, v in key if n not in matched)) if matched else label
        )
        units.append(({**spec.fixed_dials, **dict(key)}, base.child(f"{seed_label}/0")))
    return units


def _condition_dial_vectors(spec: ExperimentSpec) -> list[dict[str, Any]]:
    """Just the dial vectors of :func:`_condition_units`."""
    return [dials for dials, _seed in _condition_units(spec)]


def agent_construction_violation(spec: ExperimentSpec) -> Optional[str]:
    """Why building this run's AGENT refuses — ``None`` when every condition
    builds.

    Every per-arm agent validation used to run inside the trial: an unknown
    ``agent`` kind, ``max_tokens: 0`` as an axis level, ``max_tokens`` beside
    an ``output_schedule`` (T059's "one form per arm", enforced on the spec's
    own scalars but not across a scalar and an axis), ``history_token_limit``
    beside ``compact_at``. ``--dry`` printed every check ok and the run then
    produced N identical error records, which is the shape T051 box 4 and
    T057 proposal 3 exist to end. T066 found six instances at once, so the
    check is the constructor itself rather than six restatements of it:
    building an agent makes no model call, so this is free.
    """
    from .agents import AGENTS, _agent_factory_for
    from .llm_agent import validate_agent_config

    for dials, trial_seed in _condition_units(spec):
        cond = {k: v for k, v in dials.items() if k not in spec.fixed_dials} or dials
        kind = str(dials.get("agent", spec.agent))
        if kind not in AGENTS:
            return f"{spec.name}: condition {cond} — unknown agent kind {kind!r}; expected one of {sorted(AGENTS)}"
        if kind == "llm":
            # NOT by constructing one: a live agent reaches for the API key and
            # a provider fn, and a pre-flight that needs credentials would
            # refuse every --dry on a machine without them (and would shadow
            # the price check, which is the refusal an operator wants to see).
            # The per-arm CONFIG is what can be wrong here, so the shared
            # validator is called directly.
            try:
                validate_agent_config(
                    memory=dials.get("memory", spec.memory),
                    compact_at=dials.get("compact_at", spec.compact_at),
                    compact_budget=dials.get("compact_budget", spec.compact_budget),
                    history_token_limit=dials.get("history_token_limit", spec.history_token_limit),
                    max_tokens=dials.get("max_tokens", spec.max_tokens),
                    output_schedule=dials.get("output_schedule", spec.output_schedule),
                )
            except Exception as exc:  # noqa: BLE001 — the message is the verdict
                return f"{spec.name}: condition {cond} — {exc}"
            continue
        try:
            _agent_factory_for(spec)(trial_seed.child("agent"), dials)
        except Exception as exc:  # noqa: BLE001
            return f"{spec.name}: condition {cond} builds no agent — {exc}"
    return None


def draft_violation(spec: ExperimentSpec) -> Optional[str]:
    """Why DRAFTING this run's worlds refuses — ``None`` when every condition
    drafts.

    The generators refuse a great deal at draft time, and every one of those
    refusals used to arrive as N error records after a clean ``--dry``:
    ``certainty`` below the world's own floor (which ``world_variance`` moves
    per seed, so one fixed level is legal on some seeds and not others),
    ``certainty_windows`` not dividing ``sim_steps``, a W2 depth whose chain
    lag exceeds the bound, a declared readout that names no molecule. One
    draft per condition at the base seed catches the config-shaped ones
    before spend; a per-seed refusal still surfaces on the run, since
    drafting every seed is the run.
    """
    from .dist import Seed

    try:
        # `DRAFTERS.__missing__` resolves a head an experiment file's
        # `_includes_` registered after import (the catalog examples), so the
        # lookup is the membership test — `in` is False for those.
        drafter = DRAFTERS[spec.drafter]
    except KeyError:
        return f"{spec.name}: unknown drafter {spec.drafter!r}; expected one of {sorted(DRAFTERS)}"
    kwargs = dict(spec.drafter_kwargs or {})
    for dials, trial_seed in _condition_units(spec):
        try:
            drafter(trial_seed.child("draft"), dials, **kwargs)
        except (ValueError, TypeError, KeyError) as exc:
            # A CONFIG error only. `ValueError` (and `SkeletonError`, which
            # derives from it) is how every generator refuses a dial vector
            # it cannot draft; `TypeError` is a missing required dial;
            # `KeyError` is a declared readout that names no molecule. Any
            # other exception — a provider or IO failure raised through a
            # drafter — is left to the run, where it becomes an error record
            # a resume retries rather than a refusal that kills the grid.
            cond = {k: v for k, v in dials.items() if k not in spec.fixed_dials} or dials
            return f"{spec.drafter}: condition {cond} drafts no world — {exc}"
        except Exception:  # noqa: BLE001 — transient, not a config verdict
            return None
    return None


def inert_arm_violation(spec: ExperimentSpec) -> Optional[str]:
    """Why an arm of this run would measure nothing — ``None`` when none
    would.

    ``compact_at: k`` on an episode of ``k`` turns or fewer never fires:
    ``_maybe_compact``'s ``self._turn != self.compact_at`` gate is simply
    never true, the record carries ``compaction: None``, and the arm is
    byte-indistinguishable from its own control with no refusal and no
    marker (T066). A forgetting arm that quietly measures nothing is worse
    than one that refuses, because the contrast still gets reported.
    """
    turns = _default_expected_turns(spec.fixed_dials, spec.axes)
    for dials in _condition_dial_vectors(spec):
        at = dials.get("compact_at", spec.compact_at)
        if isinstance(at, int) and not isinstance(at, bool) and at >= turns:
            return (
                f"{spec.name}: compact_at={at} never fires in an episode of {turns} turn(s) "
                f"(turns are 0-based, so the last is {turns - 1}) — the arm would record "
                "compaction: null and read as its own control"
            )
    return None


def certainty_windows_violation(spec: ExperimentSpec) -> Optional[str]:
    """Why ``certainty_windows`` cannot divide this run's turn — ``None`` when
    it can.

    T062's rule is that ``n`` divides ``sim_steps`` (each window integrates
    ``sim_steps / n`` steps). It lived only inside ``run``, checked per
    trial, so ``--dry`` printed every check ok and the run turned every
    condition into an identical error record. The two inputs live on
    opposite sides — ``certainty_windows`` is a generator setting, ``sim_steps``
    an episode dial — so neither the draft nor the agent sees both, and this
    is the only place that does.
    """
    windows = dict(spec.drafter_kwargs or {}).get("certainty_windows")
    if windows is None:
        return None
    if isinstance(windows, bool) or not isinstance(windows, int) or windows < 1:
        return f"{spec.name}: certainty_windows must be an int >= 1, got {windows!r}"
    from .runner import run as _run

    default_steps = int(inspect.signature(_run).parameters["sim_cfg"].default.steps)
    for dials in _condition_dial_vectors(spec):
        steps = dials.get("sim_steps", default_steps)
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            continue  # the runner's own dial validation owns that verdict
        if steps % windows:
            return (
                f"{spec.name}: certainty_windows={windows} must divide sim_steps={steps} "
                "(each window integrates sim_steps / certainty_windows steps)"
            )
    return None


def brief_dials_violation(spec: ExperimentSpec) -> Optional[str]:
    """Why this run's BRIEF-side dials refuse — ``None`` when every condition
    resolves.

    The dial-only brief validators, run per condition before spend. T066
    found the monitor arm's own validation (``monitor_coverage`` out of
    range, a ``monitor_sham`` with no coverage, the in-world monitor combined
    with the M32.5 told ``monitoring`` dial) reachable only from inside the
    trial, so a malformed arm printed a clean ``--dry`` and then produced N
    identical error records. Anything that needs the drafted world as well
    belongs in :func:`draft_violation`.
    """
    from .monitor import resolve_monitor

    for dials in _condition_dial_vectors(spec):
        try:
            resolve_monitor(dials)
        except Exception as exc:  # noqa: BLE001 — the message is the verdict
            cond = {k: v for k, v in dials.items() if k not in spec.fixed_dials} or dials
            return f"{spec.name}: condition {cond} — {exc}"
    return None


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
    "registration", "no-peeking", "dials", "episode-dials", "surface", "sampling", "w2-lag",
    "brief-dials", "certainty-windows", "inert-arm", "agent", "price", "draft", "resume", "out_dir",
)


def preflight(spec: ExperimentSpec, *, out_dir: Optional[str] = None, resume: bool = False) -> Preflight:
    """Every refusal a run can make before spend, in one place (T051 box 5 /
    T057 proposal 3). :func:`run_experiment` raises the first; ``bio suite
    run --dry`` prints them all. Before this, ``--dry`` ran two of the guards
    and the run the rest — a spec with a bogus ``registration:`` printed
    all-ok and refused on the run — and the per-model price check and the
    resume-drift check (box 4) had been added to one side only.

    Order: the registration claim, the no-peeking rule, unknown dials, the
    declared surface, the sampling regime, the W2 chain lag, a price for every model level in
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

    def check(name: str, run_it: Callable[[], Any], *, only_if_clean: bool = False) -> None:
        """One verdict. ``only_if_clean`` marks a check that does real work
        (drafting every condition's world): an already-refused spec is not
        going to run, so there is nothing to learn from drafting it, and a
        cheaper verdict should not be shadowed by a slower one."""
        nonlocal refusal
        if only_if_clean and refusal is not None:
            checks.append((name, None))
            return
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
    check("episode-dials", lambda: _raise_if(misplaced_episode_dials_violation(spec), "episode-dials"))
    check("surface", lambda: _raise_if(declared_surface_violation(spec), "surface"))
    check("sampling", lambda: _raise_if(sampling_violation(spec), "sampling"))
    check("w2-lag", lambda: _raise_if(w2_lag_violation(spec), "w2-lag"))
    check("brief-dials", lambda: _raise_if(brief_dials_violation(spec), "brief-dials"))
    check("certainty-windows", lambda: _raise_if(certainty_windows_violation(spec), "certainty-windows"))
    check("inert-arm", lambda: _raise_if(inert_arm_violation(spec), "inert-arm"))
    check("agent", lambda: _raise_if(agent_construction_violation(spec), "agent"))

    def _price() -> None:
        nonlocal estimate
        estimate = estimate_cost(spec)

    check("price", _price)
    # After the price check, so an unpriced model level still refuses first:
    # drafting is free of spend but does real work, and pricing is the
    # cheaper verdict.
    check("draft", lambda: _raise_if(draft_violation(spec), "draft"), only_if_clean=True)

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
