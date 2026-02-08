"""Compiled simulator — creates runnable simulators from scenario specs.

Takes a scenario with rate expressions (Quoted or string) and compiles
them into efficient callables. The resulting CompiledSimulator works
with dict-based state for simplicity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .eval import Quoted
from .rate_compiler import compile_rate_expression


@dataclass
class ScenarioSpec:
    """Lightweight scenario specification for compiled simulation.

    Attributes:
        name: Scenario identifier
        molecules: Molecule names to properties
        reactions: Reaction name to dict with substrates, products, rate
        initial_state: Molecule name to initial concentration
        scope: Named constants for rate compilation
    """
    name: str
    molecules: dict[str, Any]
    reactions: dict[str, Any]
    initial_state: dict[str, float]
    scope: dict[str, Any] = field(default_factory=dict)


@dataclass
class _CompiledReaction:
    """A reaction with its rate compiled to a callable."""
    name: str
    substrates: list[str]
    products: list[str]
    rate_fn: Callable[[dict[str, float]], float]


class CompiledSimulator:
    """Simulator created from a scenario spec with compiled rate expressions.

    Rate expressions are compiled once at construction time. The simulator
    operates on dict-based state (molecule name -> concentration).
    """

    def __init__(self, scenario: ScenarioSpec, dt: float = 1.0) -> None:
        self._scenario = scenario
        self._dt = dt
        self._reactions = self._compile_reactions()
        self._internal_state: dict[str, float] | None = None

    def _compile_reactions(self) -> list[_CompiledReaction]:
        """Compile all rate expressions in the scenario."""
        compiled = []
        for name, rxn in self._scenario.reactions.items():
            source = rxn["rate"]
            if isinstance(source, Quoted):
                source = source.source
            elif isinstance(source, (int, float)):
                source = str(source)
            rate_fn = compile_rate_expression(str(source), self._scenario.scope)
            compiled.append(_CompiledReaction(
                name=name,
                substrates=list(rxn.get("substrates", [])),
                products=list(rxn.get("products", [])),
                rate_fn=rate_fn,
            ))
        return compiled

    def initial_state(self) -> dict[str, float]:
        """Return a fresh copy of the initial state."""
        state = dict(self._scenario.initial_state)
        self._internal_state = dict(state)
        return state

    def step(self, state: dict[str, float]) -> dict[str, float]:
        """Advance state by one timestep using Euler integration."""
        new_state = dict(state)
        for rxn in self._reactions:
            rate_state = _build_rate_state(rxn, state)
            rate = rxn.rate_fn(rate_state) * self._dt
            for mol in rxn.substrates:
                new_state[mol] = max(0.0, new_state[mol] - rate)
            for mol in rxn.products:
                new_state[mol] = new_state[mol] + rate
        self._internal_state = dict(new_state)
        return new_state

    def run(
        self, state: dict[str, float], steps: int
    ) -> list[dict[str, float]]:
        """Run simulation for N steps, returning full history.

        Returns:
            List of length steps+1 (initial state + N stepped states)
        """
        history = [dict(state)]
        current = state
        for _ in range(steps):
            current = self.step(current)
            history.append(dict(current))
        return history

    def action(self, name: str, *args: Any) -> None:
        """Execute a named action on the internal state.

        Supported actions:
            add_feedstock(molecule, amount) — increase concentration
        """
        if self._internal_state is None:
            return
        if name == "add_feedstock" and len(args) >= 2:
            molecule, amount = args[0], float(args[1])
            if molecule in self._internal_state:
                self._internal_state[molecule] += amount

    def measure(self, name: str, *args: Any) -> float:
        """Take a named measurement from the internal state."""
        if self._internal_state is None:
            return 0.0
        if name == "concentration" and len(args) >= 1:
            return self._internal_state.get(str(args[0]), 0.0)
        return 0.0


def _build_rate_state(
    rxn: _CompiledReaction, state: dict[str, float]
) -> dict[str, float]:
    """Map molecule names to rate expression variables (S, S1, P, P1, etc.)."""
    rate_state: dict[str, float] = {}
    subs = rxn.substrates
    prods = rxn.products
    if len(subs) == 1:
        rate_state["S"] = state.get(subs[0], 0.0)
    for i, mol in enumerate(subs):
        rate_state[f"S{i + 1}"] = state.get(mol, 0.0)
    if len(prods) == 1:
        rate_state["P"] = state.get(prods[0], 0.0)
    for i, mol in enumerate(prods):
        rate_state[f"P{i + 1}"] = state.get(mol, 0.0)
    return rate_state


def compile_sim(scenario: ScenarioSpec | dict[str, Any], dt: float = 1.0) -> CompiledSimulator:
    """Create a CompiledSimulator from a scenario spec.

    Args:
        scenario: ScenarioSpec or dict with keys name, molecules, reactions,
                  initial_state, scope
        dt: Timestep size (default 1.0)

    Returns:
        CompiledSimulator ready to run
    """
    if isinstance(scenario, dict):
        scenario = ScenarioSpec(
            name=scenario.get("name", "unnamed"),
            molecules=scenario.get("molecules", {}),
            reactions=scenario.get("reactions", {}),
            initial_state=scenario.get("initial_state", {}),
            scope=scenario.get("scope", {}),
        )
    return CompiledSimulator(scenario, dt=dt)
