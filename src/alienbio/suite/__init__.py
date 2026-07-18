"""The ``suite`` subsystem: neutral typed data model and sampling.

All domain meaning is carried as opaque tags; this package never inspects tag
content or evaluates rates.
"""

from __future__ import annotations

from .augment import augment, graph_stats
from .carve import CarveFail, carve, splice
from .cover import Cover, Feature, cover
from .grade import grade_answer, grade_outcome
from .ops import LLMOp
from .pressure import (
    INTENSITY_LEVELS,
    NAMED_PRESSURES,
    PERSISTENCE_LEVELS,
    EnvironmentalPressure,
    make_pressure,
)
from .render import Vocabulary, parse, render
from .vocab import build_vocabulary
from .validity import is_shortcut_resistant, non_obvious_causal
from .archetypes import IdentifyPathwayRecipe, identify_pathway
from .arch_diagnose import (
    DiagnosePerturbationRecipe,
    diagnose_perturbation,
    draft_diagnosis_world,
)
from .arch_predict import (
    PredictResponseRecipe,
    RESPONSE_TOKENS,
    draft_prediction_world,
    predict_response,
    predicted_response,
)
from .arch_intervene import (
    DesignInterventionRecipe,
    design_intervention,
    draft_intervention_world,
    make_intervention_objective,
    make_target_scorer,
)
from .perturbations import perturb_rate, remove_reaction, spike_concentration
from .generative import (
    generative_diagnose,
    generative_intervene,
    generative_predict,
)
from .observation import (
    Observation,
    add_measurement_noise,
    choose_hidden,
    full_observation,
    project_observation,
)
from .score_divergence import final_state_distance, normalized_divergence
from .score_calibration import (
    brier_score,
    expected_calibration_error,
    mean_brier,
)
from .deliberation import DeliberationStep, DeliberationTrace
from .score_surfacing import (
    coverage_at_budget,
    is_monotone_coverage,
    surfacing_depth,
    surfacing_profile,
)
from .score_conflict import (
    dominant_objective,
    favors,
    pareto_distance,
    precedence_consistency,
)
from .score_blindspot import (
    blindspot_rate,
    consideration_coverage,
    missed_considerations,
    spurious_considerations,
)
from .score_failuremode import (
    ALIGNMENT_FAKING,
    COT_UNFAITHFUL,
    DEFAULT_PRIORITY,
    MOTIVATED_REASONING,
    NONE,
    RELEVANCE_MISS,
    SANDBAGGING,
    SYCOPHANCY,
    FailureSignals,
    classify_failure_modes,
    primary_failure_mode,
)
from .info_seeking import (
    ActionRecord,
    actions_before_commit,
    destructive_count,
    destructive_rate,
    info_seeking_count,
    info_seeking_ratio,
)
from .pipeline import build_suite, draft_world
from .verify import SimConfig, VerifyResult, simulate, verify
from ..bio.world import Compartment, WorldImpl
from .dist import (
    Choice,
    Constant,
    Dist,
    LogNormal,
    Normal,
    ParamSchema,
    Seed,
    Uniform,
)
from .types import (
    Answer,
    AnswerObjective,
    Difficulty,
    Directive,
    FeatureSet,
    GraderSpec,
    Motif,
    NodeId,
    Objective,
    ObjectiveRecipe,
    Op,
    OutcomeObjective,
    Predicate,
    Question,
    Renderable,
    RoleSlot,
    ScriptedOp,
    Skeleton,
    Suite,
    SuiteSpec,
    Tags,
    TaskArchetype,
    TaskInstance,
    Timeline,
    WorldEnvelope,
)

__all__ = [
    # dist
    "Seed",
    "Dist",
    "Constant",
    "Uniform",
    "Normal",
    "LogNormal",
    "Choice",
    "ParamSchema",
    # L0
    "NodeId",
    "Tags",
    "Predicate",
    # L2 — trajectory + biology world input (bio.world)
    "Timeline",
    "WorldImpl",
    "Compartment",
    # L3
    "RoleSlot",
    "Motif",
    "Skeleton",
    # L4
    "Directive",
    "Op",
    "ScriptedOp",
    "FeatureSet",
    "WorldEnvelope",
    # L5
    "Answer",
    "Renderable",
    "Question",
    "GraderSpec",
    "Objective",
    "ObjectiveRecipe",
    "AnswerObjective",
    "OutcomeObjective",
    # L6
    "Difficulty",
    "TaskArchetype",
    "TaskInstance",
    "SuiteSpec",
    "Suite",
    # engines
    "cover",
    "Cover",
    "Feature",
    "carve",
    "splice",
    "CarveFail",
    "augment",
    "graph_stats",
    "simulate",
    "verify",
    "VerifyResult",
    "SimConfig",
    # environmental-pressure dial (M32.4)
    "EnvironmentalPressure",
    "make_pressure",
    "NAMED_PRESSURES",
    "INTENSITY_LEVELS",
    "PERSISTENCE_LEVELS",
    "grade_answer",
    "grade_outcome",
    "LLMOp",
    "render",
    "parse",
    "Vocabulary",
    "build_vocabulary",
    "non_obvious_causal",
    "is_shortcut_resistant",
    # M27.1 archetypes + M27.4 wiring
    "identify_pathway",
    "IdentifyPathwayRecipe",
    "build_suite",
    "draft_world",
    # M29 task-family archetypes (wave 1)
    "diagnose_perturbation",
    "DiagnosePerturbationRecipe",
    "draft_diagnosis_world",
    "predict_response",
    "PredictResponseRecipe",
    "predicted_response",
    "draft_prediction_world",
    "RESPONSE_TOKENS",
    "design_intervention",
    "DesignInterventionRecipe",
    "draft_intervention_world",
    "make_intervention_objective",
    "make_target_scorer",
    # WorldImpl perturbation library
    "perturb_rate",
    "remove_reaction",
    "spike_concentration",
    # M29 build_suite-ready generative archetypes (wave-1 pipeline wiring)
    "generative_diagnose",
    "generative_predict",
    "generative_intervene",
    # M28.2 observability + M28.3 measurement-noise dials (wave 2)
    "Observation",
    "full_observation",
    "choose_hidden",
    "project_observation",
    "add_measurement_noise",
    # M33.10 divergence scorer (wave 2)
    "final_state_distance",
    "normalized_divergence",
    # M33.8 calibration scorers (wave 2)
    "brier_score",
    "mean_brier",
    "expected_calibration_error",
    # M33.1 deliberation-trace capture — second-wave keystone (wave 3)
    "DeliberationStep",
    "DeliberationTrace",
    # M33.4 per-objective surfacing (wave 3)
    "surfacing_depth",
    "surfacing_profile",
    "coverage_at_budget",
    "is_monotone_coverage",
    # M33.6 conflict-resolution scoring (wave 3)
    "dominant_objective",
    "favors",
    "precedence_consistency",
    "pareto_distance",
    # M33.5 blind-spot / should-have-considered scoring (wave 4)
    "missed_considerations",
    "spurious_considerations",
    "blindspot_rate",
    "consideration_coverage",
    # M33.3 failure-mode classification (wave 4)
    "FailureSignals",
    "classify_failure_modes",
    "primary_failure_mode",
    "DEFAULT_PRIORITY",
    "RELEVANCE_MISS",
    "MOTIVATED_REASONING",
    "COT_UNFAITHFUL",
    "ALIGNMENT_FAKING",
    "SYCOPHANCY",
    "SANDBAGGING",
    "NONE",
    # M33.8 info-seeking + action-cost metrics (wave 4)
    "ActionRecord",
    "info_seeking_count",
    "info_seeking_ratio",
    "destructive_count",
    "destructive_rate",
    "actions_before_commit",
]
