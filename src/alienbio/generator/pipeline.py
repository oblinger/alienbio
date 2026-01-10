"""Generator pipeline: full template-to-scenario instantiation.

Provides:
- instantiate(): Full pipeline from spec to scenario
- Scenario: Result container with ground truth and visibility mapping
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .template import TemplateRegistry, parse_template
from .expand import apply_template
from .guards import apply_template_with_guards
from .visibility import generate_visibility_mapping, apply_visibility
from .exceptions import TemplateNotFoundError, CircularReferenceError


@dataclass
class Scenario:
    """Result of template instantiation.

    Contains the visible scenario (with opaque names) plus
    ground truth and visibility mapping for debugging/scoring.

    Attributes:
        molecules: Visible molecules (opaque names)
        reactions: Visible reactions (opaque names)
        _ground_truth_: Full scenario with internal names
        _visibility_mapping_: Map from internal to opaque names
        _seed: Random seed used for instantiation
        _metadata_: Optional metadata from spec
    """

    molecules: dict[str, Any] = field(default_factory=dict)
    reactions: dict[str, Any] = field(default_factory=dict)
    _ground_truth_: dict[str, Any] = field(default_factory=dict)
    _visibility_mapping_: dict[str, Any] = field(default_factory=dict)
    _seed: int = 0
    _metadata_: dict[str, Any] = field(default_factory=dict)


def instantiate(
    spec: dict[str, Any],
    seed: int = 0,
    registry: TemplateRegistry | None = None,
    params: dict[str, Any] | None = None,
) -> Scenario:
    """Instantiate a scenario from a generator spec.

    Full pipeline:
    1. Parse spec to find _instantiate_ blocks
    2. Apply templates with namespace prefixing
    3. Apply guards (from _guards_ section)
    4. Apply visibility mapping (from _visibility_ section)

    Args:
        spec: Generator spec dict with _instantiate_, _guards_, _visibility_
        seed: Random seed for reproducibility
        registry: Template registry for resolving template references
        params: Parameter overrides

    Returns:
        Scenario with visible and ground truth data

    Raises:
        TemplateNotFoundError: If a referenced template doesn't exist
        CircularReferenceError: If templates reference each other circularly
        GuardViolation: If guards fail in reject mode
    """
    # Use default registry if not provided
    if registry is None:
        registry = TemplateRegistry()

    # Merge spec params with overrides
    effective_params = dict(spec.get("_params_", {}))
    if params:
        effective_params.update(params)

    # Extract guards configuration
    guards_config = spec.get("_guards_", [])

    # Extract visibility configuration
    visibility_spec = spec.get("_visibility_", {
        "molecules": {"fraction_known": 1.0},
        "reactions": {"fraction_known": 1.0},
    })

    # Extract metadata
    metadata = spec.get("_metadata_", {})

    # Resolve guards
    guards = _resolve_guards(guards_config)

    # Build the scenario by processing instantiations
    ground_truth = _process_instantiations(
        spec.get("_instantiate_", {}),
        registry=registry,
        params=effective_params,
        guards=guards,
        seed=seed,
        seen_templates=set(),
    )

    # Generate visibility mapping
    visibility_mapping = generate_visibility_mapping(ground_truth, visibility_spec, seed=seed)

    # Apply visibility to create the visible scenario
    visible = apply_visibility(ground_truth, visibility_mapping)

    return Scenario(
        molecules=visible["molecules"],
        reactions=visible["reactions"],
        _ground_truth_=ground_truth,
        _visibility_mapping_=visibility_mapping,
        _seed=seed,
        _metadata_=metadata,
    )


def _process_instantiations(
    instantiate: dict[str, Any],
    registry: TemplateRegistry,
    params: dict[str, Any],
    guards: list,
    seed: int,
    seen_templates: set[str],
) -> dict[str, Any]:
    """Process _instantiate_ blocks to produce molecules and reactions.

    Args:
        instantiate: Dict of _as_ blocks
        registry: Template registry
        params: Effective parameters
        guards: List of guard functions
        seed: Random seed
        seen_templates: For circular reference detection

    Returns:
        Dict with molecules and reactions
    """
    result: dict[str, Any] = {"molecules": {}, "reactions": {}}

    for key, inst_data in instantiate.items():
        # Parse _as_ syntax
        match = re.match(r"_as_\s+(\w+)(?:\{(\w+)\s+in\s+(\d+)\.\.(\w+)\})?", key)
        if not match:
            continue

        inst_name = match.group(1)
        loop_var = match.group(2)
        start = match.group(3)
        end_expr = match.group(4)

        if loop_var:
            # Replication: _as_ name{i in 1..count}
            start_val = int(start)
            if end_expr.isdigit():
                end_val = int(end_expr)
            else:
                param_val = params.get(end_expr, 0)
                end_val = int(round(param_val)) if isinstance(param_val, float) else int(param_val)

            for i in range(start_val, end_val + 1):
                namespace = f"{inst_name}{i}"
                inst_result = _instantiate_single(
                    inst_data, namespace, registry, params, guards, seed + i,
                    seen_templates,
                )
                result["molecules"].update(inst_result["molecules"])
                result["reactions"].update(inst_result["reactions"])
        else:
            # Single instantiation: _as_ name
            namespace = inst_name
            inst_result = _instantiate_single(
                inst_data, namespace, registry, params, guards, seed,
                seen_templates,
            )
            result["molecules"].update(inst_result["molecules"])
            result["reactions"].update(inst_result["reactions"])

    return result


def _instantiate_single(
    inst_data: dict[str, Any],
    namespace: str,
    registry: TemplateRegistry,
    parent_params: dict[str, Any],
    guards: list,
    seed: int,
    seen_templates: set[str],
) -> dict[str, Any]:
    """Instantiate a single template.

    Args:
        inst_data: Instantiation data with _template_ and params
        namespace: Namespace for this instantiation
        registry: Template registry
        parent_params: Parameters from parent scope
        guards: Guard functions
        seed: Random seed
        seen_templates: For circular reference detection

    Returns:
        Dict with molecules and reactions
    """
    template_name = inst_data.get("_template_")
    if not template_name:
        # No template, just process any nested instantiations
        nested_inst = inst_data.get("_instantiate_", {})
        if nested_inst:
            return _process_instantiations(
                nested_inst, registry, parent_params, guards, seed, seen_templates
            )
        return {"molecules": {}, "reactions": {}}

    # Check for circular reference
    if template_name in seen_templates:
        raise CircularReferenceError(template_name, list(seen_templates))

    # Get template from registry
    template = registry.get(template_name)

    # Track this template for circular detection
    new_seen = seen_templates | {template_name}

    # Extract params for this instantiation (excluding special keys)
    inst_params = {}
    for k, v in inst_data.items():
        if k in ("_template_", "_instantiate_"):
            continue
        # Port connections are handled by apply_template
        inst_params[k] = v

    # Merge params
    effective_params = {**parent_params, **inst_params}

    # Apply template with guards if any
    if guards:
        result = apply_template_with_guards(
            template,
            guards=guards,
            mode="retry",
            namespace=namespace,
            seed=seed,
            registry=registry,
        )
    else:
        # Use apply_template which handles port wiring and nested instantiation
        result = apply_template(
            template,
            namespace=namespace,
            params=effective_params,
            registry=registry,
            seed=seed,
        )

    # Check for nested instantiations in the template that need circular detection
    template_instantiate = template.get("instantiate", {})
    if template_instantiate:
        for key, nested_inst_data in template_instantiate.items():
            nested_template_name = nested_inst_data.get("_template_")
            if nested_template_name and nested_template_name in new_seen:
                raise CircularReferenceError(nested_template_name, list(new_seen))

    return result


def _resolve_guards(guards_config: list[Any]) -> list:
    """Resolve guard configuration to guard functions.

    Args:
        guards_config: List of guard names or configs

    Returns:
        List of guard functions
    """
    from .guards import (
        no_new_species_dependencies,
        no_new_cycles,
        no_essential,
    )

    # Built-in guard registry
    builtin_guards = {
        "no_new_species_dependencies": no_new_species_dependencies,
        "no_new_cycles": no_new_cycles,
        "no_essential": no_essential,
    }

    guards = []
    for guard_item in guards_config:
        if isinstance(guard_item, str):
            # Simple guard name
            if guard_item in builtin_guards:
                guards.append(builtin_guards[guard_item])
        elif isinstance(guard_item, dict):
            # Guard with config
            name = guard_item.get("name")
            if name and name in builtin_guards:
                guards.append(builtin_guards[name])

    return guards
