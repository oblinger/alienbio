"""Test measurements for integration tests.

These measurements are stubs that read mock state for testing the agent interface.
Real implementations would interact with actual simulation state.
"""

from typing import Any

from alienbio import measurement


@measurement(summary="Measure concentrations in a region", targets="regions", cost=0)
def sample_substrate(state: dict[str, Any], region: str) -> dict[str, Any]:
    """Return concentrations for a region.

    For testing, just returns all non-internal state values.
    """
    return {k: v for k, v in state.items() if not k.startswith("_")}


@measurement(summary="Detailed metabolic analysis", cost=2.0)
def deep_analysis(state: dict[str, Any]) -> dict[str, Any]:
    """Perform detailed metabolic analysis.

    For testing, returns full state including internal fields.
    """
    return dict(state)


@measurement(summary="List all compartments in the system", cost=0)
def list_compartments(state: dict[str, Any]) -> list[str]:
    """List all compartments.

    For testing, looks for _compartments key or returns placeholder.
    """
    return state.get("_compartments", ["default"])


@measurement(summary="List molecules in a compartment", cost=0)
def list_molecules(state: dict[str, Any], compartment: str) -> list[str]:
    """List molecules in a compartment.

    For testing, returns all non-internal keys as molecules.
    """
    return [k for k in state.keys() if not k.startswith("_")]


@measurement(summary="Get details about a reaction", cost=0)
def describe_reaction(state: dict[str, Any], reaction: str) -> dict[str, Any]:
    """Describe a reaction.

    For testing, looks for reaction info in _reactions.
    """
    reactions = state.get("_reactions", {})
    return reactions.get(reaction, {"name": reaction, "reactants": [], "products": []})


@measurement(summary="Get current concentrations", cost=0)
def observe(state: dict[str, Any]) -> dict[str, Any]:
    """Get observable concentrations.

    For testing, returns all non-internal state values.
    """
    return {k: v for k, v in state.items() if not k.startswith("_")}


@measurement(summary="Fast measurement for timing tests", cost=0, duration=0.05)
def quick_measure(state: dict[str, Any]) -> dict[str, Any]:
    """Fast measurement for timing tests."""
    return {"measured": True}


@measurement(summary="Count population of a species", cost=0.5)
def population_count(state: dict[str, Any], species: str = None) -> dict[str, Any]:
    """Count population, optionally filtered by species.

    For testing, returns concentration values as populations.
    """
    if species:
        return {species: state.get(species, 0.0)}
    return {k: v for k, v in state.items() if not k.startswith("_") and isinstance(v, (int, float))}
