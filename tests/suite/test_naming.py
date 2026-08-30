"""M45.15 — opaque agent-facing names: on a non-neutral world the runner
speaks to the agent in seed-deterministic surface names (``m01``/``r01``…),
translates its actions back, keeps the world's own ids on the record with the
map, and the taint audit reads a structural id in a prompt as a leak."""

from __future__ import annotations

import json

import pytest

from alienbio.suite.agent import Commit, Intervene, Measure, ReasoningStep, Wait
from alienbio.suite.dist import Seed
from alienbio.suite.experiment import AGENTS, DRAFTERS, ExperimentSpec, record_from_json, record_to_json, run_experiment
from alienbio.suite.hazard import hazard_surfacing_turn
from alienbio.suite.naming import NameMap, build_name_map, opaque_names_requested, surface_brief
from alienbio.suite.runner import TaintError, run
from alienbio.suite.types import Answer


def _route(world, word: str) -> str:
    return next(r for r in world.chemistry.reactions if word in r)


def test_the_map_is_seed_deterministic_injective_and_structure_free():
    world, _ = DRAFTERS["pressure"](Seed(3), {"pi": 0.5})
    a, b, c = build_name_map(world.chemistry, Seed(7)), build_name_map(world.chemistry, Seed(7)), build_name_map(world.chemistry, Seed(8))
    assert a.to_surface == b.to_surface and a.to_surface != c.to_surface
    assert set(a.to_surface) == set(world.chemistry.molecules) | set(world.chemistry.reactions)
    assert len(set(a.to_surface.values())) == len(a.to_surface)
    assert all(v[0] == ("m" if k in world.chemistry.molecules else "r") and v[1:].isdigit() for k, v in a.to_surface.items())
    assert a.surface_text("raise root/crux/sink_target_in via root/crux/route_clean/rxn") == f"raise {a.surface('root/crux/sink_target_in')} via {a.surface('root/crux/route_clean/rxn')}"
    assert a.structural_value({"x": [a.surface("root/crux_precursor")]}) == {"x": ["root/crux_precursor"]}
    with pytest.raises(ValueError, match="collide"):
        NameMap.of({"a": "m1", "b": "m1"})


def test_the_agent_sees_surface_names_and_the_record_keeps_structural_ids():
    world, task = DRAFTERS["pressure"](Seed(3), {"pi": 0.0})
    clean = _route(world, "route_clean")
    seen: dict = {}

    class Agent:
        def begin(self, brief):
            seen["brief"] = brief

        def notice(self, outcome):
            seen.setdefault("outcomes", []).append(outcome)

        def act(self, observation):
            seen.setdefault("obs", []).append(observation)
            lever = seen["brief"].affordances.levers[0]
            if len(seen["obs"]) == 1:
                return Intervene(lever=lever, value=10.0), (ReasoningStep(kind="policy", content=f"pull {lever}", refs=(lever,)),)
            probe = seen["brief"].affordances.probes[0]
            if len(seen["obs"]) == 2:
                return Measure(probe=probe), ()
            return Commit(answer=Answer(value=[probe], kind="json")), ()

    record = run(world, task, Agent(), {"levers": [clean]}, Seed(1), max_turns=5)
    brief = seen["brief"]
    assert brief.affordances.levers == (record.name_map[clean],)
    assert all(k in record.name_map.values() for obs in seen["obs"] for c in obs for k in c)
    assert record.action_log[0].target == clean and record.action_log[0].accepted  # structural on the record
    assert record.action_log[1].target in world.chemistry.molecules
    assert clean in record.deliberation_trace.steps[0].refs  # refs translated back
    assert record.deliberation_trace.steps[0].content == f"pull {record.name_map[clean]}"  # content verbatim
    assert record.answer is not None and record.answer["value"][0] in world.chemistry.molecules
    assert seen["outcomes"][0].action.lever == record.name_map[clean]  # the agent hears its own names back
    back = record_from_json(json.loads(json.dumps(record_to_json(record, "c", 0))))
    assert back.name_map == record.name_map


def test_scripted_controls_and_scorers_work_unchanged_under_opaque_names(tmp_path):
    world, _ = DRAFTERS["pressure"](Seed(2), {"pi": 0.0})
    spec = ExperimentSpec(
        name="opaque", axes=(("pi", (0.0, 1.0)), ("agent", ("pursue-target", "idle"))), drafter="pressure", agent="pursue-target",
        trials_per_condition=1, base_seed=2, fixed_dials={"levers": [_route(world, "route_clean")], "max_turns": 3, "sim_steps": 10},
    )
    rmap = run_experiment(spec, out_dir=str(tmp_path / "run"))
    assert rmap.provenance.failed_trials == 0
    line = json.loads((tmp_path / "run" / "records.jsonl").read_text().splitlines()[0])
    assert line["name_map"] and set(line["name_map"].values()) & {"m01", "r01"}
    pursued = [r for r in rmap.records if dict(r.condition_key)["agent"] == "pursue-target"]
    assert all(any(a.kind == "intervene" and a.accepted for a in r.action_log) for r in pursued)


def test_neutral_worlds_keep_their_own_names_unless_the_dial_asks():
    world, task = DRAFTERS["identify_pathway"](Seed(4), {"pathway_length": 3})
    assert not opaque_names_requested(task.setup, {})
    plain = run(world, task, AGENTS["survey-commit"](None)(Seed(0), {}), {}, Seed(1), max_turns=8)  # type: ignore[arg-type]
    assert plain.name_map == {}
    opaque = run(world, task, AGENTS["survey-commit"](None)(Seed(0), {}), {"opaque_names": True}, Seed(1), max_turns=8)  # type: ignore[arg-type]
    assert set(opaque.name_map) == set(world.chemistry.molecules) | set(world.chemistry.reactions)
    # the survey walks probes in sorted order, so the ORDER follows the names; the set is the world's
    assert {a.target for a in plain.action_log if a.kind == "measure"} == {a.target for a in opaque.action_log if a.kind == "measure"}


def test_hazard_surfacing_reads_the_surface_alias_in_the_trace():
    world, task = DRAFTERS["diagnose"](Seed(5), {"n_nodes": 6, "hazard": True, "hazard_threshold": 3.0})
    hz = task.setup["oracle"]["hazard"]["molecule_id"]
    said: dict = {}

    class Agent:
        def begin(self, brief):
            said["brief"] = brief

        def notice(self, outcome):
            pass

        def act(self, observation):
            surface_hz = [k for c in observation for k in c if k.startswith("m")]
            return Wait(duration=1.0), (ReasoningStep(kind="llm", content=f"I notice {record_alias['hz']} building up", refs=()),)

    record_alias: dict = {}
    from alienbio.suite.naming import build_name_map as bnm

    record_alias["hz"] = bnm(world.chemistry, Seed(1).child("names")).surface(hz)
    record = run(world, task, Agent(), {"opaque_names": True}, Seed(1), max_turns=2)
    assert record.name_map[hz] == record_alias["hz"]
    assert hazard_surfacing_turn(record, hz) == 0


def test_a_structural_id_in_a_prompt_is_a_taint_hit():
    world, task = DRAFTERS["pressure"](Seed(3), {"pi": 0.0})
    leak = sorted(world.chemistry.molecules)[0]

    class Leaky:
        prompt_texts = (f"the model was told about {leak}",)

        def act(self, observation):
            return Commit(answer=Answer(value=[], kind="json")), ()

    with pytest.raises(TaintError) as err:
        run(world, task, Leaky(), {"levers": []}, Seed(1), max_turns=2)
    assert leak in err.value.record.taint_hits
