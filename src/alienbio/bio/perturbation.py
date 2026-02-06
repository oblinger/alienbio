"""Perturbation analysis: spike injection, reaction removal, intervention testing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, TYPE_CHECKING

from .state import StateImpl

if TYPE_CHECKING:
    from .biosystem import BioSystem


@dataclass
class PerturbationResult:
    """Result of a perturbation experiment."""

    recovered: bool
    baseline_final: Dict[str, float]
    perturbed_final: Dict[str, float]
    max_deviation: float
    recovery_step: Optional[int]
    steps_run: int


@dataclass
class DriftResult:
    """Result of a reaction removal drift experiment."""

    drifted: bool
    baseline_final: Dict[str, float]
    modified_final: Dict[str, float]
    drift_per_molecule: Dict[str, float]
    max_drift: float
    steps_run: int


def inject_spike(
    system: "BioSystem",
    molecule: str,
    amount: float,
    recovery_steps: int = 50,
    tolerance: float = 0.1,
) -> PerturbationResult:
    """Inject a concentration spike and observe recovery.

    Runs the system for recovery_steps, then injects a spike, then runs
    for another recovery_steps. Checks if the system returns to within
    tolerance of the pre-spike concentrations.

    Args:
        system: BioSystem to perturb
        molecule: Molecule to spike
        amount: Amount to add
        recovery_steps: Steps to run before and after spike
        tolerance: Fraction of pre-spike value considered "recovered"

    Returns:
        PerturbationResult with recovery information
    """
    from .biosystem import BioSystem as _BioSystem

    # Run to get baseline
    baseline_sys = _BioSystem(
        system.chemistry, system.state.copy(),
        dt=system.simulator.dt,
    )
    baseline_sys.run(recovery_steps)
    baseline_final = {name: baseline_sys.state[name] for name in baseline_sys.state}

    # Inject spike at initial state
    perturbed_sys = _BioSystem(
        system.chemistry, system.state.copy(),
        dt=system.simulator.dt,
    )
    perturbed_sys.run(recovery_steps)
    # Apply spike
    current = perturbed_sys.state[molecule]
    perturbed_sys.state[molecule] = current + amount

    # Run recovery
    recovery_timeline = perturbed_sys.run(recovery_steps)

    perturbed_final = {name: perturbed_sys.state[name] for name in perturbed_sys.state}

    # Check recovery
    max_dev = 0.0
    recovery_step = None
    recovered = True

    for name in baseline_final:
        base_val = baseline_final[name]
        pert_val = perturbed_final[name]
        if base_val > 0:
            dev = abs(pert_val - base_val) / base_val
        else:
            dev = abs(pert_val - base_val)
        max_dev = max(max_dev, dev)
        if dev > tolerance:
            recovered = False

    # Find recovery step (first step where all molecules are within tolerance)
    for step_idx, state in enumerate(recovery_timeline):
        all_ok = True
        for name in baseline_final:
            base_val = baseline_final[name]
            step_val = state[name]
            if base_val > 0:
                dev = abs(step_val - base_val) / base_val
            else:
                dev = abs(step_val - base_val)
            if dev > tolerance:
                all_ok = False
                break
        if all_ok:
            recovery_step = step_idx
            break

    return PerturbationResult(
        recovered=recovered,
        baseline_final=baseline_final,
        perturbed_final=perturbed_final,
        max_deviation=max_dev,
        recovery_step=recovery_step,
        steps_run=recovery_steps,
    )


def remove_reaction_drift(
    system: "BioSystem",
    reaction_name: str,
    steps: int = 50,
    drift_threshold: float = 0.01,
) -> DriftResult:
    """Remove a reaction and measure the resulting drift.

    Runs the system with and without the named reaction for the same
    number of steps. Compares final states to measure drift.

    Args:
        system: BioSystem to modify
        reaction_name: Name of reaction to remove
        steps: Steps to run
        drift_threshold: Minimum drift to consider "drifted"

    Returns:
        DriftResult with per-molecule drift measurements
    """
    from .biosystem import BioSystem as _BioSystem
    from .chemistry import ChemistryImpl

    # Run baseline
    baseline_sys = _BioSystem(
        system.chemistry, system.state.copy(),
        dt=system.simulator.dt,
    )
    baseline_sys.run(steps)
    baseline_final = {name: baseline_sys.state[name] for name in baseline_sys.state}

    # Create modified chemistry without the reaction
    remaining_reactions = {
        name: rxn for name, rxn in system.chemistry.reactions.items()
        if name != reaction_name
    }
    modified_chem = ChemistryImpl(
        system.chemistry.local_name + "_modified",
        atoms=system.chemistry.atoms,
        molecules=system.chemistry.molecules,
        reactions=remaining_reactions,
        dat=system.chemistry.dat(),
    )

    modified_state = StateImpl(modified_chem, initial={
        name: system.state[name] for name in system.state
    })
    modified_sys = _BioSystem(modified_chem, modified_state, dt=system.simulator.dt)
    modified_sys.run(steps)
    modified_final = {name: modified_sys.state[name] for name in modified_sys.state}

    # Compute per-molecule drift
    drift_per_mol: Dict[str, float] = {}
    for name in baseline_final:
        drift_per_mol[name] = abs(modified_final[name] - baseline_final[name])

    max_drift = max(drift_per_mol.values()) if drift_per_mol else 0.0

    return DriftResult(
        drifted=max_drift >= drift_threshold,
        baseline_final=baseline_final,
        modified_final=modified_final,
        drift_per_molecule=drift_per_mol,
        max_drift=max_drift,
        steps_run=steps,
    )


def measure_intervention_response(
    system: "BioSystem",
    intervention: Dict[str, float],
    steps: int = 50,
) -> Dict[str, float]:
    """Apply an intervention (set concentrations) and measure response.

    Args:
        system: BioSystem to perturb
        intervention: Dict mapping molecule names to new concentrations
        steps: Steps to run after intervention

    Returns:
        Dict mapping molecule names to change from pre-intervention values
    """
    from .biosystem import BioSystem as _BioSystem

    # Snapshot pre-intervention
    pre = {name: system.state[name] for name in system.state}

    # Create copy, apply intervention, run
    modified_sys = _BioSystem(
        system.chemistry, system.state.copy(),
        dt=system.simulator.dt,
    )
    for mol, value in intervention.items():
        modified_sys.state[mol] = value

    modified_sys.run(steps)

    # Compute deltas
    return {
        name: modified_sys.state[name] - pre[name]
        for name in pre
    }
