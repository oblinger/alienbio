"""Bio class for fetching, storing, and simulating biology specifications."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

import yaml

from .resolve import (
    SourceRoot,
    ResolvedPath,
    resolve_specifier,
    resolve_dotted_in_source_root,
    dig_into,
)
from .process import process_and_hydrate, resolve_includes, resolve_refs, resolve_py_refs
from .cache import get_global_cache, clear_global_cache
from .loader import transform_typed_keys, expand_defaults
from .eval import hydrate, eval_node, make_context, EvalContext

if TYPE_CHECKING:
    from alienbio.protocols.bio import Simulator


# =============================================================================
# Factory Registry
# =============================================================================

# Maps protocol -> {name -> implementation_class}
_factory_registry: dict[type, dict[str, type]] = {}

# Maps protocol -> default implementation name
_factory_defaults: dict[type, str] = {}


def register_factory(
    protocol: type,
    name: str,
    impl_class: type,
    default: bool = False,
) -> None:
    """Register an implementation class for a protocol.

    Args:
        protocol: Protocol class (e.g., Simulator, IO)
        name: Implementation name (e.g., "reference", "fast")
        impl_class: Implementation class
        default: If True, set as default for this protocol
    """
    if protocol not in _factory_registry:
        _factory_registry[protocol] = {}
    _factory_registry[protocol][name] = impl_class
    if default or protocol not in _factory_defaults:
        _factory_defaults[protocol] = name


def _resolve_factory(protocol: type, name: str | None = None) -> type:
    """Resolve implementation class for protocol.

    Args:
        protocol: Protocol class
        name: Implementation name, or None for default

    Returns:
        Implementation class

    Raises:
        KeyError: If protocol not registered or name not found
    """
    if protocol not in _factory_registry:
        raise KeyError(f"No implementations registered for {protocol.__name__}")

    if name is None:
        if protocol not in _factory_defaults:
            raise KeyError(f"No default implementation for {protocol.__name__}")
        name = _factory_defaults[protocol]

    implementations = _factory_registry[protocol]
    if name not in implementations:
        available = list(implementations.keys())
        raise KeyError(
            f"No implementation '{name}' for {protocol.__name__}. "
            f"Available: {available}"
        )

    return implementations[name]


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

    ORM Pattern:
        - DATs are cached: same DAT name returns the same object
        - First fetch loads DAT into memory; subsequent fetches return cached instance
    """

    def __init__(self, *, dat: str | Any | None = None) -> None:
        """Initialize Bio with default implementations.

        Args:
            dat: Optional DAT to bind this Bio to (string path or DAT object)
        """
        from alienbio.bio.simulator import ReferenceSimulatorImpl

        self._simulator_factory: "type[Simulator]" = ReferenceSimulatorImpl
        self._source_roots: list[SourceRoot] = []
        self._dat_ref: str | Any | None = dat
        self._dat_object: Any = None
        self._current_dat: Path | None = None

        # Component pegboard attributes
        self._io: Any = None
        self._sim: "Simulator | None" = None
        self._agent: Any = None
        self._chem: Any = None

        # Auto-configure catalog source root
        self._add_catalog_source_root()

    def _add_catalog_source_root(self) -> None:
        """Add the built-in catalog as a source root.

        Finds the catalog directory relative to the alienbio package and
        adds it as a source root for dotted-path resolution.
        """
        import alienbio
        package_dir = Path(alienbio.__file__).parent.parent.parent  # src/alienbio -> src -> project
        catalog_dir = package_dir / "catalog"
        if catalog_dir.exists():
            self._source_roots.append(SourceRoot(catalog_dir, module=None))

    # =========================================================================
    # Component Pegboard
    # =========================================================================

    @property
    def io(self) -> Any:
        """Active IO instance for entity I/O.

        Lazily creates a default IO instance on first access.
        """
        if self._io is None:
            from alienbio.infra.io import IO
            self._io = IO()
        return self._io

    @io.setter
    def io(self, value: Any) -> None:
        self._io = value

    @property
    def sim(self) -> "Simulator | None":
        """Active Simulator instance."""
        return self._sim

    @sim.setter
    def sim(self, value: "Simulator | None") -> None:
        self._sim = value

    @property
    def agent(self) -> Any:
        """Active Agent instance."""
        return self._agent

    @agent.setter
    def agent(self, value: Any) -> None:
        self._agent = value

    @property
    def chem(self) -> Any:
        """Active Chemistry instance."""
        return self._chem

    @chem.setter
    def chem(self, value: Any) -> None:
        self._chem = value

    def create(
        self,
        protocol: type,
        name: str | None = None,
        spec: Any = None,
    ) -> Any:
        """Create component instance via factory.

        Args:
            protocol: Protocol class (Simulator, IO, Agent, Chemistry, etc.)
            name: Implementation name. If None, uses default for protocol.
            spec: Data/configuration for the instance.

        Returns:
            New instance of the specified implementation.

        Raises:
            KeyError: If no implementation found for protocol/name.
        """
        impl_class = _resolve_factory(protocol, name)
        if spec is not None:
            return impl_class(spec)
        return impl_class()

    # =========================================================================
    # Source Root Configuration
    # =========================================================================

    def add_source_root(self, path: str | Path, module: str | None = None) -> None:
        """Add a source root for spec resolution.

        Args:
            path: Filesystem path to search for YAML files
            module: Optional Python module prefix for Python global lookups
        """
        expanded_path = Path(path).expanduser()
        self._source_roots.append(SourceRoot(expanded_path, module))

    # =========================================================================
    # Current DAT (cd)
    # =========================================================================

    def cd(self, path: str | Path | None = None) -> Path | None:
        """Get or set the current working DAT.

        Args:
            path: DAT path to set as current, or None to just get current

        Returns:
            Current DAT path
        """
        if path is not None:
            self._current_dat = Path(path).expanduser().resolve()
        return self._current_dat

    # =========================================================================
    # DAT Accessor
    # =========================================================================

    @property
    def dat(self) -> Any:
        """Get this Bio's bound DAT, creating an anonymous one if needed."""
        if self._dat_object is not None:
            return self._dat_object

        if self._dat_ref is None:
            self._dat_object = {}                             # anonymous DAT
            return self._dat_object

        if isinstance(self._dat_ref, str):
            self._dat_object = self.fetch(self._dat_ref)      # fetch by name
            return self._dat_object

        self._dat_object = self._dat_ref                      # passed directly
        return self._dat_object

    # =========================================================================
    # Cache Management
    # =========================================================================

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the DAT cache."""
        clear_global_cache()

    # =========================================================================
    # Fetch / Store / Expand
    # =========================================================================

    def fetch(
        self, specifier: str, *, raw: bool = False, hydrate: bool = True
    ) -> Any:
        """Fetch a typed object from a specifier path.

        Args:
            specifier: Path like "catalog/scenarios/mutualism" or "mute.mol.energy"
            raw: If True, return raw YAML without processing
            hydrate: If False, resolve tags but don't convert to typed objects

        Returns:
            Processed data (or typed object when hydration implemented)

        Raises:
            FileNotFoundError: If specifier not found
        """
        cache = get_global_cache()

        # Try source root resolution for dotted paths
        if "/" not in specifier and self._source_roots:
            result = self._fetch_from_source_roots(specifier, raw=raw, hydrate=hydrate)
            if result is not None:
                return result
            if "." in specifier:
                searched = [str(r.path) for r in self._source_roots]
                raise FileNotFoundError(f"'{specifier}' not found in source roots: {searched}")

        # Resolve specifier to path
        resolved = resolve_specifier(specifier, self._source_roots, self._current_dat)

        # Check cache (skip for raw or dig paths)
        if not raw and not resolved.dig_path and resolved.cache_key in cache:
            return cache.get(resolved.cache_key)

        # Load YAML
        content = resolved.path.read_text()
        data = yaml.safe_load(content)

        if data is None:
            return None

        # Raw mode: return unprocessed
        if raw:
            if resolved.dig_path:
                return dig_into(data, resolved.dig_path)
            return data

        # Process and cache
        result = process_and_hydrate(data, resolved.base_dir, hydrate=hydrate)

        if not resolved.dig_path:
            cache.set(resolved.cache_key, result)

        if resolved.dig_path:
            return dig_into(result, resolved.dig_path)

        return result

    def _fetch_from_source_roots(
        self, dotted_path: str, *, raw: bool = False, hydrate: bool = True
    ) -> Any | None:
        """Fetch from source roots using dotted path."""
        for root in self._source_roots:
            result = resolve_dotted_in_source_root(dotted_path, root)
            if result is not None:
                data, base_dir, _ = result
                if raw:
                    return data
                if isinstance(data, dict):
                    return process_and_hydrate(data, base_dir, hydrate=hydrate)
                return data
        return None

    def store(self, specifier: str, obj: Any, *, raw: bool = False) -> None:
        """Store a typed object to a specifier path.

        Dehydration pipeline (inverse of fetch):
        1. Convert typed objects to dicts (via to_dict() if available)
        2. Convert placeholders back to tag form:
           - Evaluable → {"!ev": source}
           - Quoted → {"!_": source}
           - Reference → {"!ref": name}
        3. Write YAML

        Args:
            specifier: Path like "catalog/scenarios/custom" or "./relative"
            obj: Object to store (dict, typed object, or hydrated data)
            raw: If True, write obj directly without any dehydration
        """
        from .eval import dehydrate

        # Resolve path
        if specifier.startswith("./"):
            if self._current_dat is None:
                raise ValueError("Relative path requires current DAT (use bio.cd() first)")
            path = self._current_dat / specifier[2:]
        else:
            path = Path(specifier)

        # Ensure directory exists
        if not path.exists():
            path.mkdir(parents=True)

        spec_file = path / "index.yaml"

        # Convert object to dict
        if raw:
            data = obj
        elif isinstance(obj, dict):
            data = dehydrate(obj)                              # dehydrate placeholders
        elif hasattr(obj, 'to_dict'):
            data = dehydrate(obj.to_dict())                    # convert + dehydrate
        else:
            raw_data = {k: v for k, v in vars(obj).items() if not k.startswith('_')}
            data = dehydrate(raw_data)

        # Write YAML
        with open(spec_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def expand(self, specifier: str) -> dict[str, Any]:
        """Expand a spec: resolve includes, refs, defaults without hydrating.

        Args:
            specifier: Path like "catalog/scenarios/mutualism"

        Returns:
            Fully expanded dict with _type fields
        """
        path = Path(specifier)

        if not path.exists():
            raise FileNotFoundError(f"Specifier path not found: {specifier}")

        if path.is_dir():
            spec_file = path / "index.yaml"
            if not spec_file.exists():
                raise FileNotFoundError(f"No index.yaml found in: {specifier}")
        else:
            spec_file = path

        content = spec_file.read_text()
        data = yaml.safe_load(content)

        if data is None:
            return {}

        base_dir = str(spec_file.parent)

        data = resolve_includes(data, base_dir)
        data = transform_typed_keys(data)
        data = resolve_refs(data, data.get("constants", {}))
        data = expand_defaults(data)

        return data

    # =========================================================================
    # Spec Evaluation
    # =========================================================================

    def load_spec(self, specifier: str) -> Any:
        """Load a spec file with placeholders for deferred evaluation.

        Args:
            specifier: Path to spec

        Returns:
            Hydrated spec with placeholders (not yet evaluated)
        """
        path = Path(specifier)

        if not path.exists():
            raise FileNotFoundError(f"Specifier path not found: {specifier}")

        if path.is_dir():
            spec_file = path / "index.yaml"
            if not spec_file.exists():
                raise FileNotFoundError(f"No index.yaml found in: {specifier}")
        else:
            spec_file = path

        content = spec_file.read_text()
        data = yaml.safe_load(content)

        if data is None:
            return None

        return hydrate(data, base_path=str(spec_file.parent))

    def eval_spec(
        self,
        spec: Any,
        *,
        seed: int | None = None,
        bindings: dict[str, Any] | None = None,
        ctx: EvalContext | None = None,
    ) -> Any:
        """Evaluate a hydrated spec, resolving all placeholders.

        Args:
            spec: Hydrated spec from load_spec()
            seed: Random seed for reproducibility
            bindings: Variables available to expressions
            ctx: Full evaluation context (overrides seed/bindings)

        Returns:
            Fully evaluated spec with concrete values
        """
        if ctx is None:
            ctx = make_context(seed=seed, bindings=bindings)
        return eval_node(spec, ctx)

    # =========================================================================
    # Build / Run / Sim
    # =========================================================================

    def build(
        self,
        spec: str | dict[str, Any],
        seed: int = 0,
        registry: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Build a scenario from a spec.

        Args:
            spec: Spec dict or specifier string
            seed: Random seed for reproducibility
            registry: Template registry
            params: Parameter overrides

        Returns:
            Scenario with visible and ground truth data
        """
        from alienbio.build import instantiate as build_instantiate

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
            seed: Random seed
            registry: Template registry
            params: Parameter overrides

        Returns:
            Execution result
        """
        if isinstance(target, (str, dict)):
            scenario = self.build(target, seed=seed, registry=registry, params=params)
        else:
            scenario = target

        # TODO: Execute the scenario
        return scenario


# =============================================================================
# Module-level singleton
# =============================================================================

bio = Bio()
