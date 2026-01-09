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
from ..spec_lang.eval import Evaluable, Quoted, Reference, eval_node, make_context, Context
from .template import Template, Port, TemplateRegistry
from .exceptions import PortTypeMismatchError, PortNotFoundError


@dataclass
class ExpandedPort:
    """A port with its namespaced path."""

    port: Port
    namespaced_path: str  # e.g., "r.krel.energy.work"


@dataclass
class ExpandedTemplate:
    """Result of expanding a template.

    Contains namespaced molecules and reactions, with all references resolved.
    """

    molecules: dict[str, dict[str, Any]] = field(default_factory=dict)
    reactions: dict[str, dict[str, Any]] = field(default_factory=dict)
    ports: dict[str, ExpandedPort] = field(default_factory=dict)

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
    _ctx: Context | None = None,
) -> ExpandedTemplate:
    """Expand a template with namespace prefixing.

    Args:
        template: Template to expand
        namespace: Namespace prefix (e.g., "krel")
        params: Parameter overrides (defaults come from template._params_)
        registry: Registry for resolving nested template references
        seed: Random seed for distribution sampling
        _ctx: Internal - evaluation context (created if not provided)

    Returns:
        ExpandedTemplate with namespaced molecules and reactions
    """
    # Create evaluation context if not provided
    if _ctx is None:
        _ctx = make_context(seed=seed)

    # Merge params with template defaults
    effective_params = dict(template.params)
    if params:
        effective_params.update(params)

    # Evaluate any !ev expressions in params (two-pass to handle dependencies)
    effective_params = _eval_params(effective_params, _ctx)

    result = ExpandedTemplate()

    # Get set of molecule names for reference updating
    molecule_names = set(template.molecules.keys())

    # Expand molecules with namespace prefix
    for name, mol_data in template.molecules.items():
        namespaced_name = f"m.{namespace}.{name}"
        # Deep copy, resolve refs, and evaluate !ev expressions
        expanded_data = _resolve_and_eval(mol_data, effective_params, _ctx)
        result.molecules[namespaced_name] = expanded_data

    # Expand reactions with namespace prefix
    for name, rxn_data in template.reactions.items():
        namespaced_name = f"r.{namespace}.{name}"
        # Deep copy, resolve refs, and evaluate !ev expressions
        expanded_data = _resolve_and_eval(rxn_data, effective_params, _ctx)
        # Update molecule references in reactants/products
        expanded_data = _namespace_molecule_refs(expanded_data, namespace, molecule_names)
        result.reactions[namespaced_name] = expanded_data

    # Expand ports with namespace prefix
    for path, port in template.ports.items():
        # Determine namespaced path based on port path
        if path.startswith("reactions."):
            rxn_name = path[len("reactions."):]
            namespaced_path = f"r.{namespace}.{rxn_name}"
        elif path.startswith("molecules."):
            mol_name = path[len("molecules."):]
            namespaced_path = f"m.{namespace}.{mol_name}"
        else:
            namespaced_path = f"{namespace}.{path}"

        # Store port with full namespaced key for lookup
        port_key = f"{namespace}.{path}"
        result.ports[port_key] = ExpandedPort(port=port, namespaced_path=namespaced_path)

    # Handle nested instantiation in two passes:
    # Pass 1: Expand all templates without port connections
    # Pass 2: Apply port connections (need all templates expanded first)
    if template.instantiate and registry:
        # Pass 1: Collect expansions
        expansions: list[tuple[str, dict[str, Any], ExpandedTemplate]] = []

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
                    # Resolve end value (could be a param reference or evaluated value)
                    if end_expr.isdigit():
                        end_val = int(end_expr)
                    else:
                        param_val = effective_params.get(end_expr, 0)
                        # Handle case where param is a float (from distribution sampling)
                        end_val = int(round(param_val)) if isinstance(param_val, float) else int(param_val)

                    for i in range(start_val, end_val + 1):
                        sub_namespace = f"{namespace}.{inst_name}{i}"
                        sub_result = _instantiate_nested(
                            inst_data, sub_namespace, registry, effective_params, _ctx
                        )
                        expansions.append((sub_namespace, inst_data, sub_result))
                        result.merge(sub_result)
                else:
                    # Single instantiation: _as_ name
                    sub_namespace = f"{namespace}.{inst_name}"
                    sub_result = _instantiate_nested(
                        inst_data, sub_namespace, registry, effective_params, _ctx
                    )
                    expansions.append((sub_namespace, inst_data, sub_result))
                    result.merge(sub_result)

        # Pass 2: Apply port connections now that all templates are expanded
        for sub_namespace, inst_data, sub_result in expansions:
            # Extract port connections from inst_data
            port_connections = {
                k: v for k, v in inst_data.items()
                if k != "_template_"
                and isinstance(v, str) and "." in v
                and (k.startswith("reactions.") or k.startswith("molecules."))
            }

            if port_connections:
                template_name = inst_data.get("_template_")
                if template_name:
                    sub_template = registry.get(template_name)
                    _apply_port_connections(
                        sub_result, port_connections, result, sub_namespace, namespace, sub_template
                    )

    return result


def _instantiate_nested(
    inst_data: dict[str, Any],
    namespace: str,
    registry: TemplateRegistry,
    parent_params: dict[str, Any],
    ctx: Context,
    parent_result: ExpandedTemplate | None = None,
    parent_namespace: str | None = None,
) -> ExpandedTemplate:
    """Instantiate a nested template with port wiring support."""
    template_name = inst_data.get("_template_")
    if not template_name:
        return ExpandedTemplate()

    # Get the template
    template = registry.get(template_name)

    # Separate port connections from params
    # Port connections look like "reactions.build": "other.reactions.work"
    inst_params = {}
    port_connections: dict[str, str] = {}

    for k, v in inst_data.items():
        if k == "_template_":
            continue
        # Check if this is a port connection (value contains a dot and references another instance)
        if isinstance(v, str) and "." in v and (
            k.startswith("reactions.") or k.startswith("molecules.")
        ):
            port_connections[k] = v
        else:
            inst_params[k] = v

    # Resolve any refs and evaluate !ev in inst_params
    inst_params = _resolve_and_eval(inst_params, parent_params, ctx)

    # Expand the template
    result = expand(template, namespace, params=inst_params, registry=registry, _ctx=ctx)

    # Apply port connections
    if port_connections and parent_result is not None and parent_namespace is not None:
        _apply_port_connections(
            result, port_connections, parent_result, namespace, parent_namespace, template
        )

    return result


def _apply_port_connections(
    result: ExpandedTemplate,
    port_connections: dict[str, str],
    parent_result: ExpandedTemplate,
    namespace: str,
    parent_namespace: str,
    template: Template,
) -> None:
    """Apply port connections by updating target reactions with source references."""
    for local_port_path, target_ref in port_connections.items():
        # Parse target reference: "other_inst.reactions.work" or "other_inst.molecules.M1"
        parts = target_ref.split(".", 1)
        if len(parts) != 2:
            raise PortNotFoundError(target_ref, f"in instantiation at {namespace}")

        target_inst_name, target_path = parts

        # Build the full port keys
        local_port_key = f"{namespace}.{local_port_path}"
        target_port_key = f"{parent_namespace}.{target_inst_name}.{target_path}"

        # Lookup ports
        local_expanded_port = result.ports.get(local_port_key)
        target_expanded_port = parent_result.ports.get(target_port_key)

        if target_expanded_port is None:
            raise PortNotFoundError(target_ref, f"referenced from {namespace}")

        # If local port exists, validate types
        if local_expanded_port is not None:
            local_port = local_expanded_port.port
            target_port = target_expanded_port.port

            if not local_port.compatible_with(target_port):
                raise PortTypeMismatchError(
                    local_port_path,
                    f"{local_port.type}.{local_port.direction}",
                    target_ref,
                    f"{target_port.type}.{target_port.direction}",
                )

        # Apply the connection by updating the local reaction/molecule
        if local_port_path.startswith("reactions."):
            rxn_name = local_port_path[len("reactions."):]
            namespaced_rxn = f"r.{namespace}.{rxn_name}"
            if namespaced_rxn in result.reactions:
                result.reactions[namespaced_rxn]["energy_source"] = target_expanded_port.namespaced_path
        elif local_port_path.startswith("molecules."):
            mol_name = local_port_path[len("molecules."):]
            namespaced_mol = f"m.{namespace}.{mol_name}"
            if namespaced_mol in result.molecules:
                result.molecules[namespaced_mol]["source"] = target_expanded_port.namespaced_path


def _eval_params(params: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """Evaluate !ev expressions in params, with dependency ordering.

    Evaluates params in order, adding each resolved value to bindings
    so later params can reference earlier ones.
    """
    result = {}
    # Create a child context with bindings for evaluated params
    eval_ctx = Context(
        rng=ctx.rng,
        bindings=dict(ctx.bindings),
        functions=ctx.functions,
        path=ctx.path,
    )

    for key, value in params.items():
        resolved = _resolve_and_eval(value, result, eval_ctx)
        result[key] = resolved
        # Add to bindings for subsequent params
        eval_ctx.bindings[key] = resolved

    return result


def _resolve_and_eval(data: Any, params: dict[str, Any], ctx: Context) -> Any:
    """Recursively resolve !ref and evaluate !ev expressions in data."""
    # Handle Evaluable (!ev) - evaluate the expression
    if isinstance(data, Evaluable):
        # Add current params to context bindings for evaluation
        eval_ctx = Context(
            rng=ctx.rng,
            bindings={**ctx.bindings, **params},
            functions=ctx.functions,
            path=ctx.path,
        )
        return eval_node(data, eval_ctx)

    # Handle Quoted (!_) - preserve as-is
    if isinstance(data, Quoted):
        return data.source

    # Handle Reference (!ref) - look up in params
    if isinstance(data, Reference):
        return params.get(data.name, data)

    # Handle RefTag (legacy)
    if isinstance(data, RefTag):
        return params.get(data.ref, data)

    # Handle string-based tags
    if isinstance(data, str):
        # Check for string-based !ev tag
        if data.startswith("!ev "):
            expr = data[4:].strip()
            eval_ctx = Context(
                rng=ctx.rng,
                bindings={**ctx.bindings, **params},
                functions=ctx.functions,
                path=ctx.path,
            )
            return eval_node(Evaluable(source=expr), eval_ctx)
        # Check for string-based !ref tag
        if data.startswith("!ref "):
            ref_name = data[5:].strip()
            return params.get(ref_name, data)
        return data

    # Recurse into dicts
    if isinstance(data, dict):
        return {k: _resolve_and_eval(v, params, ctx) for k, v in data.items()}

    # Recurse into lists
    if isinstance(data, list):
        return [_resolve_and_eval(item, params, ctx) for item in data]

    return data


def _resolve_refs(data: Any, params: dict[str, Any]) -> Any:
    """Recursively resolve !ref expressions in data (legacy, no eval)."""
    if isinstance(data, RefTag):
        # Resolve reference
        return params.get(data.ref, data)
    elif isinstance(data, Reference):
        return params.get(data.name, data)
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
