"""Tests for Advanced Analysis: Agent Comparison."""

from __future__ import annotations

import pytest

from alienbio.bio import (
    AgentStats,
    ComparisonTable,
    ExperimentResult,
    TestResults,
    compare,
    compare_by_task,
)


def _make_results(agent_name: str, scores: list) -> TestResults:
    """Create TestResults with given scores."""
    results = [
        ExperimentResult("predict", s, s, {"actual": 1.0})
        for s in scores
    ]
    return TestResults(suite_name=agent_name, results=results)


class TestAgentStats:

    def test_dataclass(self):
        s = AgentStats("a1", mean=0.8, std=0.1, min=0.5, max=1.0, count=10, pass_rate=0.9)
        assert s.agent_name == "a1"
        assert s.mean == 0.8


class TestCompare:

    def test_compare_two_agents(self):
        results = {
            "good": _make_results("good", [0.9, 0.8, 0.95]),
            "bad": _make_results("bad", [0.3, 0.2, 0.1]),
        }
        table = compare(results)
        assert len(table.agents) == 2

    def test_ranking_order(self):
        """Comparison correctly ranks agents."""
        results = {
            "good": _make_results("good", [0.9, 0.8, 0.95]),
            "bad": _make_results("bad", [0.3, 0.2, 0.1]),
            "mid": _make_results("mid", [0.5, 0.6, 0.55]),
        }
        table = compare(results)
        ranking = table.ranking
        assert ranking[0].agent_name == "good"
        assert ranking[1].agent_name == "mid"
        assert ranking[2].agent_name == "bad"

    def test_leader(self):
        results = {
            "a": _make_results("a", [0.9]),
            "b": _make_results("b", [0.1]),
        }
        table = compare(results)
        assert table.leader().agent_name == "a"

    def test_stats_values(self):
        results = {
            "agent": _make_results("agent", [0.2, 0.4, 0.6, 0.8, 1.0]),
        }
        table = compare(results)
        stats = table.agents[0]
        assert stats.mean == pytest.approx(0.6)
        assert stats.min == pytest.approx(0.2)
        assert stats.max == pytest.approx(1.0)
        assert stats.count == 5
        assert stats.std > 0

    def test_pass_rate(self):
        results = {
            "agent": _make_results("agent", [0.1, 0.3, 0.6, 0.8]),
        }
        table = compare(results, threshold=0.5)
        stats = table.agents[0]
        assert stats.pass_rate == pytest.approx(0.5)  # 2 of 4 >= 0.5

    def test_to_dict(self):
        results = {
            "a": _make_results("a", [0.9, 0.8]),
        }
        table = compare(results)
        d = table.to_dict()
        assert "agents" in d
        assert d["agents"][0]["agent_name"] == "a"

    def test_empty_scores(self):
        results = {
            "empty": TestResults(suite_name="empty", results=[]),
        }
        table = compare(results)
        assert table.agents[0].count == 0
        assert table.agents[0].mean == 0.0


class TestCompareByTask:

    def test_groups_by_task(self):
        # Mix predict and diagnose results
        predict_results = [
            ExperimentResult("predict", 0.9, 9.0, {}),
            ExperimentResult("predict", 0.8, 8.0, {}),
        ]
        diagnose_results = [
            ExperimentResult("diagnose", 1.0, 0, {}),
        ]
        results = {
            "agent_a": TestResults("a", predict_results + diagnose_results),
        }
        tables = compare_by_task(results)
        assert "predict" in tables
        assert "diagnose" in tables
        assert tables["predict"].agents[0].count == 2
        assert tables["diagnose"].agents[0].count == 1

    def test_multiple_agents_per_task(self):
        results = {
            "a": TestResults("a", [ExperimentResult("predict", 0.9, 0, {})]),
            "b": TestResults("b", [ExperimentResult("predict", 0.3, 0, {})]),
        }
        tables = compare_by_task(results)
        predict_table = tables["predict"]
        assert len(predict_table.agents) == 2
        assert predict_table.leader().agent_name == "a"
