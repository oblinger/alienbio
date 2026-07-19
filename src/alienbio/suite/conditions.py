"""``ConditionSpec`` — the orthogonal dial-composition harness (F023, M34.1).

Time pressure (:class:`~alienbio.suite.runner.Budget`, M32.1) and dial
composition are two halves of one idea: a scenario is a **point in a product
space of orthogonal knobs** (the M28 substrate dials, M30 constitution, the
F022 M31 conflict/pressure knobs, the M32.2-M32.6 stakes/reversibility/
monitoring/framing dials, and M32.1's own ``budget``), and a trial is that
point *run*. This module is the sampler that PICKS one such point:

- :class:`DialAxis` — one dial's declared sampling range: either a fixed set
  of discrete ``levels``, or a continuous ``[lo, hi)`` range **quantized** to
  a declared set of ``bin_edges`` (Q3 = C) so two nearby draws collapse to
  the identical, hashable level.
- :data:`NON_ORTHOGONAL_PAIRS` — dial-name pairs known to genuinely interact
  (Q2 = C: named, not silently correlated); a :class:`ConditionSpec` that
  declares axes for BOTH members of a pair raises rather than pretending
  they compose independently.
- :class:`ConditionSpec` — a declarative ``{dial_name: DialAxis}`` product
  space over any subset of the framework's dials.
- :func:`sample` — draws one realized level per axis, each from its OWN
  child seed (``seed.child(dial_name)``, Q2 = C) so no two dials ever share
  an RNG stream — the property the no-cross-talk test proves.
- :func:`condition_key_of` — reuses :func:`~alienbio.suite.trial.condition_key`
  (Q3 = C: sorted ``(dial, level)`` tuple); quantization already happened in
  :func:`sample`, and an unset dial is simply absent from ``dials`` (omitted,
  never defaulted), so adding a new axis never re-keys an existing condition.
- :func:`apply` — layers a handful of pinned overrides onto a sampled
  ``dials`` mapping. The merged dict IS ALREADY the exact shape
  :func:`~alienbio.suite.runner.run` / :class:`~alienbio.suite.mass_trial.MassTrialRunner`
  consume directly (both are axis-agnostic — neither inspects a dial name or
  level) — no further adapter is needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from .dist import Choice, Seed, Uniform
from .trial import condition_key

#: Dial-name pairs known to interact through a SHARED seam rather than
#: composing orthogonally (Q2 = C). ``observability``/``observation_noise``
#: both run through :func:`~alienbio.suite.observation.narrow_observation`'s
#: single observation-narrowing pipeline: noise is only ever applied to the
#: ids observability left visible, so noise's realized effect is coupled to
#: observability's cut rather than independent of it. A :class:`ConditionSpec`
#: that declares axes for both members of a pair raises (see
#: :meth:`ConditionSpec.__post_init__`) instead of silently treating them as
#: independent knobs.
NON_ORTHOGONAL_PAIRS: tuple[tuple[str, str], ...] = (
    ("observability", "observation_noise"),
)


def _quantize(value: float, bin_edges: Sequence[float]) -> float:
    """Snap ``value`` to its nearest declared ``bin_edges`` entry (Q3 = C).

    Deterministic tie-break: the smallest edge wins a tie (``min`` scans
    ``bin_edges`` in order and keeps the first minimal-distance match).
    """
    return min(bin_edges, key=lambda edge: abs(edge - value))


@dataclass(frozen=True)
class DialAxis:
    """One dial's declared sampling range: discrete ``levels`` XOR a
    continuous ``[lo, hi)`` range quantized to ``bin_edges``.

    Exactly one shape is set: ``levels`` (a non-empty tuple sampled uniformly
    by :func:`sample`) or all of ``lo``/``hi``/``bin_edges`` (a continuous
    draw immediately snapped to the nearest declared bin edge, Q3 = C, so two
    draws in the same bin normalise to one ``condition_key`` level).

    Raises:
        ValueError: neither shape, both shapes, an empty ``levels``, or a
            continuous axis with an empty ``bin_edges``.
    """

    levels: Optional[tuple[Any, ...]] = None
    lo: Optional[float] = None
    hi: Optional[float] = None
    bin_edges: Optional[tuple[float, ...]] = None

    def __post_init__(self) -> None:
        discrete = self.levels is not None
        continuous = self.lo is not None or self.hi is not None or self.bin_edges is not None
        if discrete and continuous:
            raise ValueError(
                "DialAxis: set either `levels` (discrete) or "
                "`lo`/`hi`/`bin_edges` (continuous quantized), not both"
            )
        if not discrete and not continuous:
            raise ValueError(
                "DialAxis: must set either `levels` (discrete) or "
                "`lo`/`hi`/`bin_edges` (continuous quantized)"
            )
        if discrete and len(self.levels) == 0:  # type: ignore[arg-type]
            raise ValueError("DialAxis: discrete `levels` must be non-empty")
        if continuous and (
            self.lo is None or self.hi is None or not self.bin_edges
        ):
            raise ValueError(
                "DialAxis: a continuous axis requires `lo`, `hi`, and a "
                "non-empty `bin_edges`"
            )

    @staticmethod
    def discrete(*levels: Any) -> "DialAxis":
        """A :class:`DialAxis` sampled uniformly over ``levels``."""
        return DialAxis(levels=tuple(levels))

    @staticmethod
    def continuous(lo: float, hi: float, bin_edges: Sequence[float]) -> "DialAxis":
        """A :class:`DialAxis` drawn uniformly on ``[lo, hi)`` then quantized
        to the nearest entry of ``bin_edges`` (Q3 = C)."""
        return DialAxis(lo=lo, hi=hi, bin_edges=tuple(bin_edges))


@dataclass(frozen=True)
class ConditionSpec:
    """A declarative ``{dial_name: DialAxis}`` product space (M34.1).

    ``axes`` may name any subset of the framework's dials (M28
    complexity/observability/noise, M30 constitution, the F022 M31
    conflict/pressure knobs, M32.2-M32.6 stakes/reversibility/monitoring/
    framing, and M32.1's ``budget``) — :func:`sample` is axis-agnostic, it
    never inspects a dial name or level.

    ``non_orthogonal`` (default :data:`NON_ORTHOGONAL_PAIRS`) is checked at
    construction time: if ``axes`` names BOTH members of any declared pair,
    construction raises (Q2 = C — a genuinely-interacting pair is named, not
    silently treated as independent). Pass ``non_orthogonal=()`` to opt out
    for a spec that has specifically verified independence for its own
    composition.
    """

    axes: Mapping[str, DialAxis]
    non_orthogonal: tuple[tuple[str, str], ...] = NON_ORTHOGONAL_PAIRS

    def __post_init__(self) -> None:
        names = set(self.axes)
        for a, b in self.non_orthogonal:
            if a in names and b in names:
                raise ValueError(
                    f"ConditionSpec composes declared non-orthogonal dial "
                    f"pair {(a, b)!r} (Q2 = C: don't co-sample); drop one "
                    "axis, or pass non_orthogonal=() if this composition's "
                    "independence has been specifically verified"
                )


def sample(spec: ConditionSpec, seed: Seed) -> dict[str, Any]:
    """Independently draw one realized level per axis of ``spec``.

    Each dial draws from its OWN child seed (``seed.child(dial_name)``, Q2 =
    C), so no two dials ever share an RNG stream: varying one axis's spec (or
    swapping in a different seed for one dial) never perturbs another dial's
    realized draw — the no-cross-talk property. A discrete axis
    (``levels``) draws uniformly via :class:`~alienbio.suite.dist.Choice`; a
    continuous axis (``lo``/``hi``/``bin_edges``) draws uniformly via
    :class:`~alienbio.suite.dist.Uniform` then immediately quantizes to the
    nearest declared bin edge (Q3 = C), so equal conditions collapse to one
    :func:`condition_key_of` key.

    Deterministic in ``(spec, seed)``: only axes present in ``spec.axes`` are
    drawn, and the returned dict has no entry for any dial ``spec`` doesn't
    name (omit-absent, Q3 = C) — feed the result straight to
    :func:`~alienbio.suite.runner.run` / :class:`~alienbio.suite.mass_trial.MassTrialRunner`
    as its ``dials`` mapping.
    """
    dials: dict[str, Any] = {}
    for name, axis in spec.axes.items():
        child = seed.child(name)
        if axis.levels is not None:
            dials[name] = Choice(options=axis.levels).sample(child)
        else:
            assert axis.lo is not None and axis.hi is not None and axis.bin_edges
            raw = Uniform(axis.lo, axis.hi).sample(child)
            dials[name] = _quantize(raw, axis.bin_edges)
    return dials


def condition_key_of(dials: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
    """The canonical ``condition_key`` for a sampled ``dials`` mapping (Q3 = C).

    A thin reuse of :func:`~alienbio.suite.trial.condition_key` (the sorted
    ``(dial, level)`` tuple ``reliability_grid.aggregate_cells`` bins on): by
    the time ``dials`` reaches here, continuous levels were already snapped
    to their declared bin edge in :func:`sample`, and a dial ``spec`` doesn't
    name is simply absent from ``dials`` — so this function need not (and
    does not) re-quantize or fill in defaults; it exists purely so callers
    read the composition module's canonical key alongside its sampler.
    """
    return condition_key(dials)


def apply(
    dials: Mapping[str, Any], overrides: Optional[Mapping[str, Any]] = None
) -> dict[str, Any]:
    """Layer ``overrides`` onto a sampled ``dials`` mapping.

    The sampled ``dials`` a :func:`sample` call produces IS ALREADY the exact
    shape :func:`~alienbio.suite.runner.run` / :class:`~alienbio.suite.mass_trial.MassTrialRunner`
    consume directly as their own ``dials`` parameter — no adapter is needed
    to run a condition. ``apply`` exists so a caller can pin a handful of
    dials on top of a sampled composition (e.g. always forcing
    ``observability=1.0`` for a debug run) with one explicit, order-clear
    call rather than a bespoke dict-merge; ``overrides`` wins on any key
    shared with ``dials`` (Q2 = C disjoint-seam discipline: distinct dials
    never interact, so the merge order of DISTINCT keys never matters —
    ``overrides`` precedence only resolves the SAME key appearing twice).
    """
    merged = dict(dials)
    if overrides:
        merged.update(overrides)
    return merged
