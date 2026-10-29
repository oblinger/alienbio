"""T091 round 4, investigator A: generators + analysis families.

Each test pins one finding (A1 … A8 as in the round-4 report): it failed
before its fix and passes after.
"""

from __future__ import annotations

import numpy as np
import pytest

from alienbio.expr import Env, X, evaluate
from alienbio.infra.mk import mk
from alienbio.suite.blocks import ReactionBlock
from alienbio.suite.dist import Constant, Seed
from alienbio.suite.dose import DoseCell, dose_profile
from alienbio.suite.grade import MalformedAnswer, _as_real
from alienbio.suite.rate_law import ModulationSpec, RateLaw
from alienbio.suite.skeleton import Port, PortDir, Role, SkeletonError


# A5 — RateLawBlock builds its sides through blocks._sides -------------------


def _law_block(**kw):
    # Imported here, not at module level: importing expr_heads during
    # collection registers the entity constructor heads before
    # tests/unit/test_dat.py defines its own, which
    # tests/expr/test_constructors.py then misses.
    from alienbio.suite.expr_heads import RateLawBlock

    ports = (Port("A", None, PortDir.IN), Port("A", None, PortDir.IN), Port("B", None, PortDir.OUT), Port("M", None, PortDir.IN))
    law = RateLaw(k=Constant(1.0), modulations=(ModulationSpec(pool="M", kind="activator", params={"a": Constant(1.0)}),))
    return RateLawBlock(name="r", role=Role.SUPPLY, ports=ports, rate=Constant(1.0), law=law, extra_pools=("M",), **kw)


_BOUND = {"A": mk.M("A"), "B": mk.M("B"), "M": mk.M("M")}


def test_a_rate_law_reaction_sums_duplicate_ports_like_a_plain_one():
    plain = ReactionBlock(name="r", role=Role.SUPPLY, ports=_law_block().ports[:3], rate=Constant(1.0))
    want = {m.name: c for m, c in plain.realize(Seed(0), "root/r", _BOUND).reactions["root/r/rxn"].reactants.items()}
    got = {m.name: c for m, c in _law_block().realize(Seed(0), "root/r", _BOUND).reactions["root/r/rxn"].reactants.items()}
    assert want == got == {"A": 2.0}


def test_a_rate_law_reaction_refuses_a_stray_stoich_key():
    with pytest.raises(SkeletonError, match="stoich names no port"):
        _law_block(stoich={"Z": 3.0}).realize(Seed(0), "root/r", _BOUND)


# A6 — the reaction head namespaces stoich keys inside a template ------------


_PLAIN = """
sk: !skeleton
  root: !block
    role: supply
    children:
      feed: !source {pool: A, rate: 1.0}
      r1: !reaction {reactants: [A], products: [B], rate: 0.4, stoich: {A: 2.0}}
      drain: !sink {pool: B}
world: !world {skeleton: !x sk}
"""

_TEMPLATE = """
dimer: !template
  body: !block
    role: supply
    children:
      feed: !source {pool: A, rate: 1.0}
      r1: !reaction {reactants: [A], products: [B], rate: 0.4, stoich: {A: 2.0}}
      drain: !sink {pool: B}
sk: !skeleton
  root: !block
    role: supply
    children:
      one: !dimer {}
world: !world {skeleton: !x sk}
"""


def _r1_reactants(doc: str) -> dict[str, float]:
    world = evaluate(X.name("world"), Env.standard(seed=1).load("d.yaml", text=doc))
    rxn = next(r for rid, r in world.chemistry.reactions.items() if "r1" in rid)
    return {m.name: c for m, c in rxn.reactants.items()}


def test_a_templated_stoich_coefficient_applies():
    assert _r1_reactants(_PLAIN) == {"root/A": 2.0}
    assert _r1_reactants(_TEMPLATE) == {"root/one.A": 2.0}


# A7 — a numpy scalar answer is a number --------------------------------------


@pytest.mark.parametrize("value", [np.int64(3), np.float32(3.0), np.float64(3.0), 3, 3.0])
def test_a_numpy_scalar_answer_grades_as_a_number(value):
    assert _as_real(value) == 3.0


@pytest.mark.parametrize("value", [True, np.bool_(True), float("nan"), float("inf"), np.float64("nan"), "3"])
def test_a_bool_or_non_finite_scalar_answer_is_malformed(value):
    with pytest.raises(MalformedAnswer):
        _as_real(value)


# A8 — the continuity share is read at the rung nearest 0.2 -------------------


def _cell(pi: float, side: float) -> DoseCell:
    return DoseCell(pi=pi, n=1, mean_t=0.0, mean_byproduct=side, mean_score=0.0, passive_t=0.0, passive_byproduct=0.0, v_target=1.0)


def test_the_continuity_share_is_read_at_the_rung_nearest_continuity_pi():
    # {0, 0.1, 0.5, 1}: the old rule read the share spent by 0.1 (0.05) and
    # passed; 0.1 IS the nearest rung here, and the rung used is reported.
    prof = dose_profile([_cell(0.0, 0.0), _cell(0.1, 0.05), _cell(0.5, 0.95), _cell(1.0, 1.0)])
    assert prof.continuity_rung == 0.1 and prof.fraction_by_continuity_pi == pytest.approx(0.05)
    # {0, 0.15, 0.25, 1}: tie -> the lower rung.
    tie = dose_profile([_cell(0.0, 0.0), _cell(0.15, 0.1), _cell(0.25, 0.9), _cell(1.0, 1.0)])
    assert tie.continuity_rung == 0.15
    # {0, 0.05, 0.28, 1}: 0.28 is nearer than 0.05 (the old rule took 0.05).
    near = dose_profile([_cell(0.0, 0.0), _cell(0.05, 0.01), _cell(0.28, 0.6), _cell(1.0, 1.0)])
    assert near.continuity_rung == 0.28 and near.continuous is False


def test_a_ladder_with_no_rung_near_continuity_pi_reads_none_not_pass():
    prof = dose_profile([_cell(0.0, 0.0), _cell(0.05, 0.01), _cell(0.5, 0.95), _cell(1.0, 1.0)])
    assert prof.fraction_by_continuity_pi is None and prof.continuous is None and prof.continuity_rung is None


# A1 — intervene's outcome is scored at the horizon after the commit ---------

from alienbio.suite.agent import Commit, Intervene, ScriptedAgent, Wait  # noqa: E402
from alienbio.suite.drafters import DRAFTERS  # noqa: E402
from alienbio.suite.runner import run  # noqa: E402
from alienbio.suite.store import record_from_json, record_to_json  # noqa: E402
from alienbio.suite.types import Answer  # noqa: E402

_EXP09 = {"n_nodes": 5, "target_margin": 0.03, "max_turns": 12, "sim_steps": 10}
_COMMIT = Commit(answer=Answer(value=[], kind="json"))


def _run(policy, seed=9, dials=_EXP09):
    world, task = DRAFTERS["intervene"](Seed(seed), dials)
    return run(world, task, ScriptedAgent(tuple(policy), Seed(0)), dials, Seed(seed))


def test_an_early_commit_scores_the_same_as_committing_at_the_last_turn_after_the_same_act():
    act = Intervene(lever="m0_m1", value=2.0)
    early = _run([act, _COMMIT])
    late = _run([act, *[Wait(duration=1.0)] * 10, _COMMIT])
    assert early.turns == 2 and late.turns == 12
    assert early.runout is not None and early.runout["from_turn"] == 2 and early.runout["to_turn"] == 12
    assert late.runout is None  # ran the whole horizon: nothing to run out
    assert early.objective_score == late.objective_score
    assert early.runout["final_state"] == dict(late.final_state)
    # The episode's own end state is the commit turn's, not the horizon's.
    assert early.final_state != late.final_state


def test_commit_time_no_longer_moves_a_do_nothing_score():
    survey = _run([_COMMIT])
    idle = _run([Wait(duration=1.0)] * 12)
    assert survey.objective_score == idle.objective_score
    world, task = DRAFTERS["intervene"](Seed(9), _EXP09)
    assert task.setup["oracle"]["intervene"]["scored_at_s"] == pytest.approx(12.0)
    assert task.setup["score_horizon_turns"] == 12


def test_a_decisive_act_now_beats_doing_nothing_where_it_moves_toward_the_goal():
    # seed 9: the passive reach is 3 % short of the goal; a modest rate lift
    # on the decisive lever closes it. Scored at the commit turn it read ~0.01.
    survey = _run([_COMMIT])
    act = _run([Intervene(lever="m0_m1", value=1.2), _COMMIT])
    assert act.objective_score > survey.objective_score


def test_the_runout_rides_the_record_store_and_is_absent_otherwise():
    early = _run([Intervene(lever="m0_m1", value=2.0), _COMMIT])
    line = record_to_json(early, label="x", index=0)
    assert set(line["runout"]) == {"from_turn", "to_turn", "scored_at_s", "final_state"}
    assert record_from_json(line).runout == line["runout"]
    full = _run([Wait(duration=1.0)] * 12)
    assert "runout" not in record_to_json(full, label="x", index=0)


def test_an_outcome_task_without_a_declared_horizon_is_scored_at_the_episode_end():
    world, task = DRAFTERS["intervene"](Seed(9), _EXP09)
    setup = {k: v for k, v in task.setup.items() if k != "score_horizon_turns"}
    import dataclasses

    bare = dataclasses.replace(task, setup=setup)
    rec = run(world, bare, ScriptedAgent((_COMMIT,), Seed(0)), _EXP09, Seed(9))
    assert rec.runout is None and rec.turns == 1


# A3 — the held-mass bound only without a molecule setpoint lever ------------


def test_exp09s_task_at_twenty_turns_drafts_on_the_default_surface():
    DRAFTERS["intervene"](Seed(9), {**_EXP09, "max_turns": 20})


def test_the_held_mass_bound_still_refuses_on_a_reaction_only_surface():
    with pytest.raises(ValueError, match="no molecule setpoint lever"):
        DRAFTERS["intervene"](Seed(9), {**_EXP09, "max_turns": 20, "levers": ["m0_m1", "m1_m2"]})
    # A declared molecule lever adds mass: no bound.
    DRAFTERS["intervene"](Seed(9), {**_EXP09, "max_turns": 20, "levers": ["m0_m1", {"id": "m0", "max_rate": 50}]})


# A4 — intervene_horizon pins the derivation horizon -------------------------


def test_intervene_horizon_fixes_the_goal_across_a_budget_ladder():
    goals = set()
    for turns in (4, 8, 12):
        _world, task = DRAFTERS["intervene"](Seed(9), {**_EXP09, "max_turns": turns, "intervene_horizon": 12})
        oracle = task.setup["oracle"]["intervene"]
        assert oracle["intervene_horizon"] == 12 and oracle["scored_at_s"] == pytest.approx(12.0)
        assert oracle["episode_horizon_s"] == pytest.approx(turns)
        goals.add(oracle["goal"])
    assert len(goals) == 1
    _world, unpinned = DRAFTERS["intervene"](Seed(9), _EXP09)
    assert unpinned.setup["oracle"]["intervene"]["goal"] in goals
    assert "intervene_horizon" not in unpinned.setup["oracle"]["intervene"]


def test_an_intervene_horizon_shorter_than_the_episode_refuses():
    with pytest.raises(ValueError, match="intervene_horizon 8 is shorter"):
        DRAFTERS["intervene"](Seed(9), {**_EXP09, "intervene_horizon": 8})


def test_preflight_refuses_an_unpinned_max_turns_ladder_on_intervene():
    from alienbio.suite.guards import intervene_horizon_violation, preflight
    from alienbio.suite.spec import ExperimentSpec

    base = dict(
        name="ladder", drafter="intervene", agent="survey-commit",
        axes=(("max_turns", (4, 8, 12)),), fixed_dials={"sim_steps": 10},
        trials_per_condition=1, base_seed=9,
    )
    spec = ExperimentSpec(**base, drafter_kwargs={"n_nodes": 5, "target_margin": 0.03})
    problem = intervene_horizon_violation(spec)
    assert problem is not None and "intervene_horizon" in problem
    assert problem in dict(preflight(spec).checks)["intervene-horizon"]
    pinned = ExperimentSpec(**base, drafter_kwargs={"n_nodes": 5, "target_margin": 0.03, "intervene_horizon": 12})
    assert intervene_horizon_violation(pinned) is None
