"""AUP 2026-09-10 — a dial nobody reads is refused, never dropped.

``DRAFTERS["pressure"](seed, {"pi": 0, "feed_max_rate": 6})`` drafted a
world at cap 20 and said nothing: ``feed_max_rate`` is a generator keyword
(``drafter_kwargs`` / ``**generator``), not a dial, and the adapter simply
did not pass it. Four AUP analysis scripts carried the key on the dials
side; their numbers survived only because nothing read the cap. An
unrecognised key now raises at the drafter, in ``run_experiment``'s
pre-flight (before spend, so it cannot become N error records) and shows on
``bio suite run --dry``. No model calls."""

from __future__ import annotations

import pytest

from alienbio.suite.dist import Seed
from alienbio.suite.experiment import (
    WORLD_INVARIANT_DIALS,
    DRAFTERS,
    ExperimentSpec,
    dial_params,
    drafter_heads,
    run_experiment,
    runtime_dials,
    unknown_dials,
    unknown_dials_violation,
)


def test_the_exact_aup_shape_refuses_with_the_routing_hint():
    with pytest.raises(ValueError, match=r"unknown dial\(s\) \['feed_max_rate'\]") as info:
        DRAFTERS["pressure"](Seed(5700), {"pi": 0.0, "feed_max_rate": 6.0})
    message = str(info.value)
    assert "drafter_kwargs" in message  # where the key belongs
    assert "feed_max_rate / target_margin" in message
    # the same key on the generator side is the right call and still works
    _, task = DRAFTERS["pressure"](Seed(5700), {"pi": 0.0}, feed_max_rate=6.0)
    assert set(task.setup["lever_caps"].values()) == {6.0}


def test_a_nonsense_dial_refuses_and_names_what_the_head_reads():
    with pytest.raises(ValueError, match="nonsense_dial") as info:
        DRAFTERS["pressure"](Seed(5700), {"pi": 0.0, "nonsense_dial": 123})
    assert "'pi'" in str(info.value)  # the head's own dials are listed


def test_every_runtime_dial_still_passes_every_drafter():
    """Brief/episode/factory dials ride the merged vector past any drafter
    (the runner and the brief read them) — the refusal is only for names
    nobody reads."""
    assert set(WORLD_INVARIANT_DIALS) <= runtime_dials()
    for name in ("sim_dt", "sample_every", "observability", "observation_noise", "compact_at", "model"):
        assert name in runtime_dials()
    for name, head in drafter_heads().items():
        assert unknown_dials(name, list(runtime_dials()) + list(dial_params(head))) == []


def test_run_experiment_refuses_before_drafting_anything(tmp_path):
    spec = ExperimentSpec(
        name="misplaced",
        axes=(("rung", ("single", "forced")),),
        drafter="conflict",
        agent="idle",
        trials_per_condition=1,
        base_seed=42,
        fixed_dials={"levers": [], "target_margin": 0.3},
    )
    assert unknown_dials_violation(spec) is not None
    assert "target_margin" in unknown_dials_violation(spec)
    with pytest.raises(ValueError, match="run_experiment: conflict: unknown dial"):
        run_experiment(spec, out_dir=str(tmp_path / "run"))
    assert not (tmp_path / "run" / "records.jsonl").exists()  # refused, not recorded as N errors
    clean = ExperimentSpec(
        name="placed",
        axes=(("rung", ("single", "forced")),),
        drafter="conflict",
        agent="idle",
        trials_per_condition=1,
        base_seed=42,
        fixed_dials={"levers": []},
    )
    assert unknown_dials_violation(clean) is None


def test_dry_run_reports_the_dial_check(tmp_path, capsys, monkeypatch):
    """The Expr form cannot even spell a misplaced key (``spec_to_text`` /
    the loader route every keyword to the head that declares it), so the
    dry run's line reads ``ok`` for a well-formed file — and ``UNKNOWN`` when
    the loaded spec carries one (a dict/JSON spec, or a manifest replay)."""
    import alienbio.commands.suite_cmd as cmd
    from alienbio.suite.experiment import spec_from_dict
    from alienbio.suite.expr_experiment import spec_to_text

    good = spec_from_dict(
        {
            "name": "dry-placed",
            "drafter": "pressure",
            "agent": "idle",
            "trials_per_condition": 1,
            "base_seed": 1,
            "axes": {"pi": [0.0, 0.5]},
            "fixed_dials": {"levers": []},
            "drafter_kwargs": {"feed_max_rate": 6.0},
        }
    )
    path = tmp_path / "spec.yaml"
    path.write_text(spec_to_text(good))
    assert cmd.suite_command(["run", str(path), "--dry"]) == 0
    assert "dials: ok" in capsys.readouterr().out

    bad = spec_from_dict(
        {
            "name": "dry-misplaced",
            "drafter": "pressure",
            "agent": "idle",
            "trials_per_condition": 1,
            "base_seed": 1,
            "axes": {"pi": [0.0, 0.5]},
            "fixed_dials": {"levers": [], "feed_max_rate": 6.0},
        }
    )
    monkeypatch.setattr(cmd, "load_spec", lambda _path: bad)
    # T057: a dry run that would refuse exits 1 and says so on the dials line.
    assert cmd.suite_command(["run", str(path), "--dry"]) == 1
    out = capsys.readouterr().out
    assert "dials: REFUSED" in out and "feed_max_rate" in out and "preflight: REFUSED" in out
