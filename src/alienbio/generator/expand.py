"""Template expansion with namespace prefixing.

Provides:
- expand(): Expand a template with namespace prefixing
- ExpandedTemplate: Result of template expansion
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..spec_lang import RefTag
from .template import Template, TemplateRegistry


@dataclass
class ExpandedTemplate:
    """Result of expanding a template.

    Contains namespaced molecules and reactions, with all references resolved.
    """

    molecules: dict[str, dict[str, Any]] = field(default_factory=dict)
    reactions: dict[str, dict[str, Any]] = field(default_factory=dict)
    ports: dict[str, Any] = field(default_factory=dict)

    def merge(self, other: ExpandedTemplate) -> None:
        """Merge another expanded template into this one."""
        self.molecules.update(other.molecules)
        self.reactions.update(other.reactions)
        self.ports.update(other.ports)


def expand(
    template: Template,
    namespace: str,
    params: dict[str, Any] | None = None,
    registry: TemplateRegistry | None = None,
    seed: int | None = None,
) -> ExpandedTemplate:
    """Expand a template with namespace prefixing.

    Args:
        template: Template to expand
        namespace: Namespace prefix (e.g., "krel")
        params: Parameter overrides (defaults come from template._params_)
        registry: Registry for resolving nested template references
        seed: Random seed for distribution sampling

    Returns:
        ExpandedTemplate with namespaced molecules and reactions
    """
    # Merge params with template defaults
    effective_params = dict(template.params)
    if params:
        effective_params.update(params)

    result = ExpandedTemplate()

    # Get set of molecule names for reference updating
    molecule_names = set(template.molecules.keys())

    # Expand molecules with namespace prefix
    for name, mol_data in template.molecules.items():
        namespaced_name = f"m.{namespace}.{name}"
        # Deep copy and resolve refs
        expanded_data = _resolve_refs(mol_data, effective_params)
        result.molecules[namespaced_name] = expanded_data

    # Expand reactions with namespace prefix
    for name, rxn_data in template.reactions.items():
        namespaced_name = f"r.{namespace}.{name}"
        # Deep copy and resolve refs
        expanded_data = _resolve_refs(rxn_data, effective_params)
        # Update molecule references in reactants/products
        expanded_data = _namespace_molecule_refs(expanded_data, namespace, molecule_names)
        result.reactions[namespaced_name] = expanded_data

    # Handle nested instantiation
    if template.instantiate and registry:
        for key, inst_data in template.instantiate.items():
            # Parse _as_ syntax
            match = re.match(r"_as_\s+(\w+)(?:\{(\w+)\s+in\s+(\d+)\.\.(\w+)\})?", key)
            if match:
                inst_name = match.group(1)
                loop_var = match.group(2)
                start = match.group(3)
                end_expr = match.group(4)

                if loop_var:
                    # Replication: _as_ name{i in 1..count}
                    start_val = int(start)
                    # Resolve end value (could be a param reference)
                    if end_expr.isdigit():
                        end_val = int(end_expr)
                    else:
                        end_val = int(effective_params.get(end_expr, 0))

                    for i in range(start_val, end_val + 1):
                        sub_namespace = f"{namespace}.{inst_name}{i}"
                        sub_result = _instantiate_nested(
                            inst_data, sub_namespace, registry, effective_params, seed
                        )
                        result.merge(sub_result)
                else:
                    # Single instantiation: _as_ name
                    sub_namespace = f"{namespace}.{inst_name}"
                    sub_result = _instantiate_nested(
                        inst_data, sub_namespace, registry, effective_params, seed
                    )
                    result.merge(sub_result)

    return result


def _instantiate_nested(
    inst_data: dict[str, Any],
    namespace: str,
    registry: TemplateRegistry,
    parent_params: dict[str, Any],
    seed: int | None,
) -> ExpandedTemplate:
    """Instantiate a nested template."""
    template_name = inst_data.get("_template_")
    if not template_name:
        return ExpandedTemplate()

    # Get the template
    template = registry.get(template_name)

    # Build params: template defaults + parent overrides + instantiation overrides
    inst_params = {
        k: v for k, v in inst_data.items()
        if k != "_template_"
    }
    # Resolve any refs in inst_params
    inst_params = _resolve_refs(inst_params, parent_params)

    return expand(template, namespace, params=inst_params, registry=registry, seed=seed)


def _resolve_refs(data: Any, params: dict[str, Any]) -> Any:
    """Recursively resolve !ref expressions in data."""
    if isinstance(data, RefTag):
        # Resolve reference
        return params.get(data.ref, data)
    elif isinstance(data, str):
        # Check for string-based ref tag (from YAML)
        if data.startswith("!ref "):
            ref_name = data[5:].strip()
            return params.get(ref_name, data)
        return data
    elif isinstance(data, dict):
        return {k: _resolve_refs(v, params) for k, v in data.items()}
    elif isinstance(data, list):
        return [_resolve_refs(item, params) for item in data]
    else:
        return data


def _namespace_molecule_refs(
    data: Any, namespace: str, molecule_names: set[str]
) -> Any:
    """Update molecule references to use namespaced names."""
    if isinstance(data, str):
        # Check if this is a molecule reference
        if data in molecule_names:
            return f"m.{namespace}.{data}"
        return data
    elif isinstance(data, dict):
        return {k: _namespace_molecule_refs(v, namespace, molecule_names) for k, v in data.items()}
    elif isinstance(data, list):
        return [_namespace_molecule_refs(item, namespace, molecule_names) for item in data]
    else:
        return data
