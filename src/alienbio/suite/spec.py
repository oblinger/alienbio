"""The experiment spec — ``ExperimentSpec``, its validators, ``load_spec`` and the dry-run cost estimate (T058; split out of ``experiment.py``)."""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union, cast


from .llm_agent import PINNED_MODEL, PROVIDER_FIXED_SAMPLING, cost_usd, load_models_snapshot, price_for
from .power import PowerDesign


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
    #: T049 — the realistic-forgetting triggers (LLM agents only; one per
    #: arm): compaction displacement at a turn (with an optional summary
    #: token budget) or fill-driven truncation by history volume. A trial
    #: dial of the same name overrides the spec value, so either can be
    #: swept as an axis through ``spec_from_dict``.
    compact_at: Optional[int] = None
    compact_budget: Optional[int] = None
    history_token_limit: Optional[int] = None
    token_ceiling: Optional[int] = None
    fixed_dials: Mapping[str, Any] = field(default_factory=dict)
    out_dir: Optional[str] = None
    #: M45.5 — the cost ceiling + dry-run cost-estimate dials.
    #: ``expected_turns`` is the dry-run turn count; :func:`spec_from_dict`
    #: defaults it from a declared ``max_turns`` (fixed dial, or the largest
    #: swept level) when the spec does not set it, and to the runner's own
    #: ``max_turns`` default when no budget is declared at all. Set it
    #: explicitly for a spec whose agent is expected to commit well before
    #: the budget.
    cost_ceiling_usd: Optional[float] = None
    price_usd_per_mtok: Optional[tuple[float, float]] = None
    expected_turns: int = 8
    expected_prompt_tokens: int = 1500
    expected_output_tokens: int = 300
    #: M46.9 — the statistical design the run is committed to (None = undeclared;
    #: a declared design refuses a spec with too few trials per condition).
    design: Optional[PowerDesign] = None
    #: M45.6 — trials in flight at once (live-model sweeps are I/O-bound).
    concurrency: int = 1
    #: M45.7 — add the matched idle arm automatically: an ``agent`` axis of
    #: ``(agent, "idle")`` under the same world seeds, so every condition has
    #: its do-nothing twin beside it. Expanded into ``axes`` at load.
    idle_baseline: bool = False
    #: M36.3 — extra swept dials to seed-match beyond :data:`WORLD_INVARIANT_DIALS`:
    #: a world *variant switch* (EXP-6's ``ill_posed`` trap) whose arms should
    #: be drawn over the same base world, so the contrast is paired.
    matched_dials: tuple[str, ...] = ()
    #: The one report readout whose figure is this experiment's key graph
    #: (``suite.plots.PLOTTERS`` names: ``dose``, ``conflict``, ``delta``,
    #: ``degradation``, ``monitoring``, ``caution``, ``blindspot``,
    #: ``consideration``, ``hazard``, ``trial``, ``cells``). ``None`` = the first
    #: readout the records carry, in report order — declare it when two apply.
    key_readout: Optional[str] = None
    #: M45.18 — the sampling parameters every live call runs under, so a
    #: dose-response's within-condition variation is *stated* sampling, not
    #: the provider's unrecorded default. ``temperature`` is required for a
    #: run with a live arm (refused at run time when absent); ``top_p`` is
    #: optional. Both ride on the manifest and on every record line. On a
    #: model with no sampling knob (the Claude 5 API refuses temperature /
    #: top_p — "deprecated for this model"), the literal
    #: ``"provider-fixed"`` is the stated regime; ``top_p`` must then be
    #: omitted.
    temperature: Optional[Union[float, str]] = None
    top_p: Optional[float] = None
    #: M45.19 — the prompt-cache hit rate the dry-run estimate assumes on the
    #: fixed system prefix (directive + brief), measured by a pilot; 0 = none.
    expected_cache_hit_rate: float = 0.0
    #: T030 — the pre-registration this spec runs under: an id in the
    #: commit-tracked ``catalog/registrations.yaml``. When set, the guard
    #: admits exactly the entry's dial set on exactly its drafter set
    #: (:func:`registration_admission`), refuses visibly on any mismatch,
    #: and the id is stamped on every record line + the manifest.
    registration: Optional[str] = None


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
        "compact_at": spec.compact_at,
        "compact_budget": spec.compact_budget,
        "history_token_limit": spec.history_token_limit,
        "token_ceiling": spec.token_ceiling,
        "trials_per_condition": spec.trials_per_condition,
        "base_seed": spec.base_seed,
        "fixed_dials": dict(spec.fixed_dials),
        "out_dir": spec.out_dir,
        "cost_ceiling_usd": spec.cost_ceiling_usd,
        "price_usd_per_mtok": (
            list(spec.price_usd_per_mtok) if spec.price_usd_per_mtok is not None else None
        ),
        "expected_turns": spec.expected_turns,
        "expected_prompt_tokens": spec.expected_prompt_tokens,
        "expected_output_tokens": spec.expected_output_tokens,
        "design": spec.design.to_dict() if spec.design is not None else None,
        "concurrency": spec.concurrency,
        "idle_baseline": spec.idle_baseline,
        "matched_dials": list(spec.matched_dials),
        "key_readout": spec.key_readout,
        "temperature": spec.temperature,
        "top_p": spec.top_p,
        "expected_cache_hit_rate": spec.expected_cache_hit_rate,
        "registration": spec.registration,
    }


def spec_from_dict(d: Mapping[str, Any]) -> ExperimentSpec:
    """A dict (as produced by :func:`spec_to_dict`, or a validated YAML load)
    -> :class:`ExperimentSpec`. Optional keys default exactly as the class does."""
    axes_raw = d["axes"]
    axes = tuple((name, tuple(levels)) for name, levels in axes_raw.items())
    idle_baseline = bool(d.get("idle_baseline", False))
    if idle_baseline and d["agent"] != "idle" and not any(name == "agent" for name, _ in axes):
        # M45.7: the idle twin is just another arm of the grid — M46.8's
        # matched seeds make it the baseline for the same (condition, trial).
        axes = axes + (("agent", (d["agent"], "idle")),)
    model = d.get("model")
    if model is not None:
        _require_pinned_model(model)
    # M46.8: an ``agent`` / ``model`` axis is validated like the scalar fields.
    from .agents import AGENTS  # agents imports this module; resolve late

    for name, levels in axes:
        if name == "agent":
            unknown = sorted(str(level) for level in levels if str(level) not in AGENTS)
            if unknown:
                raise ValueError(f"experiment spec: unknown agent axis level(s) {unknown}; expected one of {sorted(AGENTS)}")
        if name == "model":
            for level in levels:
                _require_pinned_model(level)
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
        compact_at=d.get("compact_at"),
        compact_budget=d.get("compact_budget"),
        history_token_limit=d.get("history_token_limit"),
        token_ceiling=d.get("token_ceiling"),
        fixed_dials=dict(d.get("fixed_dials") or {}),
        out_dir=d.get("out_dir"),
        cost_ceiling_usd=_validate_cost_ceiling(d.get("cost_ceiling_usd")),
        price_usd_per_mtok=_validate_price_override(d.get("price_usd_per_mtok")),
        expected_turns=_validate_positive_int(
            "expected_turns",
            d["expected_turns"] if d.get("expected_turns") is not None else _default_expected_turns(d.get("fixed_dials") or {}, axes),
        ),
        expected_prompt_tokens=_validate_positive_int(
            "expected_prompt_tokens", d.get("expected_prompt_tokens", 1500)
        ),
        expected_output_tokens=_validate_positive_int(
            "expected_output_tokens", d.get("expected_output_tokens", 300)
        ),
        design=_validate_design(d.get("design"), d["trials_per_condition"], axes),
        concurrency=_validate_positive_int("concurrency", d.get("concurrency", 1)),
        idle_baseline=idle_baseline,
        matched_dials=_validate_matched_dials(d.get("matched_dials"), axes),
        key_readout=_validate_key_readout(d.get("key_readout")),
        temperature=_validate_sampling(d.get("temperature"), d.get("top_p")),
        top_p=_validate_unit_float("top_p", d.get("top_p")),
        expected_cache_hit_rate=_validate_unit_float("expected_cache_hit_rate", d.get("expected_cache_hit_rate", 0.0)) or 0.0,
        registration=_validate_registration_id(d.get("registration")),
    )


def _validate_registration_id(value: Any) -> Optional[str]:
    """T030 — the claimed registration id: ``None`` or a non-empty string
    (resolution against the registry happens at guard/run time, where a
    missing or mismatched entry refuses visibly)."""
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"experiment spec: registration must be a non-empty string id, got {value!r}")
    return value


def _default_expected_turns(fixed_dials: Mapping[str, Any], axes: Sequence[tuple[str, tuple[Any, ...]]]) -> int:
    """The dry-run turn count when the spec does not set ``expected_turns``:
    the declared episode budget, not a constant. A fixed ``max_turns`` dial
    wins; a swept ``max_turns`` axis uses its largest level (the estimate
    should read high, not low); with no budget declared at all, the runner's
    own ``max_turns`` default — the turn count a non-committing agent will
    actually run — not a constant. AUP 2026-09-09: the constant-8 default
    priced a 20-turn episode at ~40% of its true cost — quiet in exactly the
    direction an operator checks before spending (``cost_ceiling_usd`` still
    stops a runaway mid-run; what broke was planning). T051 box 4: the
    no-budget fallback was still the literal 8 while the runner ran 50
    turns — a 6x under-estimate one deleted ``episode:`` line away."""
    from .runner import run as _run

    fixed = fixed_dials.get("max_turns")
    if isinstance(fixed, int) and not isinstance(fixed, bool) and fixed > 0:
        return fixed
    for name, levels in axes:
        if name == "max_turns":
            declared = [v for v in levels if isinstance(v, int) and not isinstance(v, bool) and v > 0]
            if declared:
                return max(declared)
    return int(inspect.signature(_run).parameters["max_turns"].default)


def _validate_matched_dials(value: Any, axes: Sequence[tuple[str, tuple[Any, ...]]]) -> tuple[str, ...]:
    """M36.3 — ``matched_dials`` must name swept axes (else it is a typo that
    would silently match nothing)."""
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ValueError(f"experiment spec: matched_dials must be a list of axis names, got {value!r}")
    names = tuple(str(v) for v in value)
    swept = {name for name, _ in axes}
    unknown = sorted(n for n in names if n not in swept)
    if unknown:
        raise ValueError(f"experiment spec: matched_dials {unknown} are not swept axes")
    return names


def _validate_design(value: Any, trials_per_condition: int, axes: Sequence[tuple[str, tuple[Any, ...]]]) -> Optional[PowerDesign]:
    """M46.9 — parse the declared design and refuse an under-powered spec.

    A design that names a ``primary_contrast`` must name a swept axis and two
    of its levels; ``trials_per_condition`` must be at least the design's
    required n — otherwise the spec is refused here, before any spend, with
    the number it needs.
    """
    if value is None:
        return None
    if isinstance(value, PowerDesign):
        design = value
    elif isinstance(value, Mapping):
        design = PowerDesign.from_dict(value)
    else:
        raise ValueError(f"experiment spec: design must be a mapping, got {value!r}")
    pc = design.primary_contrast
    if pc is not None:
        levels_by_axis = {name: set(levels) for name, levels in axes}
        if pc["axis"] not in levels_by_axis:
            raise ValueError(f"experiment spec: design.primary_contrast axis {pc['axis']!r} is not a swept axis")
        for end in ("low", "high"):
            if pc[end] not in levels_by_axis[pc["axis"]]:
                raise ValueError(
                    f"experiment spec: design.primary_contrast {end}={pc[end]!r} is not a level of axis {pc['axis']!r}"
                )
    required = design.required_trials_per_condition
    if trials_per_condition < required:
        raise ValueError(
            f"experiment spec: design needs {required} trials per condition to detect "
            f"d={design.target_effect_d} at alpha={design.alpha}, power={design.power}; "
            f"spec asks for {trials_per_condition} — raise trials_per_condition or relax the design"
        )
    return design


def _validate_sampling(temperature: Any, top_p: Any) -> Optional[Union[float, str]]:
    """M45.18: ``temperature`` is a number in [0, 1], or the literal
    :data:`~alienbio.suite.llm_agent.PROVIDER_FIXED_SAMPLING` declaring the
    pinned model exposes no sampling knob (the Claude 5 API refuses
    temperature/top_p — "deprecated for this model"); with the literal,
    ``top_p`` must be omitted (there is no knob for it either)."""
    if temperature == PROVIDER_FIXED_SAMPLING:
        if top_p is not None:
            raise ValueError(
                "experiment spec: `temperature: provider-fixed` declares a model with no sampling knob; top_p must be omitted"
            )
        return PROVIDER_FIXED_SAMPLING
    return _validate_unit_float("temperature", temperature)


def _validate_unit_float(name: str, value: Any) -> Optional[float]:
    """``None`` passes through; otherwise a real number in ``[0, 1]``."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not (0.0 <= float(value) <= 1.0):
        raise ValueError(f"experiment spec: {name} must be a number in [0, 1], got {value!r}")
    return float(value)


def _validate_key_readout(value: Any) -> Optional[str]:
    if value is None:
        return None
    from .plots import PLOTTERS

    names = [name for name, _ in PLOTTERS]
    if not isinstance(value, str) or value not in names:
        raise ValueError(f"experiment spec: key_readout must be one of {names}, got {value!r}")
    return value


def _validate_cost_ceiling(value: Any) -> Optional[float]:
    """``cost_ceiling_usd`` must be a positive number, or absent (``None``)."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"experiment spec: cost_ceiling_usd must be > 0, got {value!r}")
    return float(value)


def _validate_price_override(value: Any) -> Optional[tuple[float, float]]:
    """``price_usd_per_mtok`` must be a 2-sequence of non-negative numbers, or absent."""
    if value is None:
        return None
    try:
        seq = list(value)
    except TypeError:
        raise ValueError(
            f"experiment spec: price_usd_per_mtok must be a 2-sequence of "
            f"non-negative numbers, got {value!r}"
        )
    if len(seq) != 2 or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0 for v in seq
    ):
        raise ValueError(
            f"experiment spec: price_usd_per_mtok must be a 2-sequence of "
            f"non-negative numbers, got {value!r}"
        )
    return (float(seq[0]), float(seq[1]))


def _validate_positive_int(name: str, value: Any) -> int:
    """``dials[name]`` must be a positive ``int`` (M45.5's ``expected_*`` dials)."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"experiment spec: {name} must be a positive int, got {value!r}")
    return value


_DATED_MODEL_RE = re.compile(r".*-\d{8}$")


def _require_pinned_model(model: Any, snapshot: Optional[Mapping[str, str]] = None) -> None:
    """M45.11 / T016 — a run's model id must be a pinned generation, never a
    floating alias, so two runs that name the same id ran the same model.
    Pinned means: not ``-latest``, and either a dated id (``-YYYYMMDD``) or an
    undated id present in the recorded ``models.list`` snapshot
    (:func:`~alienbio.suite.llm_agent.load_models_snapshot`; refresh with
    ``bio suite models``), whose ``created_at`` the manifest then records.

    Raises:
        ValueError: ``model`` is not a string, ends in ``-latest``, or is
            neither dated nor in the snapshot.
    """
    if not isinstance(model, str) or not model:
        raise ValueError(f"experiment spec: model must be a non-empty string, got {model!r}")
    if model.endswith("-latest"):
        raise ValueError(f"experiment spec: model {model!r} is a floating alias — pin a generation (e.g. {PINNED_MODEL!r}) so the run is reproducible")
    if _DATED_MODEL_RE.match(model):
        return
    known = snapshot if snapshot is not None else load_models_snapshot()
    if model not in known:
        raise ValueError(
            f"experiment spec: model {model!r} is neither a dated generation nor in the recorded "
            f"models.list snapshot ({sorted(known) or 'empty'}) — pin a dated id, or refresh the "
            "snapshot with `bio suite models` if the provider now lists it"
        )


def load_spec(path: Union[str, Path]) -> ExperimentSpec:
    """Load + validate an experiment file (M47.4: through the Expr loader —
    one ``!experiment`` call whose ``task:`` / ``brief:`` / ``episode:`` are
    quoted calls; see :mod:`alienbio.suite.expr_experiment`).

    A file under the repository's ``catalog/`` loads **trusted** (it may
    ``_includes_`` Python helpers); any other path loads untrusted.

    Raises:
        ExprError: the file is not an experiment form, names a dial no head
            declares, sweeps an axis nothing reads, or fails any of the
            spec validations — a typo must never silently become a no-op.
    """
    from .expr_experiment import load_experiment

    # The framework's own catalog is trusted (its files may include Python
    # helpers); anything else loads untrusted.
    resolved = Path(path).resolve()
    trusted = (_REPO_ROOT / "catalog").resolve() in resolved.parents
    return load_experiment(path, trusted=trusted)


# ═══════════════════════════════════════════════════════════════════════════
# CostEstimate — a dry-run cost projection over a spec's grid (M45.5)
# ═══════════════════════════════════════════════════════════════════════════


def agent_kinds_in_play(spec: ExperimentSpec) -> frozenset[str]:
    """Every agent kind a run of ``spec`` can construct: the spec's own
    ``agent`` plus the levels of an ``agent`` axis, if one is swept (M46.8)."""
    kinds = {spec.agent}
    for name, levels in spec.axes:
        if name == "agent":
            kinds.update(str(level) for level in levels)
    return frozenset(kinds)


@dataclass(frozen=True)
class CostEstimate:
    """A dry-run USD cost projection over an :class:`ExperimentSpec`'s grid,
    from :func:`estimate_cost`. ``formula`` is a one-line human-readable
    rendering of the arithmetic that produced ``usd``."""

    llm_trials: int
    turns_per_trial: int
    input_tokens: int
    output_tokens: int
    usd: float
    model: Optional[str]
    formula: str


def estimate_cost(spec: ExperimentSpec) -> CostEstimate:
    """Project ``spec``'s USD cost from its grid shape alone — no trial runs.

    ``llm_trials`` is the number of ``(condition, trial)`` units whose
    ``agent`` dial resolves to ``"llm"``: every cell if ``spec.agent ==
    "llm"`` and there is no ``agent`` axis, else the count of cells whose
    ``agent`` axis level is ``"llm"`` (times ``trials_per_condition``). Zero
    llm trials means ``usd = 0.0``, ``model = None``, and no price lookup is
    even attempted (an all-scripted spec never needs a known price).

    Per-trial input tokens (``P`` = ``expected_prompt_tokens``, ``T`` =
    ``expected_turns`` — defaulted at load from the spec's declared
    ``max_turns``, so a 20-turn episode is priced at 20 turns unless the
    spec overrides it) depend on ``spec.memory``: ``"full"`` sums
    ``P * (1 + t/2)`` over ``t`` in ``range(T)`` (each prior turn's history
    roughly adds half a turn's worth of tokens); ``"none"`` is flat ``P *
    T``; an ``int`` k is ``P * T * (1 + min(k, T-1)/2)``. Output tokens are
    flat ``O * T`` (``O`` = ``expected_output_tokens``). ``usd`` is
    :func:`~alienbio.suite.llm_agent.cost_usd` at
    :func:`~alienbio.suite.llm_agent.price_for` ``(model,
    spec.price_usd_per_mtok)``.

    Raises:
        ValueError: ``llm_trials > 0``, the resolved model has no published
            price, and ``spec.price_usd_per_mtok`` gives no override.
    """
    total_cells = 1
    for _name, levels in spec.axes:
        total_cells *= len(levels)

    agent_axis = next((levels for name, levels in spec.axes if name == "agent"), None)
    if agent_axis is not None:
        llm_levels = sum(1 for level in agent_axis if str(level) == "llm")
        other_cells = 1
        for name, levels in spec.axes:
            if name != "agent":
                other_cells *= len(levels)
        llm_trials = llm_levels * other_cells * spec.trials_per_condition
    elif spec.agent == "llm":
        llm_trials = total_cells * spec.trials_per_condition
    else:
        llm_trials = 0

    turns = spec.expected_turns
    if llm_trials == 0:
        return CostEstimate(
            llm_trials=0,
            turns_per_trial=turns,
            input_tokens=0,
            output_tokens=0,
            usd=0.0,
            model=None,
            formula="0 llm trials -> $0.00",
        )

    prompt_tokens = spec.expected_prompt_tokens
    output_tokens = spec.expected_output_tokens
    memory = spec.memory
    if memory == "full":
        input_per_trial = sum(prompt_tokens * (1 + t / 2) for t in range(turns))
        memory_desc = "full"
    elif memory == "none":
        input_per_trial = prompt_tokens * turns
        memory_desc = "none"
    else:
        k = cast(int, memory)
        input_per_trial = prompt_tokens * turns * (1 + min(k, turns - 1) / 2)
        memory_desc = f"k={k}"
    output_per_trial = output_tokens * turns

    total_input_tokens = round(input_per_trial * llm_trials)
    total_output_tokens = round(output_per_trial * llm_trials)

    # T051 box 4 — a ``model`` axis is priced per level, not at
    # ``spec.model``'s rate: the axis is orthogonal to every other axis, so
    # each level owns an equal share of the llm trials. This is also the
    # pre-flight price check — the manifest is built from this estimate
    # before the first trial, so an unpriced level refuses before spend
    # instead of raising inside ``on_trial`` after a paid call.
    model_axis = next((levels for name, levels in spec.axes if name == "model"), None)
    if model_axis:
        models = [str(level) for level in model_axis]
    else:
        models = [spec.model or PINNED_MODEL]
    prices = {m: price_for(m, spec.price_usd_per_mtok) for m in models}
    # M45.19 — the fixed system prefix (directive + brief) is cacheable; a
    # pilot-measured hit rate moves that share of the input from full price
    # to the cache-read rate (cost_usd prices cache reads at 10%).
    hit = spec.expected_cache_hit_rate
    cached_tokens = round(total_input_tokens * hit)
    share = 1.0 / len(models)
    usd = sum(
        cost_usd(
            round((total_input_tokens - cached_tokens) * share),
            round(total_output_tokens * share),
            prices[m],
            cache_read_tokens=round(cached_tokens * share),
        )
        for m in models
    )
    model = models[0] if len(models) == 1 else "mixed(" + ", ".join(models) + ")"

    cache_desc = f", cache hit {hit:.0%}" if hit else ""
    if len(models) == 1:
        price = prices[models[0]]
        price_desc = f"@ ${price[0]}/${price[1]} per MTok"
    else:
        price_desc = "@ " + " + ".join(f"{m} ${prices[m][0]}/${prices[m][1]}" for m in models) + f" per MTok, {len(models)} equal shares"
    formula = (
        f"{llm_trials} llm_trials x ({turns} turns, memory={memory_desc}: "
        f"{input_per_trial:.0f} input + {output_per_trial:.0f} output tok/trial{cache_desc}) "
        f"{price_desc} = ${usd:.4f}"
    )
    return CostEstimate(
        llm_trials=llm_trials,
        turns_per_trial=turns,
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
        usd=usd,
        model=model,
        formula=formula,
    )
