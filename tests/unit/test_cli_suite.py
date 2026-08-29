"""Tests for the ``bio suite`` CLI command (M46.5)."""

from __future__ import annotations

import yaml

import alienbio.cli as cli


def _write_spec(tmp_path):
    payload = {
        "name": "clitest",
        "axes": {"rung": ["single"]},
        "drafter": "conflict",
        "agent": "idle",
        "trials_per_condition": 1,
        "base_seed": 1,
    }
    path = tmp_path / "spec.yaml"
    path.write_text(yaml.safe_dump(payload))
    return path


def test_suite_run_dry_prints_grid_summary_and_exits_0(tmp_path, capsys):
    spec_path = _write_spec(tmp_path)

    # NOTE: `--` marks end-of-options for the TOP-LEVEL `bio` parser (cli.py),
    # which is out of scope to change here (cli.py is epilog-line-only in
    # this task) — its single generic `args` positional (nargs="*") cannot
    # otherwise absorb a bare `--flag` token (a pre-existing limitation that
    # affects every subcommand's own flags identically, e.g. `bio battery
    # spec.yaml --csv` via `cli.main` hits the same "unrecognized arguments"
    # today). `suite_command` itself parses `--dry` correctly once it
    # receives it, which is what this test exercises.
    rc = cli.main(["suite", "run", str(spec_path), "--", "--dry"])

    assert rc == 0
    captured = capsys.readouterr()
    assert "trials planned" in captured.out
    assert "drafter: conflict" in captured.out
    assert "agent: idle" in captured.out
    assert "no-peeking" in captured.out


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
