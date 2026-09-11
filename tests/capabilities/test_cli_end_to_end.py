"""M48.7 — every ``bio`` subcommand end to end against the catalog, as a
subprocess (the way CI and a user run it)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ZERO = REPO / "catalog" / "experiments" / "exp04-zero.yaml"


def bio(*args: str, cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "alienbio.cli", *args], capture_output=True, text=True, cwd=cwd)


def test_help_lists_the_surviving_commands():
    out = bio("--help")
    assert out.returncode == 0
    # T057: the front door is generated from COMMANDS, so it names exactly them.
    for word in ("config", "report", "suite", "test-matrix"):
        assert word in out.stdout
    assert "hardcoded_test" not in out.stdout
    for stale in ("bio build", "bio expand", "bio hydrate", "bio store"):
        assert stale not in out.stdout
    suite_help = bio("suite", "--help")
    assert suite_help.returncode == 0 and "models" in suite_help.stdout
    report_help = bio("report", "--help")
    assert report_help.returncode == 0 and "--junit" in report_help.stdout and "--out" in report_help.stdout


def test_suite_run_dry_then_run_resume_aggregate_report(tmp_path):
    out = tmp_path / "run"
    dry = bio("suite", "run", str(ZERO), "--dry", "--out", str(out))
    assert dry.returncode == 0 and "trials planned: 4" in dry.stdout and "no-peeking: ok" in dry.stdout
    assert "preflight: ok" in dry.stdout and not out.exists()  # a dry run creates nothing
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
    assert rep.returncode == 0 and "Experiment: exp04-zero" in rep.stdout


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


def test_suite_run_refuses_an_unknown_flag_and_trailing_args(tmp_path):
    """T051 box 4 — an unknown token fell into the positional list, so
    ``--dryy`` on a live spec ran it for real, and ``resume DIR extra``
    ignored the extra silently."""
    assert bio("suite", "run", str(ZERO), "--dryy").returncode == 2
    assert bio("suite", "run", str(ZERO), "--out").returncode == 2
    assert bio("suite", "run", str(ZERO), "second.yaml", "--dry").returncode == 2
    assert not (REPO / "runs" / "exp04-zero-dryy").exists()
    verbose_after_verb = bio("suite", "run", str(ZERO), "--dry", "-v", "--out", str(tmp_path / "v"))
    assert verbose_after_verb.returncode == 0
    assert bio("suite", "resume", str(tmp_path), "extra").returncode == 2
    assert bio("suite", "aggregate", str(tmp_path), "extra").returncode == 2
    assert bio("suite", "report", str(tmp_path), "extra").returncode == 2


def test_dry_run_prints_every_refusal_the_run_would_make(tmp_path):
    """T051 box 5 / T057 — `--dry` ran two of the guards: a spec with a bogus
    `registration:` printed `no-peeking: ok · dials: ok` and exit 0, then the
    real run refused. The dry run now runs the run's own preflight and exits
    1 with every verdict on the page."""
    spec = tmp_path / "bogus.yaml"
    spec.write_text(ZERO.read_text().rstrip() + "\nregistration: no-such-filing\n")
    dry = bio("suite", "run", str(spec), "--dry", "--out", str(tmp_path / "out"))
    assert dry.returncode == 1
    assert "registration: REFUSED" in dry.stdout and "no-such-filing" in dry.stdout
    assert "preflight: REFUSED" in dry.stdout
    # An out_dir that already holds records is a refusal too, and says why.
    ran = bio("suite", "run", str(ZERO), "--out", str(tmp_path / "held"))
    assert ran.returncode == 0, ran.stderr
    dry2 = bio("suite", "run", str(ZERO), "--dry", "--out", str(tmp_path / "held"))
    assert dry2.returncode == 1 and "out_dir exists: yes (run refuses without resume)" in dry2.stdout
    assert "out_dir: REFUSED" in dry2.stdout
