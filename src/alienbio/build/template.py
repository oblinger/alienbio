"""Template parsing and registry for generator system.

Provides:
- parse_port(): Parse port specification to dict
- ports_compatible(): Check if two ports can connect
- parse_template(): Parse template data to dict
- TemplateRegistry: Storage and lookup for templates
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .exceptions import TemplateNotFoundError


# =============================================================================
# Port Functions
# =============================================================================


def parse_port(spec: str, path: str) -> dict[str, str]:
    """Parse a port specification string.

    Args:
        spec: Format "type.direction", e.g., "energy.out"
        path: The path within the template, e.g., "reactions.work"

    Returns:
        Port dict with keys: type, direction, path

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

    return {"type": port_type, "direction": direction, "path": path}


def ports_compatible(port1: dict[str, str], port2: dict[str, str]) -> bool:
    """Check if two ports can connect.

    Ports are compatible if:
    - They have the same type
    - They have opposite directions (in connects to out)

    Args:
        port1: First port dict
        port2: Second port dict

    Returns:
        True if ports are compatible
    """
    if port1["type"] != port2["type"]:
        return False
    # Opposite directions: in<->out
    return (port1["direction"] == "in" and port2["direction"] == "out") or (
        port1["direction"] == "out" and port2["direction"] == "in"
    )


# =============================================================================
# Template Functions
# =============================================================================


def parse_template(data: dict[str, Any], name: str | None = None) -> dict[str, Any]:
    """Parse a template from a dictionary.

    Args:
        data: Template data dictionary
        name: Optional template name

    Returns:
        Template dict with keys: name, params, ports, molecules, reactions, instantiate, requires
    """
    # Extract special sections
    params = data.get("_params_", {})
    ports_raw = data.get("_ports_", {})
    molecules = data.get("molecules", {})
    reactions = data.get("reactions", {})
    instantiate = data.get("_instantiate_", {})
    requires = data.get("requires", [])

    # Parse ports
    ports: dict[str, dict[str, str]] = {}
    for path, spec in ports_raw.items():
        ports[path] = parse_port(spec, path)

    return {
        "name": name,
        "params": params,
        "ports": ports,
        "molecules": molecules,
        "reactions": reactions,
        "instantiate": instantiate,
        "requires": requires,
    }


def parse_interaction(data: dict[str, Any]) -> dict[str, Any]:
    """Parse an interaction specification.

    Interactions connect multiple instantiated templates together.

    Args:
        data: Interaction data with _template_, between, and optional params

    Returns:
        Dict with keys: template, between, params

    Example:
        parse_interaction({
            "_template_": "cross_feeding",
            "between": ["Krel", "Kova"],
            "rate": 0.1
        })
        # Returns: {
        #     "template": "cross_feeding",
        #     "between": ["Krel", "Kova"],
        #     "params": {"rate": 0.1}
        # }
    """
    template = data.get("_template_")
    between = data.get("between", [])

    # All non-special keys are params
    params = {}
    for key, value in data.items():
        if key not in ("_template_", "between"):
            params[key] = value

    return {
        "template": template,
        "between": between,
        "params": params,
    }


def parse_background(data: dict[str, Any]) -> dict[str, Any]:
    """Parse a background generation specification.

    Background generation creates random filler molecules and reactions.

    Args:
        data: Background spec with molecules and reactions config

    Returns:
        Dict with molecules and reactions config

    Example:
        parse_background({
            "molecules": {"count": 10},
            "reactions": {"count": 5}
        })
        # Returns: {
        #     "molecules": {"count": 10},
        #     "reactions": {"count": 5}
        # }
    """
    return {
        "molecules": data.get("molecules", {}),
        "reactions": data.get("reactions", {}),
    }


# =============================================================================
# Template Registry
# =============================================================================


class TemplateRegistry:
    """Registry for storing and retrieving templates by name.

    Templates can be registered manually or loaded from YAML files.
    Names can be hierarchical paths like "primitives/energy_cycle".
    """

    def __init__(self) -> None:
        self._templates: dict[str, dict[str, Any]] = {}

    def register(self, name: str, template: dict[str, Any]) -> None:
        """Register a template with the given name.

        Args:
            name: Template name (can be path-like, e.g., "primitives/energy_cycle")
            template: Template dict to register
        """
        self._templates[name] = template

    def get(self, name: str) -> dict[str, Any]:
        """Get a template by name.

        Args:
            name: Template name

        Returns:
            Template dict

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
                    template_name = key[len("template."):]
                    template = parse_template(value, name=template_name)
                    # Use directory path + template name
                    full_name = str(rel_path.parent / template_name)
                    if full_name.startswith("."):
                        full_name = template_name
                    registry.register(full_name, template)
                else:
                    # Assume entire file is a template
                    template = parse_template(data)
                    registry.register(template_path, template)
                    break  # Only process once if not template.name: format

        return registry

