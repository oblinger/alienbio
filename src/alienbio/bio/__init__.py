"""Bio module: core biology classes for alienbio.

This module defines the fundamental biology abstractions:

Protocols (for type hints) - from alienbio.protocols.bio:
- Atom: protocol for atomic elements
- Molecule: protocol for molecule entities
- Reaction: protocol for reaction entities
- Flow: protocol for transport between compartments
- Chemistry: protocol for chemistry containers
- CompartmentTree: protocol for compartment topology
- WorldState: protocol for multi-compartment concentrations
- State: protocol for single-compartment concentrations
- Simulator: protocol for simulators

Implementations:
- AtomImpl: chemical elements with symbol, name, atomic_weight
- MoleculeImpl: composed of atoms with bdepth, name, derived symbol/weight
- ReactionImpl: transformations between molecules with rates
- Flow hierarchy:
  - Flow: abstract base class for all flows
  - MembraneFlow: transport across parent-child membrane with stoichiometry
  - GeneralFlow: arbitrary state modifications (placeholder, needs interpreter)
- ChemistryImpl: container for atoms, molecules, and reactions
- CompartmentImpl: biological compartment with flows, concentrations, reactions
- CompartmentTreeImpl: hierarchical compartment topology (simulation)
- WorldStateImpl: multi-compartment concentration storage (simulation)
- StateImpl: single-compartment concentrations
- ReferenceSimulatorImpl: basic single-compartment simulator
- WorldSimulatorImpl: multi-compartment simulator with flows
"""

# Protocols (for type hints) - from central protocols module
from ..protocols.bio import (
    # Type aliases
    MoleculeId,
    CompartmentId,
    # Core protocols
    Atom,
    Molecule,
    Reaction,
    Flow,
    Chemistry,
    CompartmentTree,
    WorldState,
    State,
    Simulator,
)

# Implementation classes - atoms and molecules
from .atom import AtomImpl, COMMON_ATOMS, get_atom
from .molecule import MoleculeImpl

# Implementation classes - reactions and flows
from .reaction import ReactionImpl
from .flow import Flow, MembraneFlow, GeneralFlow

# Implementation classes - containers and compartments
from .chemistry import ChemistryImpl
from .compartment import CompartmentImpl
from .compartment_tree import CompartmentTreeImpl

# Implementation classes - state
from .world_state import WorldStateImpl
from .state import StateImpl

# Implementation classes - simulation
from .simulator import ReferenceSimulatorImpl, SimulatorBase
from .world_simulator import WorldSimulatorImpl, ReactionSpec

# Implementation classes - system assembly
from .biosystem import BioSystem

# Equilibrium analysis
from .equilibrium import (
    StabilityResult,
    HomeostasisTarget,
    compute_variance,
    check_stability,
    run_to_equilibrium,
    find_unstable_rates,
    check_homeostasis,
)

# Agent interface (M7.3)
from .agent_interface import AgentInterface

# Measurements (M7.1)
from .measurements import (
    MeasurementSpec,
    ConcentrationMeasurement,
    AllConcentrationsMeasurement,
    RateMeasurement,
    MoleculeCountMeasurement,
    ReactionCountMeasurement,
)

# Actions (M7.2)
from .actions import (
    ActionSpec,
    AddMoleculeAction,
    RemoveMoleculeAction,
    SetConcentrationAction,
    AdjustRateAction,
)

# Task framework (M8)
from .task import Task, PredictTask, TaskResult
from .experiment import ExperimentResult, run_experiment

# Diagnosis and cure tasks (M11)
from ..scenarios.diagnosis import DiagnoseTask, CureTask

# Difficulty scaling (M11.3)
from ..scenarios.difficulty import generate_diagnosis_task

# Difficulty curves (M8.2 Advanced)
from ..scenarios.difficulty_curve import (
    DifficultyLevel,
    DifficultyPoint,
    DifficultyCurve,
    DifficultySpec,
    measure_difficulty_curve,
    compare_difficulty_curves,
)

# Test harness (M12)
from .harness import TestSuite, TestResults, run_suite

# Agent comparison (Advanced Analysis)
from .comparison import AgentStats, ComparisonTable, compare, compare_by_task

# Quiescence detection
from .quiescence import QuiescenceTimeout, run_until_quiet

# Skinning (M14)
from ..scenarios.skinning import (
    generate_alien_name,
    generate_description,
    generate_name_map,
    skin_task_description,
    check_no_earth_terms,
)

# Disease and variation (M10)
from ..scenarios.disease import (
    HealthRange,
    Baseline,
    Perturbation,
    Symptom,
    measure_baseline,
    generate_perturbations,
    detect_symptoms,
)

# Organ generator (M9.2)
from ..scenarios.organ_generator import (
    OrganSpec,
    TransportLink,
    Organism,
    generate_organism,
)

# Organism features (M9.3)
from ..scenarios.organism_features import (
    MaintainedMolecule,
    EnvelopeBound,
    OperatingEnvelope,
    EnvelopeViolation,
    EnvelopeStatus,
    ReproductionThreshold,
    PredationRule,
    apply_maintained_molecules,
    apply_predation,
)

# Perturbation analysis
from .perturbation import (
    PerturbationResult,
    DriftResult,
    inject_spike,
    remove_reaction_drift,
    measure_intervention_response,
)

__all__ = [
    # Type aliases
    "MoleculeId",
    "CompartmentId",
    # Protocols (for type hints)
    "Atom",
    "Molecule",
    "Reaction",
    "Flow",
    "Chemistry",
    "CompartmentTree",
    "WorldState",
    "State",
    "Simulator",
    # Implementation classes
    "AtomImpl",
    "MoleculeImpl",
    "ReactionImpl",
    "MembraneFlow",
    "GeneralFlow",
    "ChemistryImpl",
    "CompartmentImpl",
    "CompartmentTreeImpl",
    "WorldStateImpl",
    "StateImpl",
    "ReferenceSimulatorImpl",
    "WorldSimulatorImpl",
    "ReactionSpec",
    # Abstract base for subclassing
    "SimulatorBase",
    # System assembly
    "BioSystem",
    # Equilibrium analysis
    "StabilityResult",
    "HomeostasisTarget",
    "compute_variance",
    "check_stability",
    "run_to_equilibrium",
    "find_unstable_rates",
    "check_homeostasis",
    # Perturbation analysis
    "PerturbationResult",
    "DriftResult",
    "inject_spike",
    "remove_reaction_drift",
    "measure_intervention_response",
    # Measurements
    "MeasurementSpec",
    "ConcentrationMeasurement",
    "AllConcentrationsMeasurement",
    "RateMeasurement",
    "MoleculeCountMeasurement",
    "ReactionCountMeasurement",
    # Actions
    "ActionSpec",
    "AddMoleculeAction",
    "RemoveMoleculeAction",
    "SetConcentrationAction",
    "AdjustRateAction",
    # Agent interface
    "AgentInterface",
    # Task framework
    "Task",
    "PredictTask",
    "TaskResult",
    "ExperimentResult",
    "run_experiment",
    # Diagnosis and cure tasks
    "DiagnoseTask",
    "CureTask",
    # Disease and variation
    "HealthRange",
    "Baseline",
    "Perturbation",
    "Symptom",
    "measure_baseline",
    "generate_perturbations",
    "detect_symptoms",
    # Difficulty scaling
    "generate_diagnosis_task",
    # Test harness
    "TestSuite",
    "TestResults",
    "run_suite",
    # Skinning
    "generate_alien_name",
    "generate_description",
    "generate_name_map",
    "skin_task_description",
    "check_no_earth_terms",
    # Agent comparison
    "AgentStats",
    "ComparisonTable",
    "compare",
    "compare_by_task",
    # Quiescence detection
    "QuiescenceTimeout",
    "run_until_quiet",
    # Organ generator
    "OrganSpec",
    "TransportLink",
    "Organism",
    "generate_organism",
    # Organism features
    "MaintainedMolecule",
    "EnvelopeBound",
    "OperatingEnvelope",
    "EnvelopeViolation",
    "EnvelopeStatus",
    "ReproductionThreshold",
    "PredationRule",
    "apply_maintained_molecules",
    "apply_predation",
    # Difficulty curves
    "DifficultyLevel",
    "DifficultyPoint",
    "DifficultyCurve",
    "DifficultySpec",
    "measure_difficulty_curve",
    "compare_difficulty_curves",
    # Atom utilities
    "COMMON_ATOMS",
    "get_atom",
]
