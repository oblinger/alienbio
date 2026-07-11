"""Template application with namespace prefixing.

Provides:
- apply_template(): Apply a template to produce namespaced molecules and reactions
"""

from __future__ import annotations

import re
from typing import Any

from ..spec_lang.eval import Evaluable, Quoted, Reference, eval_node, make_context, EvalContext
from .template import TemplateRegistry, ports_compatible
from .exceptions import PortTypeMismatchError, PortNotFoundError, MissingParameterError, CircularReferenceError

# Pattern for molecule/reaction name expansion: "M{i in 1..3}"
_EXPANSION_RE = re.compile(r'^(.+)\{(\w+)\s+in\s+(\d+)\.\.(\d+)\}(.*)$')


def _expand_keyed_items(
    items: dict[str, Any], params: dict[str, Any], ctx: EvalContext
) -> list[tuple[str, Any]]:
    """Expand keys with {var in start..end} syntax and resolve expressions.

    Returns list of (expanded_name, resolved_data) pairs.
    """
    result = []
    for name, data in items.items():
        match = _EXPANSION_RE.match(name)
        if match:
            prefix, var, start_s, end_s, suffix = match.groups()
            for i in range(int(start_s), int(end_s) + 1):
                expanded_name = f"{prefix}{i}{suffix}"
                # Evaluate data with loop variable available
                loop_ctx = EvalContext(
                    rng=ctx.rng,
                    bindings={**ctx.bindings, **params, var: i},
                    functions=ctx.functions,
                    path=ctx.path,
                )
                expanded_data = _resolve_and_eval(data, {**params, var: i}, loop_ctx)
                result.append((expanded_name, expanded_data))
        else:
            # Normal item — resolve refs and evaluate expressions
            expanded_data = _resolve_and_eval(data, params, ctx)
            result.append((name, expanded_data))
    return result


def apply_template(
    template: dict[str, Any],
    namespace: str,
    params: dict[str, Any] | None = None,
    registry: TemplateRegistry | None = None,
    seed: int | None = None,
    _ctx: EvalContext | None = None,
    _seen: set[str] | None = None,
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

    # Merge params with template defaults, checking for required params
    effective_params = dict(template.get("params", {}))
    if params:
        effective_params.update(params)

    # Check for required params (default is None = required)
    for param_name, param_value in template.get("params", {}).items():
        if param_value is None and (params is None or param_name not in params):
            raise MissingParameterError(param_name)

    # Evaluate any !ev expressions in params (two-pass to handle dependencies)
    effective_params = _eval_params(effective_params, _ctx)

    result: dict[str, Any] = {"molecules": {}, "reactions": {}}

    # Internal port tracking for wiring (not in output)
    _ports: dict[str, dict[str, Any]] = {}

    # Expand molecule/reaction keys with {i in start..end} syntax, then process normally
    expanded_molecules = _expand_keyed_items(
        template.get("molecules", {}), effective_params, _ctx
    )
    molecule_names = set(name for name, _ in expanded_molecules)

    # Apply molecules with namespace prefix
    for name, mol_data in expanded_molecules:
        namespaced_name = f"m.{namespace}.{name}"
        result["molecules"][namespaced_name] = mol_data

    expanded_reactions = _expand_keyed_items(
        template.get("reactions", {}), effective_params, _ctx
    )

    # Apply reactions with namespace prefix
    for name, rxn_data in expanded_reactions:
        namespaced_name = f"r.{namespace}.{name}"
        expanded_data = _namespace_molecule_refs(rxn_data, namespace, molecule_names)
        result["reactions"][namespaced_name] = expanded_data

    # Track ports with namespace prefix (internal only)
    for path, port in template.get("ports", {}).items():
        namespaced_path = _resolve_port_path(path, namespace)
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
                            inst_data, sub_namespace, registry, effective_params, _ctx, _seen
                        )
                        applications.append((sub_namespace, inst_data, sub_result, sub_ports))
                        result["molecules"].update(sub_result["molecules"])
                        result["reactions"].update(sub_result["reactions"])
                        _ports.update(sub_ports)
                else:
                    # Single instantiation: _as_ name
                    sub_namespace = f"{namespace}.{inst_name}"
                    sub_result, sub_ports = _instantiate_nested(
                        inst_data, sub_namespace, registry, effective_params, _ctx, _seen
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
                    sub_template = registry.get(template_name)
                    _apply_port_connections(
                        result, port_connections, sub_namespace, namespace,
                        sub_template, sub_ports, _ports
                    )

        # Auto-wire matching ports (energy.in↔energy.out, molecule name matching)
        _auto_wire_ports(result, _ports)

    return result


def _instantiate_nested(
    inst_data: dict[str, Any],
    namespace: str,
    registry: TemplateRegistry,
    parent_params: dict[str, Any],
    ctx: EvalContext,
    _seen: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Instantiate a nested template.

    Returns:
        Tuple of (result dict, ports dict)
    """
    template_name = inst_data.get("_template_")
    if not template_name:
        return {"molecules": {}, "reactions": {}}, {}

    # Check for circular references
    if _seen is not None and template_name in _seen:
        raise CircularReferenceError(list(_seen) + [template_name])
    new_seen = (_seen or set()) | {template_name}

    # Get the template and convert if needed
    template = registry.get(template_name)

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
    result, ports = _apply_template_with_ports(template, namespace, inst_params, registry, ctx, new_seen)

    return result, ports


def _apply_template_with_ports(
    template: dict[str, Any],
    namespace: str,
    params: dict[str, Any] | None,
    registry: TemplateRegistry | None,
    ctx: EvalContext,
    _seen: set[str] | None = None,
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

    # Expand molecule/reaction keys with {i in start..end} syntax
    expanded_molecules = _expand_keyed_items(
        template.get("molecules", {}), effective_params, ctx
    )
    molecule_names = set(name for name, _ in expanded_molecules)

    for name, mol_data in expanded_molecules:
        namespaced_name = f"m.{namespace}.{name}"
        result["molecules"][namespaced_name] = mol_data

    expanded_reactions = _expand_keyed_items(
        template.get("reactions", {}), effective_params, ctx
    )

    for name, rxn_data in expanded_reactions:
        namespaced_name = f"r.{namespace}.{name}"
        expanded_data = _namespace_molecule_refs(rxn_data, namespace, molecule_names)
        result["reactions"][namespaced_name] = expanded_data

    # Track ports
    for path, port in template.get("ports", {}).items():
        namespaced_path = _resolve_port_path(path, namespace)
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
                            inst_data, sub_namespace, registry, effective_params, ctx, _seen
                        )
                        applications.append((sub_namespace, inst_data, sub_result, sub_ports))
                        result["molecules"].update(sub_result["molecules"])
                        result["reactions"].update(sub_result["reactions"])
                        _ports.update(sub_ports)
                else:
                    sub_namespace = f"{namespace}.{inst_name}"
                    sub_result, sub_ports = _instantiate_nested(
                        inst_data, sub_namespace, registry, effective_params, ctx, _seen
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
                tpl_name = inst_data.get("_template_")
                if tpl_name:
                    sub_template = registry.get(tpl_name)
                    _apply_port_connections(
                        result, port_connections, sub_namespace, namespace,
                        sub_template, sub_ports, _ports
                    )

        # Auto-wire matching ports (energy.in↔energy.out, molecule name matching)
        _auto_wire_ports(result, _ports)

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
        if parent_namespace:
            target_port_key = f"{parent_namespace}.{target_inst_name}.{target_path}"
        else:
            target_port_key = f"{target_inst_name}.{target_path}"

        # Lookup ports
        local_expanded_port = local_ports.get(local_port_key)
        target_expanded_port = all_ports.get(target_port_key)

        if target_expanded_port is None:
            raise PortNotFoundError(target_ref, f"referenced from {namespace}")

        # The local side must declare a matching port too, otherwise there is
        # nothing to type-check the connection against and the wiring would
        # be applied blind.
        if local_expanded_port is None:
            raise PortNotFoundError(local_port_path, f"local port not declared in {namespace}")

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
            if namespaced_rxn not in result["reactions"]:
                raise PortNotFoundError(
                    namespaced_rxn, f"local wiring target missing from {namespace}"
                )
            result["reactions"][namespaced_rxn]["energy_source"] = target_expanded_port["namespaced_path"]
        elif local_port_path.startswith("molecules."):
            mol_name = local_port_path[len("molecules."):]
            namespaced_mol = f"m.{namespace}.{mol_name}"
            if namespaced_mol not in result["molecules"]:
                raise PortNotFoundError(
                    namespaced_mol, f"local wiring target missing from {namespace}"
                )
            result["molecules"][namespaced_mol]["source"] = target_expanded_port["namespaced_path"]


def _resolve_port_path(path: str, namespace: str) -> str:
    """Resolve a port path to a namespaced path.

    Handles both simple paths (reactions.work, molecules.MW1) and
    nested paths (waste.molecules.MW1, energy.reactions.work).
    """
    parts = path.split(".")
    if len(parts) >= 3:
        # Nested: "{inst_name}.{type}.{name}", e.g., "waste.molecules.MW1"
        inst_prefix = parts[0]
        sub_type = parts[1]
        sub_name = ".".join(parts[2:])
        if sub_type == "reactions":
            return f"r.{namespace}.{inst_prefix}.{sub_name}"
        elif sub_type == "molecules":
            return f"m.{namespace}.{inst_prefix}.{sub_name}"
    if path.startswith("reactions."):
        return f"r.{namespace}.{path[len('reactions.'):]}"
    elif path.startswith("molecules."):
        return f"m.{namespace}.{path[len('molecules.'):]}"
    return f"{namespace}.{path}"


def _extract_mol_name(port_key: str) -> str | None:
    """Extract bare molecule name from port key like 'ns.molecules.MW1'."""
    if ".molecules." in port_key:
        return port_key.split(".molecules.")[-1]
    return None


def _auto_wire_ports(result: dict[str, Any], all_ports: dict[str, Any]) -> None:
    """Auto-wire ports with matching types and opposite directions.

    For energy-type ports: adds {type}_source field to "in" reactions.
    For molecule-type ports: replaces bare molecule references in reactions
    when molecule names match across in/out ports.
    """
    # Group ports by type and direction
    by_type: dict[str, dict[str, list[tuple[str, dict[str, Any]]]]] = {}
    for port_key, port_info in all_ports.items():
        port = port_info["port"]
        ptype = port.get("type", "")
        direction = port.get("direction", "")
        if ptype and direction:
            by_type.setdefault(ptype, {}).setdefault(direction, []).append(
                (port_key, port_info)
            )

    for ptype, dirs in by_type.items():
        out_ports = dirs.get("out", [])
        if not out_ports:
            continue

        for in_key, in_info in dirs.get("in", []):
            in_path = in_info["namespaced_path"]

            if ptype == "molecule":
                # Match by molecule name
                in_mol = _extract_mol_name(in_key)
                match = None
                for out_key, out_info in out_ports:
                    out_mol = _extract_mol_name(out_key)
                    if in_mol and out_mol and in_mol == out_mol:
                        match = out_info
                        break
                if not match:
                    continue
                out_path = match["namespaced_path"]
                # Replace bare molecule refs in scoped reactions
                in_ns = in_key.split(".molecules.")[0] if ".molecules." in in_key else None
                if in_ns and in_mol:
                    for rxn_key, rxn_data in result["reactions"].items():
                        if not rxn_key.startswith(f"r.{in_ns}"):
                            continue
                        if not isinstance(rxn_data, dict):
                            continue
                        for field in ("reactants", "products"):
                            if field in rxn_data and isinstance(rxn_data[field], list):
                                rxn_data[field] = [
                                    out_path if item == in_mol or item == in_path else item
                                    for item in rxn_data[field]
                                ]
            else:
                # Non-molecule types (energy, etc.): wire to first matching out
                out_path = out_ports[0][1]["namespaced_path"]
                if in_path.startswith("r.") and in_path in result["reactions"]:
                    field_name = f"{ptype}_source"
                    # Don't overwrite explicit port connections
                    if field_name not in result["reactions"][in_path]:
                        result["reactions"][in_path][field_name] = out_path


def _eval_params(params: dict[str, Any], ctx: EvalContext) -> dict[str, Any]:
    """Evaluate !ev expressions in params, with dependency ordering."""
    result = {}
    eval_ctx = EvalContext(
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


def _resolve_and_eval(data: Any, params: dict[str, Any], ctx: EvalContext) -> Any:
    """Recursively resolve !ref and evaluate !ev expressions in data."""
    # Handle Evaluable (!ev)
    if isinstance(data, Evaluable):
        eval_ctx = EvalContext(
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

    # Handle string-based tags
    if isinstance(data, str):
        if data.startswith("!ev "):
            expr = data[4:].strip()
            eval_ctx = EvalContext(
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
    """Recursively resolve !ref expressions in data."""
    if isinstance(data, Reference):
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
