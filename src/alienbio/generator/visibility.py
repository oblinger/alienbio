"""Visibility mapping for controlling agent perception.

Provides:
- generate_opaque_names(): Create opaque names from internal names
- apply_fraction_known(): Split items into visible/hidden
- generate_visibility_mapping(): Create full visibility mapping
- apply_visibility(): Apply mapping to rename/filter scenario
"""

from __future__ import annotations

import random
from typing import Any


def generate_opaque_names(
    names: list[str],
    prefix: str = "X",
    seed: int | None = None,
) -> dict[str, str]:
    """Generate opaque names for a list of internal names.

    Creates a deterministic, shuffled mapping from internal names
    (like "m.Krel.energy.ME1") to opaque names (like "M3").

    Args:
        names: List of internal names to map
        prefix: Prefix for opaque names (e.g., "M" for molecules, "RX" for reactions)
        seed: Random seed for reproducibility

    Returns:
        Dict mapping internal_name -> opaque_name
    """
    if not names:
        return {}

    # Create seeded RNG
    rng = random.Random(seed)

    # Create indices and shuffle them
    indices = list(range(1, len(names) + 1))
    rng.shuffle(indices)

    # Map each name to an opaque name
    mapping = {}
    for name, idx in zip(names, indices):
        mapping[name] = f"{prefix}{idx}"

    return mapping


def apply_fraction_known(
    items: list[str],
    fraction: float,
    seed: int | None = None,
) -> tuple[list[str], list[str]]:
    """Split items into visible and hidden based on fraction.

    Args:
        items: List of item names
        fraction: Fraction to make visible (0.0 to 1.0)
        seed: Random seed for reproducibility

    Returns:
        Tuple of (visible_items, hidden_items)
    """
    if not items:
        return [], []

    if fraction <= 0:
        return [], list(items)

    if fraction >= 1:
        return list(items), []

    # Calculate how many to show
    n_visible = int(round(fraction * len(items)))
    n_visible = max(0, min(len(items), n_visible))

    # Shuffle with seed
    rng = random.Random(seed)
    shuffled = list(items)
    rng.shuffle(shuffled)

    visible = shuffled[:n_visible]
    hidden = shuffled[n_visible:]

    return visible, hidden


def generate_visibility_mapping(
    expanded: Any,  # dict or object with molecules/reactions
    visibility_spec: dict[str, dict[str, Any]],
    seed: int | None = None,
) -> dict[str, Any]:
    """Generate a complete visibility mapping for a scenario.

    Args:
        expanded: Applied template with molecules and reactions (dict or object)
        visibility_spec: Config for visibility per entity type, e.g.:
            {
                "molecules": {"fraction_known": 0.8},
                "reactions": {"fraction_known": 0.5},
            }
        seed: Random seed for reproducibility

    Returns:
        Dict with:
            - opaque_name for each visible internal name
            - "_hidden_" key with lists of hidden molecules/reactions
    """
    mapping: dict[str, Any] = {}
    hidden: dict[str, list[str]] = {"molecules": [], "reactions": []}

    # Get molecules and reactions (handle both dict and object)
    if isinstance(expanded, dict):
        molecules = expanded.get("molecules", {})
        reactions = expanded.get("reactions", {})
    else:
        molecules = getattr(expanded, "molecules", {})
        reactions = getattr(expanded, "reactions", {})

    # Process molecules
    mol_spec = visibility_spec.get("molecules", {"fraction_known": 1.0})
    mol_fraction = mol_spec.get("fraction_known", 1.0)
    mol_names = list(molecules.keys())

    visible_mols, hidden_mols = apply_fraction_known(mol_names, mol_fraction, seed)
    hidden["molecules"] = hidden_mols

    # Generate opaque names for visible molecules
    mol_opaque = generate_opaque_names(visible_mols, prefix="M", seed=seed)
    mapping.update(mol_opaque)

    # Process reactions
    rxn_spec = visibility_spec.get("reactions", {"fraction_known": 1.0})
    rxn_fraction = rxn_spec.get("fraction_known", 1.0)
    rxn_names = list(reactions.keys())

    # Use different seed component for reactions
    rxn_seed = seed + 1000 if seed is not None else None
    visible_rxns, hidden_rxns = apply_fraction_known(rxn_names, rxn_fraction, rxn_seed)
    hidden["reactions"] = hidden_rxns

    # Generate opaque names for visible reactions
    rxn_opaque = generate_opaque_names(visible_rxns, prefix="RX", seed=rxn_seed)
    mapping.update(rxn_opaque)

    mapping["_hidden_"] = hidden
    return mapping


def apply_visibility(
    scenario: Any,  # dict or object with molecules/reactions
    mapping: dict[str, Any],
) -> dict[str, Any]:
    """Apply visibility mapping to create an agent-visible scenario.

    Renames molecules and reactions according to the mapping,
    updates all references, and removes hidden elements.

    Args:
        scenario: Scenario with molecules and reactions (dict or object)
        mapping: Visibility mapping from generate_visibility_mapping()

    Returns:
        Dict with "molecules" and "reactions" keys, renamed and filtered
    """
    result: dict[str, Any] = {"molecules": {}, "reactions": {}}
    hidden = mapping.get("_hidden_", {"molecules": [], "reactions": []})
    hidden_mols = set(hidden.get("molecules", []))
    hidden_rxns = set(hidden.get("reactions", []))

    # Build reverse mapping for reference updates (internal -> opaque)
    name_map = {k: v for k, v in mapping.items() if not k.startswith("_")}

    # Get molecules and reactions (handle both dict and object)
    if isinstance(scenario, dict):
        molecules = scenario.get("molecules", {})
        reactions = scenario.get("reactions", {})
    else:
        molecules = getattr(scenario, "molecules", {})
        reactions = getattr(scenario, "reactions", {})

    # Process molecules
    for mol_name, mol_data in molecules.items():
        if mol_name in hidden_mols:
            continue
        if mol_name not in name_map:
            continue

        opaque_name = name_map[mol_name]
        # Deep copy and update any references in the data
        new_data = _update_references(mol_data, name_map)
        result["molecules"][opaque_name] = new_data

    # Process reactions
    for rxn_name, rxn_data in reactions.items():
        if rxn_name in hidden_rxns:
            continue
        if rxn_name not in name_map:
            continue

        opaque_name = name_map[rxn_name]
        # Deep copy and update references
        new_data = _update_references(rxn_data, name_map)
        result["reactions"][opaque_name] = new_data

    return result


def _update_references(data: Any, name_map: dict[str, str]) -> Any:
    """Recursively update internal names to opaque names in data."""
    if isinstance(data, str):
        # Check if this string is a known internal name
        return name_map.get(data, data)

    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            # Update both keys and values
            new_k = name_map.get(k, k) if isinstance(k, str) else k
            new_v = _update_references(v, name_map)
            result[new_k] = new_v
        return result

    if isinstance(data, list):
        return [_update_references(item, name_map) for item in data]

    return data
