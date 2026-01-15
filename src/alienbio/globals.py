"""Simulator globals: hierarchical defaults system.

Provides a layered configuration system where:
1. Built-in defaults provide baseline values
2. Scenario-level `globals:` can override defaults
3. Per-action/measurement specs can override both

Uses dotted names (e.g., "action.timing.default_wait") for logical
namespacing while storing values in a flat dictionary.

Example scenario:
    globals:
      action.timing.default_wait: false
      action.cost.default_action: 2.0

    interface:
      actions:
        add_feedstock:
          cost: !ref action.cost.default_action
"""

from __future__ import annotations

from typing import Any, Optional
import copy


# Built-in default globals
BUILTIN_DEFAULTS: dict[str, Any] = {
    # Timing defaults
    "action.timing.default_wait": True,
    "action.timing.initiation_time": 0.0,
    "action.timing.default_duration": 1.0,

    # Cost defaults
    "action.cost.default_action": 1.0,
    "action.cost.default_measurement": 0.0,
    "action.cost.error": 0.0,

    # Limit defaults
    "action.limits.max_steps": float("inf"),
    "action.limits.max_sim_time": float("inf"),
    "action.limits.budget": float("inf"),
    "action.limits.wall_clock_timeout": None,
    "action.limits.termination": None,

    # Visibility defaults (fraction of true info revealed to agent)
    "action.visibility.molecules.fraction_known": 1.0,
    "action.visibility.reactions.fraction_known": 1.0,
    "action.visibility.dependencies.fraction_known": 1.0,
}


class Globals:
    """Hierarchical globals with dotted name support.

    Provides get/set with dotted names and layered overrides.

    Example:
        g = Globals()
        g.set("action.timing.default_wait", False)
        wait = g.get("action.timing.default_wait")  # False
    """

    def __init__(
        self,
        defaults: Optional[dict[str, Any]] = None,
        scenario_overrides: Optional[dict[str, Any]] = None
    ) -> None:
        """Initialize globals with optional defaults and overrides.

        Args:
            defaults: Base defaults (uses BUILTIN_DEFAULTS if not provided)
            scenario_overrides: Scenario-level overrides (from `globals:` section)
        """
        self._defaults = defaults if defaults is not None else copy.deepcopy(BUILTIN_DEFAULTS)
        self._scenario = scenario_overrides or {}
        self._local: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get a global value by dotted name.

        Resolution order (highest priority first):
        1. Local overrides (set via set())
        2. Scenario overrides (from scenario `globals:` section)
        3. Built-in defaults

        Args:
            key: Dotted name like "action.timing.default_wait"
            default: Value to return if key not found anywhere

        Returns:
            The value from the highest-priority source, or default
        """
        if key in self._local:
            return self._local[key]
        if key in self._scenario:
            return self._scenario[key]
        if key in self._defaults:
            return self._defaults[key]
        return default

    def set(self, key: str, value: Any) -> None:
        """Set a local override for a global value.

        Args:
            key: Dotted name
            value: Value to set
        """
        self._local[key] = value

    def set_scenario_override(self, key: str, value: Any) -> None:
        """Set a scenario-level override.

        Args:
            key: Dotted name
            value: Value to set
        """
        self._scenario[key] = value

    def has(self, key: str) -> bool:
        """Check if a key exists in any layer.

        Args:
            key: Dotted name

        Returns:
            True if key exists in local, scenario, or defaults
        """
        return key in self._local or key in self._scenario or key in self._defaults

    def all_keys(self) -> set[str]:
        """Return all known keys across all layers."""
        return set(self._defaults.keys()) | set(self._scenario.keys()) | set(self._local.keys())

    def to_dict(self) -> dict[str, Any]:
        """Return merged dict with all resolved values."""
        result = copy.deepcopy(self._defaults)
        result.update(self._scenario)
        result.update(self._local)
        return result

    def clear_local(self) -> None:
        """Clear local overrides."""
        self._local = {}


def create_globals_from_scenario(scenario: dict[str, Any]) -> Globals:
    """Create a Globals instance from a scenario dict.

    Args:
        scenario: Scenario specification with optional `globals:` section

    Returns:
        Globals instance with scenario overrides applied
    """
    scenario_globals = scenario.get("globals", {})
    return Globals(scenario_overrides=scenario_globals)


def resolve_ref(value: Any, globals_instance: Globals) -> Any:
    """Resolve a reference from globals.

    Supports multiple reference formats:
    1. spec_lang Reference class (from !ref tag)
    2. Dict with "__ref__" key (internal format)
    3. Dict with "!ref" key (serialized format)

    Args:
        value: Value to resolve (may be a Reference or regular value)
        globals_instance: Globals to look up references in

    Returns:
        Resolved value, or original value if not a reference
    """
    # Check for spec_lang Reference class
    try:
        from alienbio.spec_lang.eval import Reference
        if isinstance(value, Reference):
            resolved = globals_instance.get(value.name)
            if resolved is None:
                raise ValueError(f"Global reference not found: {value.name}")
            return resolved
    except ImportError:
        pass

    # Check for dict-based reference formats
    if isinstance(value, dict):
        ref_key = value.get("__ref__") or value.get("!ref")
        if ref_key:
            resolved = globals_instance.get(ref_key)
            if resolved is None:
                raise ValueError(f"Global reference not found: {ref_key}")
            return resolved
    return value


def resolve_refs_in_dict(d: dict[str, Any], globals_instance: Globals) -> dict[str, Any]:
    """Recursively resolve all !ref values in a dict.

    Args:
        d: Dictionary potentially containing !ref values
        globals_instance: Globals to resolve references from

    Returns:
        New dict with all references resolved
    """
    # Check if we have the Reference class available
    Reference = None
    try:
        from alienbio.spec_lang.eval import Reference as RefClass
        Reference = RefClass
    except ImportError:
        pass

    result = {}
    for key, value in d.items():
        if Reference is not None and isinstance(value, Reference):
            result[key] = resolve_ref(value, globals_instance)
        elif isinstance(value, dict):
            if "__ref__" in value or "!ref" in value:
                result[key] = resolve_ref(value, globals_instance)
            else:
                result[key] = resolve_refs_in_dict(value, globals_instance)
        elif isinstance(value, list):
            result[key] = [
                resolve_ref(item, globals_instance) if (Reference is not None and isinstance(item, Reference)) else
                (resolve_refs_in_dict(item, globals_instance) if isinstance(item, dict) else item)
                for item in value
            ]
        else:
            result[key] = value
    return result


