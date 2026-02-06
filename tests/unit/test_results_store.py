"""Tests for results storage: save, load, filter, merge, export.

M4.2 - Results Aggregation
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from alienbio.agent import (
    BatteryEntry,
    BatteryResult,
    ExperimentResults,
    save_results,
    load_results,
    export_csv,
    export_json,
)


def _make_result(
    scenario: str = "s1",
    seed: int = 0,
    passed: bool = True,
    scores: dict | None = None,
    cost: float = 1.0,
    status: str = "completed",
) -> ExperimentResults:
    """Create an ExperimentResults with a mock trace."""
    trace = MagicMock()
    trace.total_cost = cost
    return ExperimentResults(
        scenario=scenario,
        seed=seed,
        scores=scores or {"budget_compliance": 1.0},
        trace=trace,
        passed=passed,
        status=status,
    )


def _make_battery(*entries: tuple[str, str, int, bool]) -> BatteryResult:
    """Shorthand: entries are (agent, scenario, seed, passed)."""
    return BatteryResult(entries=[
        BatteryEntry(agent, _make_result(scenario, seed, passed))
        for agent, scenario, seed, passed in entries
    ])


# === Save / Load ===

class TestSaveResults:

    def test_save_creates_file(self, tmp_path):
        result = _make_battery(("a", "s1", 0, True))
        path = save_results(result, tmp_path / "results")
        assert path.exists()
        assert path.suffix == ".yaml"

    def test_save_adds_yaml_suffix(self, tmp_path):
        result = _make_battery(("a", "s1", 0, True))
        path = save_results(result, tmp_path / "results")
        assert path == tmp_path / "results.yaml"

    def test_save_preserves_yaml_suffix(self, tmp_path):
        result = _make_battery(("a", "s1", 0, True))
        path = save_results(result, tmp_path / "results.yaml")
        assert path == tmp_path / "results.yaml"

    def test_save_creates_parent_dirs(self, tmp_path):
        result = _make_battery(("a", "s1", 0, True))
        path = save_results(result, tmp_path / "deep" / "nested" / "results")
        assert path.exists()

    def test_save_includes_metadata(self, tmp_path):
        result = _make_battery(("a", "s1", 0, True))
        path = save_results(result, tmp_path / "results", metadata={"tag": "test"})
        with open(path) as f:
            doc = yaml.safe_load(f)
        assert doc["metadata"]["tag"] == "test"

    def test_save_includes_version(self, tmp_path):
        result = _make_battery(("a", "s1", 0, True))
        path = save_results(result, tmp_path / "results")
        with open(path) as f:
            doc = yaml.safe_load(f)
        assert doc["version"] == 1

    def test_save_includes_timestamp(self, tmp_path):
        result = _make_battery(("a", "s1", 0, True))
        path = save_results(result, tmp_path / "results")
        with open(path) as f:
            doc = yaml.safe_load(f)
        assert "saved_at" in doc

    def test_save_includes_totals(self, tmp_path):
        result = _make_battery(
            ("a", "s1", 0, True),
            ("a", "s1", 1, False),
        )
        path = save_results(result, tmp_path / "results")
        with open(path) as f:
            doc = yaml.safe_load(f)
        assert doc["total"] == 2
        assert doc["passed"] == 1
        assert doc["pass_rate"] == pytest.approx(0.5)


class TestLoadResults:

    def test_round_trip(self, tmp_path):
        original = _make_battery(
            ("agent_a", "scenario_1", 42, True),
            ("agent_b", "scenario_2", 7, False),
        )
        path = save_results(original, tmp_path / "results")
        loaded = load_results(path)

        assert loaded.total == original.total
        assert loaded.passed == original.passed
        for orig, load in zip(original.entries, loaded.entries):
            assert load.agent_name == orig.agent_name
            assert load.result.scenario == orig.result.scenario
            assert load.result.seed == orig.result.seed
            assert load.result.passed == orig.result.passed
            assert load.result.scores == orig.result.scores
            assert load.result.status == orig.result.status

    def test_load_preserves_scores(self, tmp_path):
        result = BatteryResult(entries=[
            BatteryEntry("a", _make_result(scores={"accuracy": 0.85, "cost": 3.2})),
        ])
        path = save_results(result, tmp_path / "results")
        loaded = load_results(path)
        assert loaded.entries[0].result.scores == {"accuracy": 0.85, "cost": 3.2}

    def test_load_preserves_total_cost(self, tmp_path):
        result = BatteryResult(entries=[
            BatteryEntry("a", _make_result(cost=5.5)),
        ])
        path = save_results(result, tmp_path / "results")
        loaded = load_results(path)
        assert loaded.entries[0].result.trace.total_cost == pytest.approx(5.5)

    def test_load_nonexistent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_results(tmp_path / "no_such_file.yaml")

    def test_load_invalid_format_raises(self, tmp_path):
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("just a string\n")
        with pytest.raises(ValueError, match="Invalid results file"):
            load_results(bad_file)

    def test_round_trip_incomplete_reason(self, tmp_path):
        result = BatteryResult(entries=[
            BatteryEntry("a", ExperimentResults(
                scenario="s1", seed=0, scores={},
                trace=MagicMock(total_cost=0.0),
                passed=False, status="incomplete",
                incomplete_reason="budget exhausted",
            )),
        ])
        path = save_results(result, tmp_path / "results")
        loaded = load_results(path)
        assert loaded.entries[0].result.incomplete_reason == "budget exhausted"
        assert loaded.entries[0].result.status == "incomplete"


# === Filter ===

class TestFilter:

    def _battery(self) -> BatteryResult:
        return _make_battery(
            ("agent_a", "s1", 0, True),
            ("agent_a", "s1", 1, False),
            ("agent_a", "s2", 0, True),
            ("agent_b", "s1", 0, True),
            ("agent_b", "s2", 1, False),
        )

    def test_filter_by_agent(self):
        filtered = self._battery().filter(agent="agent_a")
        assert filtered.total == 3
        assert all(e.agent_name == "agent_a" for e in filtered.entries)

    def test_filter_by_scenario(self):
        filtered = self._battery().filter(scenario="s1")
        assert filtered.total == 3
        assert all(e.result.scenario == "s1" for e in filtered.entries)

    def test_filter_by_seed(self):
        filtered = self._battery().filter(seed=0)
        assert filtered.total == 3
        assert all(e.result.seed == 0 for e in filtered.entries)

    def test_filter_combined(self):
        filtered = self._battery().filter(agent="agent_a", scenario="s1")
        assert filtered.total == 2
        assert all(
            e.agent_name == "agent_a" and e.result.scenario == "s1"
            for e in filtered.entries
        )

    def test_filter_no_match(self):
        filtered = self._battery().filter(agent="nonexistent")
        assert filtered.total == 0

    def test_filter_none_returns_all(self):
        battery = self._battery()
        filtered = battery.filter()
        assert filtered.total == battery.total


# === Merge ===

class TestMerge:

    def test_merge_combines_entries(self):
        a = _make_battery(("a", "s1", 0, True))
        b = _make_battery(("b", "s2", 1, False))
        merged = a.merge(b)
        assert merged.total == 2
        assert merged.entries[0].agent_name == "a"
        assert merged.entries[1].agent_name == "b"

    def test_merge_empty(self):
        a = _make_battery(("a", "s1", 0, True))
        b = BatteryResult()
        assert a.merge(b).total == 1
        assert b.merge(a).total == 1

    def test_merge_preserves_all_data(self):
        a = _make_battery(("a", "s1", 0, True), ("a", "s1", 1, True))
        b = _make_battery(("b", "s2", 0, False))
        merged = a.merge(b)
        assert merged.passed == 2
        assert merged.failed == 1


# === Export CSV ===

class TestExportCsv:

    def test_csv_header(self):
        result = _make_battery(("a", "s1", 0, True))
        csv = export_csv(result)
        header = csv.split("\n")[0]
        assert "agent" in header
        assert "scenario" in header
        assert "seed" in header
        assert "passed" in header

    def test_csv_rows(self):
        result = _make_battery(
            ("agent_a", "s1", 0, True),
            ("agent_b", "s2", 1, False),
        )
        csv = export_csv(result)
        lines = csv.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows
        assert lines[1].startswith("agent_a,s1,0,True")
        assert lines[2].startswith("agent_b,s2,1,False")

    def test_csv_includes_scores(self):
        result = BatteryResult(entries=[
            BatteryEntry("a", _make_result(scores={"acc": 0.9, "f1": 0.85})),
        ])
        csv = export_csv(result)
        header = csv.split("\n")[0]
        assert "acc" in header
        assert "f1" in header

    def test_csv_to_file(self, tmp_path):
        result = _make_battery(("a", "s1", 0, True))
        path = tmp_path / "out.csv"
        export_csv(result, path)
        assert path.exists()
        assert path.read_text().startswith("agent,")

    def test_csv_empty_battery(self):
        result = BatteryResult()
        csv = export_csv(result)
        lines = csv.strip().split("\n")
        assert len(lines) == 1  # header only


# === Export JSON ===

class TestExportJson:

    def test_json_structure(self):
        result = _make_battery(("a", "s1", 0, True))
        text = export_json(result)
        doc = json.loads(text)
        assert doc["total"] == 1
        assert doc["passed"] == 1
        assert "entries" in doc
        assert "summary" in doc

    def test_json_entries(self):
        result = _make_battery(
            ("agent_a", "s1", 0, True),
            ("agent_b", "s2", 1, False),
        )
        text = export_json(result)
        doc = json.loads(text)
        assert len(doc["entries"]) == 2
        assert doc["entries"][0]["agent"] == "agent_a"
        assert doc["entries"][1]["agent"] == "agent_b"

    def test_json_to_file(self, tmp_path):
        result = _make_battery(("a", "s1", 0, True))
        path = tmp_path / "out.json"
        export_json(result, path)
        assert path.exists()
        doc = json.loads(path.read_text())
        assert doc["total"] == 1

    def test_json_includes_summary(self):
        result = _make_battery(
            ("a", "s1", 0, True),
            ("a", "s1", 1, False),
        )
        text = export_json(result)
        doc = json.loads(text)
        assert len(doc["summary"]) == 1
        assert doc["summary"][0]["agent"] == "a"
        assert doc["summary"][0]["pass_rate"] == pytest.approx(0.5)


# === Integration: load from file then filter ===

class TestLoadAndFilter:

    def test_load_then_filter(self, tmp_path):
        original = _make_battery(
            ("a", "s1", 0, True),
            ("a", "s2", 1, True),
            ("b", "s1", 0, False),
        )
        path = save_results(original, tmp_path / "results")
        loaded = load_results(path)
        filtered = loaded.filter(agent="a")
        assert filtered.total == 2
        assert all(e.agent_name == "a" for e in filtered.entries)

    def test_save_load_merge(self, tmp_path):
        r1 = _make_battery(("a", "s1", 0, True))
        r2 = _make_battery(("b", "s2", 1, False))
        p1 = save_results(r1, tmp_path / "batch1")
        p2 = save_results(r2, tmp_path / "batch2")
        merged = load_results(p1).merge(load_results(p2))
        assert merged.total == 2
        assert merged.passed == 1

    def test_save_load_export_csv(self, tmp_path):
        result = _make_battery(("a", "s1", 0, True))
        path = save_results(result, tmp_path / "results")
        loaded = load_results(path)
        csv = export_csv(loaded)
        assert "agent,scenario" in csv
        assert "a,s1,0,True" in csv
