"""AgentInterface: bundles measurements and actions for agent use."""

from __future__ import annotations

from typing import Any, Dict, List, TYPE_CHECKING

from .measurements import (
    ConcentrationMeasurement,
    AllConcentrationsMeasurement,
    RateMeasurement,
    MoleculeCountMeasurement,
    ReactionCountMeasurement,
)
from .actions import (
    AddMoleculeAction,
    RemoveMoleculeAction,
    SetConcentrationAction,
    AdjustRateAction,
)

if TYPE_CHECKING:
    from .biosystem import BioSystem


class AgentInterface:
    """Agent-facing API for interacting with a BioSystem.

    Bundles all available measurements and actions with text descriptions.
    Provides a uniform interface for agents to query and modify the system.

    Example:
        interface = AgentInterface(system)
        conc = interface.measure("concentration", molecule="A")
        interface.act("add_molecule", molecule="A", amount=5.0)
    """

    def __init__(self, system: "BioSystem") -> None:
        self._system = system

        # Register built-in measurements
        self._measurements: Dict[str, Any] = {
            "concentration": ConcentrationMeasurement(),
            "all_concentrations": AllConcentrationsMeasurement(),
            "rate": RateMeasurement(),
            "molecule_count": MoleculeCountMeasurement(),
            "reaction_count": ReactionCountMeasurement(),
        }

        # Register built-in actions
        self._actions: Dict[str, Any] = {
            "add_molecule": AddMoleculeAction(),
            "remove_molecule": RemoveMoleculeAction(),
            "set_concentration": SetConcentrationAction(),
            "adjust_rate": AdjustRateAction(),
        }

    @property
    def system(self) -> "BioSystem":
        return self._system

    def available_measurements(self) -> List[Dict[str, Any]]:
        """List all available measurements with descriptions."""
        return [
            {
                "name": m.name,
                "description": m.description,
                "params": getattr(m, "params", {}),
            }
            for m in self._measurements.values()
        ]

    def available_actions(self) -> List[Dict[str, Any]]:
        """List all available actions with descriptions."""
        return [
            {
                "name": a.name,
                "description": a.description,
                "params": getattr(a, "params", {}),
            }
            for a in self._actions.values()
        ]

    def measure(self, name: str, **params: Any) -> Any:
        """Take a measurement.

        Args:
            name: Measurement name (e.g., "concentration")
            **params: Measurement parameters (e.g., molecule="A")

        Returns:
            Measurement result (type depends on measurement)

        Raises:
            KeyError: If measurement name is unknown
        """
        if name not in self._measurements:
            raise KeyError(f"Unknown measurement: {name!r}")
        m = self._measurements[name]
        return m.measure(self._system.state, **params)

    def act(self, name: str, **params: Any) -> Any:
        """Execute an action.

        For state-modifying actions (add_molecule, remove_molecule,
        set_concentration), the system's state is updated in place.

        Args:
            name: Action name (e.g., "add_molecule")
            **params: Action parameters (e.g., molecule="A", amount=5.0)

        Returns:
            The new state after the action

        Raises:
            KeyError: If action name is unknown
        """
        if name not in self._actions:
            raise KeyError(f"Unknown action: {name!r}")
        a = self._actions[name]
        new_state = a.apply(self._system.state, **params)
        self._system.state = new_state
        return new_state

    def describe(self) -> str:
        """Generate a text description of the interface for an agent."""
        lines = ["Available measurements:"]
        for m in self.available_measurements():
            params_str = ", ".join(f"{k}: {v}" for k, v in m["params"].items())
            if params_str:
                lines.append(f"  - {m['name']}({params_str}): {m['description']}")
            else:
                lines.append(f"  - {m['name']}(): {m['description']}")

        lines.append("")
        lines.append("Available actions:")
        for a in self.available_actions():
            params_str = ", ".join(f"{k}: {v}" for k, v in a["params"].items())
            if params_str:
                lines.append(f"  - {a['name']}({params_str}): {a['description']}")
            else:
                lines.append(f"  - {a['name']}(): {a['description']}")

        return "\n".join(lines)
