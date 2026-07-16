"""Acceptance tests for the op harness (LLMOp / ScriptedOp seam).

The model function is always a MOCK injected as ``llm_fn`` — no live calls.
"""

from __future__ import annotations

from typing import Any

import pytest

from alienbio.suite.dist import Seed
from alienbio.suite.ops import LLMOp
from alienbio.suite.types import Op, ScriptedOp


def is_result_dict(out: Any) -> bool:
    """The out_schema used throughout: a dict with a string ``answer`` key."""
    return isinstance(out, dict) and isinstance(out.get("answer"), str)


class CountingMock:
    """A deterministic mock model that counts invocations.

    Returns an invalid output (``None``) for the first ``fail_first`` calls,
    then a valid dict derived only from its inputs (so it is deterministic).
    Records the seed of every call.
    """

    def __init__(self, fail_first: int = 0):
        self.fail_first = fail_first
        self.calls = 0
        self.seeds_seen: list[int] = []

    def __call__(self, directive: str, context: Any, seed: Seed) -> Any:
        self.calls += 1
        self.seeds_seen.append(seed.value)
        if self.calls <= self.fail_first:
            return None  # fails is_result_dict
        return {"answer": f"{directive}|{context}|{seed.value}"}


# ── 1. Interchangeable call site ────────────────────────────────────────────

def test_scripted_and_llm_ops_interchangeable():
    scripted: Op[dict] = ScriptedOp(fn=lambda ctx: {"answer": f"scripted:{ctx}"})
    llm: Op[dict] = LLMOp(
        directive="decide",
        out_schema=is_result_dict,
        llm_fn=CountingMock(),
    )
    for op in (scripted, llm):
        result = op("ctx-1")
        assert is_result_dict(result)
    assert isinstance(scripted, Op)
    assert isinstance(llm, Op)


# ── 2. Retry-then-error ─────────────────────────────────────────────────────

def test_retry_until_valid_counts_attempts():
    k = 2
    mock = CountingMock(fail_first=k)
    op: LLMOp[dict] = LLMOp(
        directive="decide", out_schema=is_result_dict, llm_fn=mock, max_retries=3
    )
    result = op("ctx")
    assert is_result_dict(result)
    assert mock.calls == k + 1


def test_always_invalid_raises_after_max_retries():
    mock = CountingMock(fail_first=10**9)  # never valid
    op: LLMOp[dict] = LLMOp(
        directive="hopeless", out_schema=is_result_dict, llm_fn=mock, max_retries=3
    )
    with pytest.raises(ValueError, match="hopeless"):
        op("ctx")
    assert mock.calls == 3


def test_retries_use_distinct_child_seeds():
    mock = CountingMock(fail_first=2)
    op: LLMOp[dict] = LLMOp(
        directive="decide",
        out_schema=is_result_dict,
        llm_fn=mock,
        seed=Seed(7),
        max_retries=3,
    )
    op("ctx")
    assert mock.seeds_seen[0] == 7  # attempt 0 = base seed
    assert len(set(mock.seeds_seen)) == 3  # every attempt seed distinct


# ── 3. Cache ────────────────────────────────────────────────────────────────

def test_cache_hit_does_not_reinvoke_model():
    mock = CountingMock()
    op: LLMOp[dict] = LLMOp(
        directive="decide", out_schema=is_result_dict, llm_fn=mock
    )
    first = op({"q": "same"})
    second = op({"q": "same"})
    assert second is first  # identical cached object
    assert mock.calls == 1  # model NOT re-invoked
    op({"q": "different"})
    assert mock.calls == 2  # new context -> second invocation


def test_cache_key_ignores_dict_insertion_order():
    mock = CountingMock()
    op: LLMOp[dict] = LLMOp(
        directive="decide", out_schema=is_result_dict, llm_fn=mock
    )
    a = op({"x": 1, "y": 2})
    b = op({"y": 2, "x": 1})  # equal context, different insertion order
    assert b is a
    assert mock.calls == 1


# ── 4. Determinism ──────────────────────────────────────────────────────────

def test_fixed_mock_is_deterministic_across_constructions():
    def build() -> dict:
        op: LLMOp[dict] = LLMOp(
            directive="decide",
            out_schema=is_result_dict,
            llm_fn=CountingMock(fail_first=1),
            seed=Seed(42),
        )
        return op("ctx")

    assert build() == build() == build()
