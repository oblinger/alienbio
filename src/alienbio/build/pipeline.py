"""Build pipeline: full template-to-scenario instantiation.

Provides:
- instantiate(): Full pipeline from spec to scenario
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from alienbio.protocols import Scenario

from .template import TemplateRegistry, parse_template, parse_interaction, parse_background, parse_containers
from .expand import apply_template
from .guards import apply_template_with_guards
from .visibility import generate_visibility_mapping, apply_visibility
from .exceptions import TemplateNotFoundError, CircularReferenceError, PortNotFoundError


def _stable_hash(value: str) -> int:
    """Deterministic string hash, stable across processes/machines.

    Python's builtin ``hash(str)`` is salted per-process (PYTHONHASHSEED),
    so it must never be used to derive reproducible seeds.
    """
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest(), 16) % 1000


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

    # Run custom guards on the complete ground truth
    from .exceptions import GuardViolation
    from .guards import make_guard_context
    guard_context = make_guard_context(ground_truth)
    for guard_fn in guards:
        try:
            result = guard_fn(ground_truth, guard_context)
        except TypeError:
            # Lambda guards may only take 1 arg
            result = guard_fn(ground_truth)
        if result is False or (isinstance(result, dict) and not result.get("ok", True)):
            guard_name = getattr(guard_fn, "__name__", str(guard_fn))
            raise GuardViolation(f"Guard '{guard_name}' failed")

    # Process interactions
    interactions_spec = spec.get("interactions", {})
    if interactions_spec:
        ground_truth = _process_interactions(
            interactions_spec, ground_truth, registry, effective_params, seed
        )

    # Process modifications
    modify_spec = spec.get("_modify_", {})
    if modify_spec:
        ground_truth = _process_modifications(modify_spec, ground_truth)

    # Process background generation
    background_spec = spec.get("background", {})
    if background_spec:
        ground_truth = _process_background(
            background_spec, ground_truth, guards, seed
        )

    # Process container generation
    containers_spec = spec.get("parameters", {}).get("containers", {})
    regions = _process_containers(containers_spec, ground_truth, seed)

    # Generate visibility mapping
    visibility_mapping = generate_visibility_mapping(ground_truth, visibility_spec, seed=seed)

    # Apply visibility to create the visible scenario
    visible = apply_visibility(ground_truth, visibility_mapping)

    return Scenario(
        molecules=visible["molecules"],
        reactions=visible["reactions"],
        regions=regions,
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
    available_ports: set[str] | None = None,
) -> dict[str, Any]:
    """Process _instantiate_ blocks to produce molecules and reactions.

    Args:
        instantiate: Dict of _as_ blocks
        registry: Template registry
        params: Effective parameters
        guards: List of guard functions
        seed: Random seed
        seen_templates: For circular reference detection
        available_ports: Set of available port types for requires validation

    Returns:
        Dict with molecules and reactions
    """
    result: dict[str, Any] = {"molecules": {}, "reactions": {}}
    if available_ports is None:
        available_ports = set()

    # Collect all instantiation results and port info for cross-wiring
    applications: list[tuple[str, dict[str, Any]]] = []
    all_ports: dict[str, dict[str, Any]] = {}

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
                    seen_templates, available_ports,
                )
                result["molecules"].update(inst_result["molecules"])
                result["reactions"].update(inst_result["reactions"])
                applications.append((namespace, inst_data))
                _collect_ports(inst_data, namespace, registry, all_ports)
                _track_ports(inst_data, registry, available_ports)
        else:
            # Single instantiation: _as_ name
            namespace = inst_name
            inst_result = _instantiate_single(
                inst_data, namespace, registry, params, guards, seed,
                seen_templates, available_ports,
            )
            result["molecules"].update(inst_result["molecules"])
            result["reactions"].update(inst_result["reactions"])
            applications.append((namespace, inst_data))
            _collect_ports(inst_data, namespace, registry, all_ports)
            _track_ports(inst_data, registry, available_ports)

    # Pass 2: Apply explicit cross-template port connections
    for namespace, inst_data in applications:
        port_connections = {
            k: v for k, v in inst_data.items()
            if k not in ("_template_", "_instantiate_")
            and isinstance(v, str) and "." in v
            and (k.startswith("reactions.") or k.startswith("molecules."))
        }
        if port_connections and inst_data.get("_template_"):
            template = registry.get(inst_data["_template_"])
            from .expand import _apply_port_connections
            local_ports = {
                pk: pv for pk, pv in all_ports.items()
                if pk.startswith(f"{namespace}.")
            }
            _apply_port_connections(
                result, port_connections, namespace, "",
                template, local_ports, all_ports,
            )

    # Pass 3: Auto-wire matching interface ports across templates
    from .expand import _auto_wire_ports
    interface_ports: dict[str, dict[str, Any]] = {}
    for namespace, inst_data in applications:
        _collect_interface_ports(inst_data, namespace, registry, interface_ports)
    _auto_wire_ports(result, interface_ports)

    return result


def _instantiate_single(
    inst_data: dict[str, Any],
    namespace: str,
    registry: TemplateRegistry,
    parent_params: dict[str, Any],
    guards: list,
    seed: int,
    seen_templates: set[str],
    available_ports: set[str] | None = None,
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
        available_ports: Set of available port types for requires validation

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
        raise CircularReferenceError(list(seen_templates) + [template_name])

    # Get template from registry
    try:
        template = registry.get(template_name)
    except TemplateNotFoundError as e:
        e.path = namespace  # type: ignore[attr-defined]
        raise TemplateNotFoundError(
            f"{template_name} (in namespace '{namespace}')",
            e.registry_names,
        ) from e

    # Validate requires (port dependencies)
    requires = template.get("requires", [])
    if requires and available_ports is not None:
        for required_port in requires:
            if required_port not in available_ports:
                raise PortNotFoundError(
                    required_port,
                    f"required by template '{template_name}'"
                )

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
                raise CircularReferenceError(list(new_seen) + [nested_template_name])

    return result


def _collect_ports(
    inst_data: dict[str, Any],
    namespace: str,
    registry: TemplateRegistry,
    all_ports: dict[str, dict[str, Any]],
) -> None:
    """Collect direct port info from an instantiated template for cross-wiring.

    Only collects ports from the template's own _ports_ section (not
    recursively from nested templates) to avoid false auto-wiring across
    scoping levels.

    Populates all_ports with namespaced port entries like:
        "Krel.waste.molecules.MW1" → {"port": {...}, "namespaced_path": "m.Krel.waste.MW1"}
    """
    from .expand import _resolve_port_path

    template_name = inst_data.get("_template_")
    if not template_name:
        return
    try:
        template = registry.get(template_name)
    except TemplateNotFoundError:
        return
    for path, port_info in template.get("ports", {}).items():
        namespaced_path = _resolve_port_path(path, namespace)
        port_key = f"{namespace}.{path}"
        all_ports[port_key] = {"port": port_info, "namespaced_path": namespaced_path}


def _collect_interface_ports(
    inst_data: dict[str, Any],
    namespace: str,
    registry: TemplateRegistry,
    ports_dict: dict[str, dict[str, Any]],
) -> None:
    """Collect only the template's own declared ports for top-level auto-wiring.

    Unlike _collect_ports which recurses into sub-templates, this only
    collects the template's interface ports (its own _ports_ declaration).
    """
    template_name = inst_data.get("_template_")
    if not template_name:
        return
    try:
        template = registry.get(template_name)
    except TemplateNotFoundError:
        return

    for path, port_info in template.get("ports", {}).items():
        parts = path.split(".")
        if len(parts) >= 2 and parts[0] in ("reactions", "molecules"):
            # Direct: "reactions.work" or "molecules.MW1"
            elem_type = parts[0]
            elem_name = ".".join(parts[1:])
            prefix = "r" if elem_type == "reactions" else "m"
            namespaced_path = f"{prefix}.{namespace}.{elem_name}"
        elif len(parts) >= 3 and parts[1] in ("reactions", "molecules"):
            # Prefixed: "sub.reactions.name" or "sub.molecules.name"
            sub_inst = parts[0]
            elem_type = parts[1]
            elem_name = ".".join(parts[2:])
            prefix = "r" if elem_type == "reactions" else "m"
            namespaced_path = f"{prefix}.{namespace}.{sub_inst}.{elem_name}"
        else:
            namespaced_path = f"{namespace}.{path}"

        port_key = f"{namespace}.{path}"
        ports_dict[port_key] = {"port": port_info, "namespaced_path": namespaced_path}


def _track_ports(
    inst_data: dict[str, Any],
    registry: TemplateRegistry,
    available_ports: set[str],
) -> None:
    """Track ports provided by an instantiated template.

    Args:
        inst_data: Instantiation data with _template_ key
        registry: Template registry
        available_ports: Set to update with new port types
    """
    template_name = inst_data.get("_template_")
    if not template_name:
        return

    try:
        template = registry.get(template_name)
    except TemplateNotFoundError:
        return

    # Extract port types from the template's ports
    ports = template.get("ports", {})
    for port_info in ports.values():
        # Port format: {"type": "energy", "direction": "out", "path": "..."}
        port_type = port_info.get("type", "")
        direction = port_info.get("direction", "")
        if port_type and direction:
            # Store as "type.direction" for matching against requires
            available_ports.add(f"{port_type}.{direction}")


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

    # Handle both list and dict formats for _guards_
    if isinstance(guards_config, dict):
        # Dict format: {"guard_name": "lambda ..."}
        for name, value in guards_config.items():
            if name in builtin_guards:
                guards.append(builtin_guards[name])
            elif isinstance(value, str) and "lambda" in value:
                # Custom lambda guard
                guard_fn = eval(value)  # noqa: S307
                guard_fn.__name__ = name  # type: ignore[attr-defined]
                guards.append(guard_fn)
        return guards

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


def _process_interactions(
    interactions_spec: dict[str, Any],
    ground_truth: dict[str, Any],
    registry: TemplateRegistry,
    params: dict[str, Any],
    seed: int,
) -> dict[str, Any]:
    """Process interactions section to wire species together.

    Args:
        interactions_spec: Dict of interaction name -> interaction spec
        ground_truth: Current ground truth with molecules/reactions
        registry: Template registry
        params: Effective parameters
        seed: Random seed

    Returns:
        Updated ground truth with interaction wiring
    """
    for name, interaction_data in interactions_spec.items():
        parsed = parse_interaction(interaction_data)
        template_name = parsed["template"]
        between = parsed["between"]
        interaction_params = parsed["params"]

        if not template_name:
            continue

        # Get the interaction template
        template = registry.get(template_name)

        # Apply the interaction template with the between context
        # Namespace for interactions is the interaction name
        namespace = name

        # Merge params
        effective_params = {**params, **interaction_params}

        # For interactions, also include references to the connected species
        if len(between) >= 2:
            effective_params["producer"] = between[0]
            effective_params["consumer"] = between[1]

        # Apply template
        result = apply_template(
            template,
            namespace=namespace,
            params=effective_params,
            registry=registry,
            seed=seed,
        )

        # Merge into ground truth
        ground_truth["molecules"].update(result["molecules"])
        ground_truth["reactions"].update(result["reactions"])

    return ground_truth


def _process_modifications(
    modify_spec: dict[str, Any],
    ground_truth: dict[str, Any],
) -> dict[str, Any]:
    """Process _modify_ section to alter existing elements.

    Args:
        modify_spec: Dict of path -> modification spec
        ground_truth: Current ground truth

    Returns:
        Updated ground truth with modifications applied

    Raises:
        KeyError: If a path doesn't exist
    """
    for path, mod_data in modify_spec.items():
        # Parse path: "x.reactions.r1" -> namespace "x", type "reactions", name "r1"
        parts = path.split(".")
        if len(parts) < 3:
            raise KeyError(f"Invalid modify path: '{path}' (expected namespace.type.name)")

        namespace = parts[0]
        elem_type = parts[1]  # "molecules" or "reactions"
        elem_name = ".".join(parts[2:])

        # Build the full key
        prefix = "m" if elem_type == "molecules" else "r"
        full_key = f"{prefix}.{namespace}.{elem_name}"

        # Find the element
        collection = ground_truth.get(elem_type, {})
        if full_key not in collection:
            raise KeyError(f"Element not found: '{full_key}'")

        element = collection[full_key]

        # Apply _set_ modifications
        if "_set_" in mod_data:
            for key, value in mod_data["_set_"].items():
                element[key] = value

        # Apply _append_ modifications
        if "_append_" in mod_data:
            for key, values in mod_data["_append_"].items():
                if key not in element:
                    element[key] = []
                # Namespace the appended values if they're molecule references
                for val in values:
                    namespaced_val = f"m.{namespace}.{val}"
                    element[key].append(namespaced_val)

    return ground_truth


def _process_background(
    background_spec: dict[str, Any],
    ground_truth: dict[str, Any],
    guards: list,
    seed: int,
) -> dict[str, Any]:
    """Process background section to generate filler molecules and reactions.

    Args:
        background_spec: Dict with molecules and reactions config
        ground_truth: Current ground truth
        guards: Guard functions to apply
        seed: Random seed

    Returns:
        Updated ground truth with background elements
    """
    import random
    from ..spec_lang.eval import Evaluable, eval_node, make_context

    rng = random.Random(seed)
    ctx = make_context(seed=seed)

    parsed = parse_background(background_spec)
    mol_config = parsed["molecules"]
    rxn_config = parsed["reactions"]

    # Determine molecule count
    mol_count_spec = mol_config.get("count", 0)
    if isinstance(mol_count_spec, str) and mol_count_spec.startswith("!ev "):
        expr = mol_count_spec[4:].strip()
        mol_count = int(round(eval_node(Evaluable(source=expr), ctx)))
    elif isinstance(mol_count_spec, Evaluable):
        mol_count = int(round(eval_node(mol_count_spec, ctx)))
    else:
        mol_count = int(mol_count_spec)

    # Generate background molecules
    bg_molecules = []
    for i in range(mol_count):
        mol_name = f"m.bg.M{i}"
        ground_truth["molecules"][mol_name] = {}
        bg_molecules.append(mol_name)

    # Determine reaction count
    rxn_count_spec = rxn_config.get("count", 0)
    if isinstance(rxn_count_spec, str) and rxn_count_spec.startswith("!ev "):
        expr = rxn_count_spec[4:].strip()
        rxn_count = int(round(eval_node(Evaluable(source=expr), ctx)))
    elif isinstance(rxn_count_spec, Evaluable):
        rxn_count = int(round(eval_node(rxn_count_spec, ctx)))
    else:
        rxn_count = int(rxn_count_spec)

    # Generate background reactions (only use background molecules)
    if bg_molecules and rxn_count > 0:
        for i in range(rxn_count):
            rxn_name = f"r.bg.R{i}"
            # Pick random reactants and products from background molecules
            reactant = rng.choice(bg_molecules)
            product = rng.choice(bg_molecules)
            ground_truth["reactions"][rxn_name] = {
                "reactants": [reactant],
                "products": [product],
                "rate": 0.1,
            }

    return ground_truth


def _process_containers(
    containers_spec: dict[str, Any],
    ground_truth: dict[str, Any],
    seed: int,
) -> list:
    """Process container specification to generate regions and populations.

    Args:
        containers_spec: Dict with regions and populations config
        ground_truth: Current ground truth (to find species)
        seed: Random seed

    Returns:
        List of Region objects
    """
    import random
    from alienbio.protocols import Region, Organism
    from ..spec_lang.eval import Evaluable, eval_node, make_context

    if not containers_spec:
        return []

    rng = random.Random(seed)
    ctx = make_context(seed=seed)

    parsed = parse_containers(containers_spec)
    regions_config = parsed["regions"]
    populations_config = parsed["populations"]

    # Determine region count
    region_count = regions_config.get("count", 0)
    if isinstance(region_count, str) and region_count.startswith("!ev "):
        expr = region_count[4:].strip()
        region_count = int(round(eval_node(Evaluable(source=expr), ctx)))
    elif isinstance(region_count, Evaluable):
        region_count = int(round(eval_node(region_count, ctx)))
    else:
        region_count = int(region_count)

    # Get initial substrates config
    initial_substrates = regions_config.get("initial_substrates", {})

    # Extract species from ground truth (look for namespaces in molecules)
    species_names = set()
    for mol_name in ground_truth.get("molecules", {}):
        # Format: m.{species}.{molecule}
        parts = mol_name.split(".")
        if len(parts) >= 2 and parts[0] == "m" and parts[1] not in ("bg",):
            species_names.add(parts[1])

    # Determine population count per species per region
    pop_spec = populations_config.get("per_species_per_region", 0)

    # Generate regions
    regions = []
    for r_idx in range(region_count):
        region_id = f"region_{r_idx}"
        organisms = []

        # Generate organisms for each species in this region
        for species in sorted(species_names):
            # Evaluate population count (may be distribution)
            if isinstance(pop_spec, str) and pop_spec.startswith("!ev "):
                expr = pop_spec[4:].strip()
                # Create new context for each evaluation to get different samples
                pop_ctx = make_context(seed=seed + r_idx * 1000 + _stable_hash(species))
                pop_count = int(round(eval_node(Evaluable(source=expr), pop_ctx)))
            elif isinstance(pop_spec, Evaluable):
                pop_ctx = make_context(seed=seed + r_idx * 1000 + _stable_hash(species))
                pop_count = int(round(eval_node(pop_spec, pop_ctx)))
            else:
                pop_count = int(pop_spec)

            # Create organisms
            for o_idx in range(pop_count):
                org_id = f"org_{species}_{r_idx}_{o_idx}"
                organisms.append(Organism(id=org_id, species=species))

        region = Region(
            id=region_id,
            substrates=dict(initial_substrates),
            organisms=organisms,
        )
        regions.append(region)

    return regions
