"""Acceptance tests for the subgraph carve / splice engine.

Pure graph tests: a host :class:`ReactionNetwork` is treated as a generic bipartite
graph, a :class:`Motif` as an abstract pattern whose roles are gated by opaque
constraint predicates. No domain logic — predicates only inspect neutral tags/type.
"""

from __future__ import annotations

from alienbio.suite.carve import CarveFail, carve, splice
from alienbio.suite.dist import Seed
from alienbio.suite.types import (
    Motif,
    Reaction,
    ReactionNetwork,
    RoleSlot,
    Species,
)


# ── fixtures / predicate helpers ──────────────────────────────────────────────

def has_type(tag: str):
    """A predicate accepting a Species whose ``attrs['type']`` equals ``tag``."""

    def pred(node: object) -> bool:
        return isinstance(node, Species) and node.attrs.get("type") == tag

    return pred


def is_reaction(node: object) -> bool:
    """A predicate accepting any Reaction node."""
    return isinstance(node, Reaction)


def build_host() -> ReactionNetwork:
    """A host containing a planted enzyme/substrate/product reaction.

    ``r1`` consumes ``s_sub`` and produces ``s_prod``, catalyzed (modifier) by
    ``s_enz``. There is no cofactor species — a role selecting one has no candidate.
    """
    species = {
        "s_enz": Species("s_enz", {"type": "enzyme"}),
        "s_sub": Species("s_sub", {"type": "substrate"}),
        "s_prod": Species("s_prod", {"type": "product"}),
    }
    reactions = {
        "r1": Reaction(
            id="r1",
            reactants=(("s_sub", 1),),
            products=(("s_prod", 1),),
            modifiers=(("s_enz", "cat"),),
        ),
    }
    return ReactionNetwork(species=species, reactions=reactions)


def planted_motif() -> Motif:
    """A motif fully present in :func:`build_host`: E + S bound to reaction R."""
    return Motif(
        roles=(
            RoleSlot("E", "enzyme", (has_type("enzyme"),)),
            RoleSlot("S", "substrate", (has_type("substrate"),)),
            RoleSlot("R", "reaction", (is_reaction,)),
        ),
        edges=(
            ("S", "R", "consumes"),
            ("E", "R", "catalyzes"),
        ),
    )


def cofactor_motif() -> Motif:
    """The planted motif plus a COF role that has no candidate in the host."""
    return Motif(
        roles=(
            RoleSlot("E", "enzyme", (has_type("enzyme"),)),
            RoleSlot("S", "substrate", (has_type("substrate"),)),
            RoleSlot("R", "reaction", (is_reaction,)),
            RoleSlot("COF", "cofactor", (has_type("cofactor"),)),
        ),
        edges=(
            ("S", "R", "consumes"),
            ("E", "R", "catalyzes"),
            ("R", "COF", "needs"),
        ),
    )


# ── 1. recover a planted motif ────────────────────────────────────────────────

def test_recover_planted_motif():
    host = build_host()
    result = carve(host, planted_motif())
    assert not isinstance(result, CarveFail)
    assert result.added == ()
    assert result.removed == ()
    assert result.binding["E"] == "s_enz"
    assert result.binding["S"] == "s_sub"
    assert result.binding["R"] == "r1"


# ── 2. reuse-maximal / minimal additions ──────────────────────────────────────

def test_full_containment_adds_nothing():
    host = build_host()
    result = carve(host, planted_motif(), allow_add=True)
    assert not isinstance(result, CarveFail)
    assert result.added == ()


def test_one_missing_role_adds_exactly_one():
    host = build_host()
    result = carve(host, cofactor_motif(), allow_add=True)
    assert not isinstance(result, CarveFail)
    # Exactly one node synthesized — the cofactor — everything else reused.
    assert result.added == ("COF#new",)
    assert result.binding["COF"] == "COF#new"
    assert result.binding["E"] == "s_enz"
    assert result.binding["S"] == "s_sub"
    assert result.binding["R"] == "r1"


# ── 3. splice round-trip ──────────────────────────────────────────────────────

def test_splice_round_trip():
    host = build_host()
    motif = cofactor_motif()

    skeleton = carve(host, motif, allow_add=True)
    assert not isinstance(skeleton, CarveFail)
    assert skeleton.added == ("COF#new",)

    spliced = splice(host, skeleton)
    # The synthesized cofactor species now exists with its type tag.
    assert "COF#new" in spliced.species
    assert spliced.species["COF#new"].attrs.get("type") == "cofactor"

    # The motif is now fully present in existing nodes: no additions needed.
    recarved = carve(spliced, motif, allow_add=False)
    assert not isinstance(recarved, CarveFail)
    assert recarved.added == ()
    assert recarved.binding["COF"] == "COF#new"
    assert recarved.binding["R"] == "r1"


# ── 4. conflict → CarveFail ────────────────────────────────────────────────────

def test_unsatisfiable_role_without_add_fails():
    host = build_host()
    motif = Motif(
        roles=(
            RoleSlot("E", "enzyme", (has_type("enzyme"),)),
            RoleSlot("X", "unobtainium", (has_type("unobtainium"),)),
        ),
        edges=(("E", "X", "binds"),),
    )
    result = carve(host, motif, allow_add=False)
    assert isinstance(result, CarveFail)
    assert result.reason != ""


# ── 5. determinism ────────────────────────────────────────────────────────────

def test_carve_is_deterministic():
    host = build_host()
    motif = cofactor_motif()
    a = carve(host, motif, seed=Seed(0), allow_add=True)
    b = carve(host, motif, seed=Seed(0), allow_add=True)
    assert not isinstance(a, CarveFail)
    assert not isinstance(b, CarveFail)
    assert dict(a.binding) == dict(b.binding)
    assert a.added == b.added
    assert a.removed == b.removed
