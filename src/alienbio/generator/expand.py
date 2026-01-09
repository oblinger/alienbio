"""Template application with namespace prefixing.

Provides:
- apply_template(): Apply a template to produce namespaced molecules and reactions
"""

from __future__ import annotations

import re
from typing import Any

from ..spec_lang import RefTag
from ..spec_lang.eval import Evaluable, Quoted, Reference, eval_node, make_context, Context
from .template import TemplateRegistry, ports_compatible
from .exceptions import PortTypeMismatchError, PortNotFoundError


def _to_template_dict(template: Any) -> dict[str, Any]:
    """Convert a Template object or dict to a template dict.

    Handles backwards compatibility with the deprecated Template class.
    """
    if isinstance(template, dict):
        return template
    # Handle deprecated Template class
    if hasattr(template, "params"):
        return {
            "name": getattr(template, "name", None),
            "params": template.params,
            "ports": {k: {"type": v.type, "direction": v.direction, "path": v.path}
                      for k, v in template.ports.items()},
            "molecules": template.molecules,
            "reactions": template.reactions,
            "instantiate": template.instantiate,
        }
    return template


def apply_template(
    template: dict[str, Any],
    namespace: str,
    params: dict[str, Any] | None = None,
    registry: TemplateRegistry | None = None,
    seed: int | None = None,
    _ctx: Context | None = None,
) -> dict[str, Any]:
    """Apply a template with namespace prefixing.

    Args:
        template: Template dict to apply
        namespace: Namespace prefix (e.g., "krel")
        params: Parameter overrides (defaults come from template params)
        registry: Registry for resolving nested template references
        seed: Random seed for distribution sampling
        _ctx: Internal - evaluation context (created if not provided)

    Returns:
        Dict with "molecules" and "reactions" keys, all namespaced
    """
    # Create evaluation context if not provided
    if _ctx is None:
        _ctx = make_context(seed=seed)

    # Merge params with template defaults
    effective_params = dict(template.get("params", {}))
    if params:
        effective_params.update(params)

    # Evaluate any !ev expressions in params (two-pass to handle dependencies)
    effective_params = _eval_params(effective_params, _ctx)

    result: dict[str, Any] = {"molecules": {}, "reactions": {}}

    # Internal port tracking for wiring (not in output)
    _ports: dict[str, dict[str, Any]] = {}

    # Get set of molecule names for reference updating
    molecule_names = set(template.get("molecules", {}).keys())

    # Apply molecules with namespace prefix
    for name, mol_data in template.get("molecules", {}).items():
        namespaced_name = f"m.{namespace}.{name}"
        # Deep copy, resolve refs, and evaluate !ev expressions
        expanded_data = _resolve_and_eval(mol_data, effective_params, _ctx)
        result["molecules"][namespaced_name] = expanded_data

    # Apply reactions with namespace prefix
    for name, rxn_data in template.get("reactions", {}).items():
        namespaced_name = f"r.{namespace}.{name}"
        # Deep copy, resolve refs, and evaluate !ev expressions
        expanded_data = _resolve_and_eval(rxn_data, effective_params, _ctx)
        # Update molecule references in reactants/products
        expanded_data = _namespace_molecule_refs(expanded_data, namespace, molecule_names)
        result["reactions"][namespaced_name] = expanded_data

    # Track ports with namespace prefix (internal only)
    for path, port in template.get("ports", {}).items():
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
        _ports[port_key] = {"port": port, "namespaced_path": namespaced_path}

    # Handle nested instantiation in two passes:
    # Pass 1: Apply all templates without port connections
    # Pass 2: Apply port connections (need all templates applied first)
    instantiate = template.get("instantiate", {})
    if instantiate and registry:
        # Pass 1: Collect applications
        applications: list[tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]] = []

        for key, inst_data in instantiate.items():
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
                        sub_result, sub_ports = _instantiate_nested(
                            inst_data, sub_namespace, registry, effective_params, _ctx
                        )
                        applications.append((sub_namespace, inst_data, sub_result, sub_ports))
                        result["molecules"].update(sub_result["molecules"])
                        result["reactions"].update(sub_result["reactions"])
                        _ports.update(sub_ports)
                else:
                    # Single instantiation: _as_ name
                    sub_namespace = f"{namespace}.{inst_name}"
                    sub_result, sub_ports = _instantiate_nested(
                        inst_data, sub_namespace, registry, effective_params, _ctx
                    )
                    applications.append((sub_namespace, inst_data, sub_result, sub_ports))
                    result["molecules"].update(sub_result["molecules"])
                    result["reactions"].update(sub_result["reactions"])
                    _ports.update(sub_ports)

        # Pass 2: Apply port connections now that all templates are applied
        for sub_namespace, inst_data, sub_result, sub_ports in applications:
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
                    sub_template = _to_template_dict(registry.get(template_name))
                    _apply_port_connections(
                        result, port_connections, sub_namespace, namespace,
                        sub_template, sub_ports, _ports
                    )

    return result


def _instantiate_nested(
    inst_data: dict[str, Any],
    namespace: str,
    registry: TemplateRegistry,
    parent_params: dict[str, Any],
    ctx: Context,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Instantiate a nested template.

    Returns:
        Tuple of (result dict, ports dict)
    """
    template_name = inst_data.get("_template_")
    if not template_name:
        return {"molecules": {}, "reactions": {}}, {}

    # Get the template and convert if needed
    template = _to_template_dict(registry.get(template_name))

    # Separate port connections from params
    inst_params = {}
    for k, v in inst_data.items():
        if k == "_template_":
            continue
        # Check if this is a port connection
        if isinstance(v, str) and "." in v and (
            k.startswith("reactions.") or k.startswith("molecules.")
        ):
            continue  # Skip port connections, handled in pass 2
        else:
            inst_params[k] = v

    # Resolve any refs and evaluate !ev in inst_params
    inst_params = _resolve_and_eval(inst_params, parent_params, ctx)

    # Apply the template (recursively)
    # We need to track ports internally
    result, ports = _apply_template_with_ports(template, namespace, inst_params, registry, ctx)

    return result, ports


def _apply_template_with_ports(
    template: dict[str, Any],
    namespace: str,
    params: dict[str, Any] | None,
    registry: TemplateRegistry | None,
    ctx: Context,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Internal: apply template and also return ports for wiring."""
    # Merge params with template defaults
    effective_params = dict(template.get("params", {}))
    if params:
        effective_params.update(params)

    # Evaluate any !ev expressions in params
    effective_params = _eval_params(effective_params, ctx)

    result: dict[str, Any] = {"molecules": {}, "reactions": {}}
    _ports: dict[str, dict[str, Any]] = {}

    molecule_names = set(template.get("molecules", {}).keys())

    # Apply molecules
    for name, mol_data in template.get("molecules", {}).items():
        namespaced_name = f"m.{namespace}.{name}"
        expanded_data = _resolve_and_eval(mol_data, effective_params, ctx)
        result["molecules"][namespaced_name] = expanded_data

    # Apply reactions
    for name, rxn_data in template.get("reactions", {}).items():
        namespaced_name = f"r.{namespace}.{name}"
        expanded_data = _resolve_and_eval(rxn_data, effective_params, ctx)
        expanded_data = _namespace_molecule_refs(expanded_data, namespace, molecule_names)
        result["reactions"][namespaced_name] = expanded_data

    # Track ports
    for path, port in template.get("ports", {}).items():
        if path.startswith("reactions."):
            rxn_name = path[len("reactions."):]
            namespaced_path = f"r.{namespace}.{rxn_name}"
        elif path.startswith("molecules."):
            mol_name = path[len("molecules."):]
            namespaced_path = f"m.{namespace}.{mol_name}"
        else:
            namespaced_path = f"{namespace}.{path}"

        port_key = f"{namespace}.{path}"
        _ports[port_key] = {"port": port, "namespaced_path": namespaced_path}

    # Handle nested instantiation
    instantiate = template.get("instantiate", {})
    if instantiate and registry:
        applications = []

        for key, inst_data in instantiate.items():
            match = re.match(r"_as_\s+(\w+)(?:\{(\w+)\s+in\s+(\d+)\.\.(\w+)\})?", key)
            if match:
                inst_name = match.group(1)
                loop_var = match.group(2)
                start = match.group(3)
                end_expr = match.group(4)

                if loop_var:
                    start_val = int(start)
                    if end_expr.isdigit():
                        end_val = int(end_expr)
                    else:
                        param_val = effective_params.get(end_expr, 0)
                        end_val = int(round(param_val)) if isinstance(param_val, float) else int(param_val)

                    for i in range(start_val, end_val + 1):
                        sub_namespace = f"{namespace}.{inst_name}{i}"
                        sub_result, sub_ports = _instantiate_nested(
                            inst_data, sub_namespace, registry, effective_params, ctx
                        )
                        applications.append((sub_namespace, inst_data, sub_result, sub_ports))
                        result["molecules"].update(sub_result["molecules"])
                        result["reactions"].update(sub_result["reactions"])
                        _ports.update(sub_ports)
                else:
                    sub_namespace = f"{namespace}.{inst_name}"
                    sub_result, sub_ports = _instantiate_nested(
                        inst_data, sub_namespace, registry, effective_params, ctx
                    )
                    applications.append((sub_namespace, inst_data, sub_result, sub_ports))
                    result["molecules"].update(sub_result["molecules"])
                    result["reactions"].update(sub_result["reactions"])
                    _ports.update(sub_ports)

        # Apply port connections
        for sub_namespace, inst_data, sub_result, sub_ports in applications:
            port_connections = {
                k: v for k, v in inst_data.items()
                if k != "_template_"
                and isinstance(v, str) and "." in v
                and (k.startswith("reactions.") or k.startswith("molecules."))
            }

            if port_connections:
                template_name = inst_data.get("_template_")
                if template_name:
                    sub_template = _to_template_dict(registry.get(template_name))
                    _apply_port_connections(
                        result, port_connections, sub_namespace, namespace,
                        sub_template, sub_ports, _ports
                    )

    return result, _ports


def _apply_port_connections(
    result: dict[str, Any],
    port_connections: dict[str, str],
    namespace: str,
    parent_namespace: str,
    template: dict[str, Any],
    local_ports: dict[str, Any],
    all_ports: dict[str, Any],
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
        local_expanded_port = local_ports.get(local_port_key)
        target_expanded_port = all_ports.get(target_port_key)

        if target_expanded_port is None:
            raise PortNotFoundError(target_ref, f"referenced from {namespace}")

        # If local port exists, validate types
        if local_expanded_port is not None:
            local_port = local_expanded_port["port"]
            target_port = target_expanded_port["port"]

            if not ports_compatible(local_port, target_port):
                raise PortTypeMismatchError(
                    local_port_path,
                    f"{local_port['type']}.{local_port['direction']}",
                    target_ref,
                    f"{target_port['type']}.{target_port['direction']}",
                )

        # Apply the connection by updating the local reaction/molecule
        if local_port_path.startswith("reactions."):
            rxn_name = local_port_path[len("reactions."):]
            namespaced_rxn = f"r.{namespace}.{rxn_name}"
            if namespaced_rxn in result["reactions"]:
                result["reactions"][namespaced_rxn]["energy_source"] = target_expanded_port["namespaced_path"]
        elif local_port_path.startswith("molecules."):
            mol_name = local_port_path[len("molecules."):]
            namespaced_mol = f"m.{namespace}.{mol_name}"
            if namespaced_mol in result["molecules"]:
                result["molecules"][namespaced_mol]["source"] = target_expanded_port["namespaced_path"]


def _eval_params(params: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """Evaluate !ev expressions in params, with dependency ordering."""
    result = {}
    eval_ctx = Context(
        rng=ctx.rng,
        bindings=dict(ctx.bindings),
        functions=ctx.functions,
        path=ctx.path,
    )

    for key, value in params.items():
        resolved = _resolve_and_eval(value, result, eval_ctx)
        result[key] = resolved
        eval_ctx.bindings[key] = resolved

    return result


def _resolve_and_eval(data: Any, params: dict[str, Any], ctx: Context) -> Any:
    """Recursively resolve !ref and evaluate !ev expressions in data."""
    # Handle Evaluable (!ev)
    if isinstance(data, Evaluable):
        eval_ctx = Context(
            rng=ctx.rng,
            bindings={**ctx.bindings, **params},
            functions=ctx.functions,
            path=ctx.path,
        )
        return eval_node(data, eval_ctx)

    # Handle Quoted (!_)
    if isinstance(data, Quoted):
        return data.source

    # Handle Reference (!ref)
    if isinstance(data, Reference):
        return params.get(data.name, data)

    # Handle RefTag (legacy)
    if isinstance(data, RefTag):
        return params.get(data.ref, data)

    # Handle string-based tags
    if isinstance(data, str):
        if data.startswith("!ev "):
            expr = data[4:].strip()
            eval_ctx = Context(
                rng=ctx.rng,
                bindings={**ctx.bindings, **params},
                functions=ctx.functions,
                path=ctx.path,
            )
            return eval_node(Evaluable(source=expr), eval_ctx)
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
        return params.get(data.ref, data)
    elif isinstance(data, Reference):
        return params.get(data.name, data)
    elif isinstance(data, str):
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
        if data in molecule_names:
            return f"m.{namespace}.{data}"
        return data
    elif isinstance(data, dict):
        return {k: _namespace_molecule_refs(v, namespace, molecule_names) for k, v in data.items()}
    elif isinstance(data, list):
        return [_namespace_molecule_refs(item, namespace, molecule_names) for item in data]
    else:
        return data


# =============================================================================
# Backwards Compatibility (deprecated)
# =============================================================================


def expand(
    template: Any,
    namespace: str,
    params: dict[str, Any] | None = None,
    registry: TemplateRegistry | None = None,
    seed: int | None = None,
    _ctx: Context | None = None,
) -> "ExpandedTemplate":
    """Deprecated: Use apply_template() instead."""
    template_dict = _to_template_dict(template)
    result = apply_template(template_dict, namespace, params, registry, seed, _ctx)
    return ExpandedTemplate(
        molecules=result["molecules"],
        reactions=result["reactions"],
    )


class ExpandedTemplate:
    """Deprecated: apply_template() now returns a dict."""

    def __init__(
        self,
        molecules: dict | None = None,
        reactions: dict | None = None,
        ports: dict | None = None,
    ):
        self.molecules = molecules or {}
        self.reactions = reactions or {}
        self.ports = ports or {}

    def merge(self, other: "ExpandedTemplate") -> None:
        self.molecules.update(other.molecules)
        self.reactions.update(other.reactions)
        self.ports.update(other.ports)
