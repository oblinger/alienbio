"""Template classes for generator system.

Provides:
- Port: Connection point with type and direction
- Template: Reusable scenario fragment
- TemplateRegistry: Storage and lookup for templates
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .exceptions import TemplateNotFoundError


@dataclass
class Port:
    """A connection point for wiring templates together.

    Ports have a type (e.g., "energy", "molecule") and direction (in/out).
    Ports can only connect if types match and directions are complementary.
    """

    type: str
    direction: str  # "in" or "out"
    path: str  # Path within template, e.g., "reactions.work"

    @classmethod
    def parse(cls, spec: str, path: str) -> Port:
        """Parse a port specification string.

        Args:
            spec: Format "type.direction", e.g., "energy.out"
            path: The path within the template, e.g., "reactions.work"

        Returns:
            Port instance

        Raises:
            ValueError: If spec format is invalid or direction not in/out
        """
        parts = spec.split(".")
        if len(parts) != 2:
            raise ValueError(
                f"Invalid port spec '{spec}': expected 'type.direction' format"
            )

        port_type, direction = parts
        if direction not in ("in", "out"):
            raise ValueError(
                f"Invalid port direction '{direction}': must be 'in' or 'out'"
            )

        return cls(type=port_type, direction=direction, path=path)

    def compatible_with(self, other: Port) -> bool:
        """Check if this port can connect to another port.

        Ports are compatible if:
        - They have the same type
        - They have opposite directions (in connects to out)
        """
        if self.type != other.type:
            return False
        # Opposite directions: in<->out
        return (self.direction == "in" and other.direction == "out") or (
            self.direction == "out" and other.direction == "in"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Port):
            return NotImplemented
        return (
            self.type == other.type
            and self.direction == other.direction
            and self.path == other.path
        )

    def __hash__(self) -> int:
        return hash((self.type, self.direction, self.path))


@dataclass
class Template:
    """A reusable scenario fragment with parameters and ports.

    Templates can contain:
    - params: Default parameter values
    - molecules: Molecule definitions
    - reactions: Reaction definitions
    - ports: Connection points for wiring
    - instantiate: Nested template instantiations
    """

    name: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    ports: dict[str, Port] = field(default_factory=dict)
    molecules: dict[str, dict[str, Any]] = field(default_factory=dict)
    reactions: dict[str, dict[str, Any]] = field(default_factory=dict)
    instantiate: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def parse(cls, data: dict[str, Any], name: str | None = None) -> Template:
        """Parse a template from a dictionary.

        Args:
            data: Template data dictionary
            name: Optional template name

        Returns:
            Template instance
        """
        # Extract special sections
        params = data.get("_params_", {})
        ports_raw = data.get("_ports_", {})
        molecules = data.get("molecules", {})
        reactions = data.get("reactions", {})
        instantiate = data.get("_instantiate_", {})

        # Parse ports
        ports: dict[str, Port] = {}
        for path, spec in ports_raw.items():
            ports[path] = Port.parse(spec, path)

        return cls(
            name=name,
            params=params,
            ports=ports,
            molecules=molecules,
            reactions=reactions,
            instantiate=instantiate,
        )


class TemplateRegistry:
    """Registry for storing and retrieving templates by name.

    Templates can be registered manually or loaded from YAML files.
    Names can be hierarchical paths like "primitives/energy_cycle".
    """

    def __init__(self) -> None:
        self._templates: dict[str, Template] = {}

    def register(self, name: str, template: Template) -> None:
        """Register a template with the given name.

        Args:
            name: Template name (can be path-like, e.g., "primitives/energy_cycle")
            template: Template instance to register
        """
        self._templates[name] = template

    def get(self, name: str) -> Template:
        """Get a template by name.

        Args:
            name: Template name

        Returns:
            Template instance

        Raises:
            TemplateNotFoundError: If template is not registered
        """
        if name not in self._templates:
            raise TemplateNotFoundError(name, list(self._templates.keys()))
        return self._templates[name]

    def __contains__(self, name: str) -> bool:
        """Check if a template is registered."""
        return name in self._templates

    def list_all(self) -> list[str]:
        """List all registered template names."""
        return list(self._templates.keys())

    @classmethod
    def from_directory(cls, path: Path | str) -> TemplateRegistry:
        """Load templates from a directory of YAML files.

        Directory structure determines template names:
        - templates/primitives/energy_cycle.yaml -> "primitives/energy_cycle"
        - templates/organisms/autotroph.yaml -> "organisms/autotroph"

        Args:
            path: Path to templates directory

        Returns:
            TemplateRegistry with loaded templates
        """
        registry = cls()
        base_path = Path(path)

        if not base_path.exists():
            return registry

        # Find all YAML files
        for yaml_file in base_path.rglob("*.yaml"):
            # Compute relative path for template name
            rel_path = yaml_file.relative_to(base_path)
            # Remove .yaml extension and convert to forward slashes
            template_path = str(rel_path.with_suffix(""))

            # Load and parse template
            with open(yaml_file) as f:
                data = yaml.safe_load(f)

            if data is None:
                continue

            # Handle template.name: syntax at top level
            for key, value in data.items():
                if key.startswith("template."):
                    # Extract name from key
                    template_name = key[len("template.") :]
                    template = Template.parse(value, name=template_name)
                    # Use directory path + template name
                    full_name = str(rel_path.parent / template_name)
                    if full_name.startswith("."):
                        full_name = template_name
                    registry.register(full_name, template)
                else:
                    # Assume entire file is a template
                    template = Template.parse(data)
                    registry.register(template_path, template)
                    break  # Only process once if not template.name: format

        return registry
