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
]
