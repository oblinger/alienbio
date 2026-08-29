"""LLMAgent — a live-model Agent over the LLMOp seam (F025, opt-in, out of CI).

The *second* test layer over F020's ``Agent`` Protocol: where
:class:`~alienbio.suite.agent.ScriptedAgent` is deterministic and
network-free (keeps framework CI green), :class:`LLMAgent` routes its
decisions through a real model call — reusing the shipped
:class:`~alienbio.suite.ops.LLMOp` seam verbatim rather than adding a
parallel model path. It exists to run actual experiments; no framework test
constructs one with a live model, and the one opt-in end-to-end test is
``pytest.mark.skipif``-gated (see ``tests/suite/test_llm_agent.py``) so a bare
``uv run pytest`` collects it as skipped.

**Taint boundary (hard invariant).** ``act`` is handed only an
:class:`~alienbio.suite.observation.Observation` — a tuple of
``{observed_id: value}`` dicts already narrowed by
:func:`~alienbio.suite.observation.narrow_observation` — and this module's own
turn counter. :func:`render_observation` is a pure function of exactly those
two inputs; it has no handle on the world, the oracle, or the trial's
objective score, so nothing hidden can leak into a prompt by construction.
The static :data:`DEFAULT_DIRECTIVE` briefing is fixed at construction time
and never derived from world internals either. ``begin`` (M46.1/M46.2) widens
what the model is told, never the taint boundary: the
:class:`~alienbio.suite.brief.TaskBrief` it receives is itself built only
from the same taint-safe inputs (turn-0 narrowed observation, kinds, dials),
never the answer key/outcome target/oracle; and the turn-memory
:attr:`LLMAgent._history` this module now keeps records only what the agent
itself already saw (``observation``) and did (``action``/``outcome``) —
never anything it did not already have.

**Turn memory (M46.2).** ``memory`` controls how much of ``_history`` a
turn's context includes: ``"none"`` (no history), ``"full"`` (every prior
turn), or a non-negative ``int`` k (only the last k). Because history is
folded into the ``LLMOp`` context, it also enters the cache key
(``(directive, canonical(context), seed.value)``) — a stale/replayed
decision is never silently returned once history has moved on.

**Action schema IS the ``out_schema`` (Q2 = B).** The model must reply with
exactly one JSON object shaped like one of the closed
:data:`~alienbio.suite.agent.Action` variants; :func:`LLMOp` schema-validates
it, caches on ``(directive, canonical(context), seed.value)``, and retries
with a distinct child seed per attempt, raising ``ValueError`` after
``max_retries`` — this module adds zero new error handling on top of that.

**Token ceiling (Q3 = C).** The turn/step budget stays the runner's shared
concern (F021's ``Budget``, identical across ``ScriptedAgent`` and
``LLMAgent`` so conditions stay comparable). ``LLMAgent`` additionally
tracks its own coarse token estimate (chars / 4 over the rendered
directive+context — ``LLMFn`` has no usage-accounting hook, so this is a
heuristic runaway-cost guard, not billed usage) and, once ``token_ceiling``
would be exceeded, short-circuits with a ``Commit`` of a null answer tagged
``params={"aborted": "token_ceiling"}`` plus a ``ReasoningStep`` naming the
abort — ending the trial (recorded as ``"committed"`` with that tag, not a
new runner-level terminal reason) without ever calling the model again.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Optional, Sequence, Union, cast

from .agent import Action, ActionOutcome, Commit, Intervene, Measure, ReasoningStep, Wait
from .brief import TaskBrief, render_brief
from .dist import Seed
from .observation import Observation
from .ops import LLMFn, LLMOp, canonical
from .types import Answer, Directive

#: One Sonnet-class model id, pinned (not a floating alias) so runs are
#: comparable — matches the repo's own ``config`` default
#: (``providers.anthropic.default_model``).
PINNED_MODEL = "claude-sonnet-4-20250514"

#: The static task briefing/constitution (:data:`~alienbio.suite.types.Directive`)
#: handed to the model as ``LLMOp``'s ``directive`` — fixed at construction,
#: never derived from world internals.
DEFAULT_DIRECTIVE: Directive = (
    "You are a scientific agent probing an unfamiliar dynamical system through "
    "a narrow, partially-observed interface. Each turn you receive the current "
    "observation: a list of per-compartment dicts mapping observed ids to "
    "their measured values (anything you cannot see is simply absent, not "
    "shown as zero or null).\n\n"
    "Respond with EXACTLY one JSON object describing your next action and "
    "nothing else. Valid shapes:\n"
    '  {"type": "measure", "probe": "<id>"}\n'
    '  {"type": "intervene", "lever": "<id>", "value": <number>}\n'
    '  {"type": "wait", "duration": <number>}\n'
    '  {"type": "commit", "answer": {"value": <any>, "kind": '
    '"node_set|ordered_path|node_id|scalar|json"}}\n\n'
    'You may add a "reasoning" string field explaining your choice and a '
    '"params" object for any extra tags on the action. Only "commit" ends '
    "the trial — submit it once, when you are confident in your final answer."
)


def render_observation(observation: Observation, turn: int) -> Any:
    """The pure ``Observation -> LLMOp`` context render (the taint boundary).

    ``turn`` is this agent's own call count (never derived from hidden world
    state); it is folded into the context — not just the seed — purely so
    two turns whose narrowed ``Observation`` happens to be byte-identical
    (e.g. an unchanged probe read twice in a row) still get distinct
    ``LLMOp`` cache keys, rather than silently replaying a stale decision.
    """
    return {"turn": turn, "compartments": [dict(c) for c in observation]}


def render_context(observation: Observation, turn: int, history: Sequence[Mapping[str, Any]]) -> Any:
    """``render_observation`` plus a turn-memory ``"history"`` key (M46.2).

    ``history`` is whatever window of :attr:`LLMAgent._history` the caller
    has already applied (``"full"`` -> all of it; an ``int`` k -> the last
    k entries, possibly empty) — this function always includes the
    ``"history"`` key (as ``list(history)``, possibly ``[]``); a caller that
    wants NO ``"history"`` key at all (``memory="none"``) calls
    :func:`render_observation` directly instead of this function.
    """
    context = dict(render_observation(observation, turn))
    context["history"] = list(history)
    return context


def _estimate_tokens(directive: Directive, context: Any) -> int:
    """A coarse ~4-chars-per-token proxy over the rendered directive+context.

    ``LLMFn`` has no usage-accounting hook, so this cannot reflect real
    provider-reported usage; it exists only to size the runaway-cost guard
    (:data:`LLMAgent.token_ceiling`), not to bill precisely.
    """
    payload = directive + canonical(context)
    return max(1, len(payload) // 4)


#: The action verbs an ``LLMAgent`` reply's ``"type"`` field may name.
_ACTION_KINDS = frozenset({"measure", "intervene", "commit", "wait"})


def _validate_action_json(out: Any) -> bool:
    """The ``LLMOp.out_schema``: is ``out`` a well-formed ``Action`` JSON reply?"""
    if not isinstance(out, dict):
        return False
    kind = out.get("type")
    if kind not in _ACTION_KINDS:
        return False
    if kind == "measure":
        return isinstance(out.get("probe"), str)
    if kind == "intervene":
        return isinstance(out.get("lever"), str) and isinstance(
            out.get("value"), (int, float)
        )
    if kind == "wait":
        return isinstance(out.get("duration"), (int, float))
    # kind == "commit"
    answer = out.get("answer")
    return (
        isinstance(answer, dict)
        and "value" in answer
        and isinstance(answer.get("kind"), str)
    )


def _parse_action(out: dict[str, Any]) -> tuple[Action, tuple[ReasoningStep, ...]]:
    """Turn a schema-valid reply (already validated by ``_validate_action_json``)
    into an ``(Action, reasoning_steps)`` pair. An agent emits zero or one
    ``ReasoningStep`` per turn, carrying the model's own ``"reasoning"`` text
    verbatim if present."""
    reasoning_text = out.get("reasoning")
    reasoning: tuple[ReasoningStep, ...] = (
        (ReasoningStep(kind="llm", content=str(reasoning_text)),)
        if reasoning_text
        else ()
    )
    params = dict(out.get("params") or {})
    kind = out["type"]
    if kind == "measure":
        return Measure(probe=out["probe"], params=params), reasoning
    if kind == "intervene":
        return (
            Intervene(lever=out["lever"], value=out["value"], params=params),
            reasoning,
        )
    if kind == "wait":
        return Wait(duration=float(out["duration"]), params=params), reasoning
    # kind == "commit"
    answer = out["answer"]
    return (
        Commit(
            answer=Answer(value=answer["value"], kind=answer["kind"]), params=params
        ),
        reasoning,
    )


#: How much of ``LLMAgent._history`` a turn's context includes: ``"none"``
#: (no history), ``"full"`` (every prior turn), or a non-negative ``int`` k
#: (only the last k turns).
Memory = Union[str, int]

_MEMORY_STRINGS = frozenset({"none", "full"})


class LLMAgent:
    """A live-model :class:`~alienbio.suite.agent.Agent`, riding the ``LLMOp`` seam.

    ``act`` is the thin wrapper the F025 spec calls for: ``context =
    render_observation(observation, turn)`` (or :func:`render_context` when
    ``memory`` is not ``"none"``), ``raw = self._op(context)``, ``action,
    reasoning = _parse_action(raw)`` — schema-validation, caching, and
    retry-with-child-seed are all ``LLMOp``'s, reused verbatim.

    ``llm_fn`` is always injected (see :data:`~alienbio.suite.ops.LLMFn`) — a
    test passes a deterministic mock; :func:`default_anthropic_llm_fn` builds
    the real one for the opt-in e2e path. Nothing in this class performs a
    live call itself.

    Also implements :class:`~alienbio.suite.agent.SessionAgent`
    (structurally — ``suite.runner.run`` detects it via
    ``isinstance(agent, SessionAgent)``): ``begin(brief)`` composes the
    system prompt as ``directive + "\\n\\n" + render_brief(brief)`` and
    rebuilds ``self._op`` under it; ``notice(outcome)`` folds the runner's
    verdict on a prior turn's action back into that turn's ``_history`` entry.
    """

    def __init__(
        self,
        llm_fn: LLMFn,
        seed: Seed,
        *,
        directive: Directive = DEFAULT_DIRECTIVE,
        max_retries: int = 3,
        token_ceiling: Optional[int] = None,
        memory: Memory = "full",
    ) -> None:
        if isinstance(memory, int) and not isinstance(memory, bool):
            if memory < 0:
                raise ValueError(f"LLMAgent: memory int must be >= 0; got {memory!r}")
        elif not (isinstance(memory, str) and memory in _MEMORY_STRINGS):
            raise ValueError(
                f"LLMAgent: invalid memory {memory!r}; expected 'none', 'full', "
                "or a non-negative int"
            )
        self.memory = memory
        self.directive = directive
        self.llm_fn = llm_fn
        self.seed = seed
        self.max_retries = max_retries
        self.token_ceiling = token_ceiling
        self.brief: Optional[TaskBrief] = None
        self._turn = 0
        self._tokens_spent = 0
        self._history: list[dict[str, Any]] = []
        self._prompt_hashes: list[str] = []
        self._system: Directive = directive
        self._op: LLMOp[dict[str, Any]] = LLMOp(
            directive=self._system,
            out_schema=_validate_action_json,
            llm_fn=llm_fn,
            seed=seed,
            max_retries=max_retries,
        )

    @property
    def prompt_hashes(self) -> tuple[str, ...]:
        """One ``sha256(system_prompt + "\\n" + canonical(context))`` hex digest
        per REAL model call (groundwork for M46.10) — read-only."""
        return tuple(self._prompt_hashes)

    def begin(self, brief: TaskBrief) -> None:
        """:class:`~alienbio.suite.agent.SessionAgent`: told the trial's brief once, before turn 0.

        Composes the system prompt as ``directive + "\\n\\n" +
        render_brief(brief)`` and rebuilds ``self._op`` under it (same
        ``llm_fn``/``seed``/``max_retries`` as construction) — everything
        after ``begin`` sees the task-grounded prompt; ``act`` called before
        any ``begin`` (e.g. a test constructing an agent without a runner)
        keeps working unchanged, against the bare ``directive``.
        """
        self.brief = brief
        self._system = self.directive + "\n\n" + render_brief(brief)
        self._op = LLMOp(
            directive=self._system,
            out_schema=_validate_action_json,
            llm_fn=self.llm_fn,
            seed=self.seed,
            max_retries=self.max_retries,
        )

    def notice(self, outcome: ActionOutcome) -> None:
        """:class:`~alienbio.suite.agent.SessionAgent`: told one turn's fate.

        Folds ``{"accepted": outcome.accepted, "reason": outcome.reason}``
        into the ``_history`` entry whose ``"turn"`` matches
        ``outcome.turn``; silently ignored if no entry matches (e.g. a
        token-ceiling abort turn still appends its own entry, so this should
        always find one in practice).
        """
        for entry in self._history:
            if entry["turn"] == outcome.turn:
                entry["outcome"] = {"accepted": outcome.accepted, "reason": outcome.reason}
                return

    def _history_window(self) -> Optional[list[dict[str, Any]]]:
        """The ``_history`` slice this turn's context should carry, or ``None``
        for ``memory="none"`` (no ``"history"`` key at all)."""
        if self.memory == "none":
            return None
        if self.memory == "full":
            return self._history
        k = cast(int, self.memory)
        return self._history[-k:] if k > 0 else []

    def act(self, observation: Observation) -> tuple[Action, tuple[ReasoningStep, ...]]:
        window = self._history_window()
        context = (
            render_observation(observation, self._turn)
            if window is None
            else render_context(observation, self._turn, window)
        )
        estimate = _estimate_tokens(self._system, context)
        turn = self._turn
        if (
            self.token_ceiling is not None
            and self._tokens_spent + estimate > self.token_ceiling
        ):
            content = (
                f"token ceiling ({self.token_ceiling}) would be exceeded "
                f"at turn {self._turn} (spent~{self._tokens_spent}, "
                f"+~{estimate}); aborting trial as a runaway-cost guard"
            )
            reasoning = (ReasoningStep(kind="abort", content=content),)
            action: Action = Commit(
                answer=Answer(value=None, kind="json"),
                params={"aborted": "token_ceiling"},
            )
            self._history.append(
                {
                    "turn": turn,
                    "observation": [dict(c) for c in observation],
                    "action": {"type": "commit", "aborted": "token_ceiling"},
                    "reasoning": None,
                    "outcome": None,
                }
            )
            self._turn += 1
            return action, reasoning

        self._tokens_spent += estimate
        raw = self._op(context)
        self._prompt_hashes.append(
            hashlib.sha256((self._system + "\n" + canonical(context)).encode("utf-8")).hexdigest()
        )
        action, reasoning = _parse_action(raw)
        self._history.append(
            {
                "turn": turn,
                "observation": [dict(c) for c in observation],
                "action": {k: v for k, v in raw.items() if k != "reasoning"},
                "reasoning": raw.get("reasoning"),
                "outcome": None,
            }
        )
        self._turn += 1
        return action, reasoning


def default_anthropic_llm_fn(
    model: str = PINNED_MODEL, max_tokens: int = 1024
) -> LLMFn:
    """Build a real Anthropic-backed :data:`~alienbio.suite.ops.LLMFn` (opt-in only).

    Resolves the key via ``config.get_api_key("anthropic")`` (``os.environ``
    only — ``ANTHROPIC_API_KEY``, Keychain -> env via ``~/.zshrc``; no
    ``.env`` is ever read, Q4 = A) and fails loudly if it is absent.
    ``anthropic`` is imported lazily inside this function, so no framework
    test needs the package installed unless this factory is actually called.

    The returned ``llm_fn`` sends ``directive`` as the system prompt and the
    JSON-dumped ``context`` as the one user message, and returns the parsed
    JSON reply (or the raw text, which then simply fails
    ``LLMOp.out_schema`` and rides the existing retry path, on a
    non-JSON reply). ``seed`` is accepted (to match :data:`LLMFn`) but not
    forwarded to the provider — Claude has no literal-seed control; only the
    ``LLMOp`` cache key is seed-varied.

    Raises:
        RuntimeError: no Anthropic API key is set in the environment.
    """
    from .. import config

    api_key = config.get_api_key("anthropic")
    if not api_key:
        raise RuntimeError(
            "LLMAgent: no Anthropic API key found — set ANTHROPIC_API_KEY "
            "(Keychain -> env via ~/.zshrc); no .env is ever read"
        )

    import anthropic  # type: ignore[import-not-found]

    client = anthropic.Anthropic(api_key=api_key)

    def llm_fn(directive: Directive, context: Any, seed: Seed) -> Any:
        del seed  # accepted for LLMFn shape; Claude has no literal-seed control
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=directive,
            messages=[
                {"role": "user", "content": json.dumps(context, sort_keys=True)}
            ],
        )
        text = "".join(
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        )
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text  # fails out_schema -> LLMOp retries with a child seed

    return llm_fn
