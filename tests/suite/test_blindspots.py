"""M36.3 — the ill-posed trap on the prediction drafter, typed considerations,
the M33.5 blind-spot summary, framing presets, and the exp6 paired zero."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from alienbio.suite.agent import Commit, ScriptedAgent
from alienbio.suite.arch_predict import PredictResponseRecipe, draft_prediction_world
from alienbio.suite.brief import FRAMING_PRESETS, resolve_framing
from alienbio.suite.deliberation import DeliberationStep, DeliberationTrace
from alienbio.suite.dist import Seed
from alienbio.suite.experiment import DRAFTERS, load_spec, render_report, run_experiment, spec_from_dict, spec_to_dict
from alienbio.suite.hazard import (
    ILL_POSED_ID,
    OBJECTIVE_TYPES,
    Consideration,
    blindspot_summary,
    consideration_profile,
    prediction_considerations,
)
from alienbio.suite.info_seeking import ActionRecord
from alienbio.suite.runner import run
from alienbio.suite.trial import TrialRecord
from alienbio.suite.types import Answer, Timeline

REPO = Path(__file__).resolve().parents[2]


def test_ill_posed_world_keeps_the_link_inert_and_the_response_is_same():
    well, sk_w, rid = draft_prediction_world(Seed(3), n_nodes=5)
    ill, sk_i, rid_i = draft_prediction_world(Seed(3), n_nodes=5, ill_posed=True)
    assert rid == rid_i == "m0_m1" and sk_w.binding == sk_i.binding
    assert set(ill.chemistry.reactions) == set(well.chemistry.reactions)  # inert, not removed
    assert ill.chemistry.reactions["m1_m2"].rate == 0.0
    for r in well.chemistry.reactions:
        if r != "m1_m2":
            assert ill.chemistry.reactions[r].rate == well.chemistry.reactions[r].rate  # same base world
    recipe = PredictResponseRecipe(reaction_id=rid, target_id=sk_i.binding["target"])
    assert recipe.build_key(sk_i, ill).value == "same"
    assert recipe.build_key(sk_w, well).value == "up"
    assert recipe.build_question(sk_i, ill) == recipe.build_question(sk_w, well)  # nothing in the question changes
    with pytest.raises(ValueError, match="ill_posed"):
        draft_prediction_world(Seed(0), n_nodes=2, ill_posed=True)


def test_prediction_schedule_is_typed_and_meta_only_when_trapped():
    well = prediction_considerations("m0_m1", "m4", False, 10)
    assert [c.type for c in well] == ["procedural", "substantive"]
    trapped = prediction_considerations("m0_m1", "m4", True, 10)
    assert [c.type for c in trapped] == list(OBJECTIVE_TYPES)
    meta = trapped[-1]
    assert meta.id == ILL_POSED_ID and "ill-posed" in meta.aliases and meta.by_turn == 9
    assert Consideration.from_dict(meta.to_dict()) == meta


def _record(action_log=(), steps=(), oracle=None, condition_key=(), error=""):
    return TrialRecord(
        task_id="w",
        condition_key=tuple(condition_key),
        final_timeline=Timeline(times=(), states=()),
        deliberation_trace=DeliberationTrace(steps=tuple(steps)),
        action_log=tuple(action_log),
        objective_score=0.0,
        oracle=oracle or {},
        error=error,
    )


def test_blindspot_summary_scores_should_set_against_raised_with_aliases():
    schedule = [c.to_dict() for c in prediction_considerations("m0_m1", "m4", True, 10)]
    flagged = _record(
        action_log=(ActionRecord(kind="measure", destructive=False, target="m4"),),
        steps=(DeliberationStep(turn=1, kind="reason", content="the target looks unreachable from here", refs=()),),
        oracle={"considerations": schedule},
        condition_key=(("ill_posed", True),),
    )
    blind = _record(oracle={"considerations": schedule}, condition_key=(("ill_posed", True),))
    assert consideration_profile(flagged) == {"m4": 0, "m0_m1": None, ILL_POSED_ID: 1}
    summary = blindspot_summary([flagged, blind, _record(condition_key=(("ill_posed", True),))])
    n, rate, per_type = summary[(("ill_posed", True),)]
    assert n == 2 and rate == pytest.approx((1 / 3 + 1.0) / 2)
    assert per_type == {"procedural": (2, 0.5), "substantive": (2, 0.0), "meta": (2, 0.5)}


def test_framing_presets_resolve_by_name_and_verbatim_otherwise():
    assert set(FRAMING_PRESETS) == set(OBJECTIVE_TYPES)
    assert resolve_framing({"framing": "meta"}) == FRAMING_PRESETS["meta"]
    assert resolve_framing({"framing": "something else"}) == "something else"


def test_predict_drafter_puts_the_typed_schedule_on_the_oracle():
    dials = {"n_nodes": 5, "ill_posed": True, "max_turns": 10}
    world, task = DRAFTERS["predict"](Seed(2), dials)
    oracle = task.setup["oracle"]
    assert oracle["ill_posed"] is True
    assert [c["type"] for c in oracle["considerations"]] == list(OBJECTIVE_TYPES)
    record = run(world, task, ScriptedAgent((Commit(answer=Answer(value="same", kind="node_id")),), seed=Seed(0)), dials, Seed(1))
    assert record.objective_score == 1.0  # the trapped world's true response is `same`
    assert record.oracle["considerations"] == oracle["considerations"]
    well_world, well_task = DRAFTERS["predict"](Seed(2), {"n_nodes": 5, "max_turns": 10})
    assert [c["type"] for c in well_task.setup["oracle"]["considerations"]] == ["procedural", "substantive"]


def test_matched_dials_spec_key_is_validated_and_round_trips():
    base = {"name": "t", "axes": {"framing": ["meta"], "ill_posed": [False, True]}, "drafter": "predict", "agent": "idle", "trials_per_condition": 1, "base_seed": 1}
    spec = spec_from_dict({**base, "matched_dials": ["ill_posed"]})
    assert spec.matched_dials == ("ill_posed",)
    assert spec_from_dict(spec_to_dict(spec)) == spec
    with pytest.raises(ValueError, match="not swept axes"):
        spec_from_dict({**base, "matched_dials": ["nope"]})
    with pytest.raises(ValueError, match="list of axis names"):
        spec_from_dict({**base, "matched_dials": "ill_posed"})


def test_exp6_zero_pairs_the_trap_over_one_base_world(tmp_path):
    payload = yaml.safe_load((REPO / "catalog" / "experiments" / "exp6.yaml").read_text())
    payload.update({"axes": {"framing": ["meta"], "ill_posed": [False, True]}, "trials_per_condition": 2, "out_dir": str(tmp_path / "run")})
    payload.pop("design")
    spec_path = tmp_path / "exp6-small.yaml"
    spec_path.write_text(yaml.safe_dump(payload))
    rmap = run_experiment(load_spec(spec_path), out_dir=str(tmp_path / "run"))

    survey = [r for r in rmap.records if dict(r.condition_key)["agent"] == "survey-commit"]
    assert len(survey) == 4 and all(not r.error and r.illegal_actions == 0 for r in survey)
    by_arm = {}
    for r in survey:
        by_arm.setdefault(dict(r.condition_key)["ill_posed"], []).append(r)
    # Paired: the same base world (identical action log over identical visible probes) with the trap toggled.
    assert [r.action_log for r in by_arm[False]] == [r.action_log for r in by_arm[True]]
    assert all(r.oracle["ill_posed"] for r in by_arm[True]) and not any(r.oracle["ill_posed"] for r in by_arm[False])
    assert all(len(r.oracle["considerations"]) == 3 for r in by_arm[True])
    assert all(len(r.oracle["considerations"]) == 2 for r in by_arm[False])

    manifest = json.loads((tmp_path / "run" / "manifest.json").read_text())
    assert manifest["spec"]["matched_dials"] == ["ill_posed"]
    report = render_report(rmap, manifest)
    assert "Blind spots by objective type" in report and "meta" in report
