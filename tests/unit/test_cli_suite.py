"""Tests for the ``bio suite`` CLI command (M46.5)."""

from __future__ import annotations

import alienbio.cli as cli


def _write_spec(tmp_path):
    path = tmp_path / "spec.yaml"
    path.write_text(
        "!experiment\n"
        "name: clitest\n"
        "task: !q conflict(rung=rung)\n"
        "brief: !q brief(levers=[])\n"
        "agent: idle\n"
        "axes: {rung: [single]}\n"
        "trials_per_condition: 1\n"
        "base_seed: 1\n"
    )
    return path


def test_suite_run_dry_prints_grid_summary_and_exits_0(tmp_path, capsys):
    spec_path = _write_spec(tmp_path)

    # The top-level parser hands everything after the command to the
    # subcommand verbatim (argparse.REMAINDER), flags included.
    rc = cli.main(["suite", "run", str(spec_path), "--dry"])

    assert rc == 0
    captured = capsys.readouterr()
    assert "trials planned" in captured.out
    assert "drafter: conflict" in captured.out
    assert "agent: idle" in captured.out
    assert "no-peeking" in captured.out
    assert "estimated cost" in captured.out
    assert "cost ceiling: none" in captured.out


def test_suite_no_verb_exits_2(capsys):
    rc = cli.main(["suite"])

    assert rc == 2
    captured = capsys.readouterr()
    assert "Usage" in captured.err


def test_suite_report_without_manifest_exits_1_no_traceback(tmp_path, capsys):
    empty_dir = tmp_path / "no_manifest_here"
    empty_dir.mkdir()

    rc = cli.main(["suite", "report", str(empty_dir)])

    assert rc == 1
    captured = capsys.readouterr()
    assert "Error" in captured.err
    assert "Traceback" not in captured.err
