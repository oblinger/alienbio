"""Tests for M9.3 organism features: maintained molecules, envelope, reproduction, predation."""

from __future__ import annotations

import pytest

from alienbio.bio import CompartmentTreeImpl, WorldStateImpl
from alienbio.bio.organism_features import (
    MaintainedMolecule,
    EnvelopeBound,
    OperatingEnvelope,
    EnvelopeViolation,
    EnvelopeStatus,
    ReproductionThreshold,
    PredationRule,
    apply_maintained_molecules,
    apply_predation,
)


def _make_state(num_compartments: int = 3, num_molecules: int = 3) -> WorldStateImpl:
    """Create a tree+state for testing."""
    tree = CompartmentTreeImpl()
    root = tree.add_root("body")
    for i in range(num_compartments - 1):
        tree.add_child(root, f"organ_{i}")
    return WorldStateImpl(tree=tree, num_molecules=num_molecules)


# === Maintained Molecules ===

class TestMaintainedMolecules:

    def test_clamps_to_target(self):
        state = _make_state()
        state.set(1, 0, 50.0)  # organ_0, mol 0

        maintained = [MaintainedMolecule(molecule_id=0, compartment_id=1, target_concentration=10.0)]
        apply_maintained_molecules(maintained, state)

        assert state.get(1, 0) == 10.0

    def test_multiple_maintained(self):
        state = _make_state()
        state.set(1, 0, 0.0)
        state.set(2, 1, 100.0)

        maintained = [
            MaintainedMolecule(0, 1, 5.0),
            MaintainedMolecule(1, 2, 20.0),
        ]
        apply_maintained_molecules(maintained, state)

        assert state.get(1, 0) == 5.0
        assert state.get(2, 1) == 20.0

    def test_no_maintained_is_noop(self):
        state = _make_state()
        state.set(1, 0, 42.0)
        apply_maintained_molecules([], state)
        assert state.get(1, 0) == 42.0

    def test_already_at_target(self):
        state = _make_state()
        state.set(1, 0, 10.0)
        maintained = [MaintainedMolecule(0, 1, 10.0)]
        apply_maintained_molecules(maintained, state)
        assert state.get(1, 0) == 10.0


# === Operating Envelope ===

class TestEnvelopeBound:

    def test_contains(self):
        bound = EnvelopeBound(molecule_id=0, compartment_id=1, low=1.0, high=10.0)
        assert bound.contains(5.0)
        assert bound.contains(1.0)
        assert bound.contains(10.0)
        assert not bound.contains(0.5)
        assert not bound.contains(10.5)


class TestOperatingEnvelope:

    def test_viable_within_bounds(self):
        state = _make_state()
        state.set(1, 0, 5.0)

        envelope = OperatingEnvelope()
        envelope.add(molecule_id=0, compartment_id=1, low=1.0, high=10.0)

        status = envelope.check(state)
        assert status.viable
        assert len(status.violations) == 0

    def test_violation_above(self):
        state = _make_state()
        state.set(1, 0, 15.0)

        envelope = OperatingEnvelope()
        envelope.add(0, 1, 1.0, 10.0)

        status = envelope.check(state)
        assert not status.viable
        assert len(status.violations) == 1
        assert status.violations[0].actual == 15.0
        assert status.violations[0].deviation == pytest.approx(5.0)

    def test_violation_below(self):
        state = _make_state()
        state.set(1, 0, 0.0)

        envelope = OperatingEnvelope()
        envelope.add(0, 1, 1.0, 10.0)

        status = envelope.check(state)
        assert not status.viable
        assert status.violations[0].deviation == pytest.approx(1.0)

    def test_multiple_bounds_all_ok(self):
        state = _make_state()
        state.set(1, 0, 5.0)
        state.set(2, 1, 3.0)

        envelope = OperatingEnvelope()
        envelope.add(0, 1, 1.0, 10.0)
        envelope.add(1, 2, 1.0, 10.0)

        assert envelope.check(state).viable

    def test_multiple_bounds_partial_violation(self):
        state = _make_state()
        state.set(1, 0, 5.0)   # ok
        state.set(2, 1, 50.0)  # violation

        envelope = OperatingEnvelope()
        envelope.add(0, 1, 1.0, 10.0)
        envelope.add(1, 2, 1.0, 10.0)

        status = envelope.check(state)
        assert not status.viable
        assert len(status.violations) == 1

    def test_empty_envelope_is_viable(self):
        state = _make_state()
        envelope = OperatingEnvelope()
        assert envelope.check(state).viable


# === Reproduction Threshold ===

class TestReproductionThreshold:

    def test_can_reproduce_all_met(self):
        state = _make_state()
        state.set(1, 0, 10.0)
        state.set(1, 1, 20.0)

        thresh = ReproductionThreshold()
        thresh.add(0, 5.0)
        thresh.add(1, 15.0)

        assert thresh.can_reproduce(state, compartment_id=1)

    def test_cannot_reproduce_below(self):
        state = _make_state()
        state.set(1, 0, 3.0)  # below threshold of 5.0
        state.set(1, 1, 20.0)

        thresh = ReproductionThreshold()
        thresh.add(0, 5.0)
        thresh.add(1, 15.0)

        assert not thresh.can_reproduce(state, 1)

    def test_shortfall(self):
        state = _make_state()
        state.set(1, 0, 3.0)
        state.set(1, 1, 20.0)

        thresh = ReproductionThreshold()
        thresh.add(0, 5.0)
        thresh.add(1, 15.0)

        shortfall = thresh.shortfall(state, 1)
        assert shortfall == {0: pytest.approx(2.0)}

    def test_no_shortfall_when_met(self):
        state = _make_state()
        state.set(1, 0, 10.0)
        state.set(1, 1, 20.0)

        thresh = ReproductionThreshold()
        thresh.add(0, 5.0)
        thresh.add(1, 15.0)

        assert thresh.shortfall(state, 1) == {}

    def test_empty_threshold_always_reproduces(self):
        state = _make_state()
        thresh = ReproductionThreshold()
        assert thresh.can_reproduce(state, 1)

    def test_exact_threshold(self):
        state = _make_state()
        state.set(1, 0, 5.0)  # exactly at threshold

        thresh = ReproductionThreshold()
        thresh.add(0, 5.0)

        assert thresh.can_reproduce(state, 1)


# === Predation ===

class TestPredation:

    def test_predation_consumes_prey(self):
        state = _make_state()
        # mol 0 = predator, mol 1 = prey, mol 2 = energy
        state.set(1, 0, 10.0)  # predator
        state.set(1, 1, 20.0)  # prey
        state.set(1, 2, 0.0)   # energy

        rule = PredationRule(
            predator_molecule_id=0,
            prey_molecule_id=1,
            energy_molecule_id=2,
            predation_rate=0.01,
            conversion_efficiency=0.5,
        )
        apply_predation([rule], state, compartment_id=1, dt=1.0)

        # prey should decrease
        assert state.get(1, 1) < 20.0
        # energy should increase
        assert state.get(1, 2) > 0.0

    def test_predation_energy_conversion(self):
        state = _make_state()
        state.set(1, 0, 10.0)
        state.set(1, 1, 20.0)
        state.set(1, 2, 0.0)

        rule = PredationRule(0, 1, 2, predation_rate=0.01, conversion_efficiency=0.8)
        apply_predation([rule], state, 1, dt=1.0)

        consumed = 20.0 - state.get(1, 1)
        energy_gained = state.get(1, 2)
        assert energy_gained == pytest.approx(consumed * 0.8)

    def test_predation_no_prey(self):
        state = _make_state()
        state.set(1, 0, 10.0)
        state.set(1, 1, 0.0)  # no prey
        state.set(1, 2, 5.0)

        rule = PredationRule(0, 1, 2, predation_rate=0.1)
        apply_predation([rule], state, 1, dt=1.0)

        # Nothing should change
        assert state.get(1, 1) == 0.0
        assert state.get(1, 2) == 5.0

    def test_predation_no_predator(self):
        state = _make_state()
        state.set(1, 0, 0.0)   # no predator
        state.set(1, 1, 20.0)
        state.set(1, 2, 0.0)

        rule = PredationRule(0, 1, 2, predation_rate=0.1)
        apply_predation([rule], state, 1, dt=1.0)

        assert state.get(1, 1) == 20.0
        assert state.get(1, 2) == 0.0

    def test_predation_cant_consume_more_than_exists(self):
        state = _make_state()
        state.set(1, 0, 1000.0)  # huge predator population
        state.set(1, 1, 0.1)     # tiny prey population
        state.set(1, 2, 0.0)

        rule = PredationRule(0, 1, 2, predation_rate=1.0, conversion_efficiency=1.0)
        apply_predation([rule], state, 1, dt=1.0)

        # Prey should be zero, not negative
        assert state.get(1, 1) >= 0.0
        # Energy gained should be at most original prey amount
        assert state.get(1, 2) <= 0.1 + 1e-10

    def test_multiple_predation_rules(self):
        state = _make_state()
        state.set(1, 0, 10.0)  # species A (predator of B)
        state.set(1, 1, 20.0)  # species B (prey of A, predator of C... but simplified)
        state.set(1, 2, 5.0)   # energy

        rules = [
            PredationRule(0, 1, 2, predation_rate=0.01, conversion_efficiency=0.5),
            PredationRule(0, 1, 2, predation_rate=0.005, conversion_efficiency=0.3),
        ]
        apply_predation(rules, state, 1, dt=1.0)

        assert state.get(1, 1) < 20.0

    def test_predation_rule_dataclass(self):
        rule = PredationRule(0, 1, 2, predation_rate=0.05, conversion_efficiency=0.7)
        assert rule.predator_molecule_id == 0
        assert rule.prey_molecule_id == 1
        assert rule.energy_molecule_id == 2
        assert rule.predation_rate == 0.05
        assert rule.conversion_efficiency == 0.7

    def test_predation_dt_scaling(self):
        """Predation should scale with dt."""
        state1 = _make_state()
        state1.set(1, 0, 10.0)
        state1.set(1, 1, 20.0)
        state1.set(1, 2, 0.0)

        state2 = _make_state()
        state2.set(1, 0, 10.0)
        state2.set(1, 1, 20.0)
        state2.set(1, 2, 0.0)

        rule = PredationRule(0, 1, 2, predation_rate=0.001, conversion_efficiency=0.5)

        apply_predation([rule], state1, 1, dt=1.0)
        apply_predation([rule], state2, 1, dt=2.0)

        consumed1 = 20.0 - state1.get(1, 1)
        consumed2 = 20.0 - state2.get(1, 1)
        assert consumed2 == pytest.approx(consumed1 * 2.0)
