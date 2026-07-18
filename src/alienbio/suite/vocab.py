"""M27.2 — controlled vocabularies for the FT08 NL rendering engine.

Builds a per-world, seed-deterministic :class:`~alienbio.suite.render.Vocabulary`
— an injective ``token -> alien-phrase`` map over a world's node namespace
(molecule + reaction ids) — that FT08 renders/parses ``Question``/``Answer``
through. This is *content* for the neutral render engine: it authors the opaque
surface phrases; the engine's bijection / round-trip guarantees are unchanged.

Alien phrasing reuses the M14 skinning generator
(:func:`~alienbio.bio.skinning.generate_alien_name`) so the alien-name *style*
has a single source of truth.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from ..bio.skinning import generate_alien_name
from .dist import Seed
from .render import Vocabulary

if TYPE_CHECKING:
    from ..bio.world import WorldImpl

# Bound on collision re-derivation before the index-suffix fallback kicks in.
# The alien-name space is finite; for realistic worlds this is never reached.
_MAX_RESEED = 64


def build_vocabulary(
    world: "WorldImpl", seed: Seed = Seed(0), *, extra_tokens: Iterable[str] = ()
) -> Vocabulary:
    """Build an injective ``token -> alien-phrase`` vocabulary for ``world``.

    Covers every molecule and reaction id in ``world.chemistry`` — the node
    namespace that can appear in an ``Answer``/``Question`` — plus any
    ``extra_tokens`` an archetype declares whose answers are NOT world nodes
    (e.g. the ``predict_response`` family's ``up``/``down``/``same`` response
    tokens, which must render but are neither molecules nor reactions).
    Deterministic in ``(world nodes, extra_tokens, seed)``: the same token set +
    seed always yields the same map, each token drawing from an independent child
    seed.

    Injectivity is guaranteed here — a colliding alien name is re-derived from a
    bumped child seed, then index-suffixed as a last resort — and re-enforced by
    the :class:`Vocabulary` constructor, which raises on any residual collision
    rather than silently deduping (no fallback that masks the canary).
    """
    chem = world.chemistry
    tokens = sorted(set(chem.molecules) | set(chem.reactions) | set(extra_tokens))

    phrases: dict[str, str] = {}
    used: set[str] = set()
    for i, token in enumerate(tokens):
        name = generate_alien_name(token, seed=seed.child(token).value)
        bump = 0
        while name in used and bump < _MAX_RESEED:
            bump += 1
            name = generate_alien_name(token, seed=seed.child(f"{token}#{bump}").value)
        if name in used:
            # The token index is globally distinct, so this is guaranteed unique.
            name = f"{name}-{i}"
        phrases[token] = name
        used.add(name)

    return Vocabulary(phrases=phrases)
