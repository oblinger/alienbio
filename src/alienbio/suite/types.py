"""Neutral, immutable value types for the ``suite`` subsystem (L0, L2-L6).

This module carries NO domain logic: every piece of domain meaning is an
opaque :data:`Tags` mapping (``dict[str, str | float]``) that this code never
inspects or branches on.

All value types are ``@dataclass(frozen=True)`` — collections are stored as
tuples or immutable mappings, and nothing mutates after construction.

Layers:
- L0: primitive aliases (:data:`NodeId`, :data:`Tags`).
- L2: trajectory (:class:`Timeline`). ``Timeline`` holds bio
  :class:`~alienbio.protocols.bio.WorldState` snapshots (absorbed ``Trace``). The
  neutral world-input shadows (``Compartment`` / ``Topology`` / ``StateVector`` /
  ``World``) were retired into the biology
  :class:`~alienbio.bio.world.WorldImpl` (coord-PR2); a :class:`Suite` now holds
  bio ``WorldImpl`` inputs directly.
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

from .dist import Dist, ParamSchema, Seed

if TYPE_CHECKING:
    from ..bio.world import WorldImpl
    from ..protocols.bio import WorldState

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


# ═══════════════════════════════════════════════════════════════════════════
# L2 — trajectory (world inputs are the biology WorldImpl; see bio.world)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Timeline:
    """A time-ordered sequence of world states (unified model: absorbs ``Trace``).

    ``times`` are floating-point **seconds** into the simulation (no fixed tick
    grain); ``states[k]`` is the :class:`~alienbio.protocols.bio.WorldState`
    snapshot at ``times[k]`` (delta/ODE semantics — integrators stamp real
    timestamps rather than assuming a tick index).
    """

    times: tuple[float, ...]
    states: tuple["WorldState", ...]


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
class CarveResult:
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


#: A generator-based world drafter: given a seed, returns a hosted world, a
#: directly-constructed :class:`CarveResult` (ground truth by *generation choice* —
#: no carve), and optionally a pre-built :class:`Objective`. Outcome archetypes
#: build their own per-world scorer and return it here; answer archetypes return
#: ``None`` and let the pipeline build an :class:`AnswerObjective` from the
#: recipe's skeleton-read key. This is the seam that lets ``build_suite``
#: materialize archetypes whose ground truth is *chosen* (diagnose / predict /
#: intervene) alongside those whose ground truth is *carved* (identify_pathway).
Drafter = Callable[[Seed], tuple["WorldImpl", CarveResult, Optional[Objective]]]


class ObjectiveRecipe(Protocol):
    """Turns a carved :class:`CarveResult` into a task's ``Question`` + ``Objective``.

    Named by the architecture (:doc:`Suite Construction Data Model` —
    ``TaskArchetype.recipe: ObjectiveRecipe``) but never defined in code until
    now; ``recipe`` had drifted to ``Any``. A recipe is an **opaque** callable
    bundle the engines only invoke, never inspect: it holds the join between an
    archetype's *demand on the world* (its ``motif`` + ``feature_reqs``) and its
    *means of being graded*.

    Because we build the structure skeleton-first, the ground-truth key is read
    **off the skeleton by construction** — we hold the answer because we built it.
    """

    def build_question(self, skeleton: CarveResult, world: WorldImpl) -> Question:
        """Emit the structured, opaque question (``kind`` matches FT08 render kinds)."""
        ...

    def build_key(self, skeleton: CarveResult, world: WorldImpl) -> Answer:
        """Read the ground-truth answer off the skeleton by construction."""
        ...

    def grader_spec(self) -> GraderSpec:
        """Which FT06 grader + partial-credit config this archetype grades with."""
        ...


# ═══════════════════════════════════════════════════════════════════════════
# L6 — distributions everywhere, vector difficulty, worlds-as-input
# ═══════════════════════════════════════════════════════════════════════════

# Difficulty is a VECTOR: dimension name -> value.
Difficulty = dict[str, float]


@dataclass(frozen=True)
class TaskArchetype:
    """A reusable task template: motif + verb + feature requirements + recipe.

    ``drafter`` (optional) supplies a generator-constructed ``(world, skeleton,
    objective?)`` — when present, ``build_suite`` uses it instead of the
    carve-a-motif-into-a-drafted-host path, so archetypes whose ground truth is a
    generation choice (diagnose / predict / intervene) materialize through the
    same pipeline. ``extra_answer_tokens`` are answer tokens that are NOT world
    nodes (e.g. the ``predict_response`` family's ``up``/``down``/``same``),
    unioned into the vocabulary so the key can render.
    """

    id: str
    motif: Motif
    verb: str
    feature_reqs: FeatureSet
    recipe: ObjectiveRecipe
    drafter: Optional[Drafter] = None
    extra_answer_tokens: tuple[str, ...] = ()


@dataclass(frozen=True)
class TaskInstance:
    """A concrete task: archetype + world + skeleton + objective + question."""

    archetype: str
    world: str
    skeleton: CarveResult
    objective: Objective
    question: Question
    setup: Any


@dataclass(frozen=True)
class SuiteSpec:
    """A generative spec: archetype mix + per-archetype schemas + seed."""

    archetype_mix: "Dist[TaskArchetype]"


@dataclass(frozen=True)
class Suite:
    """A materialized suite: worlds + task instances."""

    worlds: tuple["WorldImpl", ...]
    tasks: tuple[TaskInstance, ...]
