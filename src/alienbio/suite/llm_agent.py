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
and never derived from world internals either.

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

import json
from typing import Any, Optional

from .agent import Action, Commit, Intervene, Measure, ReasoningStep, Wait
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


class LLMAgent:
    """A live-model :class:`~alienbio.suite.agent.Agent`, riding the ``LLMOp`` seam.

    ``act`` is the thin wrapper the F025 spec calls for: ``context =
    render_observation(observation, turn)``, ``raw = self._op(context)``,
    ``action, reasoning = _parse_action(raw)`` — schema-validation, caching,
    and retry-with-child-seed are all ``LLMOp``'s, reused verbatim.

    ``llm_fn`` is always injected (see :data:`~alienbio.suite.ops.LLMFn`) — a
    test passes a deterministic mock; :func:`default_anthropic_llm_fn` builds
    the real one for the opt-in e2e path. Nothing in this class performs a
    live call itself.
    """

    def __init__(
        self,
        llm_fn: LLMFn,
        seed: Seed,
        *,
        directive: Directive = DEFAULT_DIRECTIVE,
        max_retries: int = 3,
        token_ceiling: Optional[int] = None,
    ) -> None:
        self.directive = directive
        self.token_ceiling = token_ceiling
        self._turn = 0
        self._tokens_spent = 0
        self._op: LLMOp[dict[str, Any]] = LLMOp(
            directive=directive,
            out_schema=_validate_action_json,
            llm_fn=llm_fn,
            seed=seed,
            max_retries=max_retries,
        )

    def act(self, observation: Observation) -> tuple[Action, tuple[ReasoningStep, ...]]:
        context = render_observation(observation, self._turn)
        estimate = _estimate_tokens(self.directive, context)
        if (
            self.token_ceiling is not None
            and self._tokens_spent + estimate > self.token_ceiling
        ):
            reasoning = (
                ReasoningStep(
                    kind="abort",
                    content=(
                        f"token ceiling ({self.token_ceiling}) would be exceeded "
                        f"at turn {self._turn} (spent~{self._tokens_spent}, "
                        f"+~{estimate}); aborting trial as a runaway-cost guard"
                    ),
                ),
            )
            self._turn += 1
            return (
                Commit(
                    answer=Answer(value=None, kind="json"),
                    params={"aborted": "token_ceiling"},
                ),
                reasoning,
            )

        self._tokens_spent += estimate
        raw = self._op(context)
        action, reasoning = _parse_action(raw)
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
