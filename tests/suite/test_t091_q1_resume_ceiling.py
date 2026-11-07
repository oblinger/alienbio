"""T091 Q1 (Dan, (A)) — ``bio suite resume DIR --cost-ceiling USD``: one flag
that replaces the run's ceiling, the resume guard's refusal below the
directory's spend surfaced through the CLI, and the ceiling in the banner."""

from __future__ import annotations

import pytest

from alienbio.commands.suite_cmd import _parser, suite_command
from alienbio.suite import agents as agents_mod
from alienbio.suite.agents import _survey_commit_agent_factory
from alienbio.suite.experiment import ExperimentSpec, run_experiment
from alienbio.suite.store import read_manifest, read_records


class _Paid:
    """A scripted agent that reports $2 of usage per trial (1M input tokens)."""

    def __init__(self, inner):
        self.inner = inner
        self.usage = {"calls": 1, "input_tokens": 1_000_000, "output_tokens": 0,
                      "cache_read_tokens": 0, "cache_write_tokens": 0}

    def act(self, obs):
        return self.inner.act(obs)

    def __getattr__(self, name):
        return getattr(self.inner, name)


@pytest.fixture
def stopped(tmp_path, monkeypatch):
    """A run the $5 ceiling stopped part-way through its six trials."""
    monkeypatch.setitem(
        agents_mod.AGENTS, "paid",
        lambda spec: (lambda seed, dials: _Paid(_survey_commit_agent_factory(seed, dials))),
    )
    spec = ExperimentSpec(
        name="t091q1", axes=(("rung", ("single", "forced")),), drafter="conflict", agent="paid",
        trials_per_condition=3, base_seed=42, fixed_dials={"levers": []}, cost_ceiling_usd=5.0,
    )
    out = tmp_path / "run"
    first = run_experiment(spec, out_dir=str(out))
    assert first.provenance.stopped_early and len(first.records) < 6
    spent = sum(1 for _ in read_records(out / "records.jsonl")) * 2.0
    return out, spent


def test_a_stopped_run_resumed_with_a_higher_ceiling_finishes_and_records_it(stopped, capsys):
    out, spent = stopped
    capsys.readouterr()
    assert suite_command(["resume", str(out), "--cost-ceiling", "100"]) == 0
    captured = capsys.readouterr()
    assert f"cost ceiling: $100.0000 (was $5.0000; directory spent ${spent:.4f})" in captured.out
    assert "stopped early" not in captured.err
    assert sum(1 for _ in read_records(out / "records.jsonl")) == 6
    manifest = read_manifest(out / "manifest.json")
    assert manifest["cost_ceiling_history"] == [5.0, 100.0]
    assert manifest.get("stopped_reason") is None


def test_a_ceiling_below_the_spend_refuses_through_the_cli_with_the_engines_message(stopped, capsys):
    out, spent = stopped
    before = (out / "records.jsonl").read_text()
    capsys.readouterr()
    assert suite_command(["resume", str(out), "--cost-ceiling", str(spent - 1.0)]) == 1
    err = capsys.readouterr().err
    assert f"already spent ${spent:.4f}" in err and "never set below the spend" in err
    assert (out / "records.jsonl").read_text() == before
    assert read_manifest(out / "manifest.json")["cost_ceiling_history"] == [5.0]


@pytest.mark.parametrize("value", ["0", "-3", "nan", "inf"])
def test_a_non_positive_or_non_finite_ceiling_refuses(stopped, capsys, value):
    out, _spent = stopped
    before = (out / "records.jsonl").read_text()
    capsys.readouterr()
    assert suite_command(["resume", str(out), "--cost-ceiling", value]) == 1
    err = capsys.readouterr().err
    expected = "cost_ceiling_usd must be > 0" if value in ("0", "-3") else "must be a finite number"
    assert expected in err
    assert (out / "records.jsonl").read_text() == before


def test_a_non_number_is_a_usage_error(stopped):
    out, _spent = stopped
    assert suite_command(["resume", str(out), "--cost-ceiling", "lots"]) == 2


def test_without_the_flag_the_banner_names_the_runs_ceiling_and_an_overshot_stop_names_the_flag(stopped, capsys):
    # The stop lands after the trial that crossed $5, so the directory spent
    # more than its own ceiling: a plain resume refuses, and says how to go on.
    out, spent = stopped
    assert spent > 5.0
    capsys.readouterr()
    assert suite_command(["resume", str(out)]) == 1
    captured = capsys.readouterr()
    assert "cost ceiling: $5.0000\n" in captured.out
    assert f"already spent ${spent:.4f}" in captured.err and "--cost-ceiling USD` sets a new one" in captured.err
    assert read_manifest(out / "manifest.json")["cost_ceiling_history"] == [5.0]


def test_a_run_without_a_ceiling_banners_none(tmp_path, capsys):
    spec = ExperimentSpec(
        name="t091q1none", axes=(("rung", ("single",)),), drafter="conflict", agent="idle",
        trials_per_condition=1, base_seed=42, fixed_dials={"levers": []},
    )
    out = tmp_path / "run"
    run_experiment(spec, out_dir=str(out))
    capsys.readouterr()
    assert suite_command(["resume", str(out)]) == 0
    assert "cost ceiling: none\n" in capsys.readouterr().out
    assert suite_command(["resume", str(out), "--cost-ceiling", "2.5"]) == 0
    assert "cost ceiling: $2.5000 (was none; directory spent $0.0000)" in capsys.readouterr().out
    assert read_manifest(out / "manifest.json")["cost_ceiling_history"] == [None, 2.5]


def test_only_resume_takes_the_flag():
    parser = _parser()
    resume_help = parser._subparsers._group_actions[0].choices["resume"].format_help()  # type: ignore[union-attr]
    assert "--cost-ceiling USD" in resume_help
    for verb in ("aggregate", "report"):
        with pytest.raises(SystemExit):
            parser.parse_args([verb, "x", "--cost-ceiling", "3"])
    with pytest.raises(SystemExit):
        parser.parse_args(["run", "x.yaml", "--cost-ceiling", "3"])


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_a_non_finite_ceiling_in_a_spec_refuses_too(value):
    """``_validate_cost_ceiling`` accepted NaN and inf from a spec file
    (``.nan`` / ``.inf`` are valid YAML floats); NaN compared false against
    every spend, so such a ceiling never stopped a run (T091 Q1, Pilot)."""
    from alienbio.suite.spec import _validate_cost_ceiling

    with pytest.raises(ValueError, match="cost_ceiling_usd must be (a finite number|> 0)"):
        _validate_cost_ceiling(value)
    assert _validate_cost_ceiling(2.5) == 2.5
