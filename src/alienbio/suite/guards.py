"""Every refusal a run makes before spend — ``preflight`` and its ordered checks (:data:`PREFLIGHT_CHECKS`), one ``*_violation`` function per check (T058; split out of ``experiment.py``)."""

from __future__ import annotations

import inspect
import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional


from ..expr.registry import registry as _registry
from .phase1_gen import (
    PHASE1_DOWN_VARIANTS,
)

from .registration import REGISTRY_RELPATH, Registration, resolve_registration
from .trial import frozen_value


from .drafters import (
    CONFLICT_FREE_ADMITTED_DIALS,
    CONFLICT_FREE_DRAFTERS,
    DRAFTERS,
    EPISODE_DIALS,
    dial_params,
    guarded_dials,
    guarded_drafters,
    opaque_by_default_drafters,
    unknown_spec_dials,
    FACTORY_DIALS,
    _unknown_dials_message,
)
from .spec import (
    REPO_ROOT,
    CostEstimate,
    ExperimentSpec,
    default_expected_turns,
    agent_kinds_in_play,
    estimate_cost,
    spec_to_dict,
)


def declared_surface_violation(spec: ExperimentSpec) -> Optional[str]:
    """M45.2 — why ``spec`` has no declared control surface: a guarded drafter
    (conflict / pressure / delta and the controls on them) with no ``levers``
    dial, fixed or swept. ``None`` otherwise. The default for those worlds is
    *no levers until declared*, failing visibly — never every reaction id.

    A declaration is a list (``[]`` is the do-nothing arm): ``levers: null``
    or any other non-list, fixed or as an axis level, refuses here, naming
    the value (T084 finding B: the key's presence alone passed, and
    ``build_brief`` refused inside every trial)."""
    if spec.drafter not in guarded_drafters():
        return None
    declared: list[Any] = []
    if "levers" in spec.fixed_dials:
        declared.append(spec.fixed_dials["levers"])
    for name, levels in spec.axes:
        if name == "levers":
            declared.extend(levels)
    if declared:
        bad = [value for value in declared if not isinstance(value, (list, tuple))]
        if not bad:
            return None
        return (
            f"drafter {spec.drafter!r}: the declared control surface must be a list of lever ids "
            f"(`levers=[]` for a do-nothing arm); got {', '.join(repr(v) for v in bad)} (M45.2)"
        )
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

def unknown_drafter_violation(spec: ExperimentSpec) -> Optional[str]:
    """Why ``spec.drafter`` names no registered drafter — ``None`` when it
    does. The ONE wording (T091 AC5): ``preflight``'s first check, the
    ``draft`` check, the resume re-draft and :func:`unknown_dials_violation`
    all say it this way."""
    try:
        # `DRAFTERS.__missing__` resolves a head an experiment file's
        # `_includes_` registered after import (the catalog examples), so the
        # lookup is the membership test — `in` is False for those.
        DRAFTERS[spec.drafter]
    except KeyError:
        return f"{spec.name}: unknown drafter {spec.drafter!r}; expected one of {sorted(DRAFTERS)}"
    return None


def unknown_dials_violation(spec: ExperimentSpec) -> Optional[str]:
    """Why ``spec`` carries a dial nobody reads — ``None`` when it does not.
    Checked before spend (``run_experiment``, ``bio suite run --dry``) so a
    misplaced key refuses the run instead of becoming N error records."""
    problem = unknown_drafter_violation(spec)
    if problem is not None:
        return problem
    unknown = unknown_spec_dials(spec)
    if not unknown:
        return None
    if spec.drafter in _registry:
        return _unknown_dials_message(_registry.get(spec.drafter), unknown)
    return f"{spec.drafter}: unknown dial(s) {unknown}"


def fixed_factory_dials_violation(spec: ExperimentSpec) -> Optional[str]:
    """Why ``spec`` sets an agent-factory dial in ``fixed_dials`` — ``None``
    when it does not.

    Deep scan round 4 (2026-10-27): the factory reads the merged dial vector,
    so ``fixed_dials: {agent: llm}`` built a live model, while every guard
    (:func:`~alienbio.suite.spec.agent_kinds_in_play`, the sampling rule,
    the no-peeking rule) and :func:`~alienbio.suite.spec.estimate_cost` read
    only the spec field and the axes: preflight ok, estimate $0.00, a paid
    trial. ``model`` / ``max_tokens`` / ``memory`` there ran one setting and
    priced and recorded another. Each has a spec field (held fixed) or an
    axis (swept); one place each keeps the guards and the run agreeing.
    """
    misplaced = sorted(set(spec.fixed_dials) & FACTORY_DIALS)
    if not misplaced:
        return None
    return (
        f"{spec.name}: {', '.join(misplaced)} in fixed_dials reaches the agent factory but not the "
        "guards or the cost estimate — set the spec field (held fixed) or an axis (swept) instead"
    )


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
    reg = resolve_registration(spec.registration, registry_path or (REPO_ROOT / REGISTRY_RELPATH))
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

    base = Seed(spec.base_seed)
    return [(dials, base.child(f"{seed_label}/0")) for _label, dials, seed_label in _condition_seed_labels(spec)]


def _condition_seed_labels(spec: ExperimentSpec) -> list[tuple[str, dict[str, Any], str]]:
    """One ``(label, dials, seed_label)`` triple per grid condition: the
    record label ``MassTrialRunner`` writes, the merged dial vector, and the
    label its trial seeds derive from (``base_seed.child(f"{seed_label}/{i}")``)."""
    from .drafters import WORLD_INVARIANT_DIALS
    from .mass_trial import _condition_label, condition_grid

    axes = tuple((name, tuple(levels)) for name, levels in spec.axes)
    keys = condition_grid(axes) if axes else [()]
    # Exactly what ``run_experiment`` passes the runner: the world-invariant
    # dials (so an agent / model / budget axis keeps the matched world seed,
    # M46.8) plus the spec's own ``matched_dials``.
    matched = set(WORLD_INVARIANT_DIALS) | set(spec.matched_dials or ())
    out: list[tuple[str, dict[str, Any], str]] = []
    for key in keys:
        label = _condition_label(key)
        seed_label = (
            _condition_label(tuple((n, v) for n, v in key if n not in matched)) if matched else label
        )
        out.append((label, {**spec.fixed_dials, **dict(key)}, seed_label))
    return out


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
            agent = _agent_factory_for(spec)(trial_seed.child("agent"), dials)
        except Exception as exc:  # noqa: BLE001
            return f"{spec.name}: condition {cond} builds no agent — {exc}"
        problem = _probe_signature_problem(agent)
        if problem is not None:
            # T091 G4 — the runner calls ``probe`` only when probes are
            # declared; on a probe-free condition the old signature never
            # runs, so it is a note there, not a refusal.
            if dials.get("probes"):
                return f"{spec.name}: condition {cond} — agent {kind!r} {problem}"
            warnings.warn(
                f"{spec.name}: agent {kind!r} {problem}; no probes are declared, so the run never calls it",
                stacklevel=2,
            )
    return None


def _probe_signature_problem(agent: Any) -> Optional[str]:
    """Why ``agent.probe`` cannot take the runner's ``(text, observation)``
    call, else ``None`` (T091 B8). T088 widened ``ProbeAgent.probe`` from
    ``(text)`` to ``(text, observation)``; an agent still on the old
    signature raised ``TypeError`` on every probe, which the runner records
    as probe data ("probe failure is data"), so every probe answer of the
    run was an error and nothing refused."""
    probe = getattr(agent, "probe", None)
    if probe is None or not callable(probe):
        return None
    try:
        inspect.signature(probe).bind("text", None)
    except TypeError as exc:
        return (
            f"has probe{inspect.signature(probe)}, which cannot take (text, observation) — "
            f"ProbeAgent.probe gained the observation argument in T088 ({exc})"
        )
    except ValueError:
        return None  # no introspectable signature (a builtin): nothing to check
    return None


def _first_brief(world: Any, task: Any, dials: Mapping[str, Any], trial_seed: Any) -> Any:
    """The ``TaskBrief`` :func:`~alienbio.suite.runner.run` builds before turn
    0 of this condition's first trial — through the runner's own
    :func:`~alienbio.suite.runner.trial_preamble` over ``run``'s keyword
    defaults, so this check can only pass a brief the run would build. ``run``
    takes ``trial_seed.child("run")`` (``MassTrialRunner``). Builds no agent
    and simulates nothing, so it is free. Raises what the preamble's dial
    validation or ``build_brief`` raises."""
    from .runner import run as _run, trial_preamble

    params = inspect.signature(_run).parameters
    return trial_preamble(
        world,
        task,
        dials,
        trial_seed.child("run"),
        sim_cfg=params["sim_cfg"].default,
        max_turns=params["max_turns"].default,
        assay_kill=params["assay_kill"].default,
    ).brief


def _first_difference(recorded: Any, fresh: Any, path: str) -> Optional[str]:
    """The first path at which two canonical JSON values differ, ``None`` when equal."""
    if isinstance(recorded, dict) and isinstance(fresh, dict):
        for key in sorted(set(recorded) | set(fresh)):
            if key not in recorded or key not in fresh:
                return f"{path}.{key}"
            found = _first_difference(recorded[key], fresh[key], f"{path}.{key}")
            if found is not None:
                return found
        return None
    if isinstance(recorded, list) and isinstance(fresh, list):
        if len(recorded) != len(fresh):
            return f"{path} (length {len(recorded)} recorded vs {len(fresh)} drafted)"
        for i, (a, b) in enumerate(zip(recorded, fresh)):
            found = _first_difference(a, b, f"{path}[{i}]")
            if found is not None:
                return found
        return None
    return None if recorded == fresh else path


def _world_identity(task_id: Any, oracle: Any, brief: Any) -> dict[str, Any]:
    """What a stored record holds about its world AT DRAFT, as canonical JSON:
    the task id, the oracle (generator-held truth: ``v_target``-style stamps,
    ``hidden_ids``-derived facts, the drawn rates a generator publishes), and
    the brief's question and affordances (the probe/lever/assay lists and the
    caps). ``final_state`` is not identity — it is what the agent did."""
    import json

    from .store import _canonical_json

    brief = brief if isinstance(brief, Mapping) else {}
    payload = {
        "task_id": task_id,
        "oracle": oracle,
        "brief.question": brief.get("question"),
        "brief.affordances": brief.get("affordances"),
    }
    return _json_canonical(json.loads(_canonical_json(payload)))


def recorded_worlds_violation(spec: ExperimentSpec, records_path: Path) -> tuple[Optional[str], int]:
    """T091 R2 follow-up, widened by Y1 — whether a store's records were
    drawn under THIS code's worlds, run on EVERY resume, stamped or not (the
    stamp is a fast refusal for a known scheme change; this is the proof — a
    drafter that now draws a different world from the same seed and dials
    moves no stamp). Any record whose label the current grid does not render
    is drift and refuses naming the label (Y1: such records were skipped, so
    a store whose labels an older rule spelled verified "0 conditions" and
    resumed with every cell's n doubled). For every condition with a
    clean record, its lowest-index record is re-drafted at that record's own
    seed (``base_seed.child(f"{seed_label}/{index}")``, the derivation
    :class:`~alienbio.suite.mass_trial.MassTrialRunner` uses) through the
    drafter and the brief the run uses, and :func:`_world_identity` of the
    fresh draft is compared with the record's. Returns ``(problem, checked)``:
    ``problem`` names the condition, seed and first differing field, ``None``
    when every checked condition matches; ``checked`` is the condition count.
    Error records are not re-drafted (a resume retries them) but their
    labels are checked like any other. Bounded: one draft per recorded
    condition."""
    from .brief import resolve_monitoring
    from .dist import Seed
    from .store import _brief_to_json, _json_safe, read_records

    units = {label: (dials, seed_label) for label, dials, seed_label in _condition_seed_labels(spec)}
    first: dict[str, tuple[int, dict[str, Any]]] = {}
    for line_no, (_line, d, record) in enumerate(read_records(records_path), 1):
        label, index = d.get("label"), d.get("index")
        if label not in units:
            return (
                f"record {line_no} names condition {label!r}, which this spec's grid does not "
                "render (a label written under another label rule or another grid)",
                0,
            )
        if record.error or not isinstance(index, int):
            continue
        if label not in first or index < first[label][0]:
            first[label] = (index, d)
    problem = unknown_drafter_violation(spec)
    if problem is not None:
        return problem, 0
    drafter = DRAFTERS[spec.drafter]
    kwargs = dict(spec.drafter_kwargs or {})
    base = Seed(spec.base_seed)
    for label, (index, d) in sorted(first.items()):
        dials, seed_label = units[label]
        trial_seed = base.child(f"{seed_label}/{index}")
        where = f"condition {label!r} trial {index} (seed {seed_label}/{index})"
        try:
            world, task = drafter(trial_seed.child("draft"), dials, **kwargs)
            brief = _first_brief(world, task, dials, trial_seed)
        except Exception as exc:  # noqa: BLE001 — a world this code cannot draft is no match
            return f"{where} no longer drafts under this alienbio ({type(exc).__name__}: {exc})", len(first)
        oracle: dict[str, Any] = {}
        if isinstance(task.setup, Mapping) and isinstance(task.setup.get("oracle"), Mapping):
            oracle.update(task.setup["oracle"])
        _surfaced, monitoring_actual = resolve_monitoring(dials)
        if monitoring_actual is not None:
            oracle["monitoring_actual"] = monitoring_actual
        fresh = _world_identity(task.world, _json_safe(oracle), _brief_to_json(brief))
        recorded = _world_identity(d.get("task_id"), d.get("oracle"), d.get("brief"))
        diff = _first_difference(recorded, fresh, "record")
        if diff is not None:
            return f"{where} re-drafts a different world: first differing field {diff}", len(first)
    return None, len(first)


def draft_violation(spec: ExperimentSpec) -> Optional[str]:
    """Why DRAFTING this run's worlds refuses — ``None`` when every condition
    drafts.

    The generators refuse a great deal at draft time, and every one of those
    refusals used to arrive as N error records after a clean ``--dry``:
    ``certainty`` below the world's own floor (which ``world_variance`` moves
    per seed, so one fixed level is legal on some seeds and not others),
    ``certainty_windows`` not dividing ``sim_steps``, a W2 depth whose chain
    lag exceeds the bound, a declared readout that names no molecule. One
    draft per condition, at the seed that condition's FIRST trial will use
    (:func:`_condition_units`), catches the config-shaped ones before spend;
    a refusal only a later trial's seed hits still surfaces on the run,
    since drafting every seed is the run.

    Each drafted condition's brief is then built by the real
    :func:`~alienbio.suite.brief.build_brief`, as the run builds it before
    turn 0 (:func:`_first_brief`), and a ``ValueError`` from it is that
    condition's refusal: ``assays`` naming no reaction, a lever on the
    readout or on a structurally hidden pool (T066 Q1), a malformed
    ``levers`` entry, and any brief refusal added later (T084 finding A:
    only the hidden-pool one was pulled forward, as a hand copy).

    Every condition is drafted and every refusing one is named, joined with
    ``; `` (round 4/5 leftover, 2026-10-27: it returned on the first refusal,
    and returned ``None`` on the first NON-config exception). A
    ``ValueError`` is a config refusal (``drafts no world`` / ``builds no
    brief``); any other exception from the drafter is a generator fault,
    named with its class (``generator error``), and refuses too, since the
    run would crash on the same draft (T084 finding D).
    """
    problem = unknown_drafter_violation(spec)
    if problem is not None:
        return problem
    drafter = DRAFTERS[spec.drafter]
    kwargs = dict(spec.drafter_kwargs or {})
    refusals: list[str] = []
    for dials, trial_seed in _condition_units(spec):
        cond = {k: v for k, v in dials.items() if k not in spec.fixed_dials} or dials
        try:
            world, task = drafter(trial_seed.child("draft"), dials, **kwargs)
        except ValueError as exc:
            # A CONFIG refusal: ``ValueError`` (and ``SkeletonError``, which
            # derives from it) is how every generator deliberately refuses a
            # dial vector it cannot draft.
            refusals.append(f"{spec.drafter}: condition {cond} drafts no world — {exc}")
            continue
        except Exception as exc:  # noqa: BLE001 — a fault is still a refusal to spend
            # T084 finding D: anything else is a generator FAULT, not a config
            # verdict. A drafter is a pure function of (seed, dials) — it makes
            # no provider or network call — so the run would raise the same
            # thing on this condition's first trial. It used to read as config
            # (``TypeError``/``KeyError``) or be skipped as transient (the rest).
            refusals.append(
                f"{spec.drafter}: condition {cond} — generator error {type(exc).__name__}: {exc} "
                "(a drafter fault, not a config refusal: the run would crash on this draft)"
            )
            continue
        # The brief, built exactly as the run builds it before turn 0: every
        # brief-side refusal that reads the drafted world (``assays`` naming
        # no reaction, a lever on the readout or on a hidden pool, a
        # malformed ``levers`` entry) is ``build_brief``'s own verdict here,
        # not a copy of it (T084 finding A: those landed as N error records
        # after a clean ``--dry``).
        try:
            _first_brief(world, task, dials, trial_seed)
        except ValueError as exc:
            refusals.append(f"{spec.drafter}: condition {cond} builds no brief — {exc}")
        except Exception as exc:  # noqa: BLE001 — as for the draft: a fault, still no spend
            refusals.append(
                f"{spec.drafter}: condition {cond} — brief error {type(exc).__name__}: {exc} "
                "(a fault, not a config refusal: the run would crash building this brief)"
            )
    return "; ".join(refusals) if refusals else None


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
    # T091 B11: a swept factory dial that no agent in the grid reads (only
    # the live agent reads ``memory``, ``compact_*``, ``max_tokens`` …) gives
    # cells byte-identical apart from their label — an axis that measures
    # nothing, reported as a contrast.
    from .agents import AGENT_DIALS

    kinds = sorted(agent_kinds_in_play(spec))
    for name, _levels in spec.axes:
        if name in FACTORY_DIALS and name != "agent":
            readers = [kind for kind in kinds if name in AGENT_DIALS.get(kind, frozenset())]
            if not readers:
                return (
                    f"{spec.name}: the {name!r} axis is read by no agent in the grid "
                    f"(agents in play: {kinds}; only {sorted(k for k, d in AGENT_DIALS.items() if name in d)} "
                    "read it) — its cells would differ only by label"
                )
    # Round 4: each cell's own ``max_turns``, not the grid's largest — a
    # ``max_turns: [4, 40]`` axis with ``compact_at: 10`` left the 4-turn
    # cells inert while the 40-turn ones cleared the check.
    grid_turns = default_expected_turns(spec.fixed_dials, spec.axes)
    for dials in _condition_dial_vectors(spec):
        turns = dials.get("max_turns", grid_turns)
        if isinstance(turns, bool) or not isinstance(turns, int):
            turns = grid_turns
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
    from .runner import certainty_slice_problem, run as _run

    default_cfg = inspect.signature(_run).parameters["sim_cfg"].default
    for dials in _condition_dial_vectors(spec):
        steps = dials.get("sim_steps", default_cfg.steps)
        every = dials.get("sample_every", default_cfg.sample_every)
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            continue  # the runner's own dial validation owns that verdict
        if isinstance(every, bool) or not isinstance(every, int) or every < 1:
            continue
        problem = certainty_slice_problem(steps, windows, every)
        if problem:
            return f"{spec.name}: {problem}"
    return None


def intervene_horizon_violation(spec: ExperimentSpec) -> Optional[str]:
    """Why this ``intervene`` run's budget ladder is not paired — ``None``
    when it is (T091 A4).

    ``intervene`` derives its goal and passive reach — and scores the outcome
    — at the task's horizon, which is ``max_turns`` unless the
    ``intervene_horizon`` generator setting pins it. ``max_turns`` is in
    ``WORLD_INVARIANT_DIALS`` (a budget contrast is meant to run one task), so
    a ``max_turns`` axis without the pin gives every rung its own goal (seed
    9, n_nodes 5: goal 18.0 at 4 turns, 87.2 at 12) and the ladder reads the
    horizon, not the budget. ``diagnose`` has the same shape and the same pin
    (``hazard_horizon``)."""
    if spec.drafter != "intervene":
        return None
    if not any(axis == "max_turns" for axis, _levels in spec.axes):
        return None
    # T091 F3 — an explicit ``intervene_horizon=None`` is "unset", not a pin.
    if any(value is not None for value in _dial_values_in_play(spec, "intervene_horizon")):
        return None
    return (
        f"{spec.name}: intervene sweeps max_turns as an axis without intervene_horizon — the goal, "
        "the passive reach and the scored horizon would all move with each rung, so the budget "
        "contrast is not paired; pin the horizon on the task, e.g. intervene(..., "
        "intervene_horizon=<the largest max_turns>)"
    )


def score_window_violation(spec: ExperimentSpec) -> Optional[str]:
    """Why this run's ``score_window`` cannot be met inside its episode —
    ``None`` when it can.

    ``score_read="held"`` grades the highest level the target HOLDS for
    ``score_window`` simulated seconds, and degrades to the trajectory
    minimum when no window that long exists. Every episode starts with the
    target at 0, so an unreachable window scores every arm identically:
    T066 measured an agent that drove the target past ``v_target`` and an
    idle one both scoring 0.0847, with nothing on the record saying the
    window was unmeetable — the grid read as uniform total failure. The two
    inputs are on opposite sides (``score_window`` is a generator setting,
    the horizon is the episode's dials), so this is the only place that sees
    both; ``phase1_pressure`` already warns on the same kind of mismatch for
    its ``v_target`` derivation.
    """
    kwargs = dict(spec.drafter_kwargs or {})
    window = kwargs.get("score_window")
    if window is None or not isinstance(window, (int, float)) or isinstance(window, bool):
        return None
    if window <= 0:
        return None
    from .runner import run as _run

    params = inspect.signature(_run).parameters
    default_sim = params["sim_cfg"].default
    for dials in _condition_dial_vectors(spec):
        turns = dials.get("max_turns", params["max_turns"].default)
        steps = dials.get("sim_steps", default_sim.steps)
        dt = dials.get("sim_dt", default_sim.dt)
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (turns, steps, dt)):
            continue
        horizon = float(turns) * float(steps) * float(dt)
        if float(window) > horizon:
            return (
                f"{spec.name}: score_window={window:g} s exceeds the episode's own "
                f"{horizon:g} s ({turns} turns x {steps} steps x {dt:g} s) — no window that "
                "long exists, so score_read='held' would degrade to the trajectory minimum "
                "and every arm would score alike"
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
    from .llm_agent import _keeps_no_history
    from .monitor import resolve_monitor

    for dials in _condition_dial_vectors(spec):
        cond = {k: v for k, v in dials.items() if k not in spec.fixed_dials} or dials
        try:
            resolve_monitor(dials)
        except Exception as exc:  # noqa: BLE001 — the message is the verdict
            return f"{spec.name}: condition {cond} — {exc}"
        # T091 Q10 — ``LLMAgent.begin`` refuses T029's displacement burial
        # with no history window; checked only there, a ``memory`` axis
        # holding ``none`` or ``0`` printed a clean ``--dry`` and then wrote
        # an error record for every trial of that level.
        memory = dials.get("memory", spec.memory)
        if (
            str(dials.get("agent", spec.agent)) == "llm"
            and dials.get("constitution_in_history")
            and _keeps_no_history(memory)
        ):
            return (
                f"{spec.name}: condition {cond} — constitution_in_history requires turn memory "
                f"(memory={memory!r} keeps no history window, so the constitution would never "
                "reach the model)"
            )
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
    # T091 D7 — ``opaque_names`` is a declared dial now, so a spec can reach
    # the runner's off switch. Off, a live model reads the world's
    # structural ids (``root/crux/sink_byproduct_in``), which say what each
    # part is — the leak M45.15 closed — and the taint audit cannot see it
    # (a visible id is not a secret). With a live model it may only be
    # turned ON; no registration licenses turning it off. K D7: only where
    # names are opaque by default — on any other drafter ``False`` is the
    # default it already runs under, and refusing it there refused a spec
    # identical to an accepted one.
    opaque_default = opaque_by_default_drafters()
    if spec.drafter in opaque_default and any(
        value is not None and not value for value in _dial_values_in_play(spec, "opaque_names")
    ):
        return (
            f"opaque_names=False with a live model on {spec.drafter!r} would hand it the world's "
            "structural ids (M45.15); only opaque_names=True may be set on an llm arm of a drafter "
            f"whose names are opaque by default ({sorted(opaque_default)})"
        )
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


#: Spec fields that touch no record — never resume drift (T091 B3).
_NON_RECORD_FIELDS: frozenset[str] = frozenset({"concurrency", "out_dir", "cost_ceiling_usd"})


def _json_canonical(value: Any) -> Any:
    """``value`` as a JSON round trip would leave it, for comparison only:
    tuples and other sequences/sets as lists (sets sorted by ``repr``),
    mapping keys as strings, and a non-finite float as its own spelling so
    ``nan`` compares equal to ``nan``."""
    if isinstance(value, Mapping):
        return {str(k): _json_canonical(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return [_json_canonical(v) for v in sorted(value, key=repr)]
    if isinstance(value, (list, tuple)):
        return [_json_canonical(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return {"__nonfinite__": repr(value)}
    return value


def _resume_spec_drift(prior: Any, spec: ExperimentSpec) -> list[str]:
    """T051 box 4 — the spec fields a ``resume=True`` call changed against the
    run's manifest, empty when the resume is legitimate. A resume keyed
    records by ``(label, index)`` alone, so an edited ``base_seed``,
    ``max_turns``, ``drafter_kwargs`` or model re-labelled every stale line
    as the new spec's cell (zero re-drafts) and the rebuilt manifest then
    asserted a spec the records were never drawn under. The two legitimate
    edits are widening: more ``trials_per_condition``, or new levels on an
    existing axis (per-label seeds make both additive).

    T091 B3 — three fields shape no record and are never drift:
    ``concurrency`` (how many trials are in flight; records are identical at
    any value), ``out_dir`` (where the store lives) and ``cost_ceiling_usd``
    (when the grid stops, not what a trial is). Without the last, a grid the
    ceiling stopped could never be finished: raising the ceiling refused as
    drift, and resuming under the old one re-stopped at once. The ceiling's
    own rule — never below what the records already spent — is checked by
    :func:`preflight`'s ``resume`` verdict."""
    if not isinstance(prior, Mapping):
        return []
    # T091 D3 — both sides in the manifest's own JSON normal form: a Python
    # spec's ``levers=(id,)`` is a tuple in ``spec_to_dict`` and a list once
    # read back, and ``(id,) != [id]`` refused the identical spec's resume.
    prior = _json_canonical(prior)
    current = _json_canonical(spec_to_dict(spec))

    def _derived_turns(d: Mapping[str, Any]) -> int:
        axes = tuple((name, tuple(levels)) for name, levels in dict(d.get("axes") or {}).items())
        return default_expected_turns(d.get("fixed_dials") or {}, axes)

    # Round 5: ``expected_turns`` is persisted as its DERIVED value when the
    # spec leaves it unset — the largest ``max_turns`` level — so widening a
    # ``max_turns`` axis, one of the two legitimate edits, read as drift and
    # refused the resume. Derived on both sides follows the axes; only an
    # explicit value on either side is compared.
    derived_both = prior.get("expected_turns") == _derived_turns(prior) and current[
        "expected_turns"
    ] == _derived_turns(current)
    drift: list[str] = []
    for key in sorted(set(prior) | set(current)):
        if key in ("trials_per_condition", "axes") or key in _NON_RECORD_FIELDS:
            continue
        if key == "expected_turns" and derived_both:
            continue
        if prior.get(key) != current.get(key):
            drift.append(key)
    if int(current.get("trials_per_condition", 0)) < int(prior.get("trials_per_condition", 0)):
        drift.append("trials_per_condition")
    old_axes = dict(prior.get("axes") or {})
    new_axes = dict(current.get("axes") or {})
    for name, levels in old_axes.items():
        # T091 G1 — by the typed frozen form: ``1.0`` is not the level ``1``
        # was (``==`` said it was), and a dict level is the same level in any
        # key order.
        new_levels = [frozen_value(level, typed=True, nan_equal=True) for level in new_axes.get(name, ())]
        if name not in new_axes or any(frozen_value(level, typed=True, nan_equal=True) not in new_levels for level in levels):
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
    skipped: tuple[str, ...] = ()
    #: Whether the call was a resume. Off one, the ``resume`` check has
    #: nothing to compare and prints as ``skipped (not a resume)``, never
    #: ``ok`` (T084 finding E).
    resume: bool = False
    #: What a passing check wants said on the progress channel — today the
    #: verified pre-stamp store (T091 R2), which the run then stamps.
    notes: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.refusal is None

    def lines(self) -> list[str]:
        """The verdicts as ``bio suite run --dry`` prints them."""
        out = [f"out_dir exists: {'yes (run refuses without resume)' if self.out_exists else 'no'}"]
        for name, why in self.checks:
            if name in ("resume", "records-readable") and not self.resume:
                out.append(f"{name}: skipped (not a resume)")
            elif name in self.skipped:
                out.append(f"{name}: skipped (an earlier check refused)")
            else:
                out.append(f"{name}: ok" if why is None else f"{name}: REFUSED — {why}")
        out.extend(self.notes)
        return out


def label_collision_violation(spec: ExperimentSpec) -> Optional[str]:
    """Two distinct cells of ``spec.axes`` that render one condition label
    (``1`` and ``"1"`` on one axis): they would draw one world seed and share
    one resume key. Refused rather than re-rendered, so every existing
    label — and every stored seed and resume key — is unchanged (T084 C)."""
    from .mass_trial import label_collision

    return label_collision(tuple((name, tuple(levels)) for name, levels in spec.axes))


PREFLIGHT_CHECKS: tuple[str, ...] = (
    "drafter", "registration", "no-peeking", "dials", "labels", "episode-dials", "surface", "sampling", "w2-lag",
    "brief-dials", "certainty-windows", "score-window", "intervene-horizon", "inert-arm", "agent", "price",
    "draft", "records-readable", "resume", "out_dir",
)


def resolved_out_dir(spec: ExperimentSpec, out_dir: Optional[str] = None) -> Path:
    """The run directory a run of ``spec`` writes: ``out_dir``, else the
    spec's own, else ``runs/<name>`` (the one resolution the run, the
    pre-flight and ``--dry`` share)."""
    return Path(out_dir or spec.out_dir or f"runs/{spec.name}")


def preflight(spec: ExperimentSpec, *, out_dir: Optional[str] = None, resume: bool = False) -> Preflight:
    """Every refusal a run can make before spend, in one place (T051 box 5 /
    T057 proposal 3). :func:`run_experiment` raises the first; ``bio suite
    run --dry`` prints them all. Before this, ``--dry`` ran two of the guards
    and the run the rest — a spec with a bogus ``registration:`` printed
    all-ok and refused on the run — and the per-model price check and the
    resume-drift check (box 4) had been added to one side only.

    Order (:data:`PREFLIGHT_CHECKS`): ``drafter`` (the spec's drafter is
    registered — every later check reads it, so on a refusal each is
    skipped, T091 AC5), ``registration`` (the claim
    resolves), ``no-peeking`` (a live model on a guarded drafter, variant or
    dial, unlicensed), ``dials`` (a name nothing reads; a factory dial in
    ``fixed_dials``), ``labels`` (two axis levels that render one seed
    label and resume key, T084 C), ``episode-dials`` (a clock dial in ``drafter_kwargs``),
    ``surface`` (a guarded drafter's ``levers`` undeclared or not a list),
    ``sampling`` (a live arm with no ``temperature``), ``w2-lag`` (the W2
    chain lag bound), ``brief-dials`` (the in-world monitor arm),
    ``certainty-windows`` (slices that cannot cut the turn),
    ``score-window`` (a held window longer than the episode),
    ``intervene-horizon`` (an ``intervene`` ``max_turns`` axis with no
    ``intervene_horizon`` pin, T091 A4), ``inert-arm``
    (a ``compact_at`` that never fires), ``agent`` (each condition's agent
    config), ``price`` (a price for every model level in play; the
    estimate), ``draft`` (each condition's world and brief; skipped once
    anything above refused), ``records-readable`` (every line of an
    existing store parses, on a resume, ``records.jsonl`` and
    ``records.retried.jsonl`` both — T091 B4, M4), ``resume`` (records with
    no manifest, an unreadable or spec-less manifest, drift against it, or a
    cost ceiling below the records' spend; the re-draft of each recorded
    condition runs only when every earlier check passed; skipped off a
    resume), and ``out_dir`` (records
    present without ``resume``). ``out_dir`` is resolved exactly as the run
    resolves it and nothing here creates it.
    """
    if spec.validation != "run":
        raise ValueError(
            f"{spec.name}: a spec built with validation={spec.validation!r} is for reading a finished run "
            "(aggregate, report); a run or resume needs validation='run'"
        )
    resolved_out = resolved_out_dir(spec, out_dir)
    records_path = resolved_out / "records.jsonl"
    manifest_path = resolved_out / "manifest.json"
    out_exists = records_path.exists()
    checks: list[tuple[str, Optional[str]]] = []
    refusal: Optional[BaseException] = None
    estimate: Optional[CostEstimate] = None
    skipped: list[str] = []
    notes: list[str] = []

    #: T091 AC5 — an unregistered drafter refuses first, and every later
    #: check (each reads the drafter) is skipped rather than reporting a
    #: confusing second-hand symptom (``unknown dial(s)``, a bare KeyError).
    no_drafter = False

    def check(name: str, run_it: Callable[[], Any], *, only_if_clean: bool = False) -> None:
        """One verdict. ``only_if_clean`` marks a check that does real work
        (drafting every condition's world): an already-refused spec is not
        going to run, so there is nothing to learn from drafting it, and a
        cheaper verdict should not be shadowed by a slower one."""
        nonlocal refusal
        if (only_if_clean and refusal is not None) or no_drafter:
            # Round 4: named as skipped — ``--dry`` printed ``draft: ok``
            # for a check that never ran.
            checks.append((name, None))
            skipped.append(name)
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

    check("drafter", lambda: _raise_if(unknown_drafter_violation(spec), "drafter"))
    no_drafter = refusal is not None
    check("registration", lambda: registration_admission(spec))
    check("no-peeking", lambda: _raise_if(no_peeking_violation(spec), "no-peeking"))
    check("dials", lambda: (_raise_if(unknown_dials_violation(spec), "dials"),
                            _raise_if(fixed_factory_dials_violation(spec), "dials")))
    check("labels", lambda: _raise_if(label_collision_violation(spec), "labels"))
    check("episode-dials", lambda: _raise_if(misplaced_episode_dials_violation(spec), "episode-dials"))
    check("surface", lambda: _raise_if(declared_surface_violation(spec), "surface"))
    check("sampling", lambda: _raise_if(sampling_violation(spec), "sampling"))
    check("w2-lag", lambda: _raise_if(w2_lag_violation(spec), "w2-lag"))
    check("brief-dials", lambda: _raise_if(brief_dials_violation(spec), "brief-dials"))
    check("certainty-windows", lambda: _raise_if(certainty_windows_violation(spec), "certainty-windows"))
    check("score-window", lambda: _raise_if(score_window_violation(spec), "score-window"))
    check("intervene-horizon", lambda: _raise_if(intervene_horizon_violation(spec), "intervene-horizon"))
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

    def _records_readable() -> None:
        # T091 B4 — a torn last line (a crash mid-append) used to kill the
        # resume with a bare JSONDecodeError naming neither file nor line;
        # the store is read whole here, before spend, and refuses by name.
        # T091 M4 — records.retried.jsonl too, whenever it exists (ceiling
        # or not): a resume appends to it and reads it for the directory's
        # spend, so a torn tail there used to surface only AFTER the resume
        # had moved its error lines and rewritten records.jsonl.
        if not resume:
            return
        from .store import RETRIED_FILENAME, read_records

        for path in (records_path, resolved_out / RETRIED_FILENAME):
            if path.exists():
                for _row in read_records(path):
                    pass

    check("records-readable", _records_readable)

    def _resume() -> None:
        if not resume:
            return
        if not manifest_path.exists():
            if not records_path.exists():
                return  # nothing to continue: a resume of an empty out_dir is a fresh run
            # T091 B2: a store with records but no manifest (hand-copied,
            # moved without it, the manifest deleted) used to resume with
            # no drift check at all, relabelling every stale line as the new
            # spec's cell.
            raise ValueError(
                f"run_experiment: resume=True but {resolved_out} holds records.jsonl and no "
                f"manifest.json ({manifest_path} is missing) — the drift check cannot run, so the "
                "records cannot be matched to the spec they were drawn under; restore the manifest "
                "or start a new out_dir"
            )
        # T084 finding C: an unreadable manifest used to read as ``{}``, so
        # there was no prior spec to compare and a drifted spec resumed
        # unchecked. Only a readable manifest carrying a spec is compared.
        try:
            from .store import read_manifest  # store imports guards late; resolve late too

            prior_manifest = read_manifest(manifest_path)
        except (OSError, ValueError) as exc:
            raise ValueError(
                f"run_experiment: resume=True but {manifest_path} is unreadable ({exc}) — the resume "
                "cannot be checked against the spec the records were drawn under; restore the manifest "
                "or start a new out_dir"
            ) from exc
        prior_spec = prior_manifest.get("spec") if isinstance(prior_manifest, Mapping) else None
        if not isinstance(prior_spec, Mapping):
            raise ValueError(
                f"run_experiment: resume=True but {manifest_path} carries no spec — the resume cannot be "
                "checked against the spec the records were drawn under; restore the manifest or start a "
                "new out_dir"
            )
        # Drift first (T091 AC3): the stamp depends on the spec too (its swept
        # axes and matched dials, X1), so an edited spec would otherwise be
        # told "another seed scheme" and sent after a code change that never
        # happened. After this check the stamp speaks only for code.
        drift = _resume_spec_drift(prior_spec, spec)
        if drift:
            raise ValueError(
                f"run_experiment: resume=True but the spec differs from the run's manifest on {drift} — "
                "a resume continues the SAME experiment (only more trials_per_condition or added axis "
                f"levels may change); start a new out_dir for a new spec ({resolved_out})"
            )
        # T091 R2 — the spec drift check reads only the spec, but the seed
        # derivation and the matched-dial set live in code: a resume under
        # another alienbio could mix worlds drawn under two schemes in one
        # cell. A store stamped otherwise refuses; an unstamped one is
        # verified by re-draft below. The stamp covers only the matched
        # dials this spec sweeps (X1), so an unswept dial joining
        # WORLD_INVARIANT_DIALS moves nothing.
        from .store import world_scheme

        current_scheme = world_scheme(spec)
        prior_scheme = prior_manifest.get("world_scheme")
        if prior_scheme is not None and prior_scheme != current_scheme:
            raise ValueError(
                f"run_experiment: resume=True but {manifest_path} has world_scheme {prior_scheme!r} and this "
                f"alienbio draws under {current_scheme!r} — the records were drawn under another seed "
                "scheme, so new trials would not match their worlds; start a new out_dir"
            )
        checked = 0
        if records_path.exists() and refusal is not None:
            # T091 AC5 — the re-draft is real work and reads every check
            # above; a spec already refused is not going to resume.
            notes.append("resume: re-draft of the recorded conditions skipped (an earlier check refused)")
        elif records_path.exists():
            # Every resume, stamped or not (T091 Y1): each recorded
            # condition's first trial is re-drafted at its own seed and
            # compared with what the record holds about its world, and a
            # recorded label the grid does not render refuses. An unstamped
            # store that passes gains the current stamp on the rebuilt
            # manifest; any difference refuses.
            problem, checked = recorded_worlds_violation(spec, records_path)
            if problem is not None:
                stamp_says = "has no world_scheme field and" if prior_scheme is None else "is stamped alike but"
                raise ValueError(
                    f"run_experiment: resume=True but {manifest_path} {stamp_says} {problem} — "
                    "the records were drawn under another seed scheme, so new trials would not match their "
                    f"worlds (this alienbio draws under {current_scheme!r}); start a new out_dir"
                )
        if prior_scheme is None and records_path.exists() and refusal is None:
            notes.append(
                f"resume: {manifest_path} had no world_scheme stamp; {checked} recorded condition(s) "
                f"re-drafted identically, stamping {current_scheme}"
            )
        ceiling = spec.cost_ceiling_usd
        if ceiling is not None:
            from .store import directory_spend_usd

            # T091 D — the ceiling is a directory budget: every dollar the
            # directory spent counts, the lines earlier resumes retried included.
            spent = directory_spend_usd(resolved_out, spec)
            if ceiling < spent:
                raise ValueError(
                    f"run_experiment: resume=True with cost_ceiling_usd={ceiling} but the records "
                    f"in {resolved_out} (records.jsonl and records.retried.jsonl) already spent "
                    f"${spent:.4f} — the ceiling is the directory's budget; it may be raised on a "
                    "resume, never set below the spend"
                )

    check("resume", _resume)

    def _out_dir() -> None:
        if out_exists and not resume:
            raise FileExistsError(
                f"run_experiment: {resolved_out} already holds records.jsonl "
                "(pass resume=True to continue, or choose a different out_dir)"
            )

    check("out_dir", _out_dir)
    return Preflight(resolved_out, out_exists, tuple(checks), estimate, refusal, tuple(skipped), resume, tuple(notes))
