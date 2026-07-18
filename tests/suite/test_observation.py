"""Ground-truth tests for partial observability + measurement noise (M28.2/M28.3)."""

from __future__ import annotations

import numpy as np
import pytest

from alienbio.bio.compartment_tree import CompartmentTreeImpl
from alienbio.bio.world_state import WorldStateImpl
from alienbio.suite.dist import Seed
from alienbio.suite.observation import (
    Observation,
    add_measurement_noise,
    choose_hidden,
    full_observation,
    project_observation,
)


def _two_compartment_state() -> WorldStateImpl:
    """A self-describing 2-compartment ('c0', 'c1') WorldState over (A, B, C)."""
    tree = CompartmentTreeImpl()
    root = tree.add_root("c0")
    tree.add_child(root, "c1")
    return WorldStateImpl(
        tree=tree,
        num_molecules=3,
        initial_concentrations=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        compartment_ids=["c0", "c1"],
        molecule_ids=["A", "B", "C"],
    )


def _pure_int_state() -> WorldStateImpl:
    """A pure-int (non-self-describing) WorldState — no id axes."""
    tree = CompartmentTreeImpl()
    tree.add_root("c0")
    return WorldStateImpl(tree=tree, num_molecules=2, initial_concentrations=[1.0, 2.0])


# ═══════════════════════════════════════════════════════════════════════════
# full_observation — exact ground truth, no loss
# ═══════════════════════════════════════════════════════════════════════════


def test_full_observation_exact_values():
    state = _two_compartment_state()
    obs = full_observation(state)
    assert obs == (
        {"A": 1.0, "B": 2.0, "C": 3.0},
        {"A": 4.0, "B": 5.0, "C": 6.0},
    )


def test_full_observation_requires_self_describing_state():
    state = _pure_int_state()
    with pytest.raises(ValueError):
        full_observation(state)


# ═══════════════════════════════════════════════════════════════════════════
# choose_hidden — deterministic, correct count
# ═══════════════════════════════════════════════════════════════════════════


def test_choose_hidden_fraction_zero_is_empty():
    ids = ["A", "B", "C", "D"]
    hidden = choose_hidden(ids, 0.0, Seed(1))
    assert hidden == frozenset()


def test_choose_hidden_fraction_one_is_all():
    ids = ["A", "B", "C", "D"]
    hidden = choose_hidden(ids, 1.0, Seed(1))
    assert hidden == frozenset(ids)


def test_choose_hidden_fraction_half_count():
    ids = ["A", "B", "C", "D"]
    hidden = choose_hidden(ids, 0.5, Seed(1))
    assert len(hidden) == 2
    assert hidden <= frozenset(ids)


def test_choose_hidden_deterministic_same_seed():
    ids = ["A", "B", "C", "D", "E"]
    h1 = choose_hidden(ids, 0.4, Seed(42))
    h2 = choose_hidden(ids, 0.4, Seed(42))
    assert h1 == h2


def test_choose_hidden_rejects_out_of_range_fraction():
    with pytest.raises(ValueError):
        choose_hidden(["A"], 1.5, Seed(0))
    with pytest.raises(ValueError):
        choose_hidden(["A"], -0.1, Seed(0))


# ═══════════════════════════════════════════════════════════════════════════
# project_observation — drops exactly the hidden set
# ═══════════════════════════════════════════════════════════════════════════


def test_project_observation_drops_hidden_keeps_rest():
    obs: Observation = (
        {"A": 1.0, "B": 2.0, "C": 3.0},
        {"A": 4.0, "B": 5.0, "C": 6.0},
    )
    projected = project_observation(obs, frozenset({"B"}))
    assert projected == (
        {"A": 1.0, "C": 3.0},
        {"A": 4.0, "C": 6.0},
    )


def test_project_observation_empty_hidden_is_identity():
    obs: Observation = ({"A": 1.0, "B": 2.0},)
    assert project_observation(obs, frozenset()) == obs


def test_project_observation_hides_everything():
    obs: Observation = ({"A": 1.0, "B": 2.0},)
    assert project_observation(obs, frozenset({"A", "B"})) == ({},)


# ═══════════════════════════════════════════════════════════════════════════
# add_measurement_noise — identity at 0, deterministic, statistically unbiased
# ═══════════════════════════════════════════════════════════════════════════


def test_add_measurement_noise_zero_sigma_is_identity():
    obs: Observation = ({"A": 1.0, "B": 2.0}, {"A": 3.0})
    noised = add_measurement_noise(obs, 0.0, Seed(7))
    assert noised == obs


def test_add_measurement_noise_deterministic_same_seed():
    obs: Observation = ({"A": 1.0, "B": 2.0}, {"A": 3.0})
    n1 = add_measurement_noise(obs, 0.2, Seed(99))
    n2 = add_measurement_noise(obs, 0.2, Seed(99))
    assert n1 == n2


def test_add_measurement_noise_differs_across_seeds():
    obs: Observation = ({"A": 1.0, "B": 2.0},)
    n1 = add_measurement_noise(obs, 0.2, Seed(1))
    n2 = add_measurement_noise(obs, 0.2, Seed(2))
    assert n1 != n2


def test_add_measurement_noise_clamped_nonnegative():
    """Seed(4)'s first ``normal(0, 50.0)`` draw is ~-32.6, so ``1 + draw`` is
    negative and the clamp must engage: an unclamped implementation would
    produce a negative value here, so this pins the clamp to exactly 0.0."""
    obs: Observation = ({"A": 1.0},)
    noised = add_measurement_noise(obs, 50.0, Seed(4))
    assert noised[0]["A"] == 0.0


def test_add_measurement_noise_rejects_negative_sigma():
    with pytest.raises(ValueError):
        add_measurement_noise(({"A": 1.0},), -0.1, Seed(0))


def test_add_measurement_noise_mean_converges_to_original():
    """Statistical ground truth: over many seeds the noised mean -> original value."""
    original = 10.0
    obs: Observation = ({"A": original},)
    samples = [
        add_measurement_noise(obs, 0.3, Seed(i))[0]["A"] for i in range(2000)
    ]
    mean = float(np.mean(samples))
    assert mean == pytest.approx(original, rel=0.05)
