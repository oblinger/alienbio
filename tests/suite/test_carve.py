"""Acceptance tests for the subgraph carve / splice engine.

Pure graph tests: a host :class:`ChemistryImpl` is treated as a generic bipartite
graph (molecules = species nodes, reactions = reaction nodes, keyed by ``name``), a
:class:`Motif` as an abstract pattern whose roles are gated by opaque constraint
predicates. No domain logic in the engine — predicates only inspect a node's type
and its opaque ``description`` tag.

F007: the engine builds ``Chemistry`` (unified protocol model), so a node's opaque
"type" tag lives in the molecule's ``description``.

F008: catalysis is a first-class ``modifiers`` edge — the enzyme acts on the reaction
without being consumed (it is neither a reactant nor a product), and the reaction's
graph incidence includes its modifiers, so the enzyme is adjacent to the reaction.
"""

from __future__ import annotations

from alienbio.bio.chemistry import ChemistryImpl
from alienbio.bio.molecule import MoleculeImpl
from alienbio.bio.reaction import ReactionImpl
from alienbio.infra.entity import MockDat
from alienbio.suite.carve import CarveFail, carve, splice
from alienbio.suite.dist import Seed
from alienbio.suite.types import (
    Motif,
    RoleSlot,
)


# ── fixtures / predicate helpers ──────────────────────────────────────────────

def has_type(tag: str):
    """A predicate accepting a molecule whose ``description`` (its opaque type tag)
    equals ``tag``."""

    def pred(node: object) -> bool:
        return isinstance(node, MoleculeImpl) and node.description == tag

    return pred


def is_reaction(node: object) -> bool:
    """A predicate accepting any reaction node."""
    return isinstance(node, ReactionImpl)


def _mol(name: str, type_tag: str) -> MoleculeImpl:
    return MoleculeImpl(name, name=name, description=type_tag, dat=MockDat(f"mol/{name}"))


def build_host() -> ChemistryImpl:
    """A host containing a planted enzyme/substrate/product reaction.

    ``r1`` consumes ``s_sub`` and produces ``s_prod``, catalyzed by ``s_enz`` — the
    enzyme is a first-class **modifier** (not consumed), so it is adjacent to ``r1``
    through the reaction's modifier incidence. There is no cofactor molecule — a role
    selecting one has no candidate.
    """
    s_enz = _mol("s_enz", "enzyme")
    s_sub = _mol("s_sub", "substrate")
    s_prod = _mol("s_prod", "product")
    r1 = ReactionImpl(
        "r1",
        reactants={s_sub: 1.0},
        products={s_prod: 1.0},
        modifiers={s_enz: "catalyst"},
        dat=MockDat("rxn/r1"),
    )
    return ChemistryImpl(
        "host",
        molecules={"s_enz": s_enz, "s_sub": s_sub, "s_prod": s_prod},
        reactions={"r1": r1},
        dat=MockDat("chem/host"),
    )


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
    # The synthesized cofactor molecule now exists with its type tag (description).
    assert "COF#new" in spliced.molecules
    assert spliced.molecules["COF#new"].description == "cofactor"

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
