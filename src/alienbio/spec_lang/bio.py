"""Bio class for fetching, storing, and simulating biology specifications."""

from __future__ import annotations
from pathlib import Path
from typing import Any, TYPE_CHECKING

import yaml

from .tags import EvTag, RefTag, IncludeTag
from .loader import transform_typed_keys, expand_defaults
from .decorators import hydrate as _hydrate, dehydrate as _dehydrate

if TYPE_CHECKING:
    from alienbio.bio.simulator import SimulatorBase
    from alienbio.bio.chemistry import ChemistryImpl
    from alienbio.bio.state import StateImpl


class Bio:
    """Top-level API for Alien Biology operations.

    Bio is a singleton that provides:
    - fetch/store: Load and save typed objects from/to YAML specs
    - expand: Process specs without hydrating
    - create_simulator: Factory for creating simulators from chemistry
    - register_simulator: Register custom simulator implementations

    Usage:
        from alienbio import bio

        scenario = bio.fetch("catalog/scenarios/mutualism")
        sim = bio.create_simulator(chemistry)

        # Register custom implementation
        bio.register_simulator("jax", JaxSimulatorImpl)
    """

    def __init__(self) -> None:
        """Initialize Bio with default registries."""
        self._simulators: dict[str, type] = {}
        self._default_simulator: str = "reference"
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default implementations."""
        from alienbio.bio.simulator import ReferenceSimulatorImpl
        self._simulators["reference"] = ReferenceSimulatorImpl

    # =========================================================================
    # Simulator Registry
    # =========================================================================

    def register_simulator(self, name: str, factory: type) -> None:
        """Register a simulator implementation.

        Args:
            name: Name for the simulator (e.g., "reference", "jax")
            factory: Simulator class (must accept chemistry as first arg)
        """
        self._simulators[name] = factory

    def create_simulator(
        self,
        chemistry: "ChemistryImpl",
        name: str | None = None,
        **kwargs: Any,
    ) -> "SimulatorBase":
        """Create a simulator from the registry.

        Args:
            chemistry: Chemistry to simulate
            name: Simulator name (default: "reference")
            **kwargs: Additional args passed to simulator constructor

        Returns:
            Configured simulator instance

        Raises:
            KeyError: If simulator name not registered
        """
        name = name or self._default_simulator
        if name not in self._simulators:
            available = ", ".join(self._simulators.keys())
            raise KeyError(f"Unknown simulator: {name!r}. Available: {available}")
        return self._simulators[name](chemistry, **kwargs)

    # =========================================================================
    # Fetch / Store / Expand
    # =========================================================================

    def fetch(self, specifier: str, *, raw: bool = False) -> Any:
        """Fetch a typed object from a specifier path.

        Args:
            specifier: Path like "catalog/scenarios/mutualism"
            raw: If True, return raw YAML data without processing/hydration

        Returns:
            Hydrated object (Scenario, Chemistry, etc.) or raw dict if raw=True

        Raises:
            FileNotFoundError: If specifier path doesn't exist
        """
        path = Path(specifier)

        if not path.exists():
            raise FileNotFoundError(f"Specifier path not found: {specifier}")

        # Find spec.yaml in the directory
        if path.is_dir():
            spec_file = path / "spec.yaml"
            if not spec_file.exists():
                raise FileNotFoundError(f"No spec.yaml found in: {specifier}")
        else:
            spec_file = path

        # Load and parse YAML
        content = spec_file.read_text()
        data = yaml.safe_load(content)

        if data is None:
            return None

        # Raw mode: return unparsed YAML data
        if raw:
            return data

        # Full processing: expand and hydrate
        return self._process_and_hydrate(data, str(spec_file.parent))

    def store(self, specifier: str, obj: Any, *, raw: bool = False) -> None:
        """Store a typed object to a specifier path.

        Args:
            specifier: Path like "catalog/scenarios/custom"
            obj: Object to store (must be a biotype, or dict if raw=True)
            raw: If True, write obj directly without dehydration
        """
        path = Path(specifier)

        # Ensure directory exists
        if not path.exists():
            path.mkdir(parents=True)

        spec_file = path / "spec.yaml"

        # Dehydrate object to dict (unless raw)
        if raw:
            data = obj
        else:
            data = _dehydrate(obj)

        # Write YAML
        with open(spec_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def expand(self, specifier: str) -> dict[str, Any]:
        """Expand a spec: resolve includes, refs, defaults without hydrating.

        Args:
            specifier: Path like "catalog/scenarios/mutualism"

        Returns:
            Fully expanded dict with _type fields, ready for hydration

        Raises:
            FileNotFoundError: If specifier path doesn't exist
        """
        path = Path(specifier)

        if not path.exists():
            raise FileNotFoundError(f"Specifier path not found: {specifier}")

        # Find spec.yaml in the directory
        if path.is_dir():
            spec_file = path / "spec.yaml"
            if not spec_file.exists():
                raise FileNotFoundError(f"No spec.yaml found in: {specifier}")
        else:
            spec_file = path

        # Load and parse YAML
        content = spec_file.read_text()
        data = yaml.safe_load(content)

        if data is None:
            return {}

        base_dir = str(spec_file.parent)

        # Process the data: resolve includes, transform typed keys, etc.
        data = self._resolve_includes(data, base_dir)
        data = transform_typed_keys(data)
        data = self._resolve_refs(data, data.get("constants", {}))
        data = expand_defaults(data)

        return data

    # =========================================================================
    # Hydration (advanced)
    # =========================================================================

    def hydrate(self, data: dict[str, Any]) -> Any:
        """Convert a dict with _type field to a typed object.

        Advanced method for manual hydration. Most users should use fetch().

        Args:
            data: Dict with "_type" field and object data

        Returns:
            Instance of the registered biotype

        Raises:
            KeyError: If _type not registered
            ValueError: If data doesn't have _type field
        """
        return _hydrate(data)

    def dehydrate(self, obj: Any) -> dict[str, Any]:
        """Convert a biotype object to a dict with _type field.

        Advanced method for manual dehydration. Most users should use store().

        Args:
            obj: Object with _biotype_name attribute (decorated with @biotype)

        Returns:
            Dict with "_type" field and object data

        Raises:
            ValueError: If object is not a biotype
        """
        return _dehydrate(obj)

    # =========================================================================
    # Internal helpers
    # =========================================================================

    def _process_and_hydrate(self, data: dict[str, Any], base_dir: str) -> Any:
        """Process raw data and hydrate to typed object."""
        # Process the data: resolve includes, transform typed keys, etc.
        data = self._resolve_includes(data, base_dir)
        data = transform_typed_keys(data)
        data = self._resolve_refs(data, data.get("constants", {}))
        data = expand_defaults(data)

        # Check for top-level _type (e.g., from Bio.store)
        if "_type" in data:
            return _hydrate(data)

        # Find the first typed object and hydrate it
        for key, value in data.items():
            if isinstance(value, dict) and "_type" in value:
                return _hydrate(value)

        # If no typed object, return the raw data
        return data

    def _resolve_includes(self, data: Any, base_dir: str) -> Any:
        """Recursively resolve IncludeTags in data."""
        if isinstance(data, IncludeTag):
            return data.load(base_dir)
        elif isinstance(data, dict):
            return {k: self._resolve_includes(v, base_dir) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._resolve_includes(item, base_dir) for item in data]
        else:
            return data

    def _resolve_refs(self, data: Any, constants: dict[str, Any]) -> Any:
        """Recursively resolve RefTags and EvTags in data."""
        if isinstance(data, RefTag):
            return data.resolve(constants)
        elif isinstance(data, EvTag):
            return data.evaluate(constants)
        elif isinstance(data, dict):
            # First resolve any EvTags in constants themselves
            if "constants" in data:
                resolved_constants = {}
                for k, v in data["constants"].items():
                    if isinstance(v, EvTag):
                        resolved_constants[k] = v.evaluate(resolved_constants)
                    else:
                        resolved_constants[k] = v
                data = {**data, "constants": resolved_constants}
                constants = resolved_constants

            return {k: self._resolve_refs(v, constants) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._resolve_refs(item, constants) for item in data]
        else:
            return data


# =============================================================================
# Module-level singleton
# =============================================================================

#: The global Bio instance. Use this for all operations.
bio = Bio()


# =============================================================================
# Backwards compatibility: Static method aliases
# =============================================================================
# These allow existing code using Bio.fetch() to continue working

class _BioCompat:
    """Backwards-compatible static interface to Bio singleton."""

    @staticmethod
    def fetch(specifier: str, *, raw: bool = False) -> Any:
        return bio.fetch(specifier, raw=raw)

    @staticmethod
    def store(specifier: str, obj: Any, *, raw: bool = False) -> None:
        return bio.store(specifier, obj, raw=raw)

    @staticmethod
    def expand(specifier: str) -> dict[str, Any]:
        return bio.expand(specifier)

    @staticmethod
    def hydrate(data: dict[str, Any]) -> Any:
        return bio.hydrate(data)

    @staticmethod
    def dehydrate(obj: Any) -> dict[str, Any]:
        return bio.dehydrate(obj)

    @staticmethod
    def sim(scenario: Any) -> "SimulatorBase":
        """Create a Simulator from a Scenario (legacy interface)."""
        # Legacy: scenario was passed directly
        # New code should use bio.create_simulator(chemistry)
        from alienbio.bio.simulator import ReferenceSimulatorImpl
        return ReferenceSimulatorImpl(scenario)


# Replace Bio class reference for backwards compatibility
Bio = _BioCompat  # type: ignore
