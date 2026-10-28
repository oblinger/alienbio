"""The experiment spec — ``ExperimentSpec``, its validators, ``load_spec`` and the dry-run cost estimate (T058; split out of ``experiment.py``)."""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union, cast


from .llm_agent import PINNED_MODEL, PROVIDER_FIXED_SAMPLING, cost_usd, validate_output_budget, load_models_snapshot, price_for
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
    #: T059 — the LLM agent's per-turn output budget (AUP's Protocol Atlas):
    #: a flat ``max_tokens`` or an ``output_schedule`` ``{"every", "deep",
    #: "shallow"}``; one form per arm; a trial dial of the same name overrides,
    #: so either can be swept. Unset, the provider fn's own cap applies.
    max_tokens: Optional[int] = None
    output_schedule: Optional[Mapping[str, int]] = None
    token_ceiling: Optional[int] = None
    fixed_dials: Mapping[str, Any] = field(default_factory=dict)
    out_dir: Optional[str] = None
    #: M45.5 — the cost ceiling + dry-run cost-estimate dials.
    #: ``expected_turns`` is the dry-run turn count. Left ``None``, it is
    #: derived at construction (:meth:`__post_init__`, both forms) from a
    #: declared ``max_turns`` (the largest of the fixed dial and every swept
    #: level), else the runner's own ``max_turns`` default — so after
    #: construction it is always a positive int. Set it explicitly for a
    #: spec whose agent is expected to commit well before the budget.
    cost_ceiling_usd: Optional[float] = None
    price_usd_per_mtok: Optional[tuple[float, float]] = None
    expected_turns: Optional[int] = None
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

    def __post_init__(self) -> None:
        """The one normaliser both forms pass through (T084): the YAML form
        reaches here via :func:`spec_from_dict`, the Python form AUP's
        launchers use directly. Idempotent, so a spec rebuilt from
        :func:`spec_to_dict` equals the original.

        A ``__post_init__`` rather than a ``normalized()`` step every caller
        must remember: the defect was exactly a derivation one entry point
        ran and the other did not, and the dataclass is frozen, so the
        constructor is the only place every spec is guaranteed to pass."""
        # M45.7 for both forms: only ``spec_from_dict`` used to add the idle
        # arm, so a directly built ``idle_baseline=True`` spec ran none, while
        # ``aggregate`` and ``bio suite resume`` rebuilt it WITH the arm.
        object.__setattr__(self, "axes", _with_idle_arm(self.axes, self.agent, self.idle_baseline))
        self._validate()

    def _validate(self) -> None:
        """Every check on the spec's own field values (or two fields
        together), in the order :func:`spec_from_dict` used to run them, with
        the same messages — so a Python-built spec is refused exactly where a
        YAML one is, at construction, before any guard reads it. Each
        validator also normalises (floats, a plain-dict schedule, a parsed
        ``PowerDesign``) and is idempotent on its own output."""
        def put(name: str, value: Any) -> None:
            object.__setattr__(self, name, value)

        if self.model is not None:
            _require_pinned_model(self.model)
        # M46.8: an ``agent`` / ``model`` axis is validated like the scalar fields.
        from .agents import AGENTS  # agents imports this module; resolve late

        for name, levels in self.axes:
            if name == "agent":
                unknown = sorted(str(level) for level in levels if str(level) not in AGENTS)
                if unknown:
                    raise ValueError(f"experiment spec: unknown agent axis level(s) {unknown}; expected one of {sorted(AGENTS)}")
            if name == "model":
                for level in levels:
                    _require_pinned_model(level)
        put("output_schedule", _validate_output_schedule(self.max_tokens, self.output_schedule))
        put("cost_ceiling_usd", _validate_cost_ceiling(self.cost_ceiling_usd))
        put("price_usd_per_mtok", _validate_price_override(self.price_usd_per_mtok))
        # The 2026-10-28 module-doc finding: a directly built spec kept the
        # literal ``expected_turns = 8``, so a Python-form 20-turn live spec
        # was estimated at 8 turns, and ``spec_to_dict`` pinned the 8 through
        # every reload — the under-price an operator reads before spending.
        if self.expected_turns is None:
            turns = _default_expected_turns(self.fixed_dials, self.axes)
        else:
            turns = _validate_positive_int("expected_turns", self.expected_turns)
        put("expected_turns", turns)
        put("expected_prompt_tokens", _validate_positive_int("expected_prompt_tokens", self.expected_prompt_tokens))
        put("expected_output_tokens", _validate_positive_int("expected_output_tokens", self.expected_output_tokens))
        put("design", _validate_design(self.design, self.trials_per_condition, self.axes))
        put("concurrency", _validate_positive_int("concurrency", self.concurrency))
        put("matched_dials", _validate_matched_dials(self.matched_dials, self.axes))
        put("key_readout", _validate_key_readout(self.key_readout))
        put("temperature", _validate_sampling(self.temperature, self.top_p))
        put("top_p", _validate_unit_float("top_p", self.top_p))
        put(
            "expected_cache_hit_rate",
            _validate_unit_float("expected_cache_hit_rate", self.expected_cache_hit_rate) or 0.0,
        )
        put("registration", _validate_registration_id(self.registration))


def _with_idle_arm(
    axes: tuple[tuple[str, tuple[Any, ...]], ...], agent: str, idle_baseline: bool
) -> tuple[tuple[str, tuple[Any, ...]], ...]:
    """M45.7 — ``axes`` plus the matched idle arm: an ``agent`` axis
    ``(agent, "idle")`` when ``idle_baseline`` asks for one, unless ``agent``
    is already ``idle`` or an ``agent`` axis is swept (which also makes the
    expansion idempotent). The idle twin is just another arm of the grid —
    M46.8's matched seeds make it the baseline for the same (condition, trial)."""
    if idle_baseline and agent != "idle" and not any(name == "agent" for name, _ in axes):
        return axes + (("agent", (agent, "idle")),)
    return axes


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
        "max_tokens": spec.max_tokens,
        "output_schedule": dict(spec.output_schedule) if spec.output_schedule is not None else None,
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
    -> :class:`ExperimentSpec`. Optional keys default exactly as the class does.

    Only the dict's own shape is handled here (required keys, the ``axes``
    mapping to tuples, ``None`` for an empty mapping); every value check runs
    in the constructor (:meth:`ExperimentSpec._validate`), for both forms."""
    return ExperimentSpec(
        name=d["name"],
        axes=tuple((name, tuple(levels)) for name, levels in d["axes"].items()),
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
        max_tokens=d.get("max_tokens"),
        output_schedule=d.get("output_schedule"),
        token_ceiling=d.get("token_ceiling"),
        fixed_dials=dict(d.get("fixed_dials") or {}),
        out_dir=d.get("out_dir"),
        cost_ceiling_usd=d.get("cost_ceiling_usd"),
        price_usd_per_mtok=d.get("price_usd_per_mtok"),
        expected_turns=d.get("expected_turns"),  # None = derived in __post_init__
        expected_prompt_tokens=d.get("expected_prompt_tokens", 1500),
        expected_output_tokens=d.get("expected_output_tokens", 300),
        design=d.get("design"),
        concurrency=d.get("concurrency", 1),
        idle_baseline=bool(d.get("idle_baseline", False)),
        matched_dials=d.get("matched_dials", ()),
        key_readout=d.get("key_readout"),
        temperature=d.get("temperature"),
        top_p=d.get("top_p"),
        expected_cache_hit_rate=d.get("expected_cache_hit_rate", 0.0),
        registration=d.get("registration"),
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


def _expected_output_tokens(spec: "ExperimentSpec") -> int:
    """The per-turn output tokens to price: the DECLARED per-turn budget when
    the spec sets one, else ``expected_output_tokens``.

    T066, found twice over: ``estimate_cost`` priced output at the 300-token
    default however large a budget the spec declared, while T059's
    ``max_tokens`` / ``output_schedule`` are the caps the provider fn
    actually sends. Output is the expensive side of the pinned model ($2 in
    / $10 out), so an 8192-token arm was ~27x under-priced per turn —
    quiet in exactly the direction an operator checks before spending, which
    is the defect the ``expected_turns`` derivation two fields away exists
    to prevent. The budget is a CAP rather than a prediction, so this reads
    high by construction; an explicit ``expected_output_tokens`` above the
    cap still wins, since a caller who measured their arm knows better."""
    declared: list[int] = [int(spec.expected_output_tokens)]
    if isinstance(spec.max_tokens, int) and not isinstance(spec.max_tokens, bool):
        declared.append(int(spec.max_tokens))
    schedule = spec.output_schedule
    if isinstance(schedule, Mapping):
        declared.extend(
            int(v)
            for k, v in schedule.items()
            if k in ("deep", "shallow") and isinstance(v, int) and not isinstance(v, bool)
        )
    for name, levels in spec.axes:
        if name == "max_tokens":
            declared.extend(int(v) for v in levels if isinstance(v, int) and not isinstance(v, bool))
        elif name == "output_schedule":
            for level in levels:
                if isinstance(level, Mapping):
                    declared.extend(
                        int(v)
                        for k, v in level.items()
                        if k in ("deep", "shallow") and isinstance(v, int) and not isinstance(v, bool)
                    )
    return max(declared)


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

    declared: list[int] = []
    fixed = fixed_dials.get("max_turns")
    if isinstance(fixed, int) and not isinstance(fixed, bool) and fixed > 0:
        declared.append(fixed)
    for name, levels in axes:
        if name == "max_turns":
            declared.extend(
                v for v in levels if isinstance(v, int) and not isinstance(v, bool) and v > 0
            )
    if declared:
        # T066: "read high" has to mean the HIGHEST of everything declared,
        # not the first place one is found. The runtime merges
        # ``{**fixed_dials, **dials}``, so an axis level WINS over a fixed
        # dial of the same name — while this returned the fixed value and
        # never looked at the axis. A spec with ``fixed_dials: {max_turns:
        # 4}`` and ``axes: {max_turns: [4, 40]}`` priced every cell at 4
        # turns and ran the deepest at 40: the 2026-09-09 under-price, back
        # in a shape the fix did not cover.
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


def _validate_output_schedule(max_tokens: Any, output_schedule: Any) -> Optional[dict[str, int]]:
    """T059 — refuse a malformed output budget at load, before spend (the
    agent re-checks at construction); returns the schedule as a plain dict."""
    try:
        validate_output_budget(max_tokens, output_schedule)
    except ValueError as exc:
        raise ValueError(f"spec: {exc}") from exc
    return {k: int(v) for k, v in output_schedule.items()} if output_schedule is not None else None


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
    #: Model calls one llm trial is priced at: one per turn, plus each
    #: declared probe's forked call (per turn for ``every_turn`` /
    #: ``after_action``, once for ``at_commit``) and one summarizer call
    #: under ``compact_at``. ``0`` on an all-scripted spec.
    calls_per_trial: int = 0


def _probe_counts(spec: ExperimentSpec) -> tuple[int, int]:
    """``(per_turn, once)`` probe calls per trial — the largest declared set
    when ``probes`` is swept (read high). ``every_turn`` and ``after_action``
    fire each turn (``after_action`` only on a turn that acts; priced as if
    every turn does), ``at_commit`` once."""
    candidates: list[Any] = [spec.fixed_dials.get("probes")]
    for name, levels in spec.axes:
        if name == "probes":
            candidates.extend(levels)
    best = (0, 0)
    for decl in candidates:
        if not isinstance(decl, (list, tuple)):
            continue
        timings = [entry.get("timing") for entry in decl if isinstance(entry, Mapping)]
        counts = (
            sum(1 for t in timings if t in ("every_turn", "after_action")),
            sum(1 for t in timings if t == "at_commit"),
        )
        if sum(counts) > sum(best):
            best = counts
    return best


def _compact_turn(spec: ExperimentSpec) -> Optional[int]:
    """The turn a summarizer call fires at, read high: the latest declared
    ``compact_at`` (the spec's, or the largest swept level) — the later the
    turn, the longer the displaced history it is prompted with."""
    levels: list[Any] = [spec.compact_at]
    for name, axis_levels in spec.axes:
        if name == "compact_at":
            levels.extend(axis_levels)
    turns = [int(v) for v in levels if isinstance(v, int) and not isinstance(v, bool)]
    return max(turns) if turns else None


def _compact_budget(spec: ExperimentSpec) -> Optional[int]:
    """The summarizer reply's cap, read high: the largest declared
    ``compact_budget`` (``None`` = uncapped, priced as a turn's output)."""
    levels: list[Any] = [spec.compact_budget]
    for name, axis_levels in spec.axes:
        if name == "compact_budget":
            levels.extend(axis_levels)
    budgets = [int(v) for v in levels if isinstance(v, int) and not isinstance(v, bool)]
    return max(budgets) if budgets else None


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
    flat ``O * T`` (``O`` = ``expected_output_tokens``). Each declared probe
    (``dials["probes"]``, T026) is a forked call on the next act's context:
    an ``every_turn`` / ``after_action`` probe adds the main line's input and
    output again, an ``at_commit`` probe one last-turn call; ``compact_at``
    (T049) adds one summarizer call prompted with the history up to that
    turn (``P * (1 + c/2)``) and replying at most ``compact_budget`` tokens
    (``O`` when unset). All read high. ``usd`` is
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

    turns = cast(int, spec.expected_turns)  # an int after __post_init__
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
    output_tokens = _expected_output_tokens(spec)
    def _input_for(memory: Any) -> tuple[float, str]:
        if memory == "full":
            return sum(prompt_tokens * (1 + t / 2) for t in range(turns)), "full"
        if memory == "none":
            return prompt_tokens * turns, "none"
        k = cast(int, memory)
        return prompt_tokens * turns * (1 + min(k, turns - 1) / 2), f"k={k}"

    # Round 4 (2026-10-27): a ``memory`` axis runs per level (T066), so it is
    # priced per level — each owns an equal share of the llm trials, as the
    # model axis below. Pricing every cell at ``spec.memory`` read a
    # none/full ladder ~5.75x low at 20 turns.
    memory_axis = next((levels for name, levels in spec.axes if name == "memory"), None)
    per_level = [_input_for(m) for m in (memory_axis or (spec.memory,))]
    main_input = sum(tokens for tokens, _ in per_level) / len(per_level)
    memory_desc = "/".join(desc for _, desc in per_level)
    main_output = output_tokens * turns

    # The calls beyond one per turn (second suite round, 2026-10-28): a
    # probe is a forked call on the exact next-act context and a compaction
    # one summarizer call, both metered on the real run and both missing
    # from the estimate, which read a two-probe arm ~3x low.
    per_turn_probes, commit_probes = _probe_counts(spec)
    def _last_turn_input(memory: Any) -> float:
        if memory == "none":
            return float(prompt_tokens)
        window = turns - 1 if memory == "full" else min(cast(int, memory), turns - 1)
        return prompt_tokens * (1 + window / 2)

    last_turn_input = max(_last_turn_input(m) for m in (memory_axis or (spec.memory,)))
    compact_turn = _compact_turn(spec)
    compact_budget = _compact_budget(spec)
    input_per_trial = main_input * (1 + per_turn_probes) + last_turn_input * commit_probes
    output_per_trial = main_output * (1 + per_turn_probes) + output_tokens * commit_probes
    calls_per_trial = turns * (1 + per_turn_probes) + commit_probes
    extra_desc: list[str] = []
    if per_turn_probes or commit_probes:
        extra_desc.append(f"{per_turn_probes} per-turn + {commit_probes} at-commit probe call(s)")
    if compact_turn is not None:
        input_per_trial += prompt_tokens * (1 + compact_turn / 2)
        output_per_trial += compact_budget if compact_budget is not None else output_tokens
        calls_per_trial += 1
        extra_desc.append(f"1 summarizer call at turn {compact_turn}")

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
    calls_desc = f", {calls_per_trial} calls/trial incl. " + " + ".join(extra_desc) if extra_desc else ""
    formula = (
        f"{llm_trials} llm_trials x ({turns} turns, memory={memory_desc}{calls_desc}: "
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
        calls_per_trial=calls_per_trial,
    )
