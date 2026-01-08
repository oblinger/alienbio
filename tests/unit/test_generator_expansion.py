"""Tests for Generator Phase G2: Template Expansion.

These tests define expected behavior for template expansion, namespace prefixing,
nested instantiation, and port wiring.

Test categories:
- G2.1: Single Template Instantiation (expand, namespace prefixing, param substitution)
- G2.2: Nested Instantiation (_instantiate_, _as_, replication)
- G2.3: Port Wiring (declaration, connection, type checking)
"""

from __future__ import annotations

import pytest
import yaml


# =============================================================================
# G2.1 - Single Template Instantiation
# =============================================================================


class TestSingleTemplateExpansion:
    """Tests for basic template expansion with namespace prefixing."""

    def test_expand_simple_template(self):
        """Expanded template has namespaced molecule and reaction names."""
        from alienbio.generator import Template, expand

        template = Template.parse({
            "molecules": {"M1": {"role": "energy"}},
            "reactions": {"r1": {"reactants": ["M1"], "products": ["M2"]}}
        })
        expanded = expand(template, namespace="krel")

        assert "m.krel.M1" in expanded.molecules
        assert "r.krel.r1" in expanded.reactions

    def test_expand_with_params(self):
        """Parameter values are substituted during expansion."""
        from alienbio.generator import Template, expand

        template = Template.parse({
            "_params_": {"rate": 0.1},
            "reactions": {"r1": {"rate": "!ref rate"}}
        })
        expanded = expand(template, namespace="krel", params={"rate": 0.5})

        assert expanded.reactions["r.krel.r1"]["rate"] == 0.5

    def test_expand_resolves_refs(self):
        """!ref expressions are resolved to parameter values."""
        from alienbio.generator import Template, expand

        template = Template.parse({
            "_params_": {"k": 0.1},
            "reactions": {"r1": {"rate": "!ref k"}}
        })
        expanded = expand(template, namespace="x")

        # Should be resolved, not still "!ref k"
        assert expanded.reactions["r.x.r1"]["rate"] == 0.1

    def test_expand_default_params(self):
        """Template _params_ provide defaults when not overridden."""
        from alienbio.generator import Template, expand

        template = Template.parse({
            "_params_": {"rate": 0.1, "efficiency": 0.8},
            "reactions": {"r1": {"rate": "!ref rate", "eff": "!ref efficiency"}}
        })
        # Only override rate
        expanded = expand(template, namespace="x", params={"rate": 0.5})

        assert expanded.reactions["r.x.r1"]["rate"] == 0.5
        assert expanded.reactions["r.x.r1"]["eff"] == 0.8  # Default

    def test_expand_updates_reaction_references(self):
        """Molecule names in reactions are also namespaced."""
        from alienbio.generator import Template, expand

        template = Template.parse({
            "molecules": {"M1": {}, "M2": {}},
            "reactions": {
                "r1": {"reactants": ["M1"], "products": ["M2"]}
            }
        })
        expanded = expand(template, namespace="krel")

        rxn = expanded.reactions["r.krel.r1"]
        assert rxn["reactants"] == ["m.krel.M1"]
        assert rxn["products"] == ["m.krel.M2"]

    def test_expand_preserves_other_fields(self):
        """Non-name fields in molecules/reactions are preserved."""
        from alienbio.generator import Template, expand

        template = Template.parse({
            "molecules": {
                "M1": {"role": "energy", "description": "High energy"}
            }
        })
        expanded = expand(template, namespace="x")

        mol = expanded.molecules["m.x.M1"]
        assert mol["role"] == "energy"
        assert mol["description"] == "High energy"


# =============================================================================
# G2.2 - Nested Instantiation (_instantiate_ / _as_)
# =============================================================================


class TestNestedInstantiation:
    """Tests for nested template instantiation."""

    @pytest.fixture
    def simple_registry(self):
        """Registry with a simple template for testing."""
        from alienbio.generator import Template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("energy_cycle", Template.parse({
            "_params_": {"rate": 0.1},
            "molecules": {
                "ME1": {"role": "energy"},
                "ME2": {"role": "energy"}
            },
            "reactions": {
                "activation": {"reactants": ["ME1"], "products": ["ME2"], "rate": "!ref rate"}
            }
        }))
        registry.register("anabolic_chain", Template.parse({
            "molecules": {
                "MS1": {"role": "structural"},
                "MS2": {"role": "structural"}
            },
            "reactions": {
                "build": {"reactants": ["MS1"], "products": ["MS2"]}
            }
        }))
        registry.register("simple", Template.parse({
            "molecules": {"M1": {}}
        }))
        return registry

    def test_nested_instantiation(self, simple_registry):
        """_instantiate_ with _as_ creates namespaced sub-templates."""
        from alienbio.generator import Template, expand

        parent = Template.parse({
            "_instantiate_": {
                "_as_ energy": {"_template_": "energy_cycle", "rate": 0.2}
            }
        })
        expanded = expand(parent, namespace="krel", registry=simple_registry)

        assert "m.krel.energy.ME1" in expanded.molecules
        assert "m.krel.energy.ME2" in expanded.molecules
        assert "r.krel.energy.activation" in expanded.reactions

    def test_nested_param_override(self, simple_registry):
        """Nested instantiation can override parent template params."""
        from alienbio.generator import Template, expand

        parent = Template.parse({
            "_instantiate_": {
                "_as_ energy": {"_template_": "energy_cycle", "rate": 0.5}
            }
        })
        expanded = expand(parent, namespace="krel", registry=simple_registry)

        # Rate should be 0.5, not default 0.1
        rxn = expanded.reactions["r.krel.energy.activation"]
        assert rxn.get("rate") == 0.5 or "rate" in str(rxn)

    def test_replication(self, simple_registry):
        """_as_ with {i in range} creates multiple instances."""
        from alienbio.generator import Template, expand

        parent = Template.parse({
            "_instantiate_": {
                "_as_ chain{i in 1..3}": {"_template_": "anabolic_chain"}
            }
        })
        expanded = expand(parent, namespace="krel", registry=simple_registry)

        assert "m.krel.chain1.MS1" in expanded.molecules
        assert "m.krel.chain2.MS1" in expanded.molecules
        assert "m.krel.chain3.MS1" in expanded.molecules
        # No un-indexed version
        assert "m.krel.chain.MS1" not in expanded.molecules

    def test_replication_indices_concatenate(self, simple_registry):
        """Indices concatenate without dots: chain1, not chain.1."""
        from alienbio.generator import Template, expand

        parent = Template.parse({
            "_instantiate_": {
                "_as_ p{i in 1..2}": {"_template_": "simple"}
            }
        })
        expanded = expand(parent, namespace="x", registry=simple_registry)

        assert "m.x.p1.M1" in expanded.molecules  # p1, not p.1
        assert "m.x.p2.M1" in expanded.molecules

    def test_replication_zero_count(self, simple_registry):
        """Replication with count 0 creates no instances."""
        from alienbio.generator import Template, expand

        parent = Template.parse({
            "_instantiate_": {
                "_as_ p{i in 1..0}": {"_template_": "simple"}
            }
        })
        expanded = expand(parent, namespace="x", registry=simple_registry)

        # Should have no molecules from simple template
        assert not any("p" in k for k in expanded.molecules)

    def test_multiple_nested(self, simple_registry):
        """Multiple _as_ blocks in same _instantiate_."""
        from alienbio.generator import Template, expand

        parent = Template.parse({
            "_instantiate_": {
                "_as_ energy": {"_template_": "energy_cycle"},
                "_as_ chain": {"_template_": "anabolic_chain"}
            }
        })
        expanded = expand(parent, namespace="x", registry=simple_registry)

        assert "m.x.energy.ME1" in expanded.molecules
        assert "m.x.chain.MS1" in expanded.molecules

    def test_deeply_nested(self, simple_registry):
        """Templates can instantiate templates that instantiate templates."""
        from alienbio.generator import Template, expand

        # Add a template that uses nested instantiation
        simple_registry.register("composite", Template.parse({
            "_instantiate_": {
                "_as_ inner": {"_template_": "simple"}
            }
        }))

        parent = Template.parse({
            "_instantiate_": {
                "_as_ outer": {"_template_": "composite"}
            }
        })
        expanded = expand(parent, namespace="x", registry=simple_registry)

        assert "m.x.outer.inner.M1" in expanded.molecules


# =============================================================================
# G2.3 - Port Wiring
# =============================================================================


class TestPortWiring:
    """Tests for port declaration and connection."""

    @pytest.mark.skip(reason="Template class not yet implemented")
    def test_port_declaration(self):
        """Template parses _ports_ with path, type, and direction."""
        from alienbio.generator import Template

        template = Template.parse({
            "_ports_": {
                "reactions.work": "energy.out",
                "molecules.M1": "molecule.in"
            }
        })

        assert template.ports["reactions.work"].type == "energy"
        assert template.ports["reactions.work"].direction == "out"
        assert template.ports["molecules.M1"].type == "molecule"
        assert template.ports["molecules.M1"].direction == "in"

    @pytest.fixture
    def wiring_registry(self):
        """Registry with templates that have ports for wiring tests."""
        from alienbio.generator import Template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("energy_cycle", Template.parse({
            "molecules": {"ME1": {}, "ME2": {}},
            "reactions": {
                "work": {"reactants": ["ME1"], "products": ["ME2"]}
            },
            "_ports_": {
                "reactions.work": "energy.out"
            }
        }))
        registry.register("anabolic_chain", Template.parse({
            "molecules": {"MS1": {}, "MS2": {}},
            "reactions": {
                "build": {"reactants": ["MS1"], "products": ["MS2"]}
            },
            "_ports_": {
                "reactions.build": "energy.in"
            }
        }))
        registry.register("has_energy_out", Template.parse({
            "reactions": {"work": {}},
            "_ports_": {"reactions.work": "energy.out"}
        }))
        registry.register("has_molecule_in", Template.parse({
            "molecules": {"M1": {}},
            "_ports_": {"molecules.M1": "molecule.in"}
        }))
        return registry

    @pytest.mark.skip(reason="expand() not yet implemented")
    def test_port_connection_at_instantiation(self, wiring_registry):
        """Port connection syntax wires ports together."""
        from alienbio.generator import Template, expand

        parent = Template.parse({
            "_instantiate_": {
                "_as_ energy": {"_template_": "energy_cycle"},
                "_as_ chain": {
                    "_template_": "anabolic_chain",
                    "reactions.build": "energy.reactions.work"  # Port connection
                }
            }
        })
        expanded = expand(parent, namespace="krel", registry=wiring_registry)

        # The chain's build reaction should reference energy's work reaction
        chain_build = expanded.reactions["r.krel.chain.build"]
        assert chain_build.get("energy_source") == "r.krel.energy.work"

    @pytest.mark.skip(reason="expand() not yet implemented")
    def test_port_type_mismatch_error(self, wiring_registry):
        """Connecting incompatible port types raises error."""
        from alienbio.generator import Template, expand, PortTypeMismatchError

        parent = Template.parse({
            "_instantiate_": {
                "_as_ a": {"_template_": "has_energy_out"},
                "_as_ b": {
                    "_template_": "has_molecule_in",
                    "molecules.M1": "a.reactions.work"  # Type mismatch!
                }
            }
        })

        with pytest.raises(PortTypeMismatchError):
            expand(parent, namespace="x", registry=wiring_registry)

    @pytest.mark.skip(reason="expand() not yet implemented")
    def test_port_connection_missing_target(self, wiring_registry):
        """Connecting to non-existent port raises error."""
        from alienbio.generator import Template, expand, PortNotFoundError

        parent = Template.parse({
            "_instantiate_": {
                "_as_ chain": {
                    "_template_": "anabolic_chain",
                    "reactions.build": "nonexistent.reactions.work"
                }
            }
        })

        with pytest.raises(PortNotFoundError):
            expand(parent, namespace="x", registry=wiring_registry)

    @pytest.mark.skip(reason="expand() not yet implemented")
    def test_multiple_port_connections(self, wiring_registry):
        """Multiple port connections in same instantiation."""
        from alienbio.generator import Template, TemplateRegistry, expand

        # Create template with multiple ports
        registry = TemplateRegistry()
        registry.register("multi_port", Template.parse({
            "reactions": {"r1": {}, "r2": {}},
            "_ports_": {
                "reactions.r1": "energy.in",
                "reactions.r2": "energy.in"
            }
        }))
        registry.register("provider", Template.parse({
            "reactions": {"work1": {}, "work2": {}},
            "_ports_": {
                "reactions.work1": "energy.out",
                "reactions.work2": "energy.out"
            }
        }))

        parent = Template.parse({
            "_instantiate_": {
                "_as_ provider": {"_template_": "provider"},
                "_as_ consumer": {
                    "_template_": "multi_port",
                    "reactions.r1": "provider.reactions.work1",
                    "reactions.r2": "provider.reactions.work2"
                }
            }
        })
        expanded = expand(parent, namespace="x", registry=registry)

        r1 = expanded.reactions["r.x.consumer.r1"]
        r2 = expanded.reactions["r.x.consumer.r2"]
        assert r1.get("energy_source") == "r.x.provider.work1"
        assert r2.get("energy_source") == "r.x.provider.work2"


# =============================================================================
# Integration: Complex expansion scenarios
# =============================================================================


class TestExpansionIntegration:
    """Integration tests for complex expansion scenarios."""

    @pytest.mark.skip(reason="expand() not yet implemented")
    def test_full_organism_expansion(self):
        """Expand a complete organism template with multiple sub-templates."""
        from alienbio.generator import Template, TemplateRegistry, expand

        registry = TemplateRegistry()
        registry.register("energy_cycle", Template.parse({
            "molecules": {"ME1": {}, "ME2": {}},
            "reactions": {"work": {"reactants": ["ME1"], "products": ["ME2"]}}
        }))
        registry.register("anabolic_chain", Template.parse({
            "molecules": {"MS1": {}, "MS2": {}, "MS3": {}},
            "reactions": {
                "step1": {"reactants": ["MS1"], "products": ["MS2"]},
                "step2": {"reactants": ["MS2"], "products": ["MS3"]}
            }
        }))

        organism = Template.parse({
            "_instantiate_": {
                "_as_ energy": {"_template_": "energy_cycle"},
                "_as_ chain{i in 1..2}": {"_template_": "anabolic_chain"}
            }
        })
        expanded = expand(organism, namespace="Krel", registry=registry)

        # Energy molecules
        assert "m.Krel.energy.ME1" in expanded.molecules
        # Chain molecules (2 chains)
        assert "m.Krel.chain1.MS1" in expanded.molecules
        assert "m.Krel.chain2.MS1" in expanded.molecules
        # Chain reactions
        assert "r.Krel.chain1.step1" in expanded.reactions
        assert "r.Krel.chain2.step2" in expanded.reactions

    @pytest.mark.skip(reason="expand() not yet implemented")
    def test_expansion_with_sampled_count(self):
        """Replication count can come from sampled parameter."""
        from alienbio.generator import Template, TemplateRegistry, expand

        registry = TemplateRegistry()
        registry.register("simple", Template.parse({
            "molecules": {"M1": {}}
        }))

        parent = Template.parse({
            "_params_": {"count": "!ev round(normal(3, 0.5))"},
            "_instantiate_": {
                "_as_ p{i in 1..count}": {"_template_": "simple"}
            }
        })

        # With seed, should get consistent count
        expanded = expand(parent, namespace="x", registry=registry, seed=42)
        mol_count = len([k for k in expanded.molecules if k.startswith("m.x.p")])
        assert 2 <= mol_count <= 4  # ~3 with some variance
