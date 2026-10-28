"""T088 operator round: the ``bio`` verbs' help and exit codes, ``bio suite
models`` without a key, the capability matrix outside a checkout, the
cost-ceiling stop line (2026-10-28)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from alienbio.cli import main
from alienbio.commands import COMMANDS


@pytest.mark.parametrize("verb", sorted(COMMANDS))
def test_every_verb_takes_help_and_exits_zero(verb, capsys):
    assert main([verb, "--help"]) == 0
    assert "usage: bio" in capsys.readouterr().out


def test_a_bare_bio_prints_help_and_exits_as_a_usage_error(capsys):
    assert main([]) == 2
    assert "Commands (each takes --help)" in capsys.readouterr().out


def test_verbose_is_accepted_between_suite_and_its_verb(monkeypatch):
    import alienbio.commands.suite_cmd as suite_cmd

    seen = {}

    def fake_aggregate(out_dir, verbose):
        seen["verbose"] = verbose
        return 0

    monkeypatch.setattr(suite_cmd, "_aggregate_cmd", fake_aggregate)
    assert suite_cmd.suite_command(["-v", "aggregate", "somewhere"]) == 0
    assert seen["verbose"] is True
    assert suite_cmd.suite_command(["aggregate", "somewhere", "-v"]) == 0
    assert seen["verbose"] is True
    assert suite_cmd.suite_command(["aggregate", "somewhere"]) == 0
    assert seen["verbose"] is False


def test_suite_models_without_a_key_is_a_refusal_not_a_traceback(monkeypatch, capsys):
    from alienbio import config
    from alienbio.commands.suite_cmd import suite_command

    monkeypatch.setattr(config, "get_api_key", lambda provider: None)
    assert suite_command(["models"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("Error:") and "API key" in err


def test_a_cost_ceiling_stop_says_so(capsys):
    from alienbio.commands.suite_cmd import _report_stop

    rmap = SimpleNamespace(records=[1, 2, 3], provenance=SimpleNamespace(stopped_early=True))
    _report_stop(rmap, 10)
    assert "stopped early (cost_ceiling) after 3 of 10 trials" in capsys.readouterr().err
    _report_stop(SimpleNamespace(records=[], provenance=SimpleNamespace(stopped_early=False)), 10)
    assert capsys.readouterr().err == ""


def test_the_matrix_outside_a_checkout_names_the_missing_folder(tmp_path, monkeypatch, capsys):
    import alienbio.capabilities as capabilities

    missing = tmp_path / "no-such-tests"
    monkeypatch.setattr(capabilities, "TESTS_DIR", missing)
    with pytest.raises(FileNotFoundError, match="no-such-tests"):
        capabilities.check()
    assert main(["test-matrix", "--check"]) == 1
    assert "no proving-test folder at" in capsys.readouterr().err


def test_a_spec_load_error_names_its_path_once(tmp_path, capsys):
    spec = tmp_path / "x.yaml"
    spec.write_text("name: x\nfoo: 1\n")
    assert main(["suite", "run", str(spec), "--dry"]) == 1
    err = capsys.readouterr().err
    assert err.count(str(spec)) == 1
