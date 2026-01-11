"""Bio class for fetching, storing, and simulating biology specifications."""

from __future__ import annotations
from pathlib import Path
from typing import Any, TYPE_CHECKING

import yaml

from .tags import EvTag, RefTag, IncludeTag
from .loader import transform_typed_keys, expand_defaults
from .decorators import construct, deconstruct
from .eval import (
    hydrate,
    eval_node,
    make_context,
    EvalContext,
    Evaluable,
    Quoted,
    Reference,
)

if TYPE_CHECKING:
    from alienbio.bio.simulator import SimulatorBase
    from alienbio.bio.chemistry import ChemistryImpl
    from alienbio.bio.state import StateImpl


class _BioMeta(type):
    """Metaclass for Bio singleton pattern.

    Enables both class-level and instance-level method calls:
        Bio.fetch(...)     # class-level call delegates to singleton
        bio.fetch(...)     # instance call (bio is the singleton)
        Bio()              # returns the singleton, not a new instance
    """

    _instance: "Bio | None" = None

    def __call__(cls, *args: Any, **kwargs: Any) -> "Bio":
        """Return the singleton instance, creating it if needed."""
        if cls._instance is None:
            cls._instance = super().__call__(*args, **kwargs)
        return cls._instance

    def __getattribute__(cls, name: str) -> Any:
        """Intercept all class-level attribute access.

        For methods and public attributes, delegate to the singleton instance.
        This allows Bio.fetch() to work as if it were a static method.
        """
        # These attributes must come from the metaclass/class itself
        if name in ("_instance", "__class__", "__dict__", "__mro__", "__bases__",
                    "__name__", "__qualname__", "__module__", "__doc__"):
            return super().__getattribute__(name)

        # Get or create singleton
        instance = super().__getattribute__("_instance")
        if instance is None:
            instance = super().__call__()
            super().__setattr__("_instance", instance)

        # Delegate to instance
        return getattr(instance, name)


class Bio(metaclass=_BioMeta):
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
            data = deconstruct(obj)

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
        return construct(data)

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
        return deconstruct(obj)

    # =========================================================================
    # Spec Evaluation (M1.8j)
    # =========================================================================

    def load_spec(self, specifier: str) -> Any:
        """Load a spec file and return hydrated but unevaluated data.

        This returns a spec with placeholders (Evaluable, Quoted, Reference)
        that can be evaluated later with eval_spec(). This allows:
        - Multiple instantiations from the same spec
        - Different random seeds for different instantiations
        - Deferred evaluation of expressions

        Args:
            specifier: Path like "catalog/scenarios/mutualism"

        Returns:
            Hydrated spec with placeholders (not yet evaluated)

        Raises:
            FileNotFoundError: If specifier path doesn't exist

        Example:
            spec = bio.load_spec("catalog/scenarios/test")
            # Evaluate with seed 42
            result1 = bio.eval_spec(spec, seed=42)
            # Evaluate again with seed 123
            result2 = bio.eval_spec(spec, seed=123)
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

        base_dir = str(spec_file.parent)

        # Hydrate: convert tags to placeholders, resolve includes
        return hydrate(data, base_path=base_dir)

    def eval_spec(
        self,
        spec: Any,
        *,
        seed: int | None = None,
        bindings: dict[str, Any] | None = None,
        ctx: EvalContext | None = None,
    ) -> Any:
        """Evaluate a hydrated spec, resolving all placeholders.

        Evaluates:
        - Evaluable(!_) → execute Python expression
        - Reference(!ref) → lookup in bindings
        - Quoted(!quote) → return source string unchanged

        Args:
            spec: Hydrated spec from load_spec()
            seed: Random seed for reproducibility (ignored if ctx provided)
            bindings: Variables available to expressions (ignored if ctx provided)
            ctx: Full evaluation context (overrides seed/bindings)

        Returns:
            Fully evaluated spec with concrete values

        Example:
            spec = bio.load_spec("catalog/scenarios/test")

            # Evaluate with seed 42
            result = bio.eval_spec(spec, seed=42)

            # Evaluate with bindings
            result = bio.eval_spec(spec, bindings={"k": 0.5})

            # Evaluate with full context
            ctx = make_context(seed=42, bindings={"k": 0.5})
            result = bio.eval_spec(spec, ctx=ctx)
        """
        if ctx is None:
            ctx = make_context(seed=seed, bindings=bindings)

        return eval_node(spec, ctx)

    # =========================================================================
    # Internal helpers
    # =========================================================================

    # =========================================================================
    # Scenario Instantiation (M2.7)
    # =========================================================================

    def build(
        self,
        spec: str | dict[str, Any],
        seed: int = 0,
        registry: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Build a scenario from a spec.

        Template instantiation: expand templates into a concrete scenario.

        Args:
            spec: Spec dict or specifier string (fetched first if string)
            seed: Random seed for reproducibility
            registry: Template registry for resolving template references
            params: Parameter overrides

        Returns:
            Scenario with visible and ground truth data
        """
        from alienbio.build import instantiate as build_instantiate

        # If spec is a string, fetch it first
        if isinstance(spec, str):
            spec = self.fetch(spec, raw=True)

        return build_instantiate(spec, seed=seed, registry=registry, params=params)

    def run(
        self,
        target: str | dict[str, Any],
        seed: int = 0,
        registry: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Run a target: build if needed, then execute.

        Args:
            target: Specifier string, dict spec, or DAT
            seed: Random seed for reproducibility
            registry: Template registry for resolving template references
            params: Parameter overrides

        Returns:
            Execution result

        Behavior:
        - If target is a string: calls build(target), then executes
        - If target is a dict: calls build(dict), then executes
        - If target is a DAT: executes directly
        """
        # If string, build first (which fetches)
        if isinstance(target, str):
            scenario = self.build(target, seed=seed, registry=registry, params=params)
        elif isinstance(target, dict):
            scenario = self.build(target, seed=seed, registry=registry, params=params)
        else:
            # Already a scenario/DAT
            scenario = target

        # TODO: Execute the scenario
        # For now, just return the built scenario
        return scenario

    def sim(self, scenario: Any) -> "SimulatorBase":
        """Create a Simulator from a Scenario.

        This is a convenience method for creating a reference simulator
        directly from a scenario object.

        Args:
            scenario: Scenario object with chemistry configuration

        Returns:
            Configured simulator instance
        """
        from alienbio.bio.simulator import ReferenceSimulatorImpl
        return ReferenceSimulatorImpl(scenario)

    def _process_and_hydrate(self, data: dict[str, Any], base_dir: str) -> Any:
        """Process raw data and hydrate to typed object."""
        # Process the data: resolve includes, transform typed keys, etc.
        data = self._resolve_includes(data, base_dir)
        data = transform_typed_keys(data)
        data = self._resolve_refs(data, data.get("constants", {}))
        data = expand_defaults(data)

        # Check for top-level _type (e.g., from Bio.store)
        if "_type" in data:
            return construct(data)

        # Find the first typed object and hydrate it
        for key, value in data.items():
            if isinstance(value, dict) and "_type" in value:
                return construct(value)

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
#: Both `bio.fetch()` and `Bio.fetch()` work - they access the same singleton.
bio = Bio()
