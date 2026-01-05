"""Bio class for fetching, storing, and simulating biology specifications."""

from __future__ import annotations
from pathlib import Path
from typing import Any, TYPE_CHECKING

import yaml

from .tags import EvTag, RefTag, IncludeTag
from .loader import transform_typed_keys, expand_defaults
from .decorators import hydrate, dehydrate

if TYPE_CHECKING:
    from alienbio.bio import Simulator


class Bio:
    """Static utility class for biology specification operations.

    Methods:
        fetch(specifier) - Fetch and hydrate a typed object from a specifier
        store(specifier, obj) - Dehydrate and store a typed object
        expand(specifier) - Expand a spec (includes, refs, defaults) without hydrating
        sim(scenario) - Create a Simulator from a Scenario
    """

    @staticmethod
    def fetch(specifier: str, *, raw: bool = False) -> Any:
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
        return Bio._process_and_hydrate(data, str(spec_file.parent))

    @staticmethod
    def store(specifier: str, obj: Any, *, raw: bool = False) -> None:
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
            data = dehydrate(obj)

        # Write YAML
        with open(spec_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    @staticmethod
    def expand(specifier: str) -> dict[str, Any]:
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
        data = Bio._resolve_includes(data, base_dir)
        data = transform_typed_keys(data)
        data = Bio._resolve_refs(data, data.get("constants", {}))
        data = expand_defaults(data)

        return data

    @staticmethod
    def sim(scenario: Any) -> "Simulator":
        """Create a Simulator from a Scenario.

        Args:
            scenario: Scenario object with chemistry, containers, etc.

        Returns:
            Simulator ready to run
        """
        # Import here to avoid circular imports
        from alienbio.bio import SimpleSimulatorImpl

        # Create a simple simulator from the scenario
        # This is a basic implementation - can be enhanced later
        return SimpleSimulatorImpl(scenario)

    @staticmethod
    def _process_and_hydrate(data: dict[str, Any], base_dir: str) -> Any:
        """Process raw data and hydrate to typed object."""
        # Process the data: resolve includes, transform typed keys, etc.
        data = Bio._resolve_includes(data, base_dir)
        data = transform_typed_keys(data)
        data = Bio._resolve_refs(data, data.get("constants", {}))
        data = expand_defaults(data)

        # Check for top-level _type (e.g., from Bio.store)
        if "_type" in data:
            return hydrate(data)

        # Find the first typed object and hydrate it
        for key, value in data.items():
            if isinstance(value, dict) and "_type" in value:
                return hydrate(value)

        # If no typed object, return the raw data
        return data

    @staticmethod
    def _resolve_includes(data: Any, base_dir: str) -> Any:
        """Recursively resolve IncludeTags in data."""
        if isinstance(data, IncludeTag):
            return data.load(base_dir)
        elif isinstance(data, dict):
            return {k: Bio._resolve_includes(v, base_dir) for k, v in data.items()}
        elif isinstance(data, list):
            return [Bio._resolve_includes(item, base_dir) for item in data]
        else:
            return data

    @staticmethod
    def _resolve_refs(data: Any, constants: dict[str, Any]) -> Any:
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

            return {k: Bio._resolve_refs(v, constants) for k, v in data.items()}
        elif isinstance(data, list):
            return [Bio._resolve_refs(item, constants) for item in data]
        else:
            return data
