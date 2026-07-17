"""The ``suite`` subsystem: neutral typed data model, adapters, and sampling.

All domain meaning is carried as opaque tags; this package never inspects tag
content or evaluates rates.
"""

from __future__ import annotations

from .adapters import from_state, to_state
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
from .verify import SimConfig, VerifyResult, simulate, verify
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
    Compartment,
    Difficulty,
    Directive,
    FeatureSet,
    GraderSpec,
    Motif,
    NodeId,
    Objective,
    Op,
    OutcomeObjective,
    Predicate,
    Question,
    Renderable,
    RoleSlot,
    ScriptedOp,
    Skeleton,
    StateVector,
    Suite,
    SuiteSpec,
    Tags,
    TaskArchetype,
    TaskInstance,
    Topology,
    Trace,
    World,
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
    # adapters
    "to_state",
    "from_state",
    # L0
    "NodeId",
    "Tags",
    "Predicate",
    # L2
    "Compartment",
    "Topology",
    "StateVector",
    "Trace",
    "World",
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
]
