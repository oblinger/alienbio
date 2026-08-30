"""Bio class for fetching, storing, and simulating biology specifications."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, TYPE_CHECKING

import yaml

_UNSET = object()  # sentinel for cd() no-arg vs cd(None)

from .resolve import (
    SourceRoot,
    ResolvedPath,
    resolve_specifier,
    resolve_dotted_in_source_root,
    dig_into,
    _is_allowed_import,
)
from .process import process_and_hydrate, resolve_includes, resolve_refs, resolve_py_refs
from .cache import get_global_cache, clear_global_cache
from .loader import expand_defaults
from .eval import hydrate, eval_node, make_context, EvalContext
from .tags import UnsafeSpecError

if TYPE_CHECKING:
    from alienbio.protocols.bio import Simulator
    from alienbio.bio.state import StateImpl


@dataclass
class SimulationResult:
    """Result of running a simulation.

    Contains the timeline of states and metadata about the run.

    Attributes:
        timeline: List of states from simulation (StateImpl or dict)
        final_state: The final state after simulation
        steps: Number of steps executed
        dt: Time step used
        seed: Random seed used for the run
        scenario_name: Name of the scenario that was run
    """
    timeline: List[Any] = field(default_factory=list)
    final_state: Any = None
    steps: int = 0
    dt: float = 1.0
    seed: int = 0
    scenario_name: str = ""

    @property
    def final(self) -> dict[str, float]:
        """Return the final state as a dict of concentrations.

        Compatible with scoring functions that expect a dict.
        """
        if self.final_state is None:
            return {}
        if hasattr(self.final_state, 'items'):
            # StateImpl or dict
            return dict(self.final_state.items())
        return {}

    def __len__(self) -> int:
        """Return number of states in timeline."""
        return len(self.timeline)


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

        self._simulator_factory: Any = ReferenceSimulatorImpl
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
    # Compiled Simulator
    # =========================================================================

    def compile_sim(self, scenario: Any, dt: float = 1.0) -> Any:
        """Create a compiled simulator from a scenario spec.

        Compiles rate expressions (Quoted strings) into efficient callables,
        returning a CompiledSimulator with step/run/action/measure methods.

        Args:
            scenario: ScenarioSpec, dict, or any object with molecules,
                      reactions, initial_state, scope attributes
            dt: Timestep size (default 1.0)

        Returns:
            CompiledSimulator instance
        """
        from .compiled_sim import compile_sim
        return compile_sim(scenario, dt=dt)

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

    def cd(self, path: Any = _UNSET) -> Path | None:
        """Get, set, or reset the current working DAT.

        - ``cd()`` — return current DAT path
        - ``cd(path)`` — set current DAT to path
        - ``cd(None)`` — reset (clear current DAT)

        Args:
            path: DAT path to set, None to reset, or omit to get current

        Returns:
            Current DAT path (or None if reset/unset)
        """
        if path is _UNSET:
            return self._current_dat
        elif path is None:
            self._current_dat = None
            return None
        else:
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
        self, specifier: str, *, raw: bool = False, hydrate: bool = True,
        trusted: bool = False,
    ) -> Any:
        """Fetch a typed object from a specifier path.

        Args:
            specifier: Path like "catalog/scenarios/mutualism" or "mute.mol.energy"
            raw: If True, return raw YAML without processing
            hydrate: If False, resolve tags but don't convert to typed objects
            trusted: Must be True to permit code execution from the spec —
                ``include:`` .py files, ``!py`` tags, ``.py`` ``!include``, and
                absolute / parent-relative ``!include`` paths. Defaults to
                False, the secure default for untrusted agent-authored specs.

        Returns:
            Processed data (or typed object when hydration implemented)

        Raises:
            FileNotFoundError: If specifier not found
            UnsafeSpecError: If an untrusted spec requests code execution or an
                out-of-tree file read.
        """
        cache = get_global_cache()

        # Try source root resolution for dotted paths
        if "/" not in specifier and self._source_roots:
            result = self._fetch_from_source_roots(specifier, raw=raw, hydrate=hydrate, trusted=trusted)
            if result is not None:
                return result

        # Try Python module import for dotted paths (e.g., 'alienbio.bio.Chemistry')
        if "/" not in specifier and "." in specifier:
            result = self._fetch_python_import(specifier)
            if result is not None:
                return result
            if self._source_roots:
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
        result = process_and_hydrate(data, resolved.base_dir, hydrate=hydrate, trusted=trusted)

        if not resolved.dig_path:
            cache.set(resolved.cache_key, result)

        if resolved.dig_path:
            return dig_into(result, resolved.dig_path)

        return result

    def _fetch_from_source_roots(
        self, dotted_path: str, *, raw: bool = False, hydrate: bool = True,
        trusted: bool = False,
    ) -> Any | None:
        """Fetch from source roots using dotted path."""
        for root in self._source_roots:
            result = resolve_dotted_in_source_root(dotted_path, root, self._source_roots)
            if result is not None:
                data, base_dir, _ = result
                if raw:
                    return data
                if isinstance(data, dict):
                    return process_and_hydrate(data, base_dir, hydrate=hydrate, trusted=trusted)
                return data
        return None

    def _fetch_python_import(self, dotted_path: str) -> Any | None:
        """Try to import a Python object by its full dotted path.

        Handles paths like 'alienbio.bio.Chemistry' → imports module,
        returns the attribute.

        Raises:
            UnsafeSpecError: If the target module is not in the import
                allowlist (see ``resolve._is_allowed_import``). Specs are
                agent-authored / untrusted, so an arbitrary module name
                must not be importable this way.
        """
        import importlib

        parts = dotted_path.rsplit(".", 1)
        if len(parts) != 2:
            return None
        module_path, attr_name = parts

        if not _is_allowed_import(module_path, self._source_roots):
            raise UnsafeSpecError(
                f"Refusing to import '{module_path}': not in the import "
                f"allowlist for untrusted specs. Only 'alienbio' (and its "
                f"submodules) or a registered source root's module prefix "
                f"may be imported."
            )

        try:
            module = importlib.import_module(module_path)
            if hasattr(module, attr_name):
                return getattr(module, attr_name)
        except (ImportError, ModuleNotFoundError):
            pass
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
            specifier: Path or file like "output.yaml", "dat_dir/", or "./relative"
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

        # Determine output file: if path has .yaml/.yml suffix, write directly;
        # otherwise treat as DAT directory and write index.yaml
        if path.suffix in ('.yaml', '.yml'):
            spec_file = path
            spec_file.parent.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)
            spec_file = path / "index.yaml"

        # Convert object to dict
        if raw:
            data = obj
        elif isinstance(obj, dict):
            data = dehydrate(obj)
        elif hasattr(obj, 'to_dict'):
            raw_data = obj.to_dict()
            if hasattr(type(obj), '_biotype_name'):
                raw_data["_type"] = type(obj)._biotype_name
            data = dehydrate(raw_data)
        else:
            import dataclasses
            is_biotype = hasattr(type(obj), '_biotype_name')
            if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
                raw_data = dataclasses.asdict(obj)
            else:
                raw_data = {k: v for k, v in vars(obj).items() if not k.startswith('_')}
            if is_biotype:
                raw_data["_type"] = type(obj)._biotype_name
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
        complexity: float | str | None = None,
        transport_complexity: float | str | None = None,
        hidden_interdependency: int | dict[str, Any] | None = None,
    ) -> Any:
        """Build a scenario from a spec.

        Args:
            spec: Spec dict or specifier string
            seed: Random seed for reproducibility
            registry: Template registry
            params: Parameter overrides
            complexity: Network size / complexity dial (M28.1). Number or named
                level (small/medium/large/huge); ``None`` uses the spec default.
            transport_complexity: Compartment / transport-structure dial (M28.4).
                Number or named level (sparse/simple/branched/dense); ``None``
                uses the spec default.
            hidden_interdependency: Hidden inter-entity interdependency dial
                (M32.3). Non-negative count (int) or ``{"count": int,
                "type": str}``; ``None`` uses the spec default (0 => none).

        Returns:
            Scenario with visible and ground truth data
        """
        from alienbio.build import instantiate as build_instantiate

        if isinstance(spec, str):
            spec = self.fetch(spec, raw=True)

        return build_instantiate(
            spec,  # type: ignore[arg-type]
            seed=seed,
            registry=registry,
            params=params,
            complexity=complexity,
            transport_complexity=transport_complexity,
            hidden_interdependency=hidden_interdependency,
        )

    def run(
        self,
        target: str | dict[str, Any],
        seed: int = 0,
        registry: Any = None,
        params: dict[str, Any] | None = None,
        steps: int | None = None,
        dt: float | None = None,
    ) -> SimulationResult:
        """Run a target: build if needed, then execute simulation.

        This is the main entry point for M3.1 Scenario Execution.

        Pipeline:
        1. If target is a string or dict spec, build it into a Scenario
        2. Extract sim settings (steps, dt) from scenario or use defaults
        3. Build Chemistry from scenario ground truth
        4. Initialize State from scenario regions/containers
        5. Create simulator and run for N steps
        6. Return SimulationResult with timeline

        Args:
            target: Specifier string, dict spec, Scenario, or DAT
            seed: Random seed for reproducibility
            registry: Template registry for building
            params: Parameter overrides for building
            steps: Override number of simulation steps (default: from scenario or 100)
            dt: Override time step (default: from scenario or 1.0)

        Returns:
            SimulationResult with timeline of states
        """
        from alienbio.protocols import Scenario
        from alienbio.bio.chemistry import ChemistryImpl
        from alienbio.bio.state import StateImpl

        # Build scenario if needed
        if isinstance(target, str):
            scenario = self.build(target, seed=seed, registry=registry, params=params)
        elif isinstance(target, dict):
            # Check if it's a raw spec or already a scenario-like dict
            if "_ground_truth_" in target or "molecules" in target:
                scenario = target  # Already scenario-like
            else:
                scenario = self.build(target, seed=seed, registry=registry, params=params)
        else:
            scenario = target

        # Extract scenario data depending on type
        if isinstance(scenario, Scenario):
            ground_truth = scenario._ground_truth_
            regions = scenario.regions
            metadata = scenario._metadata_
            scenario_name = metadata.get("name", "scenario")
            scenario_seed = scenario._seed
        else:
            # Dict-based scenario
            ground_truth = scenario.get("_ground_truth_", scenario)
            regions = scenario.get("regions", [])
            metadata = scenario.get("_metadata_", {})
            scenario_name = metadata.get("name", scenario.get("name", "scenario"))
            scenario_seed = scenario.get("_seed", seed)

        # Extract sim settings (with overrides)
        sim_config = metadata.get("sim", {})
        effective_steps = steps if steps is not None else sim_config.get("steps", 100)
        effective_dt = dt if dt is not None else sim_config.get("dt", 1.0)

        # Build Chemistry from ground truth
        chemistry_data = {
            "molecules": ground_truth.get("molecules", {}),
            "reactions": ground_truth.get("reactions", {}),
        }
        chemistry = ChemistryImpl.hydrate(chemistry_data, local_name=scenario_name)

        # Initialize State from regions/containers
        initial_concentrations = self._extract_initial_state(regions, ground_truth)
        state = StateImpl(chemistry, initial=initial_concentrations)

        # Create simulator and run
        sim = self._simulator_factory(chemistry, dt=effective_dt)  # type: ignore[call-arg]
        timeline = sim.run(state, steps=effective_steps)  # type: ignore[arg-type]

        return SimulationResult(
            timeline=timeline,
            final_state=timeline[-1] if timeline else None,
            steps=effective_steps,
            dt=effective_dt,
            seed=scenario_seed,
            scenario_name=scenario_name,
        )

    def _extract_initial_state(
        self,
        regions: list,
        ground_truth: dict[str, Any],
    ) -> dict[str, float]:
        """Extract initial concentrations from regions and ground truth.

        For M3.1, this provides a simple initial state extraction.
        Future milestones will handle more complex region-based initialization.

        Args:
            regions: List of Region objects with organisms and substrates
            ground_truth: Ground truth data with molecules

        Returns:
            Dict of molecule name -> initial concentration
        """
        initial: dict[str, float] = {}

        # First, initialize all molecules to 0
        for mol_name in ground_truth.get("molecules", {}):
            initial[mol_name] = 0.0

        # Extract initial concentrations from regions
        if regions:
            from alienbio.protocols import Region
            for region in regions:
                if isinstance(region, Region):
                    # Add substrate concentrations
                    for substrate, conc in region.substrates.items():
                        # Map substrate names to molecule names
                        for mol_name in initial:
                            if substrate in mol_name or mol_name.endswith(f".{substrate}"):
                                initial[mol_name] = conc
                elif isinstance(region, dict):
                    for substrate, conc in region.get("substrates", {}).items():
                        for mol_name in initial:
                            if substrate in mol_name or mol_name.endswith(f".{substrate}"):
                                initial[mol_name] = conc

        # If no regions with substrates, set some default non-zero values
        # This ensures the simulation actually does something
        if all(v == 0.0 for v in initial.values()):
            # Set first molecule to 1.0 as a default starting point
            for mol_name in initial:
                initial[mol_name] = 1.0
                break

        return initial


# =============================================================================
# Module-level singleton
# =============================================================================

bio = Bio()
