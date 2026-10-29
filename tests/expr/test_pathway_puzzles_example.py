"""M48.9 example 6 — pathway puzzles: the suite-construction pipeline end to
end on a neutral host (draft with distractors, pattern + carve, identify with
partial credit, vocabulary round trip, cover, verify), and an experiment."""

from __future__ import annotations

from pathlib import Path

import pytest

from alienbio.bio.world import WorldImpl
from alienbio.expr import Env
from alienbio.suite.cover import Cover
from alienbio.suite.experiment import load_spec, run_experiment
from alienbio.suite.types import AnswerObjective, Question

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "catalog" / "examples" / "pathway_puzzles" / "puzzles.yaml"


@pytest.fixture(scope="module")
def values():
    return Env.standard(seed=11, trusted=True).load(SPEC).force_all()


def test_the_host_carries_the_chain_plus_distractors(values):
    host, carved = values["host"], values["carved"]
    assert isinstance(host, WorldImpl)
    assert set(carved.binding) == {"r0", "r1", "r2", "r3"}
    assert all(node in host.chemistry.molecules for node in carved.binding.values())
    assert len(host.chemistry.molecules) > 4  # the distractors are there


def test_the_identify_key_is_the_carved_chain_and_grades_with_partial_credit(values):
    puzzle = values["puzzle"]
    obj = puzzle["objective"]
    assert isinstance(obj, AnswerObjective) and obj.key.kind == "ordered_path"
    assert obj.key.value == [values["carved"].binding[f"r{i}"] for i in range(4)]
    assert values["full_credit"] == 1.0
    # T088 identify_pathway 1: the question's start node earns no credit, so
    # the right first two of four score (2 - 1) / (4 - 1), and echoing the
    # question's endpoints scores 0 (it scored 1/4).
    assert values["prefix_credit"] == pytest.approx(1 / 3)
    assert values["echo_credit"] == 0.0
    assert values["no_credit"] == 0.0
    assert values["task"].objective is obj


def test_the_key_varies_with_the_seed_and_the_ids_do_not_spell_it():
    """T096: the identify_pathway host named its chain r0 … and its reactions
    r0_r1 …, so the key was ['r0', 'r1', 'r2'] on every seed and readable off
    the ids. The opaque host deals m1 … / x1 … from the seed: the key varies,
    and no id carries a role name or a reaction's ends."""
    keys = set()
    for seed in range(12):
        v = Env.standard(seed=seed, trusted=True).load(SPEC).force_all()
        key = v["puzzle"]["objective"].key.value
        keys.add(tuple(key))
        host = v["host"]
        assert all(m.startswith("m") and m[1:].isdigit() for m in host.chemistry.molecules)
        assert all(r.startswith("x") and r[1:].isdigit() for r in host.chemistry.reactions)
        # the route lives in the stoichiometry alone
        steps = {(next(iter(r.reactants)).name, next(iter(r.products)).name) for r in host.chemistry.reactions.values()}
        assert steps == set(zip(key, key[1:]))
    assert len(keys) == 12


def test_the_question_survives_the_vocabulary_round_trip(values):
    q, text, back = values["puzzle"]["question"], values["question_text"], values["question_back"]
    assert isinstance(q, Question) and isinstance(back, Question)
    key = values["puzzle"]["objective"].key.value
    assert q.structured == [key[0], key[-1]]
    assert all(node not in text for node in key)  # opaque: no raw id leaks
    assert back == q


def test_the_coverage_plan_respects_the_admissibility_rule(values):
    plan = values["plan"]
    assert isinstance(plan, Cover)
    assert plan.containers
    for container in plan.containers:
        assert len({key for key, _ in container}) <= 2


def test_reject_sampling_returns_a_causally_non_obvious_host(values):
    checked = values["checked"]
    assert isinstance(checked, WorldImpl) and len(checked.chemistry.reactions) >= 3


def test_the_experiment_runs_over_the_chain_length(tmp_path):
    spec = load_spec(SPEC)
    assert spec.drafter == "puzzles" and spec.axes == (("pathway_length", (3, 5)),)
    rmap = run_experiment(spec, out_dir=str(tmp_path / "run"))
    assert len(rmap.records) == 4 and rmap.provenance.failed_trials == 0
