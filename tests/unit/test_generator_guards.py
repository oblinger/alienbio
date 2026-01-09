"""Tests for Generator Phase G4: Guards.

These tests define expected behavior for guard infrastructure, built-in guards,
guard modes (reject, retry, prune), and YAML configuration.

Test categories:
- G4.1: Guard Infrastructure (@guard decorator, GuardViolation, GuardContext)
- G4.2: Built-in Guards (no_new_species_dependencies, no_new_cycles, no_essential)
- G4.3: Guard Modes (reject, retry, prune)
- G4.4: Guards in YAML (_guards_ section parsing)
"""

from __future__ import annotations

import pytest
import yaml


# =============================================================================
# G4.1 - Guard Infrastructure
# =============================================================================


class TestGuardDecorator:
    """Tests for @guard decorator and basic infrastructure."""

    
    def test_guard_decorator(self):
        """@guard decorator marks function as a guard."""
        from alienbio.generator import guard

        @guard
        def my_guard(expanded, context):
            return True

        assert hasattr(my_guard, '_is_guard')
        assert my_guard._is_guard == True

    
    def test_guard_passes(self):
        """Guard that returns True passes."""
        from alienbio.generator import guard, run_guard, GuardContext

        @guard
        def always_pass(expanded, context):
            return True

        context = GuardContext(scenario=None, namespace="x", seed=42, attempt=0)
        result = run_guard(always_pass, {}, context)
        assert result == True

    
    def test_guard_violation(self):
        """Guard that raises GuardViolation fails with details."""
        from alienbio.generator import guard, run_guard, GuardViolation, GuardContext

        @guard
        def always_fail(expanded, context):
            raise GuardViolation("Nope", details={"reason": "test"})

        context = GuardContext(scenario=None, namespace="x", seed=42, attempt=0)
        with pytest.raises(GuardViolation) as exc:
            run_guard(always_fail, {}, context)
        assert "Nope" in str(exc.value)
        assert exc.value.details["reason"] == "test"

    
    def test_guard_context_has_scenario(self):
        """GuardContext provides scenario, namespace, seed, attempt."""
        from alienbio.generator import guard, run_guard, GuardContext

        received_context = None

        @guard
        def check_context(expanded, context):
            nonlocal received_context
            received_context = context
            return True

        context = GuardContext(
            scenario={"name": "test"},
            namespace="krel",
            seed=42,
            attempt=0
        )
        run_guard(check_context, {}, context)

        assert received_context.scenario is not None
        assert received_context.namespace == "krel"
        assert received_context.seed == 42
        assert received_context.attempt == 0


class TestGuardViolationDetails:
    """Tests for GuardViolation exception details."""

    
    def test_violation_message(self):
        """GuardViolation has message."""
        from alienbio.generator import GuardViolation

        exc = GuardViolation("Something went wrong")
        assert str(exc) == "Something went wrong"

    
    def test_violation_details(self):
        """GuardViolation carries details dict."""
        from alienbio.generator import GuardViolation

        exc = GuardViolation("Failed", details={
            "molecule": "m.x.M1",
            "reason": "creates dependency"
        })
        assert exc.details["molecule"] == "m.x.M1"
        assert exc.details["reason"] == "creates dependency"

    
    def test_violation_prune_list(self):
        """GuardViolation can specify elements to prune."""
        from alienbio.generator import GuardViolation

        exc = GuardViolation("Too big", prune=["m.x.big1", "m.x.big2"])
        assert exc.prune == ["m.x.big1", "m.x.big2"]


# =============================================================================
# G4.2 - Built-in Guards
# =============================================================================


class TestNoNewSpeciesDependencies:
    """Tests for no_new_species_dependencies guard."""

    @pytest.fixture
    def mock_scenario(self):
        """Scenario with two species."""
        return {
            "organisms": {
                "Krel": {"molecules": ["m.Krel.M1"]},
                "Kova": {"molecules": ["m.Kova.M2"]}
            }
        }

    
    def test_no_new_species_dependencies_passes(self, mock_scenario):
        """Reaction within single species namespace passes."""
        from alienbio.generator import no_new_species_dependencies, GuardContext

        expanded = {
            "reactions": {
                "r.Krel.r1": {
                    "reactants": ["m.Krel.M1"],
                    "products": ["m.Krel.M2"]
                }
            }
        }
        context = GuardContext(scenario=mock_scenario, namespace="x", seed=42, attempt=0)

        result = no_new_species_dependencies(expanded, context)
        assert result == True

    
    def test_no_new_species_dependencies_fails(self, mock_scenario):
        """Reaction linking two species fails."""
        from alienbio.generator import no_new_species_dependencies, GuardContext, GuardViolation

        expanded = {
            "reactions": {
                "r.x.r1": {
                    "reactants": ["m.Krel.M1", "m.Kova.M2"],
                    "products": ["m.Krel.M3"]
                }
            }
        }
        context = GuardContext(scenario=mock_scenario, namespace="x", seed=42, attempt=0)

        with pytest.raises(GuardViolation) as exc:
            no_new_species_dependencies(expanded, context)
        assert "cross-species" in str(exc.value).lower()

    
    def test_background_reactions_ok(self):
        """Reactions in background namespace don't link species."""
        from alienbio.generator import no_new_species_dependencies, GuardContext

        expanded = {
            "reactions": {
                "r.bg.r1": {
                    "reactants": ["m.bg.X1"],
                    "products": ["m.bg.X2"]
                }
            }
        }
        context = GuardContext(scenario={}, namespace="bg", seed=42, attempt=0)

        result = no_new_species_dependencies(expanded, context)
        assert result == True


class TestNoNewCycles:
    """Tests for no_new_cycles guard."""

    
    def test_no_new_cycles_linear_passes(self):
        """Linear pathway passes."""
        from alienbio.generator import no_new_cycles, GuardContext

        expanded = {
            "reactions": {
                "r1": {"reactants": ["M1"], "products": ["M2"]},
                "r2": {"reactants": ["M2"], "products": ["M3"]},
            }
        }
        context = GuardContext(scenario={}, namespace="x", seed=42, attempt=0)

        result = no_new_cycles(expanded, context)
        assert result == True

    
    def test_no_new_cycles_fails(self):
        """Circular pathway fails."""
        from alienbio.generator import no_new_cycles, GuardContext, GuardViolation

        expanded = {
            "reactions": {
                "r1": {"reactants": ["M1"], "products": ["M2"]},
                "r2": {"reactants": ["M2"], "products": ["M1"]},  # Cycle!
            }
        }
        context = GuardContext(scenario={}, namespace="x", seed=42, attempt=0)

        with pytest.raises(GuardViolation) as exc:
            no_new_cycles(expanded, context)
        assert "cycle" in str(exc.value).lower()

    
    def test_self_loop_is_cycle(self):
        """Reaction consuming and producing same molecule is a cycle."""
        from alienbio.generator import no_new_cycles, GuardContext, GuardViolation

        expanded = {
            "reactions": {
                "r1": {"reactants": ["M1"], "products": ["M1"]},
            }
        }
        context = GuardContext(scenario={}, namespace="x", seed=42, attempt=0)

        with pytest.raises(GuardViolation):
            no_new_cycles(expanded, context)


class TestNoEssential:
    """Tests for no_essential guard."""

    
    def test_no_essential_passes(self):
        """Molecule not in reproduction_threshold passes."""
        from alienbio.generator import no_essential, GuardContext

        scenario = {
            "organisms": {
                "Krel": {
                    "reproduction_threshold": {"m.Krel.essential": 5.0}
                }
            }
        }
        expanded = {
            "molecules": {"m.bg.X1": {"role": "inert"}}
        }
        context = GuardContext(scenario=scenario, namespace="bg", seed=42, attempt=0)

        result = no_essential(expanded, context)
        assert result == True

    
    def test_no_essential_fails(self):
        """New molecule referenced in reproduction_threshold fails."""
        from alienbio.generator import no_essential, GuardContext, GuardViolation

        scenario = {
            "organisms": {
                "Krel": {
                    "reproduction_threshold": {"m.bg.X1": 5.0}  # References new!
                }
            }
        }
        expanded = {
            "molecules": {"m.bg.X1": {"role": "inert"}}
        }
        context = GuardContext(scenario=scenario, namespace="bg", seed=42, attempt=0)

        with pytest.raises(GuardViolation):
            no_essential(expanded, context)


# =============================================================================
# G4.3 - Guard Modes (reject, retry, prune)
# =============================================================================


class TestGuardModes:
    """Tests for guard execution modes."""

    @pytest.fixture
    def simple_template(self):
        """Template for mode testing."""
        from alienbio.generator import Template

        return Template.parse({
            "molecules": {"M1": {}}
        })

    
    def test_reject_mode(self, simple_template):
        """reject mode fails immediately on violation."""
        from alienbio.generator import guard, expand_with_guards, GuardViolation

        @guard
        def always_fail(expanded, context):
            raise GuardViolation("Nope")

        with pytest.raises(GuardViolation):
            expand_with_guards(
                simple_template,
                guards=[always_fail],
                mode="reject",
                namespace="x"
            )

    
    def test_retry_mode_succeeds(self, simple_template):
        """retry mode resamples until guard passes."""
        from alienbio.generator import guard, expand_with_guards, GuardViolation

        attempts = []

        @guard
        def flaky(expanded, context):
            attempts.append(context.attempt)
            if context.attempt < 2:
                raise GuardViolation("Not yet")
            return True

        result = expand_with_guards(
            simple_template,
            guards=[flaky],
            mode="retry",
            max_attempts=5,
            namespace="x",
            seed=42
        )

        assert result is not None
        assert len(attempts) == 3  # 0, 1, 2

    
    def test_retry_mode_exhausted(self, simple_template):
        """retry mode fails after max_attempts."""
        from alienbio.generator import guard, expand_with_guards, GuardViolation

        @guard
        def always_fail(expanded, context):
            raise GuardViolation("Nope")

        with pytest.raises(GuardViolation) as exc:
            expand_with_guards(
                simple_template,
                guards=[always_fail],
                mode="retry",
                max_attempts=3,
                namespace="x"
            )
        error_msg = str(exc.value).lower()
        assert "max_attempts" in error_msg or "exhausted" in error_msg

    
    def test_prune_mode(self):
        """prune mode removes violating elements."""
        from alienbio.generator import guard, expand_with_guards, GuardViolation, Template

        template = Template.parse({
            "molecules": {
                "small": {"size": 1},
                "big": {"size": 100}
            }
        })

        @guard
        def no_big_molecules(expanded, context):
            violations = [m for m in expanded.get("molecules", {}) if "big" in m]
            if violations:
                raise GuardViolation("Too big", prune=violations)
            return True

        result = expand_with_guards(
            template,
            guards=[no_big_molecules],
            mode="prune",
            namespace="x"
        )

        assert "m.x.small" in result.molecules
        assert "m.x.big" not in result.molecules

    
    def test_retry_increments_seed(self, simple_template):
        """Each retry attempt uses different seed."""
        from alienbio.generator import guard, expand_with_guards, GuardViolation

        seeds = []

        @guard
        def track_seeds(expanded, context):
            seeds.append(context.seed)
            if len(seeds) < 3:
                raise GuardViolation("Not yet")
            return True

        expand_with_guards(
            simple_template,
            guards=[track_seeds],
            mode="retry",
            max_attempts=5,
            namespace="x",
            seed=42
        )

        # Each attempt should have different seed
        assert len(set(seeds)) == 3


# =============================================================================
# G4.4 - Guards in YAML
# =============================================================================


class TestGuardsInYAML:
    """Tests for parsing guards from YAML spec."""

    @pytest.mark.skip(reason="load_generator_spec not yet implemented")
    def test_global_guards(self):
        """_guards_ section lists guard names."""
        from alienbio.generator import load_generator_spec

        yaml_str = """
scenario_generator_spec:
  _guards_:
    - no_new_species_dependencies
    - no_new_cycles
  _instantiate_:
    _as_ x:
      _template_: foo
"""
        spec = load_generator_spec(yaml.safe_load(yaml_str))

        assert "no_new_species_dependencies" in spec.guards
        assert "no_new_cycles" in spec.guards

    @pytest.mark.skip(reason="load_generator_spec not yet implemented")
    def test_guard_with_params(self):
        """Guard can have parameters."""
        from alienbio.generator import load_generator_spec

        yaml_str = """
scenario_generator_spec:
  _guards_:
    - max_pathway_length: {max_length: 4}
"""
        spec = load_generator_spec(yaml.safe_load(yaml_str))

        guard_config = spec.guards[0]
        assert guard_config["name"] == "max_pathway_length"
        assert guard_config["params"]["max_length"] == 4

    @pytest.mark.skip(reason="load_generator_spec not yet implemented")
    def test_guard_with_mode(self):
        """Guard can specify mode and max_attempts."""
        from alienbio.generator import load_generator_spec

        yaml_str = """
scenario_generator_spec:
  _guards_:
    - name: no_new_cycles
      mode: retry
      max_attempts: 10
"""
        spec = load_generator_spec(yaml.safe_load(yaml_str))

        guard_config = spec.guards[0]
        assert guard_config["name"] == "no_new_cycles"
        assert guard_config["mode"] == "retry"
        assert guard_config["max_attempts"] == 10

    @pytest.mark.skip(reason="load_generator_spec not yet implemented")
    def test_guard_mixed_syntax(self):
        """Guards can mix simple names and detailed configs."""
        from alienbio.generator import load_generator_spec

        yaml_str = """
scenario_generator_spec:
  _guards_:
    - no_new_species_dependencies
    - name: no_new_cycles
      mode: prune
    - max_depth: {max: 5}
"""
        spec = load_generator_spec(yaml.safe_load(yaml_str))

        assert len(spec.guards) == 3
        # First is simple name
        assert spec.guards[0] == "no_new_species_dependencies" or \
               spec.guards[0]["name"] == "no_new_species_dependencies"


# =============================================================================
# Helper function tests
# =============================================================================


class TestGuardHelpers:
    """Tests for guard helper functions."""

    
    def test_get_species_from_path(self):
        """Extract species name from molecule/reaction path."""
        from alienbio.generator import get_species_from_path

        assert get_species_from_path("m.Krel.energy.ME1") == "Krel"
        assert get_species_from_path("r.Kova.chain.build") == "Kova"
        assert get_species_from_path("m.bg.X1") is None  # bg is not a species
        assert get_species_from_path("M1") is None  # No namespace

    
    def test_build_dependency_graph(self):
        """Build graph of molecule dependencies from reactions."""
        from alienbio.generator import build_dependency_graph

        reactions = {
            "r1": {"reactants": ["M1"], "products": ["M2"]},
            "r2": {"reactants": ["M2"], "products": ["M3"]},
        }
        graph = build_dependency_graph(reactions)

        # M2 depends on M1 (M1 -> M2)
        assert "M2" in graph.get("M1", [])
        # M3 depends on M2
        assert "M3" in graph.get("M2", [])

    
    def test_detect_cycles(self):
        """Detect cycles in dependency graph."""
        from alienbio.generator import detect_cycles

        # No cycle
        graph1 = {"A": ["B"], "B": ["C"]}
        assert detect_cycles(graph1) == []

        # Has cycle
        graph2 = {"A": ["B"], "B": ["A"]}
        cycles = detect_cycles(graph2)
        assert len(cycles) > 0
