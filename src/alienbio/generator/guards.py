"""Guard system for validating generated templates.

Provides:
- @guard: Decorator to mark functions as guards
- GuardContext: Context passed to guard functions
- run_guard(): Execute a guard function
- expand_with_guards(): Expand template with guard validation
- Built-in guards: no_new_species_dependencies, no_new_cycles, no_essential
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .template import Template, TemplateRegistry
from .expand import expand, ExpandedTemplate
from .exceptions import GuardViolation


# =============================================================================
# Guard Infrastructure
# =============================================================================


def guard(func: Callable) -> Callable:
    """Decorator to mark a function as a guard.

    Guards are functions that validate expanded templates.
    They should return True if validation passes, or raise
    GuardViolation if it fails.
    """
    func._is_guard = True
    return func


@dataclass
class GuardContext:
    """Context passed to guard functions.

    Attributes:
        scenario: The full scenario being built (may be partial)
        namespace: Current namespace being expanded
        seed: Random seed used for this expansion
        attempt: Current retry attempt (0-indexed)
    """
    scenario: dict[str, Any] | None
    namespace: str
    seed: int
    attempt: int = 0


def run_guard(
    guard_func: Callable[[dict, GuardContext], bool],
    expanded: dict,
    context: GuardContext,
) -> bool:
    """Execute a guard function.

    Args:
        guard_func: The guard function to run
        expanded: Expanded template data (as dict)
        context: Guard context

    Returns:
        True if guard passes

    Raises:
        GuardViolation: If guard fails
    """
    return guard_func(expanded, context)


def expand_with_guards(
    template: Template,
    guards: list[Callable],
    mode: str = "reject",
    namespace: str = "x",
    seed: int | None = None,
    max_attempts: int = 10,
    registry: TemplateRegistry | None = None,
    scenario: dict[str, Any] | None = None,
) -> ExpandedTemplate:
    """Expand a template with guard validation.

    Args:
        template: Template to expand
        guards: List of guard functions to run
        mode: How to handle violations:
            - "reject": Fail immediately
            - "retry": Re-expand with different seed
            - "prune": Remove violating elements
        namespace: Namespace prefix for expansion
        seed: Random seed
        max_attempts: Maximum retry attempts (for retry mode)
        registry: Template registry for nested expansion
        scenario: Current scenario state (for guards that need it)

    Returns:
        Expanded template that passes all guards

    Raises:
        GuardViolation: If guards fail in reject mode, or max_attempts exceeded in retry mode
    """
    current_seed = seed if seed is not None else 0

    for attempt in range(max_attempts):
        # Expand the template
        result = expand(template, namespace, registry=registry, seed=current_seed)

        # Convert to dict for guard functions
        expanded_dict = {
            "molecules": result.molecules,
            "reactions": result.reactions,
        }

        context = GuardContext(
            scenario=scenario,
            namespace=namespace,
            seed=current_seed,
            attempt=attempt,
        )

        try:
            # Run all guards
            for guard_func in guards:
                run_guard(guard_func, expanded_dict, context)

            # All guards passed
            return result

        except GuardViolation as e:
            if mode == "reject":
                raise
            elif mode == "retry":
                # Increment seed and try again
                current_seed = current_seed + 1
                continue
            elif mode == "prune":
                # Remove violating elements
                for item in e.prune:
                    if item in result.molecules:
                        del result.molecules[item]
                    if item in result.reactions:
                        del result.reactions[item]
                return result
            else:
                raise ValueError(f"Unknown guard mode: {mode}")

    # Max attempts exhausted
    raise GuardViolation(
        f"Guard validation failed after {max_attempts} attempts (max_attempts exhausted)"
    )


# =============================================================================
# Helper Functions
# =============================================================================


def get_species_from_path(path: str) -> str | None:
    """Extract species name from a namespaced molecule/reaction path.

    Args:
        path: Path like "m.Krel.energy.ME1" or "r.Kova.chain.build"

    Returns:
        Species name (e.g., "Krel") or None if no valid species
    """
    # Path format: prefix.species.rest
    # e.g., m.Krel.energy.ME1 -> Krel
    parts = path.split(".")
    if len(parts) < 2:
        return None

    # Skip prefix (m. or r.) and get next part
    species = parts[1] if parts[0] in ("m", "r") else parts[0]

    # "bg" is background, not a species
    if species == "bg":
        return None

    return species


def build_dependency_graph(reactions: dict[str, dict]) -> dict[str, list[str]]:
    """Build a graph of molecule dependencies from reactions.

    For each reaction, products depend on reactants:
    reactant -> product

    Args:
        reactions: Dict of reaction_name -> reaction_data

    Returns:
        Dict mapping reactant -> [products that depend on it]
    """
    graph: dict[str, list[str]] = {}

    for rxn_name, rxn_data in reactions.items():
        reactants = rxn_data.get("reactants", [])
        products = rxn_data.get("products", [])

        for reactant in reactants:
            if reactant not in graph:
                graph[reactant] = []
            graph[reactant].extend(products)

    return graph


def detect_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """Detect cycles in a dependency graph using DFS.

    Args:
        graph: Adjacency list representation

    Returns:
        List of cycles found (each cycle is a list of nodes)
    """
    cycles = []
    visited = set()
    rec_stack = set()
    path = []

    def dfs(node: str) -> bool:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in rec_stack:
                # Found cycle
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(cycle)
                return True

        path.pop()
        rec_stack.remove(node)
        return False

    for node in graph:
        if node not in visited:
            dfs(node)

    return cycles


# =============================================================================
# Built-in Guards
# =============================================================================


@guard
def no_new_species_dependencies(expanded: dict, context: GuardContext) -> bool:
    """Guard that prevents cross-species dependencies.

    Ensures reactions don't mix molecules from different species namespaces.
    Background (bg) molecules are allowed in any reaction.
    """
    for rxn_name, rxn_data in expanded.get("reactions", {}).items():
        reactants = rxn_data.get("reactants", [])
        products = rxn_data.get("products", [])

        all_molecules = reactants + products
        species_set = set()

        for mol in all_molecules:
            species = get_species_from_path(mol)
            if species:
                species_set.add(species)

        if len(species_set) > 1:
            raise GuardViolation(
                f"Cross-species dependency in reaction '{rxn_name}': "
                f"molecules from {species_set}",
                details={"reaction": rxn_name, "species": list(species_set)},
            )

    return True


@guard
def no_new_cycles(expanded: dict, context: GuardContext) -> bool:
    """Guard that prevents cyclic dependencies between molecules.

    Detects if any reaction creates a cycle where a molecule
    directly or indirectly produces itself.
    """
    reactions = expanded.get("reactions", {})
    graph = build_dependency_graph(reactions)
    cycles = detect_cycles(graph)

    if cycles:
        raise GuardViolation(
            f"Cycle detected: {' -> '.join(cycles[0])}",
            details={"cycles": cycles},
        )

    return True


@guard
def no_essential(expanded: dict, context: GuardContext) -> bool:
    """Guard that prevents new essential molecules.

    Ensures newly created molecules are not referenced in any
    organism's reproduction_threshold (which would make them essential).
    """
    if context.scenario is None:
        return True

    # Get all essential molecule references from reproduction thresholds
    essential_refs = set()
    for org_name, org_data in context.scenario.get("organisms", {}).items():
        threshold = org_data.get("reproduction_threshold", {})
        essential_refs.update(threshold.keys())

    # Check if any new molecule is essential
    new_molecules = set(expanded.get("molecules", {}).keys())
    essential_new = new_molecules & essential_refs

    if essential_new:
        raise GuardViolation(
            f"New molecules are marked as essential: {essential_new}",
            details={"essential_molecules": list(essential_new)},
        )

    return True
