"""Op harness — the scripted / LLM seam (FT07).

A uniform way to invoke a decision/generator that is either pure code
(:class:`~alienbio.suite.types.ScriptedOp`) or a model call returning
schema-validated structured output (:class:`LLMOp`). Both satisfy the
:class:`~alienbio.suite.types.Op` protocol and are used identically at the
call site: ``result = op(context)``.

This module is domain-neutral: directives, contexts, and outputs are opaque
payloads that are never inspected or interpreted. The model function is
ALWAYS injected (:data:`LLMFn`), so tests pass a mock and no live network or
model call ever happens here.

Guarantees:
- **Schema-validate before return** — an output failing ``out_schema`` is
  never returned; after ``max_retries`` failed attempts a ``ValueError``
  naming the directive is raised (fail visibly, no fallback).
- **Deterministic cache** — results are cached by
  ``(directive, canonical(context), seed.value)``; a repeat call with the
  same key returns the identical cached object without re-invoking the model.
- **Seed variation on retry** — attempt 0 uses the op's base seed; each
  retry ``i`` uses the distinct child seed ``seed.child(f"attempt{i}")`` so a
  stochastic model can vary across attempts while staying deterministic for
  a fixed model function.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar, cast

from .dist import Seed
from .types import Directive

T = TypeVar("T")

# out_schema: returns True iff the value is structurally valid.
Validator = Callable[[Any], bool]

# The injected model: (directive, context, seed) -> raw output. Always
# injected — tests pass a mock; nothing in this module performs a live call.
LLMFn = Callable[[Directive, Any, Seed], Any]

# Cache key: (directive, canonical(context), seed.value).
_CacheKey = tuple[str, str, int]


def canonical(context: Any) -> str:
    """A deterministic string key for an opaque context.

    A stable JSON dump with sorted keys and compact separators, so two equal
    JSON-ish contexts (regardless of dict insertion order) produce the same
    key. Non-JSON-serializable leaves are keyed by ``repr`` — callers using
    such contexts should ensure their ``repr`` is stable and value-based.
    """
    return json.dumps(context, sort_keys=True, separators=(",", ":"), default=repr)


@dataclass
class LLMOp(Generic[T]):
    """An :class:`~alienbio.suite.types.Op` backed by an injected model call.

    Invocation flow for ``op(context)``:

    1. Cache hit on ``(directive, canonical(context), seed.value)`` — return
       the cached object; the model is NOT re-invoked.
    2. Otherwise call ``llm_fn(directive, context, attempt_seed)``; if
       ``out_schema(out)`` holds, cache and return ``out``.
    3. On invalid output, retry with a distinct child seed per attempt
       (``seed.child(f"attempt{i}")``), up to ``max_retries`` total attempts;
       if every attempt is invalid, raise ``ValueError`` naming the directive.
    """

    directive: Directive
    out_schema: Validator
    llm_fn: LLMFn
    seed: Seed = field(default_factory=lambda: Seed(0))
    max_retries: int = 3
    _cache: dict[_CacheKey, T] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    def __call__(self, context: Any) -> T:
        key: _CacheKey = (self.directive, canonical(context), self.seed.value)
        if key in self._cache:
            return self._cache[key]
        for i in range(self.max_retries):
            attempt_seed = self.seed if i == 0 else self.seed.child(f"attempt{i}")
            out = self.llm_fn(self.directive, context, attempt_seed)
            if self.out_schema(out):
                result = cast(T, out)
                self._cache[key] = result
                return result
        raise ValueError(
            f"LLMOp {self.directive!r}: no schema-valid output after "
            f"{self.max_retries} attempts"
        )
