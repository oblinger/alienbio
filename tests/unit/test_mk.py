"""Tests for ``mk`` — the terse, env-aware maker pegboard.

``mk.M`` / ``mk.R`` / ``mk.C`` replace the ``Impl(name, name=name, dat=MockDat(...))``
boilerplate: the name auto-derives (Entity default) and the anchor is minted
from a per-type prefix + the name, unless an explicit ``dat`` / ``parent`` or an
ambient ``mk.anchor(...)`` supplies one.
"""

from __future__ import annotations

import pytest

from alienbio import mk
from alienbio.bio.chemistry import ChemistryImpl
from alienbio.bio.molecule import MoleculeImpl
from alienbio.bio.reaction import ReactionImpl
from alienbio.infra.entity import Entity, MockDat


def test_registers_the_three_bio_makers():
    assert mk.registered_keys() == ["C", "M", "R"]


def test_mk_M_derives_name_and_mock_dat():
    a = mk.M("A")
    assert isinstance(a, MoleculeImpl)
    assert a.local_name == "A"
    assert a.name == "A"  # name auto-derives from local_name
    assert a.dat().get_path_name() == "mol/A"  # anchor derived from prefix + name


def test_mk_M_forwards_keyword_overrides():
    a = mk.M("A", bdepth=3, description="root")
    assert a.bdepth == 3
    assert a.description == "root"
    assert a.dat().get_path_name() == "mol/A"


def test_mk_R_takes_reactants_products_positionally():
    a, b = mk.M("A"), mk.M("B")
    r = mk.R("R1", {a: 1.0}, {b: 1.0}, rate=0.1)
    assert isinstance(r, ReactionImpl)
    assert r.reactants == {a: 1.0}
    assert r.products == {b: 1.0}
    assert r.rate == 0.1
    assert r.dat().get_path_name() == "rxn/R1"


def test_mk_C_derives_name_keyed_dicts_from_entity_lists():
    a, b = mk.M("A"), mk.M("B")
    r = mk.R("R1", {a: 1.0}, {b: 1.0})
    chem = mk.C("world", [a, b], [r])
    assert isinstance(chem, ChemistryImpl)
    assert chem.molecules == {"A": a, "B": b}
    assert chem.reactions == {"R1": r}
    assert chem.dat().get_path_name() == "chem/world"


def test_mk_C_accepts_explicit_dicts_too():
    a = mk.M("A")
    chem = mk.C("world", {"A": a}, {})
    assert chem.molecules == {"A": a}
    assert chem.reactions == {}


def test_explicit_dat_overrides_the_derived_anchor():
    a = mk.M("A", dat=MockDat("custom/path"))
    assert a.dat().get_path_name() == "custom/path"


def test_explicit_parent_makes_a_child_entity():
    root = mk.C("world")
    child = mk.M("A", parent=root)
    assert child.parent is root
    assert child.root() is root
    assert "A" in root.children


def test_anchor_context_attaches_to_a_parent_entity():
    root = mk.C("world")
    with mk.anchor(root):
        a = mk.M("A")
        b = mk.M("B")
    assert a.parent is root
    assert b.parent is root
    # Outside the block, anchoring reverts to MockDat.
    c = mk.M("C")
    assert c.dat().get_path_name() == "mol/C"


def test_anchor_context_attaches_to_a_real_dat():
    dat = MockDat("catalog/run1")
    with mk.anchor(dat):
        a = mk.M("A")
    assert a.dat() is dat


def test_anchor_is_nestable_and_pops_cleanly():
    outer = mk.C("outer")
    inner = mk.C("inner", parent=outer)
    with mk.anchor(outer):
        top = mk.M("Top")
        with mk.anchor(inner):
            deep = mk.M("Deep")
        after = mk.M("After")
    assert top.parent is outer
    assert deep.parent is inner
    assert after.parent is outer


def test_unknown_maker_key_raises_attributeerror():
    with pytest.raises(AttributeError, match="no maker 'Q'"):
        mk.Q("x")  # type: ignore[attr-defined]


def test_registering_conflicting_key_is_rejected():
    def _other(local_name, anchor, **kwargs):  # noqa: ANN001
        return Entity(local_name, **anchor)

    with pytest.raises(ValueError, match="already registered"):
        mk.register("M", prefix="mol", build=_other)


def test_reregistering_identical_maker_is_idempotent():
    from alienbio.bio.makers import _build_molecule

    # Same build callable -> no error (module re-import safety).
    mk.register("M", prefix="mol", build=_build_molecule)
    assert mk.registered_keys() == ["C", "M", "R"]
