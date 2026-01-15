"""Tests for Generator M2.8: Interactions and Modifiers.

These tests define expected behavior for inter-species wiring and modifying
existing elements.

Test categories:
- M2.8.1: Interaction parsing and wiring
- M2.8.2: Port requirements validation
- M2.8.3: Modify and set syntax
"""

from __future__ import annotations

import pytest


# =============================================================================
# M2.8.1 - Interaction Parsing and Wiring
# =============================================================================


class TestInteractionParsing:
    """Tests for parsing interactions: section."""

    def test_parse_interaction_template(self):
        """Parse interaction with _template_ and between: fields."""
        from alienbio.build import parse_interaction

        interaction = parse_interaction({
            "_template_": "cross_feeding",
            "between": ["Krel", "Kova"],
            "rate": 0.1
        })

        assert interaction["template"] == "cross_feeding"
        assert interaction["between"] == ["Krel", "Kova"]
        assert interaction["params"]["rate"] == 0.1

    def test_interaction_wires_species(self):
        """Interaction template wires two species together."""
        from alienbio import Bio, bio
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()

        # Species templates
        registry.register("producer", parse_template({
            "molecules": {"product": {}},
            "_ports_": {"molecules.product": "resource.out"}
        }))
        registry.register("consumer", parse_template({
            "molecules": {"input": {}},
            "_ports_": {"molecules.input": "resource.in"}
        }))

        # Interaction template that connects producer.out -> consumer.in
        registry.register("exchange", parse_template({
            "reactions": {
                "transfer": {
                    "reactants": ["!port producer.molecules.product"],
                    "products": ["!port consumer.molecules.input"],
                    "rate": "!ref rate"
                }
            },
            "_params_": {"rate": 0.1}
        }))

        spec = {
            "_instantiate_": {
                "_as_ Krel": {"_template_": "producer"},
                "_as_ Kova": {"_template_": "consumer"},
            },
            "interactions": {
                "cross_feeding": {
                    "_template_": "exchange",
                    "between": ["Krel", "Kova"],
                    "rate": 0.2
                }
            }
        }

        scenario = bio.build(spec, seed=42, registry=registry)

        # Should have molecules from both species
        gt = scenario._ground_truth_
        assert "m.Krel.product" in gt["molecules"]
        assert "m.Kova.input" in gt["molecules"]

        # Should have the cross-feeding reaction
        assert len(gt["reactions"]) >= 1


# =============================================================================
# M2.8.2 - Port Requirements Validation
# =============================================================================


class TestPortRequirements:
    """Tests for requires: port validation."""

    def test_requires_validation_passes(self):
        """Requires validation passes when ports are available."""
        from alienbio import Bio, bio
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("provider", parse_template({
            "reactions": {"work": {}},
            "_ports_": {"reactions.work": "energy.out"}
        }))
        registry.register("dependent", parse_template({
            "reactions": {"consume": {}},
            "_ports_": {"reactions.consume": "energy.in"},
            "requires": ["energy.out"]  # Requires an energy output
        }))

        spec = {
            "_instantiate_": {
                "_as_ a": {"_template_": "provider"},
                "_as_ b": {
                    "_template_": "dependent",
                    "reactions.consume": "a.reactions.work"
                }
            }
        }

        # Should succeed - energy.out is available
        scenario = bio.build(spec, seed=42, registry=registry)
        assert scenario is not None

    def test_requires_validation_fails(self):
        """Requires validation fails when required port is missing."""
        from alienbio import Bio, bio
        from alienbio.build import parse_template, TemplateRegistry, PortNotFoundError

        registry = TemplateRegistry()
        registry.register("dependent", parse_template({
            "reactions": {"consume": {}},
            "_ports_": {"reactions.consume": "energy.in"},
            "requires": ["energy.out"]  # Requires an energy output
        }))

        spec = {
            "_instantiate_": {
                "_as_ b": {"_template_": "dependent"}
                # No provider with energy.out
            }
        }

        # Should fail - no energy.out available
        with pytest.raises(PortNotFoundError):
            bio.build(spec, seed=42, registry=registry)


# =============================================================================
# M2.8.3 - Modify and Set Syntax
# =============================================================================


class TestModifyAndSet:
    """Tests for _modify_ and _set_ syntax."""

    def test_modify_changes_reactants(self):
        """_modify_ changes reactants in existing reaction."""
        from alienbio import Bio, bio
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("base", parse_template({
            "molecules": {"M1": {}, "M2": {}},
            "reactions": {
                "r1": {"reactants": ["M1"], "products": ["M2"], "rate": 0.1}
            }
        }))

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "base"}
            },
            "_modify_": {
                "x.reactions.r1": {
                    "_set_": {"rate": 0.5}
                }
            }
        }

        scenario = bio.build(spec, seed=42, registry=registry)

        # Reaction rate should be modified
        gt = scenario._ground_truth_
        assert gt["reactions"]["r.x.r1"]["rate"] == 0.5

    def test_modify_adds_reactant(self):
        """_modify_ can add to reactants list."""
        from alienbio import Bio, bio
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("base", parse_template({
            "molecules": {"M1": {}, "M2": {}, "catalyst": {}},
            "reactions": {
                "r1": {"reactants": ["M1"], "products": ["M2"]}
            }
        }))

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "base"}
            },
            "_modify_": {
                "x.reactions.r1": {
                    "_append_": {"reactants": ["catalyst"]}
                }
            }
        }

        scenario = bio.build(spec, seed=42, registry=registry)

        gt = scenario._ground_truth_
        # Catalyst should be added to reactants
        assert "m.x.catalyst" in gt["reactions"]["r.x.r1"]["reactants"]

    def test_modify_path_validation(self):
        """_modify_ raises error for invalid path."""
        from alienbio import Bio, bio
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("base", parse_template({
            "molecules": {"M1": {}},
        }))

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "base"}
            },
            "_modify_": {
                "x.reactions.nonexistent": {  # Invalid path
                    "_set_": {"rate": 0.5}
                }
            }
        }

        with pytest.raises(KeyError):
            bio.build(spec, seed=42, registry=registry)
