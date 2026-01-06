"""Comprehensive tests for the simulator.

This module provides thorough test coverage for:
1. ReferenceSimulatorImpl - the Chemistry/State-based simulator
2. _run_scenario() - the dict-based DAT execution path
3. Integration tests via Bio.run()

Test categories:
- Basic simulation mechanics (step, run, timeline)
- Rate functions (constant, callable, state-dependent)
- Reaction types (simple, stoichiometric, reversible, catalytic)
- Edge cases (empty, zero concentrations, large steps)
- Scoring and verification
- DAT integration
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from alienbio.bio.molecule import MoleculeImpl
from alienbio.bio.reaction import ReactionImpl
from alienbio.bio.chemistry import ChemistryImpl
from alienbio.bio.state import StateImpl
from alienbio.bio.simulator import ReferenceSimulatorImpl, SimulatorBase


class MockDat:
    """Mock DAT for testing."""

    def __init__(self, path: str):
        self.path = path


# =============================================================================
# Part 1: ReferenceSimulatorImpl Tests
# =============================================================================


class TestSimulatorRateFunctions:
    """Tests for rate function handling."""

    def test_constant_rate(self):
        """Constant rate values work."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))
        r1 = ReactionImpl("r1", reactants={a: 1}, products={b: 1}, rate=0.5, dat=MockDat("rxn/r1"))

        chem = ChemistryImpl(
            "test", molecules={"A": a, "B": b}, reactions={"r1": r1}, dat=MockDat("chem/test")
        )
        state = StateImpl(chem, initial={"A": 10.0, "B": 0.0})
        sim = ReferenceSimulatorImpl(chem, dt=1.0)

        new_state = sim.step(state)
        assert new_state["A"] == pytest.approx(9.5)
        assert new_state["B"] == pytest.approx(0.5)

    def test_callable_rate_function(self):
        """Callable rate functions are invoked with state."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))

        # Rate depends on A concentration: rate = 0.1 * [A]
        def mass_action_rate(state):
            return 0.1 * state["A"]  # Use string key access

        r1 = ReactionImpl(
            "r1", reactants={a: 1}, products={b: 1}, rate=mass_action_rate, dat=MockDat("rxn/r1")
        )

        chem = ChemistryImpl(
            "test", molecules={"A": a, "B": b}, reactions={"r1": r1}, dat=MockDat("chem/test")
        )
        state = StateImpl(chem, initial={"A": 10.0, "B": 0.0})
        sim = ReferenceSimulatorImpl(chem, dt=1.0)

        new_state = sim.step(state)
        # Rate = 0.1 * 10 = 1.0, so A decreases by 1, B increases by 1
        assert new_state["A"] == pytest.approx(9.0)
        assert new_state["B"] == pytest.approx(1.0)

    def test_rate_function_called_with_current_state(self):
        """Rate function sees state at start of step, not mid-step."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))

        captured_states = []

        def capturing_rate(state):
            captured_states.append({"A": state["A"], "B": state["B"]})
            return 0.1

        r1 = ReactionImpl(
            "r1", reactants={a: 1}, products={b: 1}, rate=capturing_rate, dat=MockDat("rxn/r1")
        )

        chem = ChemistryImpl(
            "test", molecules={"A": a, "B": b}, reactions={"r1": r1}, dat=MockDat("chem/test")
        )
        state = StateImpl(chem, initial={"A": 10.0, "B": 0.0})
        sim = ReferenceSimulatorImpl(chem, dt=1.0)

        sim.step(state)

        # Rate function should have been called
        assert len(captured_states) == 1
        # Should see original state
        assert captured_states[0]["A"] == 10.0


class TestSimulatorMultipleReactions:
    """Tests for multiple simultaneous reactions."""

    def test_two_independent_reactions(self):
        """Two independent reactions both apply."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))
        c = MoleculeImpl("C", dat=MockDat("mol/C"))
        d = MoleculeImpl("D", dat=MockDat("mol/D"))

        r1 = ReactionImpl("r1", reactants={a: 1}, products={b: 1}, rate=0.1, dat=MockDat("rxn/r1"))
        r2 = ReactionImpl("r2", reactants={c: 1}, products={d: 1}, rate=0.2, dat=MockDat("rxn/r2"))

        chem = ChemistryImpl(
            "test",
            molecules={"A": a, "B": b, "C": c, "D": d},
            reactions={"r1": r1, "r2": r2},
            dat=MockDat("chem/test"),
        )
        state = StateImpl(chem, initial={"A": 10.0, "B": 0.0, "C": 10.0, "D": 0.0})
        sim = ReferenceSimulatorImpl(chem, dt=1.0)

        new_state = sim.step(state)

        assert new_state["A"] == pytest.approx(9.9)
        assert new_state["B"] == pytest.approx(0.1)
        assert new_state["C"] == pytest.approx(9.8)
        assert new_state["D"] == pytest.approx(0.2)

    def test_chain_reactions(self):
        """A -> B -> C chain works."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))
        c = MoleculeImpl("C", dat=MockDat("mol/C"))

        r1 = ReactionImpl("r1", reactants={a: 1}, products={b: 1}, rate=0.1, dat=MockDat("rxn/r1"))
        r2 = ReactionImpl("r2", reactants={b: 1}, products={c: 1}, rate=0.1, dat=MockDat("rxn/r2"))

        chem = ChemistryImpl(
            "test",
            molecules={"A": a, "B": b, "C": c},
            reactions={"r1": r1, "r2": r2},
            dat=MockDat("chem/test"),
        )
        state = StateImpl(chem, initial={"A": 10.0, "B": 5.0, "C": 0.0})
        sim = ReferenceSimulatorImpl(chem, dt=1.0)

        # Run multiple steps
        timeline = sim.run(state, steps=50)

        # A should decrease, C should increase
        assert timeline[-1]["A"] < timeline[0]["A"]
        assert timeline[-1]["C"] > timeline[0]["C"]


class TestSimulatorReversibleReactions:
    """Tests for reversible reactions (A <-> B)."""

    def test_reversible_reaches_equilibrium(self):
        """Forward and reverse reactions reach equilibrium with mass-action kinetics."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))

        # A -> B with rate proportional to [A]
        def forward_rate(state):
            return 0.1 * state["A"]

        # B -> A with rate proportional to [B]
        def reverse_rate(state):
            return 0.1 * state["B"]

        r_forward = ReactionImpl(
            "forward", reactants={a: 1}, products={b: 1}, rate=forward_rate, dat=MockDat("rxn/forward")
        )
        r_reverse = ReactionImpl(
            "reverse", reactants={b: 1}, products={a: 1}, rate=reverse_rate, dat=MockDat("rxn/reverse")
        )

        chem = ChemistryImpl(
            "test",
            molecules={"A": a, "B": b},
            reactions={"forward": r_forward, "reverse": r_reverse},
            dat=MockDat("chem/test"),
        )
        state = StateImpl(chem, initial={"A": 10.0, "B": 0.0})
        sim = ReferenceSimulatorImpl(chem, dt=0.1)  # Smaller dt for stability

        timeline = sim.run(state, steps=500)

        # Should reach roughly equal equilibrium (50/50 with equal rates)
        final = timeline[-1]
        total = final["A"] + final["B"]
        assert total == pytest.approx(10.0, rel=0.01)  # Conservation
        assert final["A"] == pytest.approx(final["B"], rel=0.2)  # Near equilibrium


class TestSimulatorCatalysts:
    """Tests for catalytic reactions (catalyst required but not consumed)."""

    def test_catalyst_required_not_consumed(self):
        """Catalyst enables reaction but isn't consumed."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))
        enzyme = MoleculeImpl("E", dat=MockDat("mol/E"))

        # Rate depends on enzyme: no enzyme = no reaction
        def catalyzed_rate(state):
            e_conc = state["E"]
            a_conc = state["A"]
            return 0.1 * e_conc * a_conc

        # Enzyme is NOT in reactants (not consumed)
        r1 = ReactionImpl(
            "r1", reactants={a: 1}, products={b: 1}, rate=catalyzed_rate, dat=MockDat("rxn/r1")
        )

        chem = ChemistryImpl(
            "test",
            molecules={"A": a, "B": b, "E": enzyme},
            reactions={"r1": r1},
            dat=MockDat("chem/test"),
        )

        # With enzyme
        state_with = StateImpl(chem, initial={"A": 10.0, "B": 0.0, "E": 1.0})
        sim = ReferenceSimulatorImpl(chem, dt=1.0)
        new_with = sim.step(state_with)

        # Reaction should proceed
        assert new_with["A"] < 10.0
        assert new_with["B"] > 0.0
        assert new_with["E"] == 1.0  # Enzyme unchanged

        # Without enzyme
        state_without = StateImpl(chem, initial={"A": 10.0, "B": 0.0, "E": 0.0})
        new_without = sim.step(state_without)

        # No reaction without enzyme
        assert new_without["A"] == 10.0
        assert new_without["B"] == 0.0


class TestSimulatorEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_chemistry(self):
        """Empty chemistry (no reactions) maintains state."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))

        chem = ChemistryImpl(
            "test", molecules={"A": a}, reactions={}, dat=MockDat("chem/test")
        )
        state = StateImpl(chem, initial={"A": 10.0})
        sim = ReferenceSimulatorImpl(chem, dt=1.0)

        timeline = sim.run(state, steps=10)

        assert all(s["A"] == 10.0 for s in timeline)

    def test_zero_initial_concentrations(self):
        """Zero concentrations don't cause errors."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))

        r1 = ReactionImpl("r1", reactants={a: 1}, products={b: 1}, rate=0.1, dat=MockDat("rxn/r1"))

        chem = ChemistryImpl(
            "test", molecules={"A": a, "B": b}, reactions={"r1": r1}, dat=MockDat("chem/test")
        )
        state = StateImpl(chem, initial={"A": 0.0, "B": 0.0})
        sim = ReferenceSimulatorImpl(chem, dt=1.0)

        new_state = sim.step(state)

        assert new_state["A"] == 0.0
        assert new_state["B"] == pytest.approx(0.1)  # Still produces

    def test_very_small_dt(self):
        """Very small dt produces proportionally small changes."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))

        r1 = ReactionImpl("r1", reactants={a: 1}, products={b: 1}, rate=1.0, dat=MockDat("rxn/r1"))

        chem = ChemistryImpl(
            "test", molecules={"A": a, "B": b}, reactions={"r1": r1}, dat=MockDat("chem/test")
        )
        state = StateImpl(chem, initial={"A": 10.0, "B": 0.0})
        sim = ReferenceSimulatorImpl(chem, dt=0.001)

        new_state = sim.step(state)

        assert new_state["A"] == pytest.approx(9.999)
        assert new_state["B"] == pytest.approx(0.001)


class TestSimulatorTimeline:
    """Tests for timeline/history tracking."""

    def test_timeline_length(self):
        """Timeline has correct length (initial + steps)."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        r1 = ReactionImpl("r1", reactants={a: 1}, products={}, rate=0.1, dat=MockDat("rxn/r1"))

        chem = ChemistryImpl(
            "test", molecules={"A": a}, reactions={"r1": r1}, dat=MockDat("chem/test")
        )
        state = StateImpl(chem, initial={"A": 10.0})
        sim = ReferenceSimulatorImpl(chem, dt=1.0)

        timeline = sim.run(state, steps=100)
        assert len(timeline) == 101

    def test_timeline_states_independent(self):
        """Each timeline state is independent (not aliased)."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        r1 = ReactionImpl("r1", reactants={a: 1}, products={}, rate=0.1, dat=MockDat("rxn/r1"))

        chem = ChemistryImpl(
            "test", molecules={"A": a}, reactions={"r1": r1}, dat=MockDat("chem/test")
        )
        state = StateImpl(chem, initial={"A": 10.0})
        sim = ReferenceSimulatorImpl(chem, dt=1.0)

        timeline = sim.run(state, steps=10)

        # Modify first state
        timeline[0]["A"] = 999.0

        # Should not affect other states
        assert timeline[1]["A"] != 999.0

    def test_timeline_monotonic_depletion(self):
        """Reactant depletes monotonically with simple irreversible reaction."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))
        r1 = ReactionImpl("r1", reactants={a: 1}, products={b: 1}, rate=0.1, dat=MockDat("rxn/r1"))

        chem = ChemistryImpl(
            "test", molecules={"A": a, "B": b}, reactions={"r1": r1}, dat=MockDat("chem/test")
        )
        state = StateImpl(chem, initial={"A": 10.0, "B": 0.0})
        sim = ReferenceSimulatorImpl(chem, dt=1.0)

        timeline = sim.run(state, steps=50)

        # A should monotonically decrease
        a_values = [s["A"] for s in timeline]
        for i in range(1, len(a_values)):
            assert a_values[i] <= a_values[i - 1]


# =============================================================================
# Part 2: run.py _run_scenario() Tests
# =============================================================================


class TestRunScenarioDict:
    """Tests for the dict-based _run_scenario() function."""

    def test_simple_scenario_dict(self):
        """Basic scenario dict runs correctly."""
        from alienbio.run import _run_scenario

        scenario = {
            "chemistry": {
                "molecules": {"A": {}, "B": {}},
                "reactions": {
                    "r1": {
                        "reactants": ["A"],
                        "products": ["B"],
                        "rate": lambda state: 0.1 * state.get("A", 0),
                    }
                },
            },
            "initial_state": {"A": 10.0, "B": 0.0},
            "sim": {"steps": 10},
            "verify": [],
            "scoring": {},
        }

        mock_dat = MagicMock()
        mock_dat.path = "/tmp/test_scenario"
        Path(mock_dat.path).mkdir(parents=True, exist_ok=True)

        result = _run_scenario(scenario, mock_dat)

        assert result["final_state"]["A"] < 10.0
        assert result["final_state"]["B"] > 0.0

    def test_scenario_verification_passes(self):
        """Verification assertions that pass."""
        from alienbio.run import _run_scenario

        scenario = {
            "chemistry": {
                "molecules": {"A": {}, "B": {}},
                "reactions": {
                    "r1": {
                        "reactants": ["A"],
                        "products": ["B"],
                        "rate": lambda state: 0.5,
                    }
                },
            },
            "initial_state": {"A": 10.0, "B": 0.0},
            "sim": {"steps": 10},
            "verify": [
                {"assert": "state['A'] < 10.0", "message": "A should decrease"},
                {"assert": "state['B'] > 0.0", "message": "B should increase"},
            ],
            "scoring": {},
        }

        mock_dat = MagicMock()
        mock_dat.path = "/tmp/test_scenario_verify"
        Path(mock_dat.path).mkdir(parents=True, exist_ok=True)

        result = _run_scenario(scenario, mock_dat)

        assert result["success"] is True
        assert all(v["passed"] for v in result["verify_results"])

    def test_scenario_scoring(self):
        """Scoring functions are called with trace."""
        from alienbio.run import _run_scenario, SimulationTrace

        def my_score(trace: SimulationTrace):
            return 1.0 - trace.final.get("A", 0) / 10.0

        scenario = {
            "chemistry": {
                "molecules": {"A": {}, "B": {}},
                "reactions": {
                    "r1": {
                        "reactants": ["A"],
                        "products": ["B"],
                        "rate": lambda state: 0.5,
                    }
                },
            },
            "initial_state": {"A": 10.0, "B": 0.0},
            "sim": {"steps": 10},
            "verify": [],
            "scoring": {"depletion": my_score},
        }

        mock_dat = MagicMock()
        mock_dat.path = "/tmp/test_scenario_score"
        Path(mock_dat.path).mkdir(parents=True, exist_ok=True)

        result = _run_scenario(scenario, mock_dat)

        assert "depletion" in result["scores"]
        assert result["scores"]["depletion"] > 0.0


# =============================================================================
# Part 3: Integration Tests via Bio.run()
# =============================================================================


class TestBioRunIntegration:
    """Integration tests using Bio.run() with actual DAT execution."""

    @pytest.mark.skip(reason="Requires DAT setup - run manually")
    def test_hardcoded_test_job(self):
        """The hardcoded_test job runs and passes."""
        from alienbio.spec_lang import Bio

        # This would run the actual hardcoded_test job
        result = Bio.run("jobs/hardcoded_test")

        assert result["success"] is True
        assert result["scores"]["score"] >= 0.5


# =============================================================================
# Part 4: Conservation Laws
# =============================================================================


class TestConservationLaws:
    """Tests for mass/atom conservation."""

    def test_mass_conservation_simple(self):
        """Total mass conserved in simple A -> B reaction."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))

        r1 = ReactionImpl("r1", reactants={a: 1}, products={b: 1}, rate=0.1, dat=MockDat("rxn/r1"))

        chem = ChemistryImpl(
            "test", molecules={"A": a, "B": b}, reactions={"r1": r1}, dat=MockDat("chem/test")
        )
        state = StateImpl(chem, initial={"A": 10.0, "B": 0.0})
        sim = ReferenceSimulatorImpl(chem, dt=1.0)

        timeline = sim.run(state, steps=100)

        # Total should be conserved
        initial_total = timeline[0]["A"] + timeline[0]["B"]
        final_total = timeline[-1]["A"] + timeline[-1]["B"]

        assert final_total == pytest.approx(initial_total, rel=0.01)

    def test_mass_conservation_complex(self):
        """Mass conservation in 2A -> B reaction."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))

        # 2A -> B (2 moles A become 1 mole B)
        r1 = ReactionImpl("r1", reactants={a: 2}, products={b: 1}, rate=0.1, dat=MockDat("rxn/r1"))

        chem = ChemistryImpl(
            "test", molecules={"A": a, "B": b}, reactions={"r1": r1}, dat=MockDat("chem/test")
        )
        state = StateImpl(chem, initial={"A": 10.0, "B": 0.0})
        sim = ReferenceSimulatorImpl(chem, dt=1.0)

        timeline = sim.run(state, steps=50)

        # For 2A -> B: A + 2*B should be conserved
        # (2 moles A consumed produces 1 mole B, so dA = -2*dB)
        # Initial: 10 + 2*0 = 10
        # Final: A + 2*B should still = 10
        final = timeline[-1]
        conserved = final["A"] + 2 * final["B"]

        assert conserved == pytest.approx(10.0, rel=0.01)
