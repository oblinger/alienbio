"""Scenarios: scenario-building infrastructure for alienbio.

This package contains modules for building specific test cases and
demonstrations on top of the core biology framework.
"""

# Disease and variation (M10)
from .disease import (
    HealthRange,
    Baseline,
    Perturbation,
    Symptom,
    measure_baseline,
    generate_perturbations,
    detect_symptoms,
)

# Diagnosis and cure tasks (M11)
from .diagnosis import DiagnoseTask, CureTask

# Difficulty scaling (M11.3)
from .difficulty import generate_diagnosis_task

# Difficulty curves (M8.2 Advanced)
from .difficulty_curve import (
    DifficultyLevel,
    DifficultyPoint,
    DifficultyCurve,
    DifficultySpec,
    measure_difficulty_curve,
    compare_difficulty_curves,
)

# Organ generator (M9.2)
from .organ_generator import (
    OrganSpec,
    TransportLink,
    Organism,
    generate_organism,
)

# Organism features (M9.3)
from .organism_features import (
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

# Skinning (M14)
from .skinning import (
    generate_alien_name,
    generate_description,
    generate_name_map,
    skin_task_description,
    check_no_earth_terms,
)

__all__ = [
    # Disease and variation
    "HealthRange",
    "Baseline",
    "Perturbation",
    "Symptom",
    "measure_baseline",
    "generate_perturbations",
    "detect_symptoms",
    # Diagnosis and cure tasks
    "DiagnoseTask",
    "CureTask",
    # Difficulty scaling
    "generate_diagnosis_task",
    # Difficulty curves
    "DifficultyLevel",
    "DifficultyPoint",
    "DifficultyCurve",
    "DifficultySpec",
    "measure_difficulty_curve",
    "compare_difficulty_curves",
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
    # Skinning
    "generate_alien_name",
    "generate_description",
    "generate_name_map",
    "skin_task_description",
    "check_no_earth_terms",
]
