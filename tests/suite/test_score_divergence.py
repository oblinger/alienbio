"""Ground-truth tests for the M33.10 final-state divergence scorer."""

from __future__ import annotations

import math

import pytest

from alienbio.bio.compartment_tree import CompartmentTreeImpl
from alienbio.bio.world_state import WorldStateImpl
from alienbio.suite.score_divergence import final_state_distance, normalized_divergence
from alienbio.suite.types import Timeline


def _one_compartment_state(concentrations: list[float]) -> WorldStateImpl:
    """A self-describing 1-compartment ('c0') state over ids (A, B)."""
    tree = CompartmentTreeImpl()
    tree.add_root("c0")
    return WorldStateImpl(
        tree=tree,
        num_molecules=2,
        initial_concentrations=concentrations,
        compartment_ids=["c0"],
        molecule_ids=["A", "B"],
    )


def _two_compartment_state(
    c0_values: list[float], c1_values: list[float]
) -> WorldStateImpl:
    """A self-describing 2-compartment ('c0', 'c1') state over ids (A, B)."""
    tree = CompartmentTreeImpl()
    root = tree.add_root("c0")
    tree.add_child(root, "c1")
    return WorldStateImpl(
        tree=tree,
        num_molecules=2,
        initial_concentrations=c0_values + c1_values,
        compartment_ids=["c0", "c1"],
        molecule_ids=["A", "B"],
    )


def _timeline(state: WorldStateImpl) -> Timeline:
    """A one-state Timeline (only the final state matters to this scorer)."""
    return Timeline(times=(0.0,), states=(state,))


# ═══════════════════════════════════════════════════════════════════════════
# identical outcomes -> zero
# ═══════════════════════════════════════════════════════════════════════════

def test_timeline_vs_itself_is_zero_distance_and_divergence():
    timeline = _timeline(_one_compartment_state([1.0, 2.0]))

    assert final_state_distance(timeline, timeline) == pytest.approx(0.0)
    assert normalized_divergence(timeline, timeline) == pytest.approx(0.0)


# ═══════════════════════════════════════════════════════════════════════════
# hand-computed exact L2 (2 compartments summed per id -> known totals)
# ═══════════════════════════════════════════════════════════════════════════

def test_exact_l2_hand_computed_over_two_compartments():
    # a: A total = 1.0 + 3.0 = 4.0; B total = 2.0 + 0.0 = 2.0
    a = _timeline(_two_compartment_state([1.0, 2.0], [3.0, 0.0]))
    # b: A total = 0.0 + 1.0 = 1.0; B total = 5.0 + 1.0 = 6.0
    b = _timeline(_two_compartment_state([0.0, 5.0], [1.0, 1.0]))

    # diff_A = 4.0 - 1.0 = 3.0; diff_B = 2.0 - 6.0 = -4.0
    # L2 = sqrt(3.0^2 + (-4.0)^2) = sqrt(9 + 16) = sqrt(25) = 5.0
    expected = 5.0
    assert final_state_distance(a, b) == pytest.approx(expected)
    assert normalized_divergence(a, b) == pytest.approx(expected / (expected + 1.0))


# ═══════════════════════════════════════════════════════════════════════════
# symmetry
# ═══════════════════════════════════════════════════════════════════════════

def test_distance_is_symmetric():
    a = _timeline(_one_compartment_state([1.0, 2.0]))
    b = _timeline(_one_compartment_state([4.0, -1.0]))

    assert final_state_distance(a, b) == pytest.approx(final_state_distance(b, a))


# ═══════════════════════════════════════════════════════════════════════════
# normalized_divergence bounded in [0, 1]
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize(
    "a_values,b_values",
    [
        ([0.0, 0.0], [0.0, 0.0]),
        ([1.0, 1.0], [1.0, 1.0]),
        ([0.0, 0.0], [1e6, -1e6]),
        ([3.0, 7.0], [3.0, 7.0001]),
    ],
)
def test_normalized_divergence_always_in_unit_interval(a_values, b_values):
    a = _timeline(_one_compartment_state(a_values))
    b = _timeline(_one_compartment_state(b_values))

    d = normalized_divergence(a, b)
    assert 0.0 <= d <= 1.0
    assert math.isfinite(d)


# ═══════════════════════════════════════════════════════════════════════════
# ids restriction changes the result as expected
# ═══════════════════════════════════════════════════════════════════════════

def test_ids_restriction_changes_result():
    # A totals differ by 3.0, B totals differ by 4.0 (same shape as the L2 test).
    a = _timeline(_one_compartment_state([4.0, 2.0]))
    b = _timeline(_one_compartment_state([1.0, 6.0]))

    full = final_state_distance(a, b)
    assert full == pytest.approx(5.0)

    only_a = final_state_distance(a, b, ids=["A"])
    assert only_a == pytest.approx(3.0)

    only_b = final_state_distance(a, b, ids=["B"])
    assert only_b == pytest.approx(4.0)

    assert only_a != pytest.approx(full)
    assert only_b != pytest.approx(full)


# ═══════════════════════════════════════════════════════════════════════════
# monotonic: a strictly larger per-id gap yields a strictly larger distance
# ═══════════════════════════════════════════════════════════════════════════

def test_distance_is_monotonic_in_the_gap():
    a = _timeline(_one_compartment_state([1.0, 1.0]))
    near = _timeline(_one_compartment_state([1.0, 2.0]))
    far = _timeline(_one_compartment_state([1.0, 5.0]))

    d_near = final_state_distance(a, near)
    d_far = final_state_distance(a, far)

    assert 0.0 < d_near < d_far


def test_final_state_distance_raises_on_empty_timeline():
    empty = Timeline(times=(), states=())
    other = _timeline(_one_compartment_state([1.0, 1.0]))

    with pytest.raises(ValueError):
        final_state_distance(empty, other)
