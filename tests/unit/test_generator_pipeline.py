"""Tests for Generator Phase G6: Full Generator Pipeline.

These tests define expected behavior for the complete generator pipeline,
from template specification to final scenario.

Test categories:
- G6.1: Bio.generate() API
- G6.2: End-to-End Pipeline
- G6.3: Error Handling & Debugging
"""

from __future__ import annotations

import pytest
import yaml


# =============================================================================
# G6.1 - Bio.generate() API
# =============================================================================


class TestBioGenerateAPI:
    """Tests for the Bio.generate() function."""

    @pytest.mark.skip(reason="Bio.generate() not yet implemented")
    def test_bio_generate_basic(self):
        """Bio.generate() produces a valid scenario."""
        from alienbio import Bio

        spec = Bio.fetch("scenarios/mutualism/hidden_dependency")
        scenario = Bio.generate(spec, seed=42)

        assert scenario is not None
        assert hasattr(scenario, 'molecules')
        assert hasattr(scenario, 'reactions')
        assert len(scenario.molecules) > 0
        assert len(scenario.reactions) > 0

    @pytest.mark.skip(reason="Bio.generate() not yet implemented")
    def test_bio_generate_reproducible(self):
        """Same seed produces identical scenarios."""
        from alienbio import Bio

        spec = Bio.fetch("scenarios/mutualism/hidden_dependency")
        s1 = Bio.generate(spec, seed=42)
        s2 = Bio.generate(spec, seed=42)

        assert s1.molecules == s2.molecules
        assert s1.reactions == s2.reactions

    @pytest.mark.skip(reason="Bio.generate() not yet implemented")
    def test_bio_generate_different_seeds(self):
        """Different seeds produce different scenarios."""
        from alienbio import Bio

        spec = Bio.fetch("scenarios/mutualism/hidden_dependency")
        s1 = Bio.generate(spec, seed=42)
        s2 = Bio.generate(spec, seed=43)

        # Should differ (with high probability if spec has stochastic elements)
        # At minimum, different seeds should be tracked
        assert s1._seed != s2._seed

    @pytest.mark.skip(reason="Bio.generate() not yet implemented")
    def test_bio_generate_ground_truth(self):
        """Ground truth is preserved in _ground_truth_."""
        from alienbio import Bio

        spec = Bio.fetch("scenarios/mutualism/hidden_dependency")
        scenario = Bio.generate(spec, seed=42)

        # Ground truth should have internal names
        assert hasattr(scenario, '_ground_truth_')
        gt = scenario._ground_truth_

        # Ground truth molecules use internal naming
        for name in gt.molecules:
            assert name.startswith("m.")

    @pytest.mark.skip(reason="Bio.generate() not yet implemented")
    def test_bio_generate_visibility_mapping(self):
        """Visibility mapping is preserved for debugging."""
        from alienbio import Bio

        spec = Bio.fetch("scenarios/mutualism/hidden_dependency")
        scenario = Bio.generate(spec, seed=42)

        assert hasattr(scenario, '_visibility_mapping_')
        mapping = scenario._visibility_mapping_

        # Should map internal to opaque names
        assert isinstance(mapping, dict)

    @pytest.mark.skip(reason="Bio.generate() not yet implemented")
    def test_bio_generate_from_dict(self):
        """Bio.generate() works with dict spec directly."""
        from alienbio import Bio

        spec = {
            "_instantiate_": {
                "_as_ energy": {
                    "_template_": "primitives/energy_cycle"
                }
            }
        }
        scenario = Bio.generate(spec, seed=42)

        assert scenario is not None
        assert len(scenario.molecules) > 0

    @pytest.mark.skip(reason="Bio.generate() not yet implemented")
    def test_bio_generate_with_params(self):
        """Bio.generate() accepts parameter overrides."""
        from alienbio import Bio

        spec = {
            "_params_": {"rate": 0.1},
            "_instantiate_": {
                "_as_ x": {"_template_": "primitives/energy_cycle", "rate": "!ref rate"}
            }
        }

        s1 = Bio.generate(spec, seed=42, params={"rate": 0.5})
        s2 = Bio.generate(spec, seed=42, params={"rate": 0.9})

        # Different params should produce different rates in reactions
        # (This depends on how rates are stored in the scenario)


# =============================================================================
# G6.2 - End-to-End Pipeline
# =============================================================================


class TestEndToEndPipeline:
    """Tests for the complete pipeline from template to scenario."""

    @pytest.mark.skip(reason="pipeline not yet implemented")
    def test_pipeline_template_to_scenario(self):
        """Pipeline converts template spec to valid scenario."""
        from alienbio import Bio
        from alienbio.generator import Template, TemplateRegistry, expand

        # Define a simple template
        template_yaml = """
        template.simple:
          _params_:
            rate: !ev lognormal(0.1, 0.3)
          molecules:
            M1: {role: energy}
            M2: {role: energy}
          reactions:
            r1:
              reactants: [M1]
              products: [M2]
              rate: !ref rate
          _ports_:
            reactions.r1: energy.out
        """

        registry = TemplateRegistry()
        data = yaml.safe_load(template_yaml)
        template = Template.parse(data["template.simple"], name="simple")
        registry.register("simple", template)

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "simple"}
            }
        }

        scenario = Bio.generate(spec, seed=42, registry=registry)

        assert len(scenario.molecules) == 2
        assert len(scenario.reactions) == 1

    @pytest.mark.skip(reason="pipeline not yet implemented")
    def test_pipeline_multi_template(self):
        """Pipeline handles multiple template instantiations."""
        from alienbio import Bio
        from alienbio.generator import TemplateRegistry

        registry = TemplateRegistry.from_directory("catalog/templates")

        spec = {
            "_instantiate_": {
                "_as_ energy": {"_template_": "primitives/energy_cycle"},
                "_as_ chain{i in 1..2}": {"_template_": "primitives/anabolic_chain"}
            }
        }

        scenario = Bio.generate(spec, seed=42, registry=registry)

        # Should have molecules from all instantiations
        assert len(scenario.molecules) >= 3

    @pytest.mark.skip(reason="pipeline not yet implemented")
    def test_pipeline_nested_templates(self):
        """Pipeline handles nested template instantiation."""
        from alienbio import Bio
        from alienbio.generator import Template, TemplateRegistry

        registry = TemplateRegistry()

        # Inner template
        inner = Template.parse({
            "molecules": {"M1": {"role": "energy"}}
        })
        registry.register("inner", inner)

        # Outer template that uses inner
        outer = Template.parse({
            "_instantiate_": {
                "_as_ sub": {"_template_": "inner"}
            }
        })
        registry.register("outer", outer)

        spec = {
            "_instantiate_": {
                "_as_ top": {"_template_": "outer"}
            }
        }

        scenario = Bio.generate(spec, seed=42, registry=registry)

        # Should have molecule from inner template
        assert len(scenario.molecules) >= 1

    @pytest.mark.skip(reason="pipeline not yet implemented")
    def test_pipeline_with_guards(self):
        """Pipeline applies guards during generation."""
        from alienbio import Bio
        from alienbio.generator import Template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("simple", Template.parse({
            "molecules": {"M1": {"role": "energy"}},
            "_guards_": {
                "no_negative_rates": "lambda r: r.rate >= 0"
            }
        }))

        spec = {
            "_instantiate_": {
                "_as_ x": {
                    "_template_": "simple"
                }
            }
        }

        # Should succeed (no negative rates)
        scenario = Bio.generate(spec, seed=42, registry=registry)
        assert scenario is not None

    @pytest.mark.skip(reason="pipeline not yet implemented")
    def test_pipeline_with_visibility(self):
        """Pipeline applies visibility mapping."""
        from alienbio import Bio

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "primitives/energy_cycle"}
            },
            "_visibility_": {
                "molecules": {"fraction_known": 1.0},
                "reactions": {"fraction_known": 1.0}
            }
        }

        scenario = Bio.generate(spec, seed=42)

        # Visible molecules should not have internal prefixes
        for name in scenario.molecules:
            assert not name.startswith("m.")

    @pytest.mark.skip(reason="pipeline not yet implemented")
    def test_pipeline_preserves_metadata(self):
        """Pipeline preserves metadata through generation."""
        from alienbio import Bio

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "primitives/energy_cycle"}
            },
            "_metadata_": {
                "author": "test",
                "version": "1.0"
            }
        }

        scenario = Bio.generate(spec, seed=42)

        assert scenario._metadata_["author"] == "test"
        assert scenario._metadata_["version"] == "1.0"


# =============================================================================
# G6.3 - Error Handling & Debugging
# =============================================================================


class TestErrorHandling:
    """Tests for error handling and debugging support."""

    @pytest.mark.skip(reason="Bio.generate() not yet implemented")
    def test_template_not_found_error(self):
        """Clear error when template doesn't exist."""
        from alienbio import Bio
        from alienbio.generator import TemplateNotFoundError

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "nonexistent_template"}
            }
        }

        with pytest.raises(TemplateNotFoundError) as exc:
            Bio.generate(spec, seed=42)
        assert "nonexistent_template" in str(exc.value)

    @pytest.mark.skip(reason="Bio.generate() not yet implemented")
    def test_port_type_error_message(self):
        """Helpful error when port types don't match."""
        from alienbio import Bio
        from alienbio.generator import PortTypeMismatchError, Template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("energy_out", Template.parse({
            "reactions": {"work": {}},
            "_ports_": {"reactions.work": "energy.out"}
        }))
        registry.register("molecule_in", Template.parse({
            "molecules": {"M1": {}},
            "_ports_": {"molecules.M1": "molecule.in"}
        }))

        spec = {
            "_instantiate_": {
                "_as_ a": {"_template_": "energy_out"},
                "_as_ b": {
                    "_template_": "molecule_in",
                    "molecules.M1": "a.reactions.work"  # Type mismatch!
                }
            }
        }

        with pytest.raises(PortTypeMismatchError) as exc:
            Bio.generate(spec, seed=42, registry=registry)
        # Error should mention the port types
        assert "energy" in str(exc.value).lower() or "molecule" in str(exc.value).lower()

    @pytest.mark.skip(reason="Bio.generate() not yet implemented")
    def test_guard_violation_error(self):
        """Clear error when guard is violated."""
        from alienbio import Bio
        from alienbio.generator import GuardViolation

        # Spec that should fail guard (to be determined by implementation)
        spec = {
            "_guards_": {
                "always_fail": "lambda _: False"
            },
            "_instantiate_": {
                "_as_ x": {"_template_": "primitives/energy_cycle"}
            }
        }

        with pytest.raises(GuardViolation):
            Bio.generate(spec, seed=42)

    @pytest.mark.skip(reason="Bio.generate() not yet implemented")
    def test_missing_param_error(self):
        """Clear error when required param is missing."""
        from alienbio import Bio
        from alienbio.generator import Template, TemplateRegistry, MissingParameterError

        registry = TemplateRegistry()
        registry.register("needs_param", Template.parse({
            "_params_": {"required_rate": None},  # Required, no default
            "reactions": {"r1": {"rate": "!ref required_rate"}}
        }))

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "needs_param"}
                # Missing required_rate param
            }
        }

        with pytest.raises(MissingParameterError) as exc:
            Bio.generate(spec, seed=42, registry=registry)
        assert "required_rate" in str(exc.value)

    @pytest.mark.skip(reason="Bio.generate() not yet implemented")
    def test_error_includes_context_path(self):
        """Errors include path context for debugging."""
        from alienbio import Bio
        from alienbio.generator import TemplateNotFoundError

        spec = {
            "_instantiate_": {
                "_as_ outer": {
                    "_template_": "composite",
                    # This template internally uses a bad reference
                }
            }
        }

        try:
            Bio.generate(spec, seed=42)
        except Exception as e:
            # Error should indicate where in the spec the problem occurred
            assert "outer" in str(e) or hasattr(e, 'path')

    @pytest.mark.skip(reason="Bio.generate() not yet implemented")
    def test_circular_template_reference(self):
        """Detect circular template references."""
        from alienbio import Bio
        from alienbio.generator import Template, TemplateRegistry, CircularReferenceError

        registry = TemplateRegistry()

        # Template A references B, B references A
        registry.register("A", Template.parse({
            "_instantiate_": {"_as_ sub": {"_template_": "B"}}
        }))
        registry.register("B", Template.parse({
            "_instantiate_": {"_as_ sub": {"_template_": "A"}}
        }))

        spec = {"_instantiate_": {"_as_ x": {"_template_": "A"}}}

        with pytest.raises(CircularReferenceError):
            Bio.generate(spec, seed=42, registry=registry)


# =============================================================================
# Integration: Complete Pipeline Scenarios
# =============================================================================


class TestPipelineIntegration:
    """Integration tests for realistic pipeline scenarios."""

    @pytest.mark.skip(reason="pipeline not yet implemented")
    def test_mutualism_scenario_generation(self):
        """Generate a mutualism scenario with two species."""
        from alienbio import Bio

        spec = {
            "_instantiate_": {
                "_as_ Krel": {"_template_": "organisms/autotroph"},
                "_as_ Kova": {"_template_": "organisms/heterotroph"}
            },
            "_visibility_": {
                "molecules": {"fraction_known": 0.8},
                "reactions": {"fraction_known": 0.5}
            }
        }

        scenario = Bio.generate(spec, seed=42)

        # Should have molecules from both organisms
        assert len(scenario.molecules) > 0
        assert len(scenario.reactions) > 0

        # Should have hidden elements
        assert len(scenario._ground_truth_.molecules) >= len(scenario.molecules)

    @pytest.mark.skip(reason="pipeline not yet implemented")
    def test_replication_with_varied_params(self):
        """Replicated instances can have varied parameters."""
        from alienbio import Bio

        spec = {
            "_instantiate_": {
                "_as_ chain{i in 1..3}": {
                    "_template_": "primitives/anabolic_chain",
                    "length": "!ev 3 + i"  # Varies with i
                }
            }
        }

        scenario = Bio.generate(spec, seed=42)

        # Should have 3 chains with different lengths
        # (Implementation detail: how lengths affect molecule counts)

    @pytest.mark.skip(reason="pipeline not yet implemented")
    def test_full_organism_generation(self):
        """Generate a complete organism with energy and metabolism."""
        from alienbio import Bio

        spec = {
            "_instantiate_": {
                "_as_ organism": {
                    "_template_": "organisms/minimal_organism",
                    "energy_rate": 0.1,
                    "metabolism_rate": 0.05
                }
            }
        }

        scenario = Bio.generate(spec, seed=42)

        # Should have functional organism
        assert len(scenario.molecules) > 0
        assert len(scenario.reactions) > 0

    @pytest.mark.skip(reason="pipeline not yet implemented")
    def test_scenario_is_simulatable(self):
        """Generated scenario can be simulated."""
        from alienbio import Bio

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "primitives/energy_cycle"}
            }
        }

        scenario = Bio.generate(spec, seed=42)

        # Should be able to run simulation
        result = Bio.sim(scenario, steps=10)
        assert len(result.timeline) == 11  # Initial + 10 steps
