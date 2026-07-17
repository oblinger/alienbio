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
]
