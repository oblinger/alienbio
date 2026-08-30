"""Skinning: generate alien descriptions and apply to tasks."""

from __future__ import annotations

import hashlib
import random
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .biosystem import BioSystem
    from .task import Task

# Alien syllable pools for generating opaque names
_PREFIXES = [
    "zor", "kth", "vel", "nyx", "pho", "qua", "xen", "myr",
    "dra", "ith", "glo", "fra", "obe", "ule", "tha", "cri",
]
_SUFFIXES = [
    "ax", "on", "ul", "em", "ix", "ar", "ith", "os",
    "an", "el", "um", "is", "or", "yl", "en", "at",
]
_CONNECTORS = [
    "-", "'", ".", "",
]

# Earth biology terms that should not appear in skinned output
EARTH_TERMS = {
    "molecule", "atom", "carbon", "hydrogen", "oxygen", "nitrogen",
    "protein", "enzyme", "cell", "organ", "organism", "dna", "rna",
    "glucose", "atp", "mitochondria", "nucleus", "membrane",
    "gene", "chromosome", "amino", "acid", "lipid", "carbohydrate",
    "reaction", "concentration", "chemistry", "biology",
}


def generate_alien_name(base: str, *, seed: Optional[int] = None) -> str:
    """Generate an opaque alien name from a base string.

    The name is deterministic given the same base and seed.

    Args:
        base: The original name to obfuscate
        seed: Random seed (defaults to hash of base)

    Returns:
        An alien-sounding name
    """
    if seed is None:
        h = hashlib.md5(base.encode()).hexdigest()
        seed = int(h[:8], 16)

    rng = random.Random(seed)
    prefix = rng.choice(_PREFIXES)
    suffix = rng.choice(_SUFFIXES)
    connector = rng.choice(_CONNECTORS)

    return f"{prefix}{connector}{suffix}"


def generate_description(
    system: "BioSystem",
    *,
    detail_level: int = 2,
    name_map: Optional[Dict[str, str]] = None,
    seed: Optional[int] = None,
) -> str:
    """Generate a natural language description of a biological system.

    Args:
        system: The system to describe
        detail_level: 1=minimal hints, 2=moderate, 3=full explanation
        name_map: Optional mapping from real names to alien names
        seed: Random seed for name generation

    Returns:
        Description string using alien terminology
    """
    if name_map is None:
        name_map = generate_name_map(system, seed=seed)

    mols = list(system.chemistry.molecules.keys())
    rxns = list(system.chemistry.reactions.keys())

    lines = []

    if detail_level >= 1:
        lines.append(
            f"System contains {len(mols)} substances and {len(rxns)} processes."
        )
        alien_mols = [name_map.get(m) or m for m in mols]
        lines.append("Substances: " + ", ".join(alien_mols))

    if detail_level >= 2:
        lines.append("")
        lines.append("Processes:")
        for rxn_name, rxn in system.chemistry.reactions.items():
            reactant_names = [name_map.get(str(m.name), str(m.name)) for m in rxn.reactants]
            product_names = [name_map.get(str(m.name), str(m.name)) for m in rxn.products]

            r_str = " + ".join(reactant_names) if reactant_names else "(source)"
            p_str = " + ".join(product_names) if product_names else "(sink)"
            proc_name = name_map.get(rxn_name, rxn_name)
            lines.append(f"  {proc_name}: {r_str} -> {p_str}")

    if detail_level >= 3:
        lines.append("")
        lines.append("Current state:")
        for mol_name in mols:
            alien_name = name_map.get(mol_name, mol_name)
            conc = system.state[mol_name]
            lines.append(f"  {alien_name}: {conc:.2f}")

    return "\n".join(lines)


def generate_name_map(
    system: "BioSystem",
    *,
    seed: Optional[int] = None,
) -> Dict[str, str]:
    """Generate a mapping from real names to alien names.

    Maps molecules and reactions to opaque alien names.

    Args:
        system: The system whose names to map
        seed: Random seed for deterministic names

    Returns:
        Dict mapping original names to alien names
    """
    name_map: Dict[str, str] = {}
    base_seed = seed if seed is not None else 0
    used: set = set()

    for i, mol_name in enumerate(system.chemistry.molecules):
        name = generate_alien_name(mol_name, seed=base_seed + i)
        while name in used:
            base_seed += 100
            name = generate_alien_name(mol_name, seed=base_seed + i)
        name_map[mol_name] = name
        used.add(name)

    for i, rxn_name in enumerate(system.chemistry.reactions):
        name = generate_alien_name(rxn_name, seed=base_seed + 1000 + i)
        while name in used:
            base_seed += 100
            name = generate_alien_name(rxn_name, seed=base_seed + 1000 + i)
        name_map[rxn_name] = name
        used.add(name)

    return name_map


def skin_task_description(
    task: "Task",
    name_map: Dict[str, str],
) -> str:
    """Apply alien naming to a task description.

    Replaces any known molecule/reaction names with alien equivalents.

    Args:
        task: The task to skin
        name_map: Mapping from real names to alien names

    Returns:
        Task description with alien terminology
    """
    desc = task.description
    # Replace real names with alien names (longest first to avoid partial matches)
    for real_name in sorted(name_map.keys(), key=len, reverse=True):
        alien_name = name_map[real_name]
        desc = desc.replace(real_name, alien_name)
    return desc


def check_no_earth_terms(text: str) -> List[str]:
    """Check that text contains no Earth biology terms.

    Args:
        text: Text to check

    Returns:
        List of Earth terms found (empty if clean)
    """
    text_lower = text.lower()
    found = []
    for term in EARTH_TERMS:
        if term in text_lower:
            found.append(term)
    return sorted(found)
