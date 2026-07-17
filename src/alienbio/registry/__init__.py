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

from .scoring import (
    behavioral_alignment,
    budget_score,
    efficiency_score,
    population_health,
)

__all__ = [
    # Scoring functions
    "behavioral_alignment",
    "budget_score",
    "population_health",
    "efficiency_score",
]
