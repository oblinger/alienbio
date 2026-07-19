"""Partial observability + measurement noise over a fully-known state (M28.2/M28.3).

An :class:`~alienbio.protocols.bio.WorldState` snapshot is the ground truth: it
knows the exact value of every opaque id in every compartment. An agent under
partial observability never sees that snapshot directly — it sees a
:data:`Observation`, a tuple of per-compartment ``{id: value}`` dicts that has
been narrowed (some ids hidden) and/or corrupted (instrument noise). This module
is the pure pipeline turning ground truth into what the agent actually observes:

- :func:`full_observation` reads the ground truth off a self-describing
  ``WorldState`` (no loss).
- :func:`choose_hidden` deterministically picks which ids an agent cannot see.
- :func:`project_observation` drops the hidden ids (partial observability).
- :func:`add_measurement_noise` multiplies surviving values by seeded relative
  Gaussian instrument noise (measurement error).
- :func:`narrow_observation` (F021) composes all three into the one
  dial-driven entry point ``suite.runner.run`` calls every turn: ground truth
  in, agent-visible :data:`Observation` out.

Every stochastic step draws from a :class:`~alienbio.suite.dist.Seed`-derived
``numpy.random.Generator`` — never the ``random`` module or numpy's global
state — so identical inputs always yield identical observations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Collection, Mapping, Sequence, cast

from .dist import Seed

if TYPE_CHECKING:
    from ..bio.world_state import WorldStateImpl
    from ..protocols.bio import WorldState

#: One ``{observed_id: observed_value}`` dict per compartment, in compartment order.
Observation = tuple[dict[str, float], ...]


def full_observation(state: "WorldState") -> Observation:
    """Read every id in every compartment of ``state`` into an :data:`Observation`.

    Mirrors the ``mol_ids`` + ``as_array()`` reading pattern used elsewhere in
    ``suite``: ``state`` must be self-describing (its id axes populated), and
    the returned dicts carry the exact values off ``as_array()`` — no rounding,
    no loss, no hidden ids.

    Raises:
        ValueError: if ``state`` is not self-describing (either id axis is
            ``None``), so there is nothing to name the observed values with.
    """
    impl = cast("WorldStateImpl", state)
    mol_ids = impl.molecule_ids
    comp_ids = impl.compartment_ids
    if mol_ids is None or comp_ids is None:
        raise ValueError(
            "full_observation requires a self-describing WorldState "
            "(molecule_ids and compartment_ids); this state is pure-int"
        )
    arr = impl.as_array()
    return tuple(
        {mol_ids[j]: float(arr[i][j]) for j in range(len(mol_ids))}
        for i in range(len(comp_ids))
    )


def choose_hidden(ids: Sequence[str], fraction: float, seed: Seed) -> frozenset[str]:
    """Deterministically pick ``~fraction`` of ``ids`` to hide from an agent.

    ``fraction`` is clamped by construction to ``[0.0, 1.0]`` semantics via a
    rounded count (``round(fraction * len(ids))``): ``0.0`` hides nothing,
    ``1.0`` hides everything. The draw is seeded, so ``(ids, fraction, seed)``
    always yields the same hidden set.

    Raises:
        ValueError: if ``fraction`` is outside ``[0.0, 1.0]``.
    """
    if not (0.0 <= fraction <= 1.0):
        raise ValueError(f"fraction must be in [0.0, 1.0]; got {fraction!r}")
    ids_seq = list(ids)
    count = round(fraction * len(ids_seq))
    if count <= 0:
        return frozenset()
    if count >= len(ids_seq):
        return frozenset(ids_seq)
    rng = seed.rng()
    idx = rng.choice(len(ids_seq), size=count, replace=False)
    return frozenset(ids_seq[int(i)] for i in idx)


def project_observation(obs: Observation, hidden: Collection[str]) -> Observation:
    """Drop every id in ``hidden`` from each compartment dict of ``obs``.

    Non-hidden entries pass through with their values unchanged; ids that never
    appear in ``obs`` are ignored. Models partial observability: whatever is in
    ``hidden`` is simply absent from the result.
    """
    hidden_set = frozenset(hidden)
    return tuple(
        {k: v for k, v in compartment.items() if k not in hidden_set}
        for compartment in obs
    )


def add_measurement_noise(
    obs: Observation, rel_sigma: float, seed: Seed
) -> Observation:
    """Multiply each observed value by seeded relative Gaussian instrument noise.

    Each value ``v`` becomes ``v * max(0.0, 1 + rng.normal(0, rel_sigma))`` —
    zero-mean relative noise, clamped so a value never goes negative from noise
    alone. ``rel_sigma == 0.0`` is the identity (the draw is always exactly
    ``0.0``). Deterministic in ``(obs, rel_sigma, seed)``.

    Raises:
        ValueError: if ``rel_sigma`` is negative.
    """
    if rel_sigma < 0.0:
        raise ValueError(f"rel_sigma must be >= 0.0; got {rel_sigma!r}")
    rng = seed.rng()
    return tuple(
        {
            k: v * max(0.0, 1.0 + float(rng.normal(0.0, rel_sigma)))
            for k, v in compartment.items()
        }
        for compartment in obs
    )


def narrow_observation(
    state: "WorldState", dials: Mapping[str, Any], seed: Seed
) -> Observation:
    """Ground truth -> agent-visible :data:`Observation`, driven by ``dials``.

    The single shared narrower :func:`~alienbio.suite.runner.run` calls once
    per turn (single source of truth over :func:`full_observation` /
    :func:`choose_hidden` / :func:`project_observation` /
    :func:`add_measurement_noise` — no second copy of this composition).

    Two opaque, independently-optional dials, read straight off ``dials``:

    - ``"observability"`` — fraction of molecule ids VISIBLE, in ``[0.0,
      1.0]`` (the same convention as the legacy
      ``agent.session``/``build.visibility`` observability dial: ``1.0`` =
      fully observable). ``None`` (unset, the default) or ``1.0`` is the
      identity — no ids hidden. Internally translated to the hidden
      COMPLEMENT fraction :func:`choose_hidden` expects.
    - ``"observation_noise"`` — relative Gaussian sigma fed to
      :func:`add_measurement_noise`. ``None`` or ``0.0`` is the identity.

    Both draws use independent child seeds (``"observability"`` /
    ``"noise"``) derived from ``seed``, so ``(state, dials, seed)`` always
    yields the identical narrowed :data:`Observation`. Any other ``dials``
    entry is opaque and ignored here.

    Raises:
        ValueError: if ``observability`` is set but ``state`` is not
            self-describing (no ``molecule_ids`` to hide from).
    """
    obs = full_observation(state)

    observability = dials.get("observability")
    if observability is not None and float(observability) < 1.0:
        impl = cast("WorldStateImpl", state)
        mol_ids = impl.molecule_ids
        if mol_ids is None:
            raise ValueError(
                "narrow_observation: observability dial requires a "
                "self-describing WorldState (molecule_ids); this state is pure-int"
            )
        hidden = choose_hidden(
            mol_ids, 1.0 - float(observability), seed.child("observability")
        )
        obs = project_observation(obs, hidden)

    noise = dials.get("observation_noise")
    if noise:
        obs = add_measurement_noise(obs, float(noise), seed.child("noise"))

    return obs
