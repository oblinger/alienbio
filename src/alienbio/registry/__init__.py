"""Registry for reusable components.

The registry pattern provides a central location for registerable components
that can be referenced by name in scenarios and configurations.

Components registered here become available in a global namespace when
creating simulations.

Submodules:
- scoring: Scoring functions for evaluating agent performance
- actions: (future) Built-in action implementations
- measurements: (future) Built-in measurement implementations
"""

from .scoring import budget_score, population_health, efficiency_score

__all__ = [
    # Scoring functions
    "budget_score",
    "population_health",
    "efficiency_score",
]
