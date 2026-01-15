"""Test fixtures as Python module attributes.

This module demonstrates several patterns for defining fixtures that can be
loaded via the do-system:

1. Plain dict fixtures (simple, molecules, kegg1)
2. YAML string spec (experiment_template)
3. Callable functions (process_data, compute_metric)
4. Proper DAT specs with dat: section (runnable_experiment)
5. H1-H5 experiment scenarios (scenarios.py)
"""

# H1-H5 experiment scenarios
from .scenarios import (
    H1_MINIMAL,
    H1_SMALL,
    H2_SINGLE_REACTION,
    H2_MULTI_REACTION,
    H3_SIMPLE_SEQUENCE,
    H4_DIRECT_INTERVENTION,
    H4_INDIRECT_INTERVENTION,
    H5_HIDDEN_REACTION,
    SIMPLE_SCENARIO,
    TIMING_SCENARIO,
)

# =============================================================================
# Plain dict fixtures - basic data structures
# =============================================================================

simple = {
    "name": "simple_fixture",
    "description": "A simple test fixture for DAT integration tests",
    "value": 42,
    "data": {"items": ["apple", "banana", "cherry"]}
}

molecules = {
    "name": "test_molecules",
    "description": "Test molecule fixture",
    "molecules": [
        {"id": "mol_a", "name": "Alpha", "concentration": 1.0},
        {"id": "mol_b", "name": "Beta", "concentration": 0.5},
        {"id": "mol_c", "name": "Gamma", "concentration": 0.25},
    ]
}

kegg1 = {
    "name": "kegg1",
    "description": "Stub KEGG-derived biochemistry model",
    "type": "biochemistry_model",
    "molecule_count": 0,
    "reaction_count": 0,
}


# =============================================================================
# YAML string spec - embedded YAML configuration
# =============================================================================

experiment_template = """yaml
dat:
  kind: Dat
  target_exists: overwrite
name: experiment_from_yaml
description: A DAT spec defined as a YAML string in Python
parameters:
  learning_rate: 0.01
  epochs: 100
  batch_size: 32
"""


# =============================================================================
# Callable functions - can be invoked via do()
# =============================================================================

def process_data(items: list) -> dict:
    """Process a list of items and return summary statistics.

    This function can be called via do("fixtures.process_data", items=[...])
    """
    return {
        "count": len(items),
        "first": items[0] if items else None,
        "last": items[-1] if items else None,
    }


def compute_metric(dat=None, *, multiplier: int = 1) -> int:
    """Compute a metric from a DAT's spec.

    This is a simple function that can be called directly via do().
    NOT suitable for dat.run() - use run_compute_metric for that.

    Args:
        dat: The Dat object (optional)
        multiplier: Value to multiply the result by

    Returns:
        The computed metric value
    """
    if dat is None:
        return 42 * multiplier
    # Access the DAT's spec to compute something
    spec = dat.get_spec()
    base_value = spec.get("value", 10)
    return base_value * multiplier


def run_compute_metric(dat) -> tuple[bool, dict]:
    """Run function for dat.run() - follows the (success, metadata) protocol.

    This function demonstrates the dat.run() protocol where the function
    must return a tuple of (success: bool, metadata: dict).

    Args:
        dat: The Dat object (passed by dat.run())

    Returns:
        Tuple of (success, metadata) where metadata contains the result
    """
    try:
        spec = dat.get_spec()
        base_value = spec.get("value", 10)
        return True, {"return": base_value}
    except Exception as e:
        return False, {"error": str(e)}


# =============================================================================
# DAT specs with proper dat: section - can be used with create()
# =============================================================================

runnable_experiment = {
    "dat": {
        "kind": "Dat",
        "do": "fixtures.run_compute_metric",
        "target_exists": "overwrite",
    },
    "name": "runnable_experiment",
    "description": "A DAT spec that can be run via dat.run()",
    "value": 7,
}

simple_dat = {
    "dat": {
        "kind": "Dat",
        "target_exists": "overwrite",
    },
    "name": "simple_dat",
    "description": "A simple DAT spec with proper dat: section",
    "value": 100,
}
