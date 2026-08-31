"""M48.9 example 8 — the agent loop: brief + session memory, rejection-as-data
and the illegal-action limit, the empty taint audit, the $0 scripted cost
estimate, and a pinned-memory live arm the CI never runs."""

from __future__ import annotations

from pathlib import Path

import pytest

from alienbio.expr import Env
from alienbio.suite.experiment import estimate_cost, load_spec, no_peeking_violation, run_experiment
from alienbio.suite.types import OutcomeObjective

REPO = Path(__file__).resolve().parents[2]
HERE = REPO / "catalog" / "examples" / "agent_loop"
SPEC = HERE / "agent_loop.yaml"
LIVE = HERE / "live.yaml"


@pytest.fixture(scope="module")
def rmap(tmp_path_factory):
    spec = load_spec(SPEC)
    return run_experiment(spec, out_dir=str(tmp_path_factory.mktemp("agent_loop") / "run"))


def _by_agent(rmap):
    out = {}
    for record in rmap.records:
        out.setdefault(dict(record.condition_key)["agent"], []).append(record)
    return out


def test_the_outcome_task_is_on_the_chain():
    values = Env.standard(seed=21, trusted=True).load(SPEC).force_all()
    task = values["task"]
    assert isinstance(task.objective, OutcomeObjective)


def test_rejection_as_data_is_noticed_and_recoverable(rmap):
    """retry-commit's first probe is illegal; the notice lets it recover
    through the brief and commit — one illegal action, no crash."""
    for record in _by_agent(rmap)["retry-commit"]:
        assert record.terminal_reason == "committed"
        assert record.illegal_actions == 1
        assert record.action_log[0].accepted is False and "no-such-probe" in record.action_log[0].reason
        assert record.action_log[1].accepted is True


def test_the_illegal_action_limit_contains_a_confused_agent(rmap):
    """clumsy-commit names an unknown lever every turn: ten rejections, then
    the trial stops with reason illegal_limit — as data, not an exception."""
    for record in _by_agent(rmap)["clumsy-commit"]:
        assert record.terminal_reason == "illegal_limit"
        assert record.illegal_actions == 10
        assert all(not a.accepted for a in record.action_log)


def test_scripted_trials_carry_no_usage_and_pass_the_taint_audit(rmap):
    for record in rmap.records:
        assert record.usage is None
        assert record.taint_hits == ()
        assert record.brief is not None and not record.error


def test_the_dry_run_costs_nothing_for_an_all_scripted_grid(rmap):
    del rmap
    estimate = estimate_cost(load_spec(SPEC))
    assert estimate.llm_trials == 0 and estimate.usd == 0.0


def test_the_live_arm_pins_its_memory_window():
    """The AUP condition (2026-08-31): no memory-window sweep with an LLM —
    live.yaml keeps `memory` a scalar, sweeps nothing, and the no-peeking
    guard admits it on this neutral world."""
    spec = load_spec(LIVE)
    assert spec.agent == "llm" and spec.memory == 6
    assert spec.axes == ()
    assert "memory" not in dict(spec.axes)
    assert spec.temperature is not None and spec.top_p is not None
    assert no_peeking_violation(spec) is None
