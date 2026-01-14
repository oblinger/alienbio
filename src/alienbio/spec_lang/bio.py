"""Bio class for fetching, storing, and simulating biology specifications."""

from __future__ import annotations
from pathlib import Path
from typing import Any, TYPE_CHECKING

import yaml

from .tags import EvTag, RefTag, IncludeTag, PyRef
from .loader import transform_typed_keys, expand_defaults
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
    from alienbio.protocols.bio import Simulator
    from alienbio.bio.chemistry import ChemistryImpl
    from alienbio.bio.state import StateImpl


class SourceRoot:
    """Configuration for a source root directory.

    A source root maps a filesystem path to a Python module prefix,
    enabling fetch() to find both YAML files and Python module globals.

    Attributes:
        path: Filesystem path to search for YAML files
        module: Optional Python module prefix for Python global lookups
    """

    def __init__(self, path: str | Path, module: str | None = None):
        self.path = Path(path).resolve()
        self.module = module

    def __repr__(self) -> str:
        return f"SourceRoot({self.path!r}, module={self.module!r})"


class Bio:
    """Top-level API for Alien Biology operations.

    Bio acts as a "pegboard" holding references to implementation classes.
    The module singleton `bio` is used by default; create new instances
    for sandboxing or customization.

    Usage:
        from alienbio import Bio, bio

        bio.fetch(...)        # Use the module singleton
        bio.sim(scenario)     # Create simulator using default Simulator class

        # Customize for sandboxing:
        my_bio = Bio()
        my_bio._simulator_factory = JaxSimulator
        my_bio.sim(scenario)  # Uses JaxSimulator

        # Configure source roots:
        bio.add_source_root("./catalog", module="myproject.catalog")

        # Create Bio bound to a specific DAT:
        sandbox = Bio(dat="experiments/baseline")
        sandbox = Bio(dat=dat_obj)  # From DAT object

    Pegboard attributes (can be overridden per-instance):
        _simulator_factory: Class used by sim() to create simulators
        _source_roots: List of SourceRoot for dotted name resolution

    ORM Pattern:
        - DATs are cached: same DAT name returns the same object
        - First fetch loads DAT into memory; subsequent fetches return cached instance
        - This ensures consistent state across multiple references to the same DAT
    """

    # Class-level DAT cache (shared across all Bio instances)
    _dat_cache: dict[str, Any] = {}

    def __init__(self, *, dat: str | Any | None = None) -> None:
        """Initialize Bio with default implementations.

        Args:
            dat: Optional DAT to bind this Bio to. Can be:
                - String (DAT name): Will be fetched when needed
                - DAT object: Used directly
                - None: Anonymous DAT created lazily via bio.dat accessor
        """
        from alienbio.bio.simulator import ReferenceSimulatorImpl
        self._simulator_factory: "type[Simulator]" = ReferenceSimulatorImpl
        self._source_roots: list[SourceRoot] = []
        self._dat_ref: str | Any | None = dat  # String path or DAT object
        self._dat_object: Any = None  # Resolved DAT object (lazily loaded)

    def add_source_root(self, path: str | Path, module: str | None = None) -> None:
        """Add a source root for spec resolution.

        Args:
            path: Filesystem path to search for YAML files
            module: Optional Python module prefix for Python global lookups

        Example:
            bio.add_source_root("./catalog", module="myproject.catalog")
            bio.add_source_root("~/.alienbio/std", module="alienbio.std")
        """
        expanded_path = Path(path).expanduser()
        self._source_roots.append(SourceRoot(expanded_path, module))

    @property
    def dat(self) -> Any:
        """Get this Bio's bound DAT, creating an anonymous one if needed.

        Returns:
            The DAT object bound to this Bio. If no DAT was specified in the
            constructor and none has been created yet, creates an anonymous DAT.

        Example:
            bio = Bio()
            bio.dat  # Creates anonymous DAT on first access
            bio.dat  # Returns same DAT object
        """
        if self._dat_object is not None:
            return self._dat_object

        if self._dat_ref is None:
            # Create anonymous DAT
            # TODO: Implement anonymous DAT creation
            self._dat_object = {}
            return self._dat_object

        if isinstance(self._dat_ref, str):
            # Fetch DAT by name (uses ORM cache)
            self._dat_object = self.fetch(self._dat_ref)
            return self._dat_object

        # DAT object was passed directly
        self._dat_object = self._dat_ref
        return self._dat_object

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the DAT cache.

        Useful for testing or when DAT files have changed on disk.
        """
        cls._dat_cache.clear()

    def _load_from_python_global(
        self, module_path: str, global_name: str
    ) -> tuple[Any, str] | None:
        """Try to load data from a Python module global.

        Args:
            module_path: Full module path like "myproject.catalog.mute.mol"
            global_name: Global variable name like "ME_BASIC" or "TEMPLATE"

        Returns:
            Tuple of (data, base_dir) if found, None otherwise.
            base_dir is the directory containing the Python file.
        """
        import importlib
        import sys

        try:
            module = importlib.import_module(module_path)
        except ImportError:
            return None

        # Try the specific global name first
        if hasattr(module, global_name):
            value = getattr(module, global_name)
        # Try uppercase version
        elif hasattr(module, global_name.upper()):
            value = getattr(module, global_name.upper())
        else:
            return None

        # Get base directory from module file
        module_file = getattr(module, "__file__", None)
        if module_file:
            base_dir = str(Path(module_file).parent)
        else:
            base_dir = "."

        # Handle "yaml: " string format
        if isinstance(value, str) and value.startswith("yaml:"):
            yaml_content = value[5:].lstrip()  # Remove "yaml:" prefix
            data = yaml.safe_load(yaml_content)
            return data, base_dir

        # Handle dict format directly
        if isinstance(value, dict):
            return value, base_dir

        return None

    def _resolve_dotted_in_source_root(
        self, dotted_path: str, root: SourceRoot
    ) -> tuple[Any, str] | None:
        """Try to resolve a dotted path within a source root.

        Checks for YAML file first, then Python module global.

        Args:
            dotted_path: Path like "mute.mol.energy.ME_basic" or single "config"
            root: Source root to search in

        Returns:
            Tuple of (data, base_dir) if found, None otherwise.
        """
        parts = dotted_path.split(".") if "." in dotted_path else [dotted_path]

        # Try YAML file resolution (greedy: try longest path first)
        for i in range(len(parts), 0, -1):
            # Convert dot path to filesystem path
            yaml_path = root.path / "/".join(parts[:i])

            # Try as .yaml file
            yaml_file = yaml_path.with_suffix(".yaml")
            if yaml_file.exists():
                content = yaml_file.read_text()
                data = yaml.safe_load(content)
                base_dir = str(yaml_file.parent)

                # Dig into remaining path
                remaining = parts[i:]
                for key in remaining:
                    if isinstance(data, dict) and key in data:
                        data = data[key]
                    else:
                        return None  # Key not found

                return data, base_dir

            # Try as directory with index.yaml
            index_file = yaml_path / "index.yaml"
            if index_file.exists():
                content = index_file.read_text()
                data = yaml.safe_load(content)
                base_dir = str(index_file.parent)

                # Dig into remaining path
                remaining = parts[i:]
                for key in remaining:
                    if isinstance(data, dict) and key in data:
                        data = data[key]
                    else:
                        return None  # Key not found

                return data, base_dir

        # No YAML found, try Python module global if module prefix configured
        if root.module is not None:  # Allow empty string module
            # Build module path: root.module + all but last part
            module_parts = parts[:-1]
            global_name = parts[-1]

            if root.module:
                if module_parts:
                    full_module = f"{root.module}.{'.'.join(module_parts)}"
                else:
                    full_module = root.module
            else:
                # Empty module prefix - use parts directly
                full_module = ".".join(module_parts) if module_parts else None

            if full_module:
                result = self._load_from_python_global(full_module, global_name)
                if result is not None:
                    return result

        return None

    # =========================================================================
    # Fetch / Store / Expand
    # =========================================================================

    def fetch(self, specifier: str, *, raw: bool = False) -> Any:
        """Fetch a typed object from a specifier path.

        Routing:
        - Contains "/" → filesystem/DAT path
        - All dots → source root resolution (YAML first, then Python globals)

        Args:
            specifier: Path like "catalog/scenarios/mutualism" or dotted "mute.mol.energy.ME1"
            raw: If True, return raw YAML data without processing/hydration

        Returns:
            Hydrated object (Scenario, Chemistry, etc.) or raw dict if raw=True

        Raises:
            FileNotFoundError: If specifier path doesn't exist
        """
        # Route based on specifier format
        if "/" not in specifier and self._source_roots:
            # No slash and source roots configured → try source root resolution
            # This handles both "mute.mol.energy" and single-segment "config"
            try:
                return self._fetch_from_source_roots(specifier, raw=raw)
            except FileNotFoundError as e:
                # If specifier has dots, it's definitely a dotted path - don't try filesystem
                if "." in specifier:
                    raise
                # Single-segment: fall through to filesystem resolution
                pass

        # Filesystem/DAT path resolution
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

        # ORM caching: use resolved path as cache key
        cache_key = str(spec_file.resolve())

        # Check cache for processed data (not raw)
        if not raw and cache_key in Bio._dat_cache:
            return Bio._dat_cache[cache_key]

        # Load and parse YAML
        content = spec_file.read_text()
        data = yaml.safe_load(content)

        if data is None:
            return None

        # Raw mode: return unparsed YAML data (not cached)
        if raw:
            return data

        # Full processing: expand and hydrate
        result = self._process_and_hydrate(data, str(spec_file.parent))

        # Cache the processed result
        Bio._dat_cache[cache_key] = result

        return result

    def _fetch_from_source_roots(self, dotted_path: str, *, raw: bool = False) -> Any:
        """Fetch from configured source roots using dotted path.

        Searches source roots in order, checking YAML files first,
        then Python module globals.

        Args:
            dotted_path: Path like "mute.mol.energy.ME1"
            raw: If True, return raw data without processing

        Returns:
            Loaded and optionally processed data

        Raises:
            FileNotFoundError: If not found in any source root
        """
        searched = []

        for root in self._source_roots:
            result = self._resolve_dotted_in_source_root(dotted_path, root)
            if result is not None:
                data, base_dir = result

                if raw:
                    return data

                # Process if it's a dict (could be a primitive from dig)
                if isinstance(data, dict):
                    return self._process_and_hydrate(data, base_dir)
                return data

            searched.append(str(root.path))

        raise FileNotFoundError(
            f"'{dotted_path}' not found in source roots: {searched}"
        )

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

        # Convert object to dict (unless raw or already a dict)
        if raw or isinstance(obj, dict):
            data = obj
        elif hasattr(obj, 'to_dict'):
            data = obj.to_dict()
        else:
            # Fall back to storing object attributes
            data = {k: v for k, v in vars(obj).items() if not k.startswith('_')}

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

    def sim(self, scenario: Any) -> "Simulator":
        """Create a Simulator from a Scenario.

        Uses self._simulator_factory (defaults to ReferenceSimulatorImpl).
        Override _simulator_factory to use a different implementation.

        Args:
            scenario: Scenario object with chemistry configuration

        Returns:
            Configured simulator instance
        """
        return self._simulator_factory(scenario)

    def _process_and_hydrate(self, data: dict[str, Any], base_dir: str) -> Any:
        """Process raw data: resolve includes, refs, py refs, defaults.

        Processing pipeline:
        1. Resolve !include tags (inline other files)
        2. Transform typed keys (key.Type: → key: {_type: Type, ...})
        3. Resolve !ref tags (cross-references)
        4. Resolve !py tags (local Python access)
        5. Expand defaults
        """
        data = self._resolve_includes(data, base_dir)
        data = transform_typed_keys(data)
        data = self._resolve_refs(data, data.get("constants", {}))
        data = self._resolve_py_refs(data, base_dir)
        data = expand_defaults(data)

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

    def _resolve_py_refs(self, data: Any, base_dir: str) -> Any:
        """Recursively resolve PyRef tags in data.

        Args:
            data: Data structure potentially containing PyRef placeholders
            base_dir: Directory to resolve relative Python imports from

        Returns:
            Data with PyRef placeholders resolved to actual Python objects
        """
        if isinstance(data, PyRef):
            return data.resolve(base_dir)
        elif isinstance(data, dict):
            return {k: self._resolve_py_refs(v, base_dir) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._resolve_py_refs(item, base_dir) for item in data]
        else:
            return data


# =============================================================================
# Module-level singleton
# =============================================================================

#: The global Bio instance. Use this for all operations.
#: Both `bio.fetch()` and `Bio.fetch()` work - they access the same singleton.
bio = Bio()
