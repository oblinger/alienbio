"""The ``suite`` subsystem: neutral typed data model, adapters, and sampling.

A generic reaction-network / graph library. All domain meaning is carried as
opaque tags; this package never inspects tag content or evaluates rates.
"""

from __future__ import annotations

from .adapters import from_network, from_state, to_network, to_state
from .augment import augment, graph_stats
from .carve import CarveFail, carve, splice
from .cover import Cover, Feature, cover
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
    RateSpec,
    Reaction,
    ReactionNetwork,
    Renderable,
    RoleSlot,
    ScriptedOp,
    Skeleton,
    Species,
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
    "to_network",
    "from_network",
    "to_state",
    "from_state",
    # L0
    "NodeId",
    "Tags",
    "Predicate",
    # L1
    "Species",
    "RateSpec",
    "Reaction",
    "ReactionNetwork",
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
]
