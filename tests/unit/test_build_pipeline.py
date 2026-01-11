"""Tests for Generator Phase G6: Full Generator Pipeline.

These tests define expected behavior for the complete generator pipeline,
from template specification to final scenario.

Test categories:
- G6.1: Bio.build() API
- G6.2: End-to-End Pipeline
- G6.3: Error Handling & Debugging
"""

from __future__ import annotations

import pytest
import yaml


# =============================================================================
# G6.1 - Bio.build() API
# =============================================================================


class TestBioGenerateAPI:
    """Tests for the Bio.build() function."""

    @pytest.fixture
    def simple_registry(self):
        """Create a registry with a simple template."""
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()
        template = parse_template({
            "molecules": {"M1": {"role": "energy"}, "M2": {"role": "energy"}},
            "reactions": {"r1": {"reactants": ["M1"], "products": ["M2"], "rate": 0.1}}
        })
        registry.register("simple", template)
        return registry

    def test_bio_generate_basic(self, simple_registry):
        """Bio.build() produces a valid scenario."""
        from alienbio import Bio

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "simple"}
            }
        }
        scenario = Bio.build(spec, seed=42, registry=simple_registry)

        assert scenario is not None
        assert hasattr(scenario, 'molecules')
        assert hasattr(scenario, 'reactions')
        assert len(scenario.molecules) > 0
        assert len(scenario.reactions) > 0

    def test_bio_generate_reproducible(self, simple_registry):
        """Same seed produces identical scenarios."""
        from alienbio import Bio

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "simple"}
            }
        }
        s1 = Bio.build(spec, seed=42, registry=simple_registry)
        s2 = Bio.build(spec, seed=42, registry=simple_registry)

        assert s1.molecules == s2.molecules
        assert s1.reactions == s2.reactions

    def test_bio_generate_different_seeds(self, simple_registry):
        """Different seeds produce scenarios with different _seed values."""
        from alienbio import Bio

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "simple"}
            }
        }
        s1 = Bio.build(spec, seed=42, registry=simple_registry)
        s2 = Bio.build(spec, seed=43, registry=simple_registry)

        # Different seeds should be tracked
        assert s1._seed != s2._seed

    def test_bio_generate_ground_truth(self, simple_registry):
        """Ground truth is preserved in _ground_truth_."""
        from alienbio import Bio

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "simple"}
            }
        }
        scenario = Bio.build(spec, seed=42, registry=simple_registry)

        # Ground truth should have internal names
        assert hasattr(scenario, '_ground_truth_')
        gt = scenario._ground_truth_

        # Ground truth molecules use internal naming
        for name in gt["molecules"]:
            assert name.startswith("m.")

    def test_bio_generate_visibility_mapping(self, simple_registry):
        """Visibility mapping is preserved for debugging."""
        from alienbio import Bio

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "simple"}
            }
        }
        scenario = Bio.build(spec, seed=42, registry=simple_registry)

        assert hasattr(scenario, '_visibility_mapping_')
        mapping = scenario._visibility_mapping_

        # Should map internal to opaque names
        assert isinstance(mapping, dict)

    def test_bio_generate_from_dict(self, simple_registry):
        """Bio.build() works with dict spec directly."""
        from alienbio import Bio

        spec = {
            "_instantiate_": {
                "_as_ energy": {"_template_": "simple"}
            }
        }
        scenario = Bio.build(spec, seed=42, registry=simple_registry)

        assert scenario is not None
        assert len(scenario.molecules) > 0

    def test_bio_generate_with_params(self):
        """Bio.build() accepts parameter overrides."""
        from alienbio import Bio
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()
        template = parse_template({
            "_params_": {"rate": 0.1},
            "molecules": {"M1": {}, "M2": {}},
            "reactions": {"r1": {"reactants": ["M1"], "products": ["M2"], "rate": "!ref rate"}}
        })
        registry.register("parameterized", template)

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "parameterized"}
            }
        }

        # Generate with default params
        s1 = Bio.build(spec, seed=42, registry=registry)
        # Generate with overridden params
        s2 = Bio.build(spec, seed=42, registry=registry, params={"rate": 0.9})

        # Both should succeed
        assert s1 is not None
        assert s2 is not None


# =============================================================================
# G6.2 - End-to-End Pipeline
# =============================================================================


class TestEndToEndPipeline:
    """Tests for the complete pipeline from template to scenario."""

    def test_pipeline_template_to_scenario(self):
        """Pipeline converts template spec to valid scenario."""
        from alienbio import Bio
        from alienbio.build import parse_template, TemplateRegistry

        # Define a simple template
        template = parse_template({
            "_params_": {"rate": 0.1},
            "molecules": {
                "M1": {"role": "energy"},
                "M2": {"role": "energy"}
            },
            "reactions": {
                "r1": {
                    "reactants": ["M1"],
                    "products": ["M2"],
                    "rate": "!ref rate"
                }
            }
        })

        registry = TemplateRegistry()
        registry.register("simple", template)

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "simple"}
            }
        }

        scenario = Bio.build(spec, seed=42, registry=registry)

        assert len(scenario.molecules) == 2
        assert len(scenario.reactions) == 1

    def test_pipeline_multi_template(self):
        """Pipeline handles multiple template instantiations."""
        from alienbio import Bio
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()
        template = parse_template({
            "molecules": {"M1": {"role": "energy"}}
        })
        registry.register("single_mol", template)

        spec = {
            "_instantiate_": {
                "_as_ a": {"_template_": "single_mol"},
                "_as_ b": {"_template_": "single_mol"}
            }
        }

        scenario = Bio.build(spec, seed=42, registry=registry)

        # Should have molecules from both instantiations
        assert len(scenario._ground_truth_["molecules"]) == 2

    def test_pipeline_nested_templates(self):
        """Pipeline handles nested template instantiation."""
        from alienbio import Bio
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()

        # Inner template
        inner = parse_template({
            "molecules": {"M1": {"role": "energy"}}
        })
        registry.register("inner", inner)

        # Outer template that uses inner (use _instantiate_ with underscores)
        outer = parse_template({
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

        scenario = Bio.build(spec, seed=42, registry=registry)

        # Should have molecule from inner template
        assert len(scenario._ground_truth_["molecules"]) >= 1

    def test_pipeline_with_guards(self):
        """Pipeline applies guards during generation."""
        from alienbio import Bio
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("simple", parse_template({
            "molecules": {"M1": {"role": "energy"}},
        }))

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "simple"}
            },
            "_guards_": ["no_new_cycles"]
        }

        # Should succeed (no cycles)
        scenario = Bio.build(spec, seed=42, registry=registry)
        assert scenario is not None

    def test_pipeline_with_visibility(self):
        """Pipeline applies visibility mapping."""
        from alienbio import Bio
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("simple", parse_template({
            "molecules": {"M1": {}, "M2": {}},
            "reactions": {"r1": {"reactants": ["M1"], "products": ["M2"]}}
        }))

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "simple"}
            },
            "_visibility_": {
                "molecules": {"fraction_known": 1.0},
                "reactions": {"fraction_known": 1.0}
            }
        }

        scenario = Bio.build(spec, seed=42, registry=registry)

        # Visible molecules should not have internal prefixes
        for name in scenario.molecules:
            assert not name.startswith("m.")

    def test_pipeline_preserves_metadata(self):
        """Pipeline preserves metadata through generation."""
        from alienbio import Bio
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("simple", parse_template({
            "molecules": {"M1": {}}
        }))

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "simple"}
            },
            "_metadata_": {
                "author": "test",
                "version": "1.0"
            }
        }

        scenario = Bio.build(spec, seed=42, registry=registry)

        assert scenario._metadata_["author"] == "test"
        assert scenario._metadata_["version"] == "1.0"


# =============================================================================
# G6.3 - Error Handling & Debugging
# =============================================================================


class TestErrorHandling:
    """Tests for error handling and debugging support."""

    def test_template_not_found_error(self):
        """Clear error when template doesn't exist."""
        from alienbio import Bio
        from alienbio.build import TemplateNotFoundError, TemplateRegistry

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "nonexistent_template"}
            }
        }

        registry = TemplateRegistry()
        with pytest.raises(TemplateNotFoundError) as exc:
            Bio.build(spec, seed=42, registry=registry)
        assert "nonexistent_template" in str(exc.value)

    @pytest.mark.skip(reason="Cross-instantiation port wiring requires M2.8 Interactions")
    def test_port_type_error_message(self):
        """Helpful error when port types don't match."""
        from alienbio import Bio
        from alienbio.build import PortTypeMismatchError, parse_template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("energy_out", parse_template({
            "reactions": {"work": {}},
            "_ports_": {"reactions.work": "energy.out"}
        }))
        registry.register("molecule_in", parse_template({
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
            Bio.build(spec, seed=42, registry=registry)
        # Error should mention the port types
        error_str = str(exc.value).lower()
        assert "energy" in error_str or "molecule" in error_str

    @pytest.mark.skip(reason="Custom guard definition not yet implemented")
    def test_guard_violation_error(self):
        """Clear error when guard is violated."""
        from alienbio import Bio
        from alienbio.build import GuardViolation

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
            Bio.build(spec, seed=42)

    @pytest.mark.skip(reason="Required param validation not yet implemented")
    def test_missing_param_error(self):
        """Clear error when required param is missing."""
        from alienbio import Bio
        from alienbio.build import parse_template, TemplateRegistry, MissingParameterError

        registry = TemplateRegistry()
        registry.register("needs_param", parse_template({
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
            Bio.build(spec, seed=42, registry=registry)
        assert "required_rate" in str(exc.value)

    @pytest.mark.skip(reason="Error path context not yet implemented")
    def test_error_includes_context_path(self):
        """Errors include path context for debugging."""
        from alienbio import Bio
        from alienbio.build import TemplateNotFoundError

        spec = {
            "_instantiate_": {
                "_as_ outer": {
                    "_template_": "composite",
                    # This template internally uses a bad reference
                }
            }
        }

        try:
            Bio.build(spec, seed=42)
        except Exception as e:
            # Error should indicate where in the spec the problem occurred
            assert "outer" in str(e) or hasattr(e, 'path')

    @pytest.mark.skip(reason="Circular detection in nested templates requires expand.py changes")
    def test_circular_template_reference(self):
        """Detect circular template references."""
        from alienbio import Bio
        from alienbio.build import parse_template, TemplateRegistry, CircularReferenceError

        registry = TemplateRegistry()

        # Template A references B, B references A (use _instantiate_ with underscores)
        registry.register("A", parse_template({
            "_instantiate_": {"_as_ sub": {"_template_": "B"}}
        }))
        registry.register("B", parse_template({
            "_instantiate_": {"_as_ sub": {"_template_": "A"}}
        }))

        spec = {"_instantiate_": {"_as_ x": {"_template_": "A"}}}

        with pytest.raises(CircularReferenceError):
            Bio.build(spec, seed=42, registry=registry)


# =============================================================================
# Integration: Complete Pipeline Scenarios
# =============================================================================


class TestPipelineIntegration:
    """Integration tests for realistic pipeline scenarios."""

    def test_mutualism_scenario_generation(self):
        """Generate a mutualism scenario with two species."""
        from alienbio import Bio
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()

        # Create simple organism templates
        registry.register("organisms/autotroph", parse_template({
            "molecules": {"energy": {"role": "energy"}, "biomass": {"role": "structural"}},
            "reactions": {"metabolism": {"reactants": ["energy"], "products": ["biomass"]}}
        }))
        registry.register("organisms/heterotroph", parse_template({
            "molecules": {"food": {"role": "nutrient"}, "waste": {"role": "waste"}},
            "reactions": {"digest": {"reactants": ["food"], "products": ["waste"]}}
        }))

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

        scenario = Bio.build(spec, seed=42, registry=registry)

        # Should have molecules from both organisms
        assert len(scenario.molecules) > 0
        assert len(scenario.reactions) > 0

        # Should have hidden elements (since fraction_known < 1)
        assert len(scenario._ground_truth_["molecules"]) >= len(scenario.molecules)

    def test_replication_with_varied_params(self):
        """Replicated instances can have varied parameters."""
        from alienbio import Bio
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("chain", parse_template({
            "_params_": {"length": 3},
            "molecules": {"start": {}, "end": {}},
        }))

        spec = {
            "_instantiate_": {
                "_as_ chain{i in 1..3}": {
                    "_template_": "chain",
                }
            }
        }

        scenario = Bio.build(spec, seed=42, registry=registry)

        # Should have molecules from 3 chain instances
        assert len(scenario._ground_truth_["molecules"]) == 6  # 2 per chain * 3

    def test_full_organism_generation(self):
        """Generate a complete organism with energy and metabolism."""
        from alienbio import Bio
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("organisms/minimal_organism", parse_template({
            "_params_": {"energy_rate": 0.1, "metabolism_rate": 0.05},
            "molecules": {
                "ATP": {"role": "energy"},
                "ADP": {"role": "energy"},
                "nutrient": {"role": "nutrient"},
                "biomass": {"role": "structural"},
            },
            "reactions": {
                "energy_cycle": {
                    "reactants": ["ADP"],
                    "products": ["ATP"],
                    "rate": "!ref energy_rate"
                },
                "metabolism": {
                    "reactants": ["ATP", "nutrient"],
                    "products": ["ADP", "biomass"],
                    "rate": "!ref metabolism_rate"
                }
            }
        }))

        spec = {
            "_instantiate_": {
                "_as_ organism": {
                    "_template_": "organisms/minimal_organism",
                    "energy_rate": 0.1,
                    "metabolism_rate": 0.05
                }
            }
        }

        scenario = Bio.build(spec, seed=42, registry=registry)

        # Should have functional organism
        assert len(scenario.molecules) > 0
        assert len(scenario.reactions) > 0

    @pytest.mark.skip(reason="Bio.sim integration not yet implemented")
    def test_scenario_is_simulatable(self):
        """Generated scenario can be simulated."""
        from alienbio import Bio
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("simple", parse_template({
            "molecules": {"M1": {}, "M2": {}},
            "reactions": {"r1": {"reactants": ["M1"], "products": ["M2"]}}
        }))

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "simple"}
            }
        }

        scenario = Bio.build(spec, seed=42, registry=registry)

        # Should be able to run simulation
        result = Bio.sim(scenario, steps=10)
        assert len(result.timeline) == 11  # Initial + 10 steps
