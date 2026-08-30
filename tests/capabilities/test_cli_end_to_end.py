"""M48.7 — every ``bio`` subcommand end to end against the catalog, as a
subprocess (the way CI and a user run it)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ZERO = REPO / "catalog" / "experiments" / "exp4-zero.yaml"


def bio(*args: str, cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "alienbio.cli", *args], capture_output=True, text=True, cwd=cwd)


def test_help_lists_the_surviving_commands():
    out = bio("--help")
    assert out.returncode == 0
    for word in ("suite run", "suite resume|aggregate|report", "config", "test-matrix"):
        assert word in out.stdout
    assert "hardcoded_test" not in out.stdout


def test_suite_run_dry_then_run_resume_aggregate_report(tmp_path):
    dry = bio("suite", "run", str(ZERO), "--dry")
    assert dry.returncode == 0 and "trials planned: 4" in dry.stdout and "no-peeking: ok" in dry.stdout
    out = tmp_path / "run"
    ran = bio("suite", "run", str(ZERO), "--out", str(out))
    assert ran.returncode == 0, ran.stderr
    assert (out / "records.jsonl").exists() and (out / "manifest.json").exists() and (out / "report.txt").exists()
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["trials_completed"] == 4
    # a second plain run refuses to clobber; resume is a no-op that succeeds
    again = bio("suite", "run", str(ZERO), "--out", str(out))
    assert again.returncode != 0
    resumed = bio("suite", "resume", str(out))
    assert resumed.returncode == 0, resumed.stderr
    agg = bio("suite", "aggregate", str(out))
    assert agg.returncode == 0, agg.stderr
    rep = bio("suite", "report", str(out))
    assert rep.returncode == 0 and "Experiment: exp4-zero" in rep.stdout


def test_suite_run_on_the_ecosystem_example(tmp_path):
    example = REPO / "catalog" / "examples" / "ecosystem" / "ecosystem.yaml"
    ran = bio("suite", "run", str(example), "--out", str(tmp_path / "eco"))
    assert ran.returncode == 0, ran.stderr
    lines = (tmp_path / "eco" / "records.jsonl").read_text().splitlines()
    assert len(lines) == 8


def test_test_matrix_and_config():
    matrix = bio("test-matrix", "--check")
    assert matrix.returncode == 0, matrix.stderr
    table = bio("test-matrix", "--markdown")
    assert table.returncode == 0 and table.stdout.startswith("| Id |")
    config = bio("config", "show")
    assert config.returncode == 0, config.stderr


def test_bad_usage_exits_2():
    assert bio("suite").returncode == 2
    assert bio("test-matrix", "--bogus").returncode == 2
