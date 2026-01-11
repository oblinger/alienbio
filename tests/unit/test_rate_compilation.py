"""Tests for rate expression compilation (M1.8b).

Tests for simulator creation from scenarios with rate expressions.
Rate expressions use !quote to preserve them through evaluation,
then get compiled to callable functions at bio.sim() time.

See [[Simulator]] and [[Spec Evaluation]] for specifications.

Key concepts tested:
- Rate expressions: !quote k * S → compiled to callable
- Constants baked in: Vmax, Km from spec scope
- Substrate variables: S, S1, S2 bound to concentrations
- bio.sim(scenario) integration
- Reproducibility with seeded RNG
"""

import pytest
import numpy as np
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

# These imports will fail until implementation exists.
# Tests are written first as executable specification.

# from alienbio.spec_lang import Bio
# from alienbio.spec_lang.eval import Quoted, Context, hydrate, eval_node


# =============================================================================
# Stub Placeholders (until implementation exists)
# =============================================================================

@dataclass
class Quoted:
    """Placeholder for !quote expressions."""
    source: str


@dataclass
class Scenario:
    """Stub scenario for testing."""
    name: str
    molecules: Dict[str, Any]
    reactions: Dict[str, Any]
    initial_state: Dict[str, float]
    scope: Dict[str, Any]  # Constants


class CompiledSimulator:
    """Stub compiled simulator."""

    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self._state: Dict[str, float] = {}
        self._history: List[Dict[str, float]] = []

    def initial_state(self) -> Dict[str, float]:
        raise NotImplementedError("Simulator not yet implemented")

    def step(self, state: Dict[str, float]) -> Dict[str, float]:
        raise NotImplementedError("Simulator not yet implemented")

    def run(self, state: Dict[str, float], steps: int) -> List[Dict[str, float]]:
        raise NotImplementedError("Simulator not yet implemented")

    def action(self, name: str, *args) -> None:
        raise NotImplementedError("action not yet implemented")

    def measure(self, name: str, *args) -> float:
        raise NotImplementedError("measure not yet implemented")


class Bio:
    """Stub Bio class."""

    @staticmethod
    def load(path: str, scenario_name: str = None) -> Any:
        raise NotImplementedError("Bio.load not yet implemented")

    @staticmethod
    def sim(scenario: Any) -> CompiledSimulator:
        raise NotImplementedError("bio.sim not yet implemented")

    @staticmethod
    def eval(spec: Any, ctx: Any) -> Any:
        raise NotImplementedError("Bio.eval not yet implemented")


def compile_rate_expression(source: str, constants: Dict[str, float]) -> Callable:
    """Stub rate expression compiler."""
    raise NotImplementedError("compile_rate_expression not yet implemented")


# =============================================================================
# RATE COMPILATION TESTS
# =============================================================================

class TestRateSimpleConstant:
    """Test constant rate expressions."""

    @pytest.mark.skip(reason="Implementation pending")
    def test_rate_simple_constant(self):
        """rate: !quote 0.5 compiles to constant rate function."""
        source = "0.5"
        rate_fn = compile_rate_expression(source, constants={})

        # Should return constant regardless of state
        state = {"S": 10.0}
        assert rate_fn(state) == 0.5

        state2 = {"S": 100.0}
        assert rate_fn(state2) == 0.5

    @pytest.mark.skip(reason="Implementation pending")
    def test_rate_constant_from_scope(self):
        """rate: !quote k compiles with k from constants."""
        source = "k"
        rate_fn = compile_rate_expression(source, constants={"k": 0.3})

        state = {"S": 10.0}
        assert rate_fn(state) == 0.3

    @pytest.mark.skip(reason="Implementation pending")
    def test_rate_constant_arithmetic(self):
        """rate: !quote k1 + k2 combines constants."""
        source = "k1 + k2"
        rate_fn = compile_rate_expression(source, constants={"k1": 0.1, "k2": 0.2})

        state = {}
        assert rate_fn(state) == pytest.approx(0.3)


class TestRateMassAction:
    """Test mass-action kinetics rate expressions."""

    @pytest.mark.skip(reason="Implementation pending")
    def test_rate_mass_action_single_substrate(self):
        """rate: !quote k * S for single substrate."""
        source = "k * S"
        rate_fn = compile_rate_expression(source, constants={"k": 0.1})

        state = {"S": 10.0}
        assert rate_fn(state) == pytest.approx(1.0)  # 0.1 * 10

        state2 = {"S": 50.0}
        assert rate_fn(state2) == pytest.approx(5.0)  # 0.1 * 50

    @pytest.mark.skip(reason="Implementation pending")
    def test_rate_mass_action_two_substrates(self):
        """rate: !quote k * S1 * S2 for two substrates."""
        source = "k * S1 * S2"
        rate_fn = compile_rate_expression(source, constants={"k": 0.01})

        state = {"S1": 10.0, "S2": 20.0}
        assert rate_fn(state) == pytest.approx(2.0)  # 0.01 * 10 * 20

    @pytest.mark.skip(reason="Implementation pending")
    def test_rate_mass_action_three_substrates(self):
        """rate: !quote k * S1 * S2 * S3 for three substrates."""
        source = "k * S1 * S2 * S3"
        rate_fn = compile_rate_expression(source, constants={"k": 0.001})

        state = {"S1": 10.0, "S2": 10.0, "S3": 10.0}
        assert rate_fn(state) == pytest.approx(1.0)  # 0.001 * 1000


class TestRateMichaelisMenten:
    """Test Michaelis-Menten kinetics."""

    @pytest.mark.skip(reason="Implementation pending")
    def test_rate_michaelis_menten_basic(self):
        """rate: !quote Vmax * S / (Km + S) standard MM kinetics."""
        source = "Vmax * S / (Km + S)"
        rate_fn = compile_rate_expression(source, constants={"Vmax": 10.0, "Km": 5.0})

        # At Km, rate should be Vmax/2
        state = {"S": 5.0}
        assert rate_fn(state) == pytest.approx(5.0)  # 10 * 5 / (5 + 5) = 5

        # At very high S, rate approaches Vmax
        state_high = {"S": 1000.0}
        assert rate_fn(state_high) == pytest.approx(10.0, rel=0.01)

    @pytest.mark.skip(reason="Implementation pending")
    def test_rate_michaelis_menten_low_substrate(self):
        """MM rate at low substrate is approximately linear."""
        source = "Vmax * S / (Km + S)"
        rate_fn = compile_rate_expression(source, constants={"Vmax": 10.0, "Km": 100.0})

        # At S << Km, rate ≈ (Vmax/Km) * S
        state = {"S": 1.0}
        expected = 10.0 * 1.0 / (100.0 + 1.0)  # ~0.099
        assert rate_fn(state) == pytest.approx(expected)

    @pytest.mark.skip(reason="Implementation pending")
    def test_rate_michaelis_menten_zero_substrate(self):
        """MM rate at zero substrate is zero."""
        source = "Vmax * S / (Km + S)"
        rate_fn = compile_rate_expression(source, constants={"Vmax": 10.0, "Km": 5.0})

        state = {"S": 0.0}
        assert rate_fn(state) == 0.0


class TestRateHillEquation:
    """Test Hill equation kinetics."""

    @pytest.mark.skip(reason="Implementation pending")
    def test_rate_hill_n1(self):
        """Hill equation with n=1 equals Michaelis-Menten."""
        source = "Vmax * S**n / (K**n + S**n)"
        rate_fn = compile_rate_expression(source, constants={"Vmax": 10.0, "K": 5.0, "n": 1})

        state = {"S": 5.0}
        # Should equal MM: 10 * 5 / (5 + 5) = 5
        assert rate_fn(state) == pytest.approx(5.0)

    @pytest.mark.skip(reason="Implementation pending")
    def test_rate_hill_n2_cooperative(self):
        """Hill equation with n=2 shows cooperativity."""
        source = "Vmax * S**n / (K**n + S**n)"
        rate_fn = compile_rate_expression(source, constants={"Vmax": 10.0, "K": 5.0, "n": 2})

        # At S = K, rate = Vmax/2 regardless of n
        state = {"S": 5.0}
        assert rate_fn(state) == pytest.approx(5.0)  # 10 * 25 / (25 + 25) = 5

        # But at S = K/2, n=2 gives lower rate than n=1
        state_half = {"S": 2.5}
        # 10 * 6.25 / (25 + 6.25) = 62.5 / 31.25 = 2.0
        assert rate_fn(state_half) == pytest.approx(2.0)

    @pytest.mark.skip(reason="Implementation pending")
    def test_rate_hill_n4_ultrasensitive(self):
        """Hill equation with n=4 shows ultrasensitivity."""
        source = "Vmax * S**n / (K**n + S**n)"
        rate_fn = compile_rate_expression(source, constants={"Vmax": 10.0, "K": 5.0, "n": 4})

        # Steeper transition around K
        state_low = {"S": 2.5}   # S = K/2
        state_high = {"S": 10.0}  # S = 2*K

        rate_low = rate_fn(state_low)
        rate_high = rate_fn(state_high)

        # With n=4, difference should be more pronounced
        assert rate_high / rate_low > 10  # High ultrasensitivity


class TestRateConstantsBakedIn:
    """Test that constants are baked into compiled rate functions."""

    @pytest.mark.skip(reason="Implementation pending")
    def test_constants_not_looked_up_at_runtime(self):
        """Constants are baked in at compile time, not looked up at runtime."""
        source = "k * S"
        constants = {"k": 0.5}
        rate_fn = compile_rate_expression(source, constants)

        # Modifying constants dict after compilation should have no effect
        constants["k"] = 999.0

        state = {"S": 10.0}
        assert rate_fn(state) == pytest.approx(5.0)  # Still uses original k=0.5

    @pytest.mark.skip(reason="Implementation pending")
    def test_multiple_constants_all_baked_in(self):
        """All referenced constants are baked in."""
        source = "Vmax * S / (Km + S) + baseline"
        constants = {"Vmax": 10.0, "Km": 5.0, "baseline": 0.1}
        rate_fn = compile_rate_expression(source, constants)

        state = {"S": 5.0}
        expected = 10.0 * 5.0 / (5.0 + 5.0) + 0.1  # 5.1
        assert rate_fn(state) == pytest.approx(expected)


class TestRateSubstrateVariables:
    """Test substrate variable binding conventions."""

    @pytest.mark.skip(reason="Implementation pending")
    def test_substrate_S_single(self):
        """S refers to first/only substrate concentration."""
        source = "0.1 * S"
        rate_fn = compile_rate_expression(source, constants={})

        state = {"S": 25.0}
        assert rate_fn(state) == pytest.approx(2.5)

    @pytest.mark.skip(reason="Implementation pending")
    def test_substrate_S1_S2_positional(self):
        """S1, S2 refer to substrates by position."""
        source = "k * S1 * S2"
        rate_fn = compile_rate_expression(source, constants={"k": 1.0})

        # Order matters: S1 is first substrate, S2 is second
        state = {"S1": 2.0, "S2": 3.0}
        assert rate_fn(state) == pytest.approx(6.0)

    @pytest.mark.skip(reason="Implementation pending")
    def test_substrate_variables_from_reaction(self):
        """Substrate variables bound based on reaction definition."""
        # This would test the full integration where the simulator
        # binds S1, S2 based on the reaction's substrates list
        pass  # Integration test with bio.sim


class TestRateProductVariables:
    """Test product variable binding (if needed for rate expressions)."""

    @pytest.mark.skip(reason="Implementation pending")
    def test_product_P_single(self):
        """P refers to first/only product concentration."""
        # Some rate expressions may depend on product (e.g., reversible)
        source = "kf * S - kr * P"
        rate_fn = compile_rate_expression(source, constants={"kf": 0.1, "kr": 0.05})

        state = {"S": 10.0, "P": 5.0}
        expected = 0.1 * 10.0 - 0.05 * 5.0  # 1.0 - 0.25 = 0.75
        assert rate_fn(state) == pytest.approx(0.75)

    @pytest.mark.skip(reason="Implementation pending")
    def test_product_P1_P2_positional(self):
        """P1, P2 refer to products by position."""
        source = "k * (S - P1 * P2 / Keq)"
        rate_fn = compile_rate_expression(source, constants={"k": 0.1, "Keq": 10.0})

        state = {"S": 10.0, "P1": 2.0, "P2": 3.0}
        # 0.1 * (10 - 6/10) = 0.1 * 9.4 = 0.94
        assert rate_fn(state) == pytest.approx(0.94)


# =============================================================================
# SIMULATOR CREATION TESTS
# =============================================================================

class TestSimCreatesFromScenario:
    """Test bio.sim(scenario) creates simulator correctly."""

    @pytest.mark.skip(reason="Implementation pending")
    def test_sim_creates_from_scenario(self):
        """bio.sim(scenario) returns a working simulator."""
        scenario = Scenario(
            name="test",
            molecules={"A": {}, "B": {}},
            reactions={
                "r1": {
                    "substrates": ["A"],
                    "products": ["B"],
                    "rate": Quoted(source="0.1 * S"),
                }
            },
            initial_state={"A": 10.0, "B": 0.0},
            scope={}
        )

        sim = bio.sim(scenario)

        assert sim is not None
        assert hasattr(sim, 'step')
        assert hasattr(sim, 'run')

    @pytest.mark.skip(reason="Implementation pending")
    def test_sim_compiles_rates(self):
        """Rate expressions become callable functions."""
        scenario = Scenario(
            name="test",
            molecules={"A": {}, "B": {}},
            reactions={
                "r1": {
                    "substrates": ["A"],
                    "products": ["B"],
                    "rate": Quoted(source="k * S"),
                }
            },
            initial_state={"A": 10.0, "B": 0.0},
            scope={"k": 0.1}
        )

        sim = bio.sim(scenario)
        state = sim.initial_state()

        # Step should work (rate was compiled)
        new_state = sim.step(state)
        assert new_state["A"] < 10.0
        assert new_state["B"] > 0.0

    @pytest.mark.skip(reason="Implementation pending")
    def test_sim_initial_state(self):
        """initial_state() returns configured initial concentrations."""
        scenario = Scenario(
            name="test",
            molecules={"A": {}, "B": {}, "C": {}},
            reactions={},
            initial_state={"A": 100.0, "B": 50.0, "C": 0.0},
            scope={}
        )

        sim = bio.sim(scenario)
        state = sim.initial_state()

        assert state["A"] == 100.0
        assert state["B"] == 50.0
        assert state["C"] == 0.0

    @pytest.mark.skip(reason="Implementation pending")
    def test_sim_step_advances(self):
        """step() advances state by one timestep."""
        scenario = Scenario(
            name="test",
            molecules={"A": {}, "B": {}},
            reactions={
                "r1": {
                    "substrates": ["A"],
                    "products": ["B"],
                    "rate": Quoted(source="0.5"),
                }
            },
            initial_state={"A": 10.0, "B": 0.0},
            scope={}
        )

        sim = bio.sim(scenario)
        state = sim.initial_state()

        state1 = sim.step(state)
        state2 = sim.step(state1)

        # State should change each step
        assert state1["A"] < state["A"]
        assert state2["A"] < state1["A"]

    @pytest.mark.skip(reason="Implementation pending")
    def test_sim_run_multiple(self):
        """run(steps=100) returns history list."""
        scenario = Scenario(
            name="test",
            molecules={"A": {}, "B": {}},
            reactions={
                "r1": {
                    "substrates": ["A"],
                    "products": ["B"],
                    "rate": Quoted(source="0.1"),
                }
            },
            initial_state={"A": 10.0, "B": 0.0},
            scope={}
        )

        sim = bio.sim(scenario)
        state = sim.initial_state()

        history = sim.run(state, steps=100)

        assert len(history) == 101  # initial + 100 steps
        assert history[0]["A"] == 10.0
        assert history[-1]["A"] < history[0]["A"]

    @pytest.mark.skip(reason="Implementation pending")
    def test_sim_action_available(self):
        """sim.action() is callable."""
        scenario = Scenario(
            name="test",
            molecules={"A": {}},
            reactions={},
            initial_state={"A": 10.0},
            scope={}
        )

        sim = bio.sim(scenario)

        # Should have action method
        assert hasattr(sim, 'action')
        assert callable(sim.action)

    @pytest.mark.skip(reason="Implementation pending")
    def test_sim_measure_available(self):
        """sim.measure() is callable."""
        scenario = Scenario(
            name="test",
            molecules={"A": {}},
            reactions={},
            initial_state={"A": 10.0},
            scope={}
        )

        sim = bio.sim(scenario)

        # Should have measure method
        assert hasattr(sim, 'measure')
        assert callable(sim.measure)


# =============================================================================
# SIMULATION CORRECTNESS TESTS
# =============================================================================

class TestSimulationCorrectness:
    """Test simulation produces correct results."""

    @pytest.mark.skip(reason="Implementation pending")
    def test_simulation_conservation(self):
        """Mass conserved in simple A -> B reaction."""
        scenario = Scenario(
            name="test",
            molecules={"A": {}, "B": {}},
            reactions={
                "r1": {
                    "substrates": ["A"],
                    "products": ["B"],
                    "rate": Quoted(source="0.1 * S"),
                }
            },
            initial_state={"A": 10.0, "B": 0.0},
            scope={}
        )

        sim = bio.sim(scenario)
        state = sim.initial_state()
        history = sim.run(state, steps=100)

        # Total should be conserved throughout
        for s in history:
            total = s["A"] + s["B"]
            assert total == pytest.approx(10.0, rel=0.01)

    @pytest.mark.skip(reason="Implementation pending")
    def test_simulation_equilibrium(self):
        """Reversible reaction reaches equilibrium."""
        scenario = Scenario(
            name="test",
            molecules={"A": {}, "B": {}},
            reactions={
                "forward": {
                    "substrates": ["A"],
                    "products": ["B"],
                    "rate": Quoted(source="kf * S"),
                },
                "reverse": {
                    "substrates": ["B"],
                    "products": ["A"],
                    "rate": Quoted(source="kr * S"),
                }
            },
            initial_state={"A": 10.0, "B": 0.0},
            scope={"kf": 0.1, "kr": 0.1}
        )

        sim = bio.sim(scenario)
        state = sim.initial_state()
        history = sim.run(state, steps=500)

        final = history[-1]
        # With equal rates, should reach ~50/50
        assert final["A"] == pytest.approx(5.0, rel=0.2)
        assert final["B"] == pytest.approx(5.0, rel=0.2)

    @pytest.mark.skip(reason="Implementation pending")
    def test_simulation_perturbation(self):
        """System responds to feedstock injection."""
        scenario = Scenario(
            name="test",
            molecules={"A": {}, "B": {}},
            reactions={
                "r1": {
                    "substrates": ["A"],
                    "products": ["B"],
                    "rate": Quoted(source="0.1 * S"),
                }
            },
            initial_state={"A": 10.0, "B": 0.0},
            scope={}
        )

        sim = bio.sim(scenario)
        state = sim.initial_state()

        # Run a bit
        for _ in range(10):
            state = sim.step(state)

        a_before_injection = state["A"]

        # Inject more A
        sim.action("add_feedstock", "A", 5.0)
        state = sim.step(state)

        # A should have increased from injection
        # (This depends on action implementation)
        # For now, just verify action doesn't crash
        assert state is not None

    @pytest.mark.skip(reason="Implementation pending")
    def test_simulation_reproducible(self):
        """Same seed produces same trajectory."""
        scenario = Scenario(
            name="test",
            molecules={"A": {}, "B": {}},
            reactions={
                "r1": {
                    "substrates": ["A"],
                    "products": ["B"],
                    "rate": Quoted(source="0.1 * S"),
                }
            },
            initial_state={"A": 10.0, "B": 0.0},
            scope={}
        )

        # Run twice with same seed
        sim1 = bio.sim(scenario)
        history1 = sim1.run(sim1.initial_state(), steps=50)

        sim2 = bio.sim(scenario)
        history2 = sim2.run(sim2.initial_state(), steps=50)

        # Should be identical
        for s1, s2 in zip(history1, history2):
            assert s1["A"] == s2["A"]
            assert s1["B"] == s2["B"]

    @pytest.mark.skip(reason="Implementation pending")
    def test_simulation_different_seeds(self):
        """Different seeds produce different trajectories (if stochastic)."""
        # Note: Deterministic simulators will produce same results
        # This test is for stochastic simulators
        scenario = Scenario(
            name="test",
            molecules={"A": {}, "B": {}},
            reactions={
                "r1": {
                    "substrates": ["A"],
                    "products": ["B"],
                    "rate": Quoted(source="normal(0.1, 0.01)"),  # Stochastic rate
                }
            },
            initial_state={"A": 10.0, "B": 0.0},
            scope={}
        )

        # This would require stochastic rate evaluation
        # For now, just verify it doesn't crash
        pass


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestBioSimIntegration:
    """Integration tests for Bio.load() -> bio.sim() -> run."""

    @pytest.mark.skip(reason="Implementation pending")
    def test_load_eval_sim_pipeline(self):
        """Full pipeline: load spec, eval, create sim, run."""
        # Load spec (returns hydrated, unevaluated)
        spec = Bio.load("fixtures/test_scenario.yaml")

        # Eval with seed
        from alienbio.spec_lang.eval import Context
        ctx = Context(rng=np.random.default_rng(42))
        scenario = Bio.eval(spec, ctx)

        # Create simulator (compiles rate expressions)
        sim = bio.sim(scenario)

        # Run simulation
        state = sim.initial_state()
        history = sim.run(state, steps=100)

        assert len(history) == 101

    @pytest.mark.skip(reason="Implementation pending")
    def test_multiple_instantiations_from_spec(self):
        """Same spec, different seeds, different scenarios."""
        spec = Bio.load("fixtures/test_scenario.yaml")

        from alienbio.spec_lang.eval import Context

        results = []
        for seed in range(10):
            ctx = Context(rng=np.random.default_rng(seed))
            scenario = Bio.eval(spec, ctx)
            sim = bio.sim(scenario)
            history = sim.run(sim.initial_state(), steps=50)
            results.append(history[-1])

        # With stochastic !_ expressions, results should vary
        # (If spec has no !_ expressions, results will be identical)
        # This test validates the pipeline works for multiple instantiations

    @pytest.mark.skip(reason="Implementation pending")
    def test_quotes_survive_eval(self):
        """!quote expressions survive Bio.eval and reach simulator."""
        from alienbio.spec_lang.eval import Context, Quoted

        spec = {
            "reactions": {
                "r1": {
                    "rate": Quoted(source="k * S"),
                }
            }
        }

        ctx = Context(rng=np.random.default_rng(42))
        # After eval, rate should still be a string (was Quoted)
        # bio.sim will compile it

        # This tests that Bio.eval preserves Quoted -> string
        # and bio.sim compiles string -> callable
