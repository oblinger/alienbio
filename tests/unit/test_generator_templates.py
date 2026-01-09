"""Tests for Generator Phase G1: Template Representation & Parsing.

These tests define expected behavior for template data structures and registry.
See [[Generator Spec Language]] for YAML syntax specification.

Test categories:
- G1.1: Template Data Structures (Template, Port classes)
- G1.2: Template Registry (registration, lookup, loading from files)
"""

from __future__ import annotations

import pytest
import yaml
from pathlib import Path


# =============================================================================
# G1.1 - Template Data Structures
# =============================================================================


class TestTemplateDataStructures:
    """Tests for Template and Port classes."""

    def test_template_has_params(self):
        """Template parses _params_ section into params dict."""
        from alienbio.generator import Template

        t = Template.parse({
            "_params_": {"rate": 0.1, "count": 5},
            "molecules": {}
        })
        assert t.params["rate"] == 0.1
        assert t.params["count"] == 5

    
    def test_template_has_ports(self):
        """Template parses _ports_ section with type and direction."""
        from alienbio.generator import Template

        t = Template.parse({
            "_ports_": {
                "reactions.work": "energy.out",
                "molecules.M1": "molecule.in"
            }
        })
        assert t.ports["reactions.work"].type == "energy"
        assert t.ports["reactions.work"].direction == "out"
        assert t.ports["molecules.M1"].type == "molecule"
        assert t.ports["molecules.M1"].direction == "in"

    
    def test_template_has_molecules_and_reactions(self):
        """Template parses molecules and reactions sections."""
        from alienbio.generator import Template

        t = Template.parse({
            "molecules": {
                "M1": {"role": "energy"},
                "M2": {"role": "energy"}
            },
            "reactions": {
                "r1": {"reactants": ["M1"], "products": ["M2"]}
            }
        })
        assert "M1" in t.molecules
        assert "M2" in t.molecules
        assert "r1" in t.reactions
        assert t.molecules["M1"]["role"] == "energy"

    
    def test_template_empty_sections(self):
        """Template handles missing optional sections."""
        from alienbio.generator import Template

        t = Template.parse({"molecules": {"M1": {}}})
        assert t.params == {}
        assert t.ports == {}
        assert t.reactions == {}
        assert "M1" in t.molecules

    
    def test_template_name_from_typed_key(self):
        """Template extracts name from template.name: syntax."""
        from alienbio.generator import Template

        data = yaml.safe_load("""
        template.energy_cycle:
          molecules:
            ME1: {role: energy}
        """)
        key = list(data.keys())[0]
        t = Template.parse(data[key], name="energy_cycle")
        assert t.name == "energy_cycle"

    
    def test_template_with_instantiate_block(self):
        """Template can have _instantiate_ section for nesting."""
        from alienbio.generator import Template

        t = Template.parse({
            "_instantiate_": {
                "_as_ energy": {"_template_": "energy_cycle"}
            },
            "molecules": {}
        })
        assert "_as_ energy" in t.instantiate
        assert t.instantiate["_as_ energy"]["_template_"] == "energy_cycle"


class TestPortClass:
    """Tests for Port data class."""

    
    def test_port_from_string_out(self):
        """Port.parse handles 'type.out' format."""
        from alienbio.generator import Port

        p = Port.parse("energy.out", path="reactions.work")
        assert p.type == "energy"
        assert p.direction == "out"
        assert p.path == "reactions.work"

    
    def test_port_from_string_in(self):
        """Port.parse handles 'type.in' format."""
        from alienbio.generator import Port

        p = Port.parse("molecule.in", path="molecules.M1")
        assert p.type == "molecule"
        assert p.direction == "in"

    
    def test_port_invalid_direction(self):
        """Port.parse raises on invalid direction."""
        from alienbio.generator import Port

        with pytest.raises(ValueError, match="direction"):
            Port.parse("energy.sideways", path="x")

    
    def test_port_equality(self):
        """Ports with same attributes are equal."""
        from alienbio.generator import Port

        p1 = Port.parse("energy.out", path="reactions.work")
        p2 = Port.parse("energy.out", path="reactions.work")
        assert p1 == p2

    
    def test_port_compatible(self):
        """Ports are compatible if types match and directions are in/out."""
        from alienbio.generator import Port

        out_port = Port.parse("energy.out", path="r.work")
        in_port = Port.parse("energy.in", path="r.consume")
        assert out_port.compatible_with(in_port)
        assert in_port.compatible_with(out_port)

    
    def test_port_incompatible_type(self):
        """Ports with different types are incompatible."""
        from alienbio.generator import Port

        energy_port = Port.parse("energy.out", path="r.work")
        molecule_port = Port.parse("molecule.in", path="m.M1")
        assert not energy_port.compatible_with(molecule_port)


# =============================================================================
# G1.2 - Template Registry
# =============================================================================


class TestTemplateRegistry:
    """Tests for TemplateRegistry class."""

    
    def test_template_registration(self):
        """Registry stores and retrieves templates by name."""
        from alienbio.generator import Template, TemplateRegistry

        registry = TemplateRegistry()
        template = Template.parse({"molecules": {"M1": {}}})
        registry.register("my_template", template)
        assert registry.get("my_template") is template

    
    def test_template_not_found(self):
        """Registry raises TemplateNotFoundError for missing templates."""
        from alienbio.generator import TemplateRegistry, TemplateNotFoundError

        registry = TemplateRegistry()
        with pytest.raises(TemplateNotFoundError):
            registry.get("nonexistent")

    
    def test_template_not_found_message(self):
        """TemplateNotFoundError includes the template name."""
        from alienbio.generator import TemplateRegistry, TemplateNotFoundError

        registry = TemplateRegistry()
        with pytest.raises(TemplateNotFoundError) as exc:
            registry.get("my_missing_template")
        assert "my_missing_template" in str(exc.value)

    
    def test_registry_contains(self):
        """Registry supports 'in' operator for checking existence."""
        from alienbio.generator import Template, TemplateRegistry

        registry = TemplateRegistry()
        template = Template.parse({"molecules": {}})
        registry.register("exists", template)

        assert "exists" in registry
        assert "missing" not in registry

    
    def test_template_from_yaml_file(self, tmp_path):
        """Registry loads templates from YAML files."""
        from alienbio.generator import TemplateRegistry

        # Create template file
        template_dir = tmp_path / "templates" / "primitives"
        template_dir.mkdir(parents=True)
        template_file = template_dir / "energy_cycle.yaml"
        template_file.write_text("""
template.energy_cycle:
  _params_:
    rate: 0.1
  molecules:
    ME1: {role: energy}
    ME2: {role: energy}
  reactions:
    activation:
      reactants: [ME1]
      products: [ME2]
      rate: !ref rate
""")
        registry = TemplateRegistry.from_directory(tmp_path / "templates")
        assert "primitives/energy_cycle" in registry

    
    def test_template_nested_path(self, tmp_path):
        """Registry handles nested directory paths."""
        from alienbio.generator import TemplateRegistry

        # Create nested template
        nested_dir = tmp_path / "templates" / "organisms" / "producers"
        nested_dir.mkdir(parents=True)
        (nested_dir / "autotroph.yaml").write_text("""
template.autotroph:
  molecules:
    ATP: {role: energy}
""")
        registry = TemplateRegistry.from_directory(tmp_path / "templates")
        assert "organisms/producers/autotroph" in registry

    
    def test_registry_list_all(self):
        """Registry lists all registered template names."""
        from alienbio.generator import Template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("a", Template.parse({}))
        registry.register("b", Template.parse({}))
        registry.register("c", Template.parse({}))

        names = registry.list_all()
        assert set(names) == {"a", "b", "c"}

    
    def test_registry_overwrite(self):
        """Registering same name overwrites previous template."""
        from alienbio.generator import Template, TemplateRegistry

        registry = TemplateRegistry()
        t1 = Template.parse({"molecules": {"M1": {}}})
        t2 = Template.parse({"molecules": {"M2": {}}})

        registry.register("same", t1)
        registry.register("same", t2)

        retrieved = registry.get("same")
        assert "M2" in retrieved.molecules
        assert "M1" not in retrieved.molecules


# =============================================================================
# Integration: Template parsing from real YAML
# =============================================================================


class TestTemplateYAMLParsing:
    """Integration tests for parsing templates from YAML strings."""

    
    def test_parse_full_template(self):
        """Parse a complete template with all sections."""
        from alienbio.generator import Template

        yaml_str = """
        _params_:
          rate: 0.1
          efficiency: 0.8
        molecules:
          ME1: {role: energy, description: "High energy carrier"}
          ME2: {role: energy, description: "Low energy carrier"}
        reactions:
          work:
            reactants: [ME1]
            products: [ME2]
            rate: !ref rate
        _ports_:
          reactions.work: energy.out
        """
        data = yaml.safe_load(yaml_str)
        t = Template.parse(data)

        assert t.params["rate"] == 0.1
        assert t.params["efficiency"] == 0.8
        assert len(t.molecules) == 2
        assert len(t.reactions) == 1
        assert "reactions.work" in t.ports

    
    def test_parse_template_with_instantiate(self):
        """Parse template with nested instantiation."""
        from alienbio.generator import Template

        yaml_str = """
        _params_:
          chain_count: 3
        _instantiate_:
          _as_ energy:
            _template_: energy_cycle
            rate: 0.2
          _as_ chain{i in 1..chain_count}:
            _template_: anabolic_chain
            length: 5
        molecules: {}
        """
        data = yaml.safe_load(yaml_str)
        t = Template.parse(data)

        assert "_as_ energy" in t.instantiate
        assert "_as_ chain{i in 1..chain_count}" in t.instantiate
