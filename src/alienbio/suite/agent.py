"""Agent interface + deterministic scripted agent (F020, Phase-2 D4).

The load-bearing seam the whole Phase-2 runtime binds to: a structural
:class:`Agent` Protocol (``act(observation) -> (action, reasoning_steps)``)
and a concrete, deterministic :class:`ScriptedAgent` that keeps framework CI
green with zero LLM calls. ``LLMAgent`` is a deliberate follow-on over the
existing ``LLMOp`` seam (out of scope here).

- :class:`Measure` / :class:`Intervene` / :class:`Commit` / :class:`Wait` —
  the closed, neutral :data:`Action` set every world-agnostic scorer pattern
  matches on by TYPE, never by string name. Each carries an opaque ``params``
  bag (:data:`~alienbio.suite.types.Tags`) so a specific world's domain
  vocabulary never leaks into this module.
- :class:`ReasoningStep` — one opaque reasoning/decision fragment an
  :class:`Agent` produces while deciding its next :class:`Action`; threaded
  1:1 into a :class:`~alienbio.suite.deliberation.DeliberationTrace` by
  ``suite.trial.thread_reasoning_steps``.
- :class:`Agent` — the structural Protocol every decision-maker (scripted or
  LLM-backed) implements.
- :class:`WaitUntil` + :class:`ScriptedAgent` — a small declarative
  step/policy DSL (data-defined steps + a conditional-hook guard) so one
  policy behaves sensibly across stochastic, partially-observed worlds,
  deterministic under a passed :class:`~alienbio.suite.dist.Seed`. A
  ``Callable`` policy is kept as an escape hatch for the rare case a
  step-list can't express.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, Union, runtime_checkable

from .dist import Seed
from .observation import Observation
from .types import Answer, Tags

# ═══════════════════════════════════════════════════════════════════════════
# Action — closed, neutral verb set (Q2 = A)
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Measure:
    """Read a probe/observable; non-mutating.

    ``probe`` names the observable read (opaque to this module); ``params``
    carries any additional opaque configuration a specific world needs.
    """

    probe: str
    params: Tags = field(default_factory=dict)


@dataclass(frozen=True)
class Intervene:
    """Perturb a control-surface lever (set a rate, clamp a value, knock a node).

    ``lever`` names the control surface; ``value`` is the opaque setpoint;
    ``params`` carries any additional opaque configuration.
    """

    lever: str
    value: Any
    params: Tags = field(default_factory=dict)


@dataclass(frozen=True)
class Commit:
    """Submit a terminal :class:`~alienbio.suite.types.Answer`.

    The unambiguous terminal verb: a trial ends when (and only when) a
    ``Commit`` action is emitted.
    """

    answer: Answer
    params: Tags = field(default_factory=dict)


@dataclass(frozen=True)
class Wait:
    """Advance simulated time by ``duration`` seconds without measuring or acting."""

    duration: float
    params: Tags = field(default_factory=dict)


#: The closed neutral action set. Scorers pattern-match on TYPE, never on name.
Action = Union[Measure, Intervene, Commit, Wait]


# ═══════════════════════════════════════════════════════════════════════════
# ReasoningStep — one opaque reasoning fragment, threaded into DeliberationTrace
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ReasoningStep:
    """One opaque reasoning/decision fragment produced while choosing an :data:`Action`.

    Mirrors :class:`~alienbio.suite.deliberation.DeliberationStep`'s
    ``kind``/``content``/``refs`` shape, minus ``turn`` — the turn index is
    assigned when a batch of steps is threaded into a
    :class:`~alienbio.suite.deliberation.DeliberationTrace`
    (``suite.trial.thread_reasoning_steps``), since that is when the step's
    position in the overall trial timeline becomes known. An agent chooses
    its own granularity: zero, one, or many ``ReasoningStep`` entries per turn.
    """

    kind: str
    content: str
    refs: tuple[str, ...] = ()


# ═══════════════════════════════════════════════════════════════════════════
# Agent — the structural Protocol every decision-maker implements
# ═══════════════════════════════════════════════════════════════════════════


@runtime_checkable
class Agent(Protocol):
    """A decision-maker: observation in, action + reasoning out.

    Single method, deliberately diverging from the legacy
    ``agent.agents.Agent`` (``start``/``decide``/``end``, ``decide`` returns
    only an action). Here the agent returns both the :data:`Action` to take
    **and** the :class:`ReasoningStep`\\ s it produced deciding it; the
    Phase-2 runner threads the steps into the trial's
    :class:`~alienbio.suite.deliberation.DeliberationTrace` and applies the
    action.
    """

    def act(
        self, observation: Observation
    ) -> tuple[Action, tuple[ReasoningStep, ...]]: ...


# ═══════════════════════════════════════════════════════════════════════════
# ScriptedAgent — declarative step/policy DSL (Q1 = A), seeded + deterministic
# ═══════════════════════════════════════════════════════════════════════════

#: A predicate over the current turn's :data:`Observation`; only ever called,
#: never inspected.
ObservationPredicate = Callable[[Observation], bool]


@dataclass(frozen=True)
class WaitUntil:
    """A conditional-hook guard: hold at this policy position until satisfied.

    While ``predicate(observation)`` is ``False``, the agent stays parked on
    this step and emits ``Measure(probe)`` each turn (so a stochastic or
    partially-observed world can be polled until it crosses a threshold).
    The first turn ``predicate`` is ``True``, the policy advances to its next
    step and that step fires immediately (in the same ``act`` call).
    """

    predicate: ObservationPredicate
    probe: str


#: One step of a :class:`ScriptedAgent` policy: either a directly-fired
#: :data:`Action` (``Measure`` / ``Intervene`` / ``Commit``) or a
#: :class:`WaitUntil` conditional-hook guard.
PolicyStep = Union[Measure, Intervene, Commit, WaitUntil]

#: The declarative form (a step list) or the ``Callable`` escape hatch, which
#: receives the current observation and the agent's seed and must itself
#: return a deterministic ``(action, reasoning_steps)`` pair.
Policy = Union[
    "tuple[PolicyStep, ...]",
    Callable[[Observation, Seed], "tuple[Action, tuple[ReasoningStep, ...]]"],
]


class ScriptedAgent:
    """A deterministic, seeded agent driven by a declarative :data:`Policy`.

    With a step-list policy, ``act`` walks the list in order: each
    ``Measure``/``Intervene``/``Commit`` step fires as-is (that literal
    :data:`Action` is returned) and the agent advances past it; each
    ``WaitUntil`` step is a conditional-hook guard (see :class:`WaitUntil`).
    Exactly one synthetic :class:`ReasoningStep` is emitted per fired policy
    step, naming the rule that fired.

    All decisions are a pure function of ``(policy, seed, observation
    sequence)`` — a fresh ``ScriptedAgent`` built from the same ``(policy,
    seed)`` and fed the same observations in order always produces an
    identical action log, byte for byte. ``seed`` is threaded through (and
    handed to the ``Callable`` escape hatch) for any policy that needs its
    own seeded randomness; the step-list path needs none.

    Raises:
        RuntimeError: if ``act`` is called again after the policy's step
            list is exhausted (i.e. after its terminal ``Commit`` has fired).
    """

    def __init__(self, policy: Policy, seed: Seed) -> None:
        self.policy = policy
        self.seed = seed
        self._pos = 0

    def act(self, observation: Observation) -> tuple[Action, tuple[ReasoningStep, ...]]:
        if not isinstance(self.policy, tuple):
            return self.policy(observation, self.seed)

        steps = self.policy
        while True:
            if self._pos >= len(steps):
                raise RuntimeError(
                    "ScriptedAgent policy exhausted: no further steps after "
                    "its terminal Commit"
                )
            step = steps[self._pos]
            if isinstance(step, WaitUntil):
                if step.predicate(observation):
                    self._pos += 1
                    continue
                action: Action = Measure(probe=step.probe)
                reasoning = (
                    ReasoningStep(
                        kind="policy",
                        content=f"WaitUntil({step.probe!r}) unmet; measuring",
                        refs=(step.probe,),
                    ),
                )
                return action, reasoning

            self._pos += 1
            reasoning = (
                ReasoningStep(
                    kind="policy",
                    content=f"fired policy step {type(step).__name__}",
                    refs=(),
                ),
            )
            return step, reasoning
