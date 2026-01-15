"""Tests for results storage functionality."""

from __future__ import annotations

from pathlib import Path

import pytest

from alienbio.agent import (
    save_results,
    load_results,
    list_results,
    aggregate_results,
    ExperimentResults,
    Trace,
    Action,
    Observation,
)


def _make_observation(step: int = 0) -> Observation:
    """Create a minimal observation for testing."""
    return Observation(
        briefing="test",
        constitution="test",
        available_actions={},
        available_measurements={},
        current_state={},
        step=step,
        budget=100.0,
        spent=0.0,
        remaining=100.0,
    )


@pytest.fixture
def sample_trace():
    """Create a sample trace for testing."""
    trace = Trace()
    trace.append(Action(name="observe", params={}), _make_observation(0), step=0, cost=1.0)
    trace.append(Action(name="sample", params={"region": "A"}), _make_observation(1), step=1, cost=2.0)
    return trace


@pytest.fixture
def sample_results(sample_trace):
    """Create sample experiment results."""
    return ExperimentResults(
        scenario="test/scenario",
        seed=42,
        scores={"accuracy": 0.85, "efficiency": 0.90},
        trace=sample_trace,
        passed=True,
        status="completed",
    )


class TestSaveResults:
    """Tests for save_results function."""

    def test_save_creates_directory(self, sample_results, tmp_path):
        """Test that save_results creates the result directory."""
        result_dir = save_results(sample_results, base_dir=tmp_path)

        assert result_dir.exists()
        assert result_dir.is_dir()

    def test_save_creates_index_yaml(self, sample_results, tmp_path):
        """Test that save_results creates index.yaml."""
        result_dir = save_results(sample_results, base_dir=tmp_path)

        index_file = result_dir / "index.yaml"
        assert index_file.exists()

    def test_save_includes_scenario(self, sample_results, tmp_path):
        """Test that saved results include scenario name."""
        result_dir = save_results(sample_results, base_dir=tmp_path)
        loaded = load_results(result_dir)

        assert loaded["scenario"] == "test/scenario"

    def test_save_includes_seed(self, sample_results, tmp_path):
        """Test that saved results include seed."""
        result_dir = save_results(sample_results, base_dir=tmp_path)
        loaded = load_results(result_dir)

        assert loaded["seed"] == 42

    def test_save_includes_scores(self, sample_results, tmp_path):
        """Test that saved results include scores."""
        result_dir = save_results(sample_results, base_dir=tmp_path)
        loaded = load_results(result_dir)

        assert loaded["scores"]["accuracy"] == 0.85
        assert loaded["scores"]["efficiency"] == 0.90

    def test_save_includes_agent_type(self, sample_results, tmp_path):
        """Test that saved results include agent type."""
        result_dir = save_results(
            sample_results,
            agent_type="anthropic",
            base_dir=tmp_path,
        )
        loaded = load_results(result_dir)

        assert loaded["agent_type"] == "anthropic"

    def test_save_includes_model(self, sample_results, tmp_path):
        """Test that saved results include model name."""
        result_dir = save_results(
            sample_results,
            agent_type="anthropic",
            model="claude-opus-4",
            base_dir=tmp_path,
        )
        loaded = load_results(result_dir)

        assert loaded["model"] == "claude-opus-4"

    def test_save_includes_trace_summary(self, sample_results, tmp_path):
        """Test that saved results include trace summary."""
        result_dir = save_results(sample_results, base_dir=tmp_path)
        loaded = load_results(result_dir)

        assert "trace" in loaded
        assert loaded["trace"]["action_count"] == 2
        assert loaded["trace"]["total_cost"] == 3.0

    def test_save_sanitizes_scenario_name(self, sample_results, tmp_path):
        """Test that scenario names with slashes are sanitized."""
        sample_results.scenario = "path/to/scenario"
        result_dir = save_results(sample_results, base_dir=tmp_path)

        # Directory should use underscores instead of slashes
        assert "path_to_scenario" in str(result_dir)


class TestLoadResults:
    """Tests for load_results function."""

    def test_load_from_directory(self, sample_results, tmp_path):
        """Test loading results from directory path."""
        result_dir = save_results(sample_results, base_dir=tmp_path)
        loaded = load_results(result_dir)

        assert loaded["scenario"] == "test/scenario"

    def test_load_from_index_file(self, sample_results, tmp_path):
        """Test loading results from index.yaml path."""
        result_dir = save_results(sample_results, base_dir=tmp_path)
        loaded = load_results(result_dir / "index.yaml")

        assert loaded["scenario"] == "test/scenario"

    def test_load_not_found_raises(self, tmp_path):
        """Test that loading non-existent results raises error."""
        with pytest.raises(FileNotFoundError):
            load_results(tmp_path / "nonexistent")


class TestListResults:
    """Tests for list_results function."""

    def test_list_empty_returns_empty(self, tmp_path):
        """Test that listing empty directory returns empty list."""
        results = list_results(base_dir=tmp_path)
        assert results == []

    def test_list_returns_all_results(self, sample_results, tmp_path):
        """Test that list_results returns all saved results."""
        # Save multiple results
        save_results(sample_results, base_dir=tmp_path)
        sample_results.scenario = "other/scenario"
        save_results(sample_results, base_dir=tmp_path)

        results = list_results(base_dir=tmp_path)
        assert len(results) == 2

    def test_list_filters_by_scenario(self, sample_results, tmp_path):
        """Test that list_results can filter by scenario."""
        save_results(sample_results, base_dir=tmp_path)
        sample_results.scenario = "other/scenario"
        save_results(sample_results, base_dir=tmp_path)

        results = list_results(scenario="test/scenario", base_dir=tmp_path)
        assert len(results) == 1
        assert results[0]["scenario"] == "test/scenario"

    def test_list_includes_path(self, sample_results, tmp_path):
        """Test that list_results includes _path field."""
        save_results(sample_results, base_dir=tmp_path)

        results = list_results(base_dir=tmp_path)
        assert "_path" in results[0]

    def test_list_sorted_newest_first(self, sample_results, tmp_path):
        """Test that results are sorted newest first."""
        import time

        save_results(sample_results, base_dir=tmp_path)
        time.sleep(1.1)  # Ensure different timestamp
        sample_results.seed = 99
        save_results(sample_results, base_dir=tmp_path)

        results = list_results(base_dir=tmp_path)
        assert results[0]["seed"] == 99  # Newer result first


class TestAggregateResults:
    """Tests for aggregate_results function."""

    def test_aggregate_empty_returns_zeros(self, tmp_path):
        """Test that aggregating empty results returns zeros."""
        stats = aggregate_results(base_dir=tmp_path)

        assert stats["count"] == 0
        assert stats["pass_rate"] == 0.0
        assert stats["scenarios"] == []

    def test_aggregate_counts_results(self, sample_results, tmp_path, monkeypatch):
        """Test that aggregate counts total results."""
        # Use different timestamps to avoid collision
        timestamps = iter(["20250101_120000", "20250101_120001"])
        monkeypatch.setattr(
            "alienbio.agent.results_storage._generate_timestamp",
            lambda: next(timestamps)
        )
        save_results(sample_results, base_dir=tmp_path)
        save_results(sample_results, base_dir=tmp_path)

        stats = aggregate_results(base_dir=tmp_path)
        assert stats["count"] == 2

    def test_aggregate_calculates_pass_rate(self, sample_results, tmp_path, monkeypatch):
        """Test that aggregate calculates pass rate."""
        timestamps = iter(["20250101_120000", "20250101_120001"])
        monkeypatch.setattr(
            "alienbio.agent.results_storage._generate_timestamp",
            lambda: next(timestamps)
        )
        save_results(sample_results, base_dir=tmp_path)  # passed=True
        sample_results.passed = False
        save_results(sample_results, base_dir=tmp_path)

        stats = aggregate_results(base_dir=tmp_path)
        assert stats["pass_rate"] == 0.5

    def test_aggregate_calculates_score_stats(self, sample_results, tmp_path, monkeypatch):
        """Test that aggregate calculates score statistics."""
        timestamps = iter(["20250101_120000", "20250101_120001"])
        monkeypatch.setattr(
            "alienbio.agent.results_storage._generate_timestamp",
            lambda: next(timestamps)
        )
        sample_results.scores = {"accuracy": 0.8}
        save_results(sample_results, base_dir=tmp_path)
        sample_results.scores = {"accuracy": 0.9}
        save_results(sample_results, base_dir=tmp_path)

        stats = aggregate_results(base_dir=tmp_path)
        assert stats["score_stats"]["accuracy"]["mean"] == pytest.approx(0.85)
        assert stats["score_stats"]["accuracy"]["min"] == pytest.approx(0.8)
        assert stats["score_stats"]["accuracy"]["max"] == pytest.approx(0.9)

    def test_aggregate_groups_by_scenario(self, sample_results, tmp_path):
        """Test that aggregate groups results by scenario."""
        save_results(sample_results, base_dir=tmp_path)
        sample_results.scenario = "other/scenario"
        save_results(sample_results, base_dir=tmp_path)

        stats = aggregate_results(base_dir=tmp_path)
        assert len(stats["scenarios"]) == 2
        assert "test/scenario" in stats["scenarios"]
        assert "other/scenario" in stats["scenarios"]


class TestRoundTrip:
    """Test that results survive save/load round-trip."""

    def test_roundtrip_preserves_data(self, sample_results, tmp_path):
        """Test that all data survives round-trip."""
        result_dir = save_results(
            sample_results,
            agent_type="random",
            model=None,
            base_dir=tmp_path,
        )
        loaded = load_results(result_dir)

        assert loaded["scenario"] == sample_results.scenario
        assert loaded["seed"] == sample_results.seed
        assert loaded["passed"] == sample_results.passed
        assert loaded["status"] == sample_results.status
        assert loaded["scores"] == sample_results.scores
        assert loaded["agent_type"] == "random"
