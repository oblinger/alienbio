"""Ground-truth tests for the M34.4 reliability-grid aggregation functions."""

from __future__ import annotations

import math
from typing import Mapping

import pytest

from alienbio.suite.reliability_grid import (
    CellStats,
    aggregate_cells,
    cell_mean,
    two_way_interaction,
)


# ═══════════════════════════════════════════════════════════════════════════
# aggregate_cells
# ═══════════════════════════════════════════════════════════════════════════

def test_aggregate_cells_hand_computed_two_groups():
    observations = [
        ("c1", 1.0),
        ("c2", 2.0),
        ("c1", 3.0),
        ("c1", 5.0),
        ("c2", 4.0),
    ]
    # c1 = [1, 3, 5]: mean = 3.0; sample stdev = sqrt(((1-3)^2+(3-3)^2+(5-3)^2)/2)
    #   = sqrt((4+0+4)/2) = sqrt(4) = 2.0
    # c2 = [2, 4]: mean = 3.0; sample stdev = sqrt(((2-3)^2+(4-3)^2)/1) = sqrt(2)
    result = aggregate_cells(observations)
    assert result["c1"] == CellStats(n=3, mean=3.0, std=2.0)
    assert result["c2"].n == 2
    assert result["c2"].mean == pytest.approx(3.0)
    assert result["c2"].std == pytest.approx(math.sqrt(2.0))


def test_aggregate_cells_singleton_group_has_zero_std():
    result = aggregate_cells([("x", 7.0)])
    assert result == {"x": CellStats(n=1, mean=7.0, std=0.0)}


def test_aggregate_cells_empty_input_is_empty_dict():
    assert aggregate_cells([]) == {}


def test_aggregate_cells_opaque_keys_not_inspected():
    # Keys are arbitrary hashables (e.g. tuples); only equality/grouping matters.
    observations = [(("x", 1), 10.0), (("x", 1), 20.0), (("y", 2), 5.0)]
    result = aggregate_cells(observations)
    assert result[("x", 1)].n == 2
    assert result[("x", 1)].mean == pytest.approx(15.0)
    assert result[("x", 1)].std == pytest.approx(math.sqrt(50.0))
    assert result[("y", 2)] == CellStats(n=1, mean=5.0, std=0.0)


# ═══════════════════════════════════════════════════════════════════════════
# cell_mean
# ═══════════════════════════════════════════════════════════════════════════

def test_cell_mean_hand_computed():
    observations = [("c1", 1.0), ("c2", 2.0), ("c1", 3.0), ("c1", 5.0)]
    assert cell_mean(observations, "c1") == pytest.approx(3.0)
    assert cell_mean(observations, "c2") == pytest.approx(2.0)


def test_cell_mean_raises_keyerror_on_missing_key():
    observations = [("c1", 1.0), ("c2", 2.0)]
    with pytest.raises(KeyError):
        cell_mean(observations, "missing")


def test_cell_mean_raises_keyerror_on_empty_observations():
    with pytest.raises(KeyError):
        cell_mean([], "anything")


def test_cell_mean_agrees_with_aggregate_cells_for_self_unequal_key():
    # float('nan') is hashable but nan != nan, so dict grouping (which
    # aggregate_cells relies on) groups same-object NaN keys together via
    # its identity shortcut. cell_mean must use the same identity-or-equality
    # rule so the two functions report a consistent view of one group.
    nan = float("nan")
    observations = [(nan, 1.0), (nan, 3.0)]
    grouped = aggregate_cells(observations)
    assert grouped[nan].n == 2
    assert grouped[nan].mean == pytest.approx(2.0)
    assert cell_mean(observations, nan) == pytest.approx(2.0)


# ═══════════════════════════════════════════════════════════════════════════
# two_way_interaction
# ═══════════════════════════════════════════════════════════════════════════

def test_two_way_interaction_purely_additive_design_is_zero():
    # a1 - a0 == 2.0 at both b0 (3-1) and b1 (4-2) -> no interaction.
    cells: Mapping[tuple[object, object], float] = {
        ("a0", "b0"): 1.0,
        ("a0", "b1"): 2.0,
        ("a1", "b0"): 3.0,
        ("a1", "b1"): 4.0,
    }
    assert two_way_interaction(cells) == pytest.approx(0.0)


def test_two_way_interaction_super_additive_cell_hand_computed():
    # Same base cells, but (a1, b1) is boosted to 10.0 instead of the
    # additive prediction of 4.0 -> contrast = 10 - 3 - 2 + 1 = 6.0.
    cells: Mapping[tuple[object, object], float] = {
        ("a0", "b0"): 1.0,
        ("a0", "b1"): 2.0,
        ("a1", "b0"): 3.0,
        ("a1", "b1"): 10.0,
    }
    assert two_way_interaction(cells) == pytest.approx(6.0)


def test_two_way_interaction_level_ordering_uses_sorted_levels():
    # Levels must be mutually comparable; smaller sorts first as level 0.
    # A-levels {0, 1} sort ascending as (a0=0, a1=1); B-levels {10, 20} sort
    # ascending as (b0=10, b1=20). The design is deliberately non-additive
    # (m[1,20]=10.0 well above the additive prediction of 4.0) so the sorted-
    # ascending convention is pinned: contrast = m[1,20] - m[1,10] - m[0,20]
    # + m[0,10] = 10 - 3 - 2 + 1 = 6.0, whereas swapping only the A-level
    # ordering (a0=1, a1=0, as a reverse-sort mutant would) computes
    # m[0,20] - m[0,10] - m[1,20] + m[1,10] = 2 - 1 - 10 + 3 = -6.0.
    cells: Mapping[tuple[object, object], float] = {
        (0, 10): 1.0,
        (0, 20): 2.0,
        (1, 10): 3.0,
        (1, 20): 10.0,
    }
    assert two_way_interaction(cells) == pytest.approx(6.0)


def test_two_way_interaction_raises_on_missing_combination():
    cells: Mapping[tuple[object, object], float] = {
        ("a0", "b0"): 1.0,
        ("a0", "b1"): 2.0,
        ("a1", "b0"): 3.0,
        # ("a1", "b1") missing
    }
    with pytest.raises(ValueError):
        two_way_interaction(cells)


def test_two_way_interaction_raises_on_wrong_number_of_a_levels():
    cells: Mapping[tuple[object, object], float] = {
        ("a0", "b0"): 1.0,
        ("a0", "b1"): 2.0,
        ("a1", "b0"): 3.0,
        ("a1", "b1"): 4.0,
        ("a2", "b0"): 5.0,
    }
    with pytest.raises(ValueError):
        two_way_interaction(cells)


def test_two_way_interaction_raises_on_wrong_number_of_b_levels():
    cells: Mapping[tuple[object, object], float] = {
        ("a0", "b0"): 1.0,
        ("a0", "b1"): 2.0,
        ("a1", "b0"): 3.0,
        ("a1", "b1"): 4.0,
        ("a1", "b2"): 5.0,
    }
    with pytest.raises(ValueError):
        two_way_interaction(cells)


def test_two_way_interaction_raises_on_empty_cells():
    with pytest.raises(ValueError):
        two_way_interaction({})
