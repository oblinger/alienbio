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

import datetime
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence, Union, cast

from .agent import Action, ActionOutcome, Commit, Intervene, Measure, ReasoningStep, Wait
from .brief import TaskBrief, render_brief
from .dist import Seed
from .observation import Observation
from .ops import LLMFn, LLMOp, canonical
from .types import Answer, Directive

#: One Sonnet-class model id, pinned (not a floating alias) so runs are
#: comparable — matches the repo's own ``config`` default
#: (``providers.anthropic.default_model``). Re-pinned 2026-08-29: the
#: original ``claude-sonnet-4-20250514`` is retired (404 for new keys).
PINNED_MODEL = "claude-sonnet-5"

#: M45.18 amendment (2026-08-31): the legal `temperature:` spelling for a model
#: with NO sampling knob. The Claude 5 API refuses `temperature`/`top_p`
#: outright ("`temperature` is deprecated for this model", probed live
#: 2026-08-31), so a spec pinned to such a model states its regime with this
#: literal instead of a number — still a STATED, reproducible regime on every
#: manifest and record line, which is what M45.18 exists to guarantee.
PROVIDER_FIXED_SAMPLING = "provider-fixed"

#: Indirection over ``time.sleep`` so :func:`_call_with_retry`'s backoff is
#: unit-testable (a test monkeypatches this module attribute rather than the
#: stdlib) without ever actually sleeping.
_sleep = time.sleep

#: Published Anthropic API list prices (USD per million tokens, input/output)
#: for the pinned model ids this repo runs, as of those generations' release
#: (M45.5). A model absent here has no known price — :func:`price_for` raises
#: rather than guess, unless the caller supplies an explicit override.
MODEL_PRICES_USD_PER_MTOK: Mapping[str, tuple[float, float]] = {
    "claude-sonnet-5": (2.0, 10.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-sonnet-4-5-20250929": (3.0, 15.0),
    "claude-opus-4-5-20251101": (5.0, 25.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}

#: T016 — the recorded ``models.list`` snapshot: ``model id -> created_at``
#: (ISO date), refreshed by ``bio suite models``. An UNDATED id (the Claude 5
#: family: ``claude-sonnet-5``, ``claude-opus-4-8``…) is pinned only if it
#: appears here, and its ``created_at`` goes on the manifest — so two runs
#: naming the same id are still provably the same generation.
MODELS_SNAPSHOT_PATH = Path(__file__).with_name("models_snapshot.json")


def load_models_snapshot(path: Optional[Path] = None) -> dict[str, str]:
    """The recorded snapshot as ``{model_id: created_at}``; ``{}`` if none."""
    path = path or MODELS_SNAPSHOT_PATH
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {str(k): str(v) for k, v in data.get("models", {}).items()}


def fetch_models_snapshot(client: Any = None) -> dict[str, str]:
    """Call the provider's ``models.list`` and return ``{id: created_at}``.
    ``client`` is any object with ``.models.list(limit=…)`` (the Anthropic
    SDK client, or a fake in tests); ``None`` builds the real one from the
    configured key. Free — no tokens are spent."""
    if client is None:
        from .. import config

        api_key = config.get_api_key("anthropic")
        if not api_key:
            raise RuntimeError("fetch_models_snapshot: no Anthropic API key found — set ANTHROPIC_API_KEY")
        import anthropic  # type: ignore[import-not-found]

        client = anthropic.Anthropic(api_key=api_key)
    out: dict[str, str] = {}
    for m in client.models.list(limit=100):
        created = getattr(m, "created_at", None)
        out[str(m.id)] = created.date().isoformat() if isinstance(created, datetime.datetime) else str(created or "")
    return out


def write_models_snapshot(models: Mapping[str, str], path: Optional[Path] = None) -> Path:
    """Record ``models`` (from :func:`fetch_models_snapshot`) with the UTC
    time it was taken. Returns the path written."""
    path = path or MODELS_SNAPSHOT_PATH
    payload = {"taken_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "models": dict(sorted(models.items()))}
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def model_created_at(model: Optional[str], snapshot: Optional[Mapping[str, str]] = None) -> Optional[str]:
    """The recorded ``created_at`` of ``model`` (``None`` when unknown)."""
    if model is None:
        return None
    return (snapshot if snapshot is not None else load_models_snapshot()).get(model)


def price_for(model: str, override: Optional[tuple[float, float]] = None) -> tuple[float, float]:
    """``(input, output)`` USD-per-million-token price for ``model``.

    ``override`` wins when given (an ``ExperimentSpec.price_usd_per_mtok``,
    e.g.); otherwise the published :data:`MODEL_PRICES_USD_PER_MTOK` entry.

    Raises:
        ValueError: ``model`` is not in :data:`MODEL_PRICES_USD_PER_MTOK` and
            no ``override`` is given — a paid sweep must never guess a price.
    """
    if override is not None:
        return override
    if model not in MODEL_PRICES_USD_PER_MTOK:
        raise ValueError(
            f"price_for: no published price for model {model!r}; pass an "
            "explicit price_usd_per_mtok override"
        )
    return MODEL_PRICES_USD_PER_MTOK[model]


def cost_usd(
    input_tokens: int,
    output_tokens: int,
    price: tuple[float, float],
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """USD cost of one call's token counts at ``price`` = ``(input, output)`` USD/MTok.

    Cache-read tokens are priced at 10% of the input rate and cache-write
    tokens at 125% of the input rate — Anthropic's published cache ratios.
    """
    input_price, output_price = price
    total = (
        input_tokens * input_price
        + output_tokens * output_price
        + cache_read_tokens * input_price * 0.10
        + cache_write_tokens * input_price * 1.25
    )
    return total / 1_000_000.0


@dataclass
class UsageMeter:
    """Real provider-reported usage, accumulated across every call it sees.

    ``per_call`` keeps one entry per real model call (``model``,
    ``input_tokens``, ``output_tokens``, ``cache_read_tokens``,
    ``cache_write_tokens``, ``latency_s``, ``attempt``); ``events`` keeps one
    entry per retried rate-limit/server/connection error (``kind``,
    ``attempt``, ``wait_s``, ``message``) — never swallowed silently.
    """

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    per_call: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)

    def record(
        self,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        latency_s: float,
        attempt: int = 1,
    ) -> None:
        """Fold one real call's usage into the running totals + ``per_call`` log."""
        self.calls += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cache_read_tokens += cache_read_tokens
        self.cache_write_tokens += cache_write_tokens
        self.per_call.append(
            {
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read_tokens": cache_read_tokens,
                "cache_write_tokens": cache_write_tokens,
                "latency_s": latency_s,
                "attempt": attempt,
            }
        )

    def snapshot(self) -> dict[str, Any]:
        """The running totals only (``calls`` + the four token counters)."""
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
        }


def _retry_kind(exc: BaseException) -> Optional[str]:
    """Which retry bucket ``exc`` falls into, matched by class NAME (not
    ``isinstance``) so this module never needs to import ``anthropic`` — a
    test can raise a plain class sharing the real exception's name."""
    name = type(exc).__name__
    if name == "RateLimitError":
        return "rate_limit"
    if name == "APIConnectionError":
        return "connection_error"
    if name == "APIStatusError" and getattr(exc, "status_code", 0) >= 500:
        return "server_error"
    return None


def _call_with_retry(
    create: Callable[[], Any],
    meter: Optional[UsageMeter],
    max_attempts: int,
    backoff_s: float,
) -> Any:
    """Call ``create()``, retrying on a rate-limit/server/connection error.

    Every retried attempt appends a ``{"kind", "attempt", "wait_s",
    "message"}`` event — to ``meter.events`` when a meter is given, else
    logged (never swallowed silently). Backoff is ``backoff_s * 2**(attempt
    - 1)``, slept through the module-level :data:`_sleep` indirection. Any
    exception NOT matched by :func:`_retry_kind` propagates immediately;
    after ``max_attempts`` total attempts the last exception is re-raised.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return create()
        except Exception as exc:
            kind = _retry_kind(exc)
            if kind is None:
                raise
            wait_s = backoff_s * 2 ** (attempt - 1)
            event = {
                "kind": kind,
                "attempt": attempt,
                "wait_s": wait_s,
                "message": str(exc)[:200],
            }
            if meter is not None:
                meter.events.append(event)
            else:
                logging.getLogger(__name__).warning("LLM retry event: %s", event)
            if attempt >= max_attempts:
                raise
            _sleep(wait_s)

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


#: JSON Schema for the action reply — the provider-native structured-output
#: contract (M46.4): ``default_anthropic_llm_fn`` offers it as the input schema
#: of a forced ``emit_action`` tool, so a compliant model never emits prose
#: around its action at all. Mirrors :func:`_validate_action_json` exactly;
#: that validator remains the authority (a tool reply is still validated).
ACTION_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": sorted(_ACTION_KINDS)},
        "probe": {"type": "string"},
        "lever": {"type": "string"},
        "value": {"type": "number"},
        "duration": {"type": "number"},
        "answer": {
            "type": "object",
            "properties": {
                "value": {},
                "kind": {
                    "type": "string",
                    "enum": ["node_set", "ordered_path", "node_id", "scalar", "json"],
                },
            },
            "required": ["value", "kind"],
        },
        "reasoning": {"type": "string"},
        "params": {"type": "object"},
    },
    "required": ["type"],
}

_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


def extract_action_json(text: str) -> Optional[dict[str, Any]]:
    """Pull the one JSON object out of a model reply that is not bare JSON (M46.4).

    Real replies arrive fenced (```` ```json ... ``` ````), prefaced ("Here is
    my action:"), or with trailing prose. Tries, in order: the whole text as
    JSON; the contents of each fenced block; the first balanced ``{...}``
    object found by scanning every ``{`` with ``JSONDecoder.raw_decode``.
    Returns the first candidate that is a ``dict``, else ``None`` — the
    caller's ``out_schema`` then decides whether it is a well-formed action.
    Pure; no model involved.
    """
    candidates: list[str] = [text]
    candidates.extend(m.group(1) for m in _FENCE_RE.finditer(text))
    decoder = json.JSONDecoder()
    for candidate in candidates:
        stripped = candidate.strip()
        try:
            parsed = json.loads(stripped)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed
    for match in re.finditer(r"\{", text):
        try:
            parsed, _ = decoder.raw_decode(text, match.start())
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def reply_from_content(blocks: Sequence[Any]) -> Any:
    """Turn a provider reply's content blocks into the ``llm_fn`` return value.

    A ``tool_use`` block (the structured path) wins and yields its ``input``
    dict verbatim; otherwise the concatenated ``text`` blocks are handed to
    :func:`extract_action_json`, and if even that finds nothing the raw text
    is returned — which fails ``LLMOp.out_schema`` and rides the retry path.
    Pure over duck-typed blocks (``.type``, ``.input``, ``.text``) so it is
    unit-testable without the provider SDK.
    """
    for block in blocks:
        if getattr(block, "type", None) == "tool_use":
            payload = getattr(block, "input", None)
            if isinstance(payload, dict):
                return payload
    text = "".join(
        getattr(block, "text", "") for block in blocks if getattr(block, "type", None) == "text"
    )
    extracted = extract_action_json(text)
    return extracted if extracted is not None else text


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
        meter: Optional[UsageMeter] = None,
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
        self.meter = meter or UsageMeter()
        self.brief: Optional[TaskBrief] = None
        self._turn = 0
        self._tokens_spent = 0
        self._turn_usage: list[dict[str, Any]] = []
        self._history: list[dict[str, Any]] = []
        self._prompt_hashes: list[str] = []
        self._prompt_texts: list[str] = []
        self._system: Directive = directive
        #: M46.4 — every schema-invalid reply (each retry) is counted, never
        #: silently absorbed; ``aborted`` names why this agent gave up, if it did.
        self.parse_failures = 0
        self.aborted: Optional[str] = None
        #: T026 — discarded-branch probe accounting: real spend (metered, so
        #: money stays visible) that must never alter main-line control flow.
        self._probe_usage: list[dict[str, Any]] = []
        self._probe_tokens = 0
        self._op: LLMOp[dict[str, Any]] = self._make_op()

    def _tolerant_llm_fn(self, directive: Directive, context: Any, seed: Seed) -> Any:
        """Wrap the injected ``llm_fn`` so a string reply carrying JSON inside
        fences or prose still reaches ``out_schema`` as a dict (M46.4)."""
        out = self.llm_fn(directive, context, seed)
        if isinstance(out, str):
            extracted = extract_action_json(out)
            if extracted is not None:
                return extracted
        return out

    def _counting_schema(self, out: Any) -> bool:
        ok = _validate_action_json(out)
        if not ok:
            self.parse_failures += 1
        return ok

    def _make_op(self) -> LLMOp[dict[str, Any]]:
        return LLMOp(
            directive=self._system,
            out_schema=self._counting_schema,
            llm_fn=self._tolerant_llm_fn,
            seed=self.seed,
            max_retries=self.max_retries,
        )

    @property
    def prompt_texts(self) -> tuple[str, ...]:
        """The exact ``system + "\\n" + canonical(context)`` text of every REAL
        model call, in order — what the runner's taint audit (M46.10) scans
        against that trial's hidden ids and answer key. Read-only."""
        return tuple(self._prompt_texts)

    @property
    def prompt_hashes(self) -> tuple[str, ...]:
        """One ``sha256(system_prompt + "\\n" + canonical(context))`` hex digest
        per REAL model call (groundwork for M46.10) — read-only."""
        return tuple(self._prompt_hashes)

    @property
    def usage(self) -> dict[str, Any]:
        """Real provider-reported usage this agent has accrued (M45.5).

        ``self.meter.snapshot()`` (totals) plus ``per_turn`` (one
        ``{"turn", "calls", "input_tokens", ...}`` delta dict per turn that
        made a real call — a mock ``llm_fn`` that never touches ``self.meter``
        leaves every delta at zero) and ``events`` (the meter's retry log).
        """
        out = {**self.meter.snapshot(), "per_turn": list(self._turn_usage), "events": list(self.meter.events)}
        if self._probe_usage:
            out["per_probe"] = list(self._probe_usage)
        return out

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
                if outcome.result is not None:
                    entry["outcome"]["result"] = outcome.result
                return

    def probe(self, text: str) -> Optional[str]:
        """:class:`~alienbio.suite.agent.ProbeAgent` (T026) — answer ``text``
        on a discarded branch.

        The probe context is a COPY of exactly what the next ``act`` would
        see (the same memory-policy history window, the same system prompt)
        plus the probe question — sent through ``llm_fn`` directly (free
        text, no action schema), on an independent child seed. Nothing the
        main line reads moves: ``_history``, ``_turn``, and
        ``_tokens_spent`` are untouched, and the metered probe spend is
        subtracted from the token-ceiling comparison (see ``act``) — the
        run continues as if the probe never happened. The probe prompt IS
        appended to ``prompt_texts``/``prompt_hashes`` so the taint audit
        covers it like any other prompt.
        """
        window = self._history_window()
        context: dict[str, Any] = {"probe": text, "turn": self._turn}
        if window is not None:
            context["history"] = list(window)
        prompt_text = self._system + "\n" + canonical(context)
        self._prompt_hashes.append(hashlib.sha256(prompt_text.encode("utf-8")).hexdigest())
        self._prompt_texts.append(prompt_text)
        before = self.meter.snapshot()
        try:
            raw = self.llm_fn(self._system, context, self.seed.child(f"probe/{len(self._probe_usage)}"))
        finally:
            after = self.meter.snapshot()
            delta = {k: after[k] - before[k] for k in after}
            self._probe_usage.append({"turn": self._turn, **delta})
            self._probe_tokens += delta.get("input_tokens", 0) + delta.get("output_tokens", 0)
        if raw is None:
            return None
        return raw if isinstance(raw, str) else canonical(raw)

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
        # M45.5: once the meter has real usage, the ceiling check uses
        # whichever of the heuristic chars/4 running total or the real
        # provider-reported total is larger — real usage never makes the
        # guard LESS conservative than the estimate alone would.
        # T026: probe spend is real (metered, priced) but the branch is
        # discarded — it must not shift WHEN the main line hits the ceiling,
        # or probes-on vs probes-off transcripts would diverge; so the
        # main-line comparison subtracts it.
        meter_tokens = self.meter.input_tokens + self.meter.output_tokens - self._probe_tokens
        spent_so_far = max(self._tokens_spent + estimate, meter_tokens)
        if self.token_ceiling is not None and spent_so_far > self.token_ceiling:
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
        prompt_text = self._system + "\n" + canonical(context)
        self._prompt_hashes.append(hashlib.sha256(prompt_text.encode("utf-8")).hexdigest())
        self._prompt_texts.append(prompt_text)
        # M45.5: bracket the real model call(s) with meter snapshots so this
        # turn's usage delta lands in `_turn_usage` regardless of outcome — a
        # mock `llm_fn` in tests that never touches `self.meter` leaves every
        # delta at zero (see `usage`'s docstring).
        before = self.meter.snapshot()
        try:
            raw = self._op(context)
        except ValueError as exc:
            after = self.meter.snapshot()
            self._turn_usage.append({"turn": turn, **{k: after[k] - before[k] for k in after}})
            # M46.4: parse exhaustion is data, not a raise — the trial ends with
            # a tagged null Commit (like the token-ceiling guard) so the record
            # carries the failure and a mass-trial sweep keeps going.
            self.aborted = "parse_exhausted"
            content = (
                f"no schema-valid action after {self.max_retries} attempts at turn "
                f"{turn} ({self.parse_failures} invalid replies so far): {exc}"
            )
            reasoning = (ReasoningStep(kind="abort", content=content),)
            action = Commit(
                answer=Answer(value=None, kind="json"),
                params={"aborted": "parse_exhausted"},
            )
            self._history.append(
                {
                    "turn": turn,
                    "observation": [dict(c) for c in observation],
                    "action": {"type": "commit", "aborted": "parse_exhausted"},
                    "reasoning": None,
                    "outcome": None,
                }
            )
            self._turn += 1
            return action, reasoning
        after = self.meter.snapshot()
        self._turn_usage.append({"turn": turn, **{k: after[k] - before[k] for k in after}})
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
    model: str = PINNED_MODEL,
    max_tokens: int = 1024,
    *,
    structured: bool = True,
    meter: Optional[UsageMeter] = None,
    max_attempts: int = 5,
    backoff_s: float = 1.0,
    temperature: Optional[Union[float, str]] = None,
    top_p: Optional[float] = None,
    cache_system: bool = True,
) -> LLMFn:
    """Build a real Anthropic-backed :data:`~alienbio.suite.ops.LLMFn` (opt-in only).

    ``temperature`` / ``top_p`` (M45.18) are forwarded to every call when
    given, so the sampling a record was drawn under is the spec's stated
    number, not the provider default; ``None`` sends nothing (the provider
    default applies — a run with a live arm is refused upstream unless it
    declares ``temperature``). The literal
    :data:`PROVIDER_FIXED_SAMPLING` (``"provider-fixed"``) sends nothing by
    declaration: the Claude 5 API refuses sampling params outright
    ("deprecated for this model"), so on those models the stated regime is
    the provider's single fixed one. ``cache_system`` (M45.19) marks the system
    prompt — the fixed directive plus the trial's brief, identical for every
    turn of a trial and for every trial of a condition — as a prompt-cache
    prefix (``cache_control: ephemeral``); the model sees the same text, the
    meter's ``cache_read_tokens`` shows the hits.

    ``structured=True`` (M46.4, the default) uses the provider-native
    structured-output path: the action schema (:data:`ACTION_INPUT_SCHEMA`)
    is offered as a forced ``emit_action`` tool, so the reply is a
    ``tool_use`` block whose ``input`` IS the action dict — no prose to
    parse. ``structured=False`` is the plain JSON-mode fallback. Either way
    the reply goes through :func:`reply_from_content`, which tolerates fences
    and surrounding prose on a text reply, and through ``LLMOp.out_schema``,
    which stays the authority on well-formedness.

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

    ``meter`` (M45.5), when given, has every successful call's
    ``response.usage`` folded in (input/output/cache-read/cache-write token
    counts, wall latency, 1-based attempt number). A
    ``RateLimitError``/``APIConnectionError``/``APIStatusError`` (5xx) is
    retried up to ``max_attempts`` total attempts with ``backoff_s *
    2**(attempt-1)`` exponential backoff (:func:`_call_with_retry`); any
    other exception propagates immediately.

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

    tool_kwargs: dict[str, Any] = {}
    if structured:
        tool_kwargs = {
            "tools": [
                {
                    "name": "emit_action",
                    "description": (
                        "Emit your next action for this turn as a structured "
                        "object. Exactly one call per turn."
                    ),
                    "input_schema": ACTION_INPUT_SCHEMA,
                }
            ],
            "tool_choice": {"type": "tool", "name": "emit_action"},
        }

    sampling_kwargs: dict[str, Any] = {}
    if temperature is not None and temperature != PROVIDER_FIXED_SAMPLING:
        sampling_kwargs["temperature"] = float(temperature)
    if top_p is not None:
        sampling_kwargs["top_p"] = float(top_p)

    def llm_fn(directive: Directive, context: Any, seed: Seed) -> Any:
        del seed  # accepted for LLMFn shape; Claude has no literal-seed control
        attempt_count = [0]
        system: Any = (
            [{"type": "text", "text": directive, "cache_control": {"type": "ephemeral"}}]
            if cache_system
            else directive
        )

        def create() -> Any:
            attempt_count[0] += 1
            start = time.perf_counter()
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[
                    {"role": "user", "content": json.dumps(context, sort_keys=True)}
                ],
                **sampling_kwargs,
                **tool_kwargs,
            )
            latency_s = time.perf_counter() - start
            if meter is not None:
                usage = response.usage
                meter.record(
                    model=model,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
                    cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
                    latency_s=latency_s,
                    attempt=attempt_count[0],
                )
            return response

        response = _call_with_retry(create, meter, max_attempts, backoff_s)
        return reply_from_content(response.content)

    return llm_fn
