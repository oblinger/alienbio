"""Neutral, immutable value types for the ``suite`` subsystem (L0, L2-L6).

This module carries NO domain logic: every piece of domain meaning is an
opaque :data:`Tags` mapping (``dict[str, str | float]``) that this code never
inspects or branches on.

All value types are ``@dataclass(frozen=True)`` — collections are stored as
tuples or immutable mappings, and nothing mutates after construction.

Layers:
- L0: primitive aliases (:data:`NodeId`, :data:`Tags`).
- L2: world / physics / state (:class:`Compartment`, :class:`Topology`,
  :class:`StateVector`, :class:`Trace`, :class:`World`).
- L3: motif (abstract) vs skeleton (concrete binding).
- L4: dynamism seam (:class:`Op`, :class:`ScriptedOp`) + covering / envelopes.
- L5: question / objective / answer.
- L6: distributions everywhere, vector difficulty, worlds-as-input.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Generic,
    Mapping,
    Optional,
    Protocol,
    TYPE_CHECKING,
    TypeVar,
    Union,
    runtime_checkable,
)

import numpy as np
import numpy.typing as npt

from .dist import Dist, ParamSchema

if TYPE_CHECKING:
    from ..bio.chemistry import ChemistryImpl

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)

# ═══════════════════════════════════════════════════════════════════════════
# L0 — primitives
# ═══════════════════════════════════════════════════════════════════════════

NodeId = str
Tags = dict[str, Union[str, float]]

# A predicate is an opaque callable over a Species/Reaction — only ever called,
# never inspected.
Predicate = Callable[[Any], bool]

# A 2D float array [n_compartments x n_species].
FloatArray = npt.NDArray[np.float64]


# ═══════════════════════════════════════════════════════════════════════════
# L2 — world (physics / space / state)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Compartment:
    """A node in the compartment tree; the root has ``parent = None``."""

    id: NodeId
    parent: Optional[NodeId]
    kind: str
    volume: float


@dataclass(frozen=True)
class Topology:
    """A compartment tree (a tuple of compartments; root has no parent)."""

    compartments: tuple[Compartment, ...]


@dataclass(frozen=True, eq=False)
class StateVector:
    """A [n_compartments x n_species] float array with id-labelled axes.

    ``__eq__`` compares array *values* (not identity) along with the axis
    labels; ``__hash__`` falls back to identity.
    """

    data: FloatArray
    compartments: tuple[NodeId, ...]
    species: tuple[NodeId, ...]

    def get(self, comp_id: NodeId, species_id: NodeId) -> float:
        ci = self.compartments.index(comp_id)
        si = self.species.index(species_id)
        return float(self.data[ci, si])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StateVector):
            return NotImplemented
        return (
            self.compartments == other.compartments
            and self.species == other.species
            and np.array_equal(self.data, other.data)
        )

    def __hash__(self) -> int:
        return object.__hash__(self)


@dataclass(frozen=True)
class Trace:
    """A time-ordered sequence of states."""

    times: tuple[float, ...]
    states: tuple[StateVector, ...]


@dataclass(frozen=True)
class World:
    """A chemistry + topology + initial state.

    F007: ``network`` is a biology :class:`~alienbio.bio.chemistry.ChemistryImpl`
    (the unified protocol model — one data model everywhere). ``topology`` /
    ``initial`` remain the neutral coordinate types until their own absorption phase.
    """

    network: "ChemistryImpl"
    topology: Topology
    initial: StateVector


# ═══════════════════════════════════════════════════════════════════════════
# L3 — motif (abstract) vs skeleton (concrete binding)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RoleSlot:
    """An abstract role: a name, a type tag, and opaque constraint predicates."""

    name: str
    type_tag: str
    constraints: tuple[Predicate, ...] = ()


@dataclass(frozen=True)
class Motif:
    """An abstract subgraph pattern: roles + tagged edges + opaque params."""

    roles: tuple[RoleSlot, ...]
    edges: tuple[tuple[str, str, str], ...]
    params: Tags = field(default_factory=dict)


@dataclass(frozen=True)
class Skeleton:
    """A concrete binding of a motif's roles to host nodes, plus edits."""

    motif: Motif
    binding: Mapping[str, NodeId]
    added: tuple[NodeId, ...] = ()
    removed: tuple[NodeId, ...] = ()


# ═══════════════════════════════════════════════════════════════════════════
# L4 — dynamism seam + covering / envelopes
# ═══════════════════════════════════════════════════════════════════════════

Directive = str


@runtime_checkable
class Op(Protocol[T_co]):
    """An opaque callable operation over a context."""

    def __call__(self, context: Any) -> T_co: ...


@dataclass(frozen=True)
class ScriptedOp(Generic[T]):
    """An :class:`Op` backed by a Python callable."""

    fn: Callable[[Any], T]

    def __call__(self, context: Any) -> T:
        return self.fn(context)


@dataclass(frozen=True)
class FeatureSet:
    """A set of named predicates a world must satisfy."""

    features: frozenset[tuple[str, Predicate]] = frozenset()


@dataclass(frozen=True)
class WorldEnvelope:
    """A parameter schema, required features, and an optional directive."""

    params: ParamSchema
    must_satisfy: FeatureSet
    directive: Optional[Directive] = None


# ═══════════════════════════════════════════════════════════════════════════
# L5 — question / objective / answer
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Answer:
    """An opaque JSON-ish value tagged by ``kind``.

    ``kind`` in {node_set, ordered_path, node_id, scalar, json}.
    """

    value: Any
    kind: str


@runtime_checkable
class Renderable(Protocol):
    """Something that can render itself to text given a vocabulary."""

    def render(self, vocabulary: Any) -> str: ...


@dataclass(frozen=True)
class Question:
    """A structured, opaque JSON-ish question tagged by ``kind``."""

    structured: Any
    kind: str


@dataclass(frozen=True)
class GraderSpec:
    """Grader configuration (tolerance / partial-credit knobs as tags)."""

    kind: str
    config: Tags = field(default_factory=dict)


@dataclass(frozen=True)
class AnswerObjective:
    """Grade a submitted answer against a key with a grader."""

    grader: GraderSpec
    key: Answer


@dataclass(frozen=True)
class OutcomeObjective:
    """Score an outcome against a target with an opaque scorer."""

    scorer: Callable
    target: Any


Objective = Union[AnswerObjective, OutcomeObjective]


# ═══════════════════════════════════════════════════════════════════════════
# L6 — distributions everywhere, vector difficulty, worlds-as-input
# ═══════════════════════════════════════════════════════════════════════════

# Difficulty is a VECTOR: dimension name -> value.
Difficulty = dict[str, float]


@dataclass(frozen=True)
class TaskArchetype:
    """A reusable task template: motif + verb + feature requirements + recipe."""

    id: str
    motif: Motif
    verb: str
    feature_reqs: FeatureSet
    recipe: Any


@dataclass(frozen=True)
class TaskInstance:
    """A concrete task: archetype + world + skeleton + objective + question."""

    archetype: str
    world: str
    skeleton: Skeleton
    objective: Objective
    question: Question
    setup: Any


@dataclass(frozen=True)
class SuiteSpec:
    """A generative spec: archetype mix + per-archetype schemas + seed."""

    archetype_mix: "Dist[TaskArchetype]"
    per_archetype: Mapping[str, tuple[ParamSchema, "Dist[Difficulty]"]]
    seed: int


@dataclass(frozen=True)
class Suite:
    """A materialized suite: worlds + task instances."""

    worlds: tuple[World, ...]
    tasks: tuple[TaskInstance, ...]
