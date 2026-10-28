"""Defects the suite module-doc writers reproduced with the source open.

Each section pins one finding: it failed before its fix and passes after.

A. ``compact_budget`` reached the summarizer only as model-visible text
   (``budget_tokens``); the provider fn's ``max_tokens`` seam never saw it,
   so the bound the compact-turn ceiling pre-check assumes was not enforced.
"""

from __future__ import annotations

import pytest

from alienbio.suite.dist import Seed
from alienbio.suite.drafters import DRAFTERS
from alienbio.suite.llm_agent import (
    OUTPUT_BUDGET_KEY,
    LLMAgent,
    is_compact_context,
    pop_output_budget,
)
from alienbio.suite.runner import run


P1_LEVERS = ["root/uptake_route_in", "root/uptake_neutral_in"]


def _p1_world(seed: int = 5, **extra):
    dials = {"variant": "commitment_no_coupling", "levers": list(P1_LEVERS), **extra}
    world, task = DRAFTERS["phase1_pressure"](Seed(seed).child("d"), dials)
    return world, task, dials


# A ---------------------------------------------------------------------------


@pytest.mark.parametrize("max_tokens", [None, 300])
def test_compact_budget_rides_the_output_budget_seam(max_tokens):
    calls: list[tuple[bool, object]] = []

    def llm_fn(directive, context, seed):
        budget, stripped = pop_output_budget(context)
        calls.append((is_compact_context(stripped), budget))
        if is_compact_context(stripped):
            return "summary"
        return {"type": "wait", "duration": 1.0}

    world, task, dials = _p1_world()
    agent = LLMAgent(
        llm_fn, Seed(5).child("llm"), memory="full", compact_at=2,
        compact_budget=77, max_tokens=max_tokens,
    )
    record = run(world, task, agent, dials, Seed(5).child("r"), max_turns=4)
    assert record.compaction is not None
    compact = [b for is_c, b in calls if is_c]
    main = [b for is_c, b in calls if not is_c]
    assert compact == [77]
    assert main and all(b == max_tokens for b in main)
    # The model-facing prompt never carries the seam key.
    assert not any(f'"{OUTPUT_BUDGET_KEY}"' in t for t in agent.prompt_texts)
