"""Module-doc findings on ``WorldStateImpl``: every accessor bounds-checks
its ids against the state's own axes.

Repro (before the fix): on a 2-compartment / 3-molecule state
``set(0, 3, v)`` wrote compartment 1's first slot, ``get(1, 3)`` raised a
bare ``IndexError`` on the flat list, ``set(0, -1, v)`` wrote the last slot
of the whole list, ``get_multiplicity(-1)`` returned the last compartment's,
and ``get_compartment(5)`` returned ``[]``.
"""

from __future__ import annotations

import pytest

from alienbio.bio.compartment_tree import CompartmentTreeImpl
from alienbio.bio.world_state import WorldStateImpl


def _state(**kw) -> WorldStateImpl:
    tree = CompartmentTreeImpl()
    root = tree.add_root("a")
    tree.add_child(root, "b")
    return WorldStateImpl(tree=tree, num_molecules=3, **kw)


@pytest.mark.parametrize("comp, mol", [(0, 3), (1, 3), (0, -1), (-1, 0), (2, 0)])
def test_concentration_accessors_refuse_an_out_of_range_id(comp, mol) -> None:
    state = _state()
    before = [state.get(c, m) for c in range(2) for m in range(3)]
    with pytest.raises(IndexError, match=r"out of range"):
        state.set(comp, mol, 7.0)
    with pytest.raises(IndexError, match=r"out of range"):
        state.get(comp, mol)
    with pytest.raises(IndexError):
        state.amount(comp, mol)
    assert [state.get(c, m) for c in range(2) for m in range(3)] == before


@pytest.mark.parametrize("comp", [-1, 2])
def test_compartment_accessors_refuse_an_out_of_range_id(comp) -> None:
    state = _state()
    for call in (
        lambda: state.get_multiplicity(comp),
        lambda: state.set_multiplicity(comp, 2.0),
        lambda: state.get_volume(comp),
        lambda: state.set_volume(comp, 2.0),
        lambda: state.get_compartment(comp),
        lambda: state.set_compartment(comp, [1.0, 2.0, 3.0]),
    ):
        with pytest.raises(IndexError, match=r"compartment"):
            call()
    assert state.get_all_multiplicities() == [1.0, 1.0]
    assert state.get_all_volumes() == [1.0, 1.0]


def test_the_error_names_the_id_and_the_bound() -> None:
    with pytest.raises(IndexError, match=r"molecule id 3 out of range \[0, 3\)"):
        _state().get(0, 3)
    with pytest.raises(IndexError, match=r"compartment id -1 out of range \[0, 2\)"):
        _state().get_multiplicity(-1)


def test_the_constructor_refuses_id_lists_of_the_wrong_length() -> None:
    with pytest.raises(ValueError, match="molecule_ids"):
        _state(molecule_ids=["x", "y"])
    with pytest.raises(ValueError, match="compartment_ids"):
        _state(compartment_ids=["a"])


def test_from_array_checks_the_shape() -> None:
    np = pytest.importorskip("numpy")
    state = _state()
    with pytest.raises(ValueError, match="shape"):
        state.from_array(np.zeros((3, 2)))
    state.from_array(np.arange(6.0).reshape(2, 3))
    assert state.get(1, 0) == 3.0


def test_as_array_is_a_copy() -> None:
    pytest.importorskip("numpy")
    state = _state()
    arr = state.as_array()
    arr[0, 0] = 9.0
    assert state.get(0, 0) == 0.0
    assert "copy" in (WorldStateImpl.as_array.__doc__ or "")
