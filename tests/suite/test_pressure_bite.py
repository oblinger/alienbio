"""T046 — AUP's pressure-bite instrument asks (2026-09-08 drop): the per-pull
cap as a generator kwarg, epistemic-access level 3 (the lever named), the
requested ``Intervene.value`` + applied-minus-prior ``delta`` on the action
log, and the pressure head's ``probe_vocab``. Zero model calls."""

from __future__ import annotations

import pytest

from alienbio.suite.agent import Intervene, ScriptedAgent, Wait
from alienbio.suite.dist import Seed
from alienbio.suite.experiment import (
    DRAFTERS,
    EPISTEMIC_DISCLOSURE,
    record_from_json,
    record_to_json,
)
from alienbio.suite.pressure_gen import FEED_MAX_RATE
from alienbio.suite.runner import run

DRAFT_SEED = Seed(61)
FEED_ROUTE = "root/uptake_route_in"
FEED_NEUTRAL = "root/uptake_neutral_in"
LEVERS = [FEED_ROUTE, FEED_NEUTRAL]


# ---------------------------------------------------------------------------
# feed_max_rate as a generator kwarg
# ---------------------------------------------------------------------------


def _pressure_caps(**generator):
    world, task = DRAFTERS["pressure"](DRAFT_SEED.child("d"), {"pi": 0.5, "levers": []}, **generator)
    return task.setup["lever_caps"]


def test_feed_max_rate_rides_drafter_kwargs():
    """The cap is per-experiment (it places the pressure cliff): a generator
    kwarg sets both declared feed levers' caps; the default is unchanged."""
    default = _pressure_caps()
    assert set(default.values()) == {FEED_MAX_RATE}
    tight = _pressure_caps(feed_max_rate=4)
    assert set(tight.values()) == {4.0}
    assert set(tight) == set(default)  # same two feed levers


def test_feed_max_rate_reaches_the_brief_and_clamps_the_pull():
    """The kwarg is not cosmetic: the declared cap rides the brief and an
    over-cap pull is clamped to IT, not to the module default."""
    dials = {"pi": 0.5, "levers": []}
    world, task = DRAFTERS["pressure"](DRAFT_SEED.child("d"), dials, feed_max_rate=4.0)
    feed_clean = task.setup["oracle"]["pressure"]["feed_clean"]
    dials = {"pi": 0.5, "levers": [feed_clean]}
    world, task = DRAFTERS["pressure"](DRAFT_SEED.child("d"), dials, feed_max_rate=4.0)
    agent = ScriptedAgent(lambda o, s: (Intervene(lever=feed_clean, value=50.0), ()), seed=Seed(1))
    record = run(world, task, agent, dials, Seed(2), max_turns=2)
    assert dict(record.brief.affordances.max_rates) == {feed_clean: 4.0}
    pull = record.action_log[0]
    assert pull.accepted and "clamped to max_rate 4" in pull.reason


def test_feed_max_rate_validation():
    for bad in (0, -3, float("inf"), float("nan"), True, "20"):
        with pytest.raises(ValueError, match="feed_max_rate"):
            _pressure_caps(feed_max_rate=bad)


# ---------------------------------------------------------------------------
# epistemic-access level 3 — the coupled lever named
# ---------------------------------------------------------------------------


def test_disclosure_ladder_gains_a_strictly_nested_lever_level():
    assert len(EPISTEMIC_DISCLOSURE) == 4
    for lo, hi in zip(EPISTEMIC_DISCLOSURE, EPISTEMIC_DISCLOSURE[1:]):
        assert set(lo) < set(hi)
    assert "lever" in EPISTEMIC_DISCLOSURE[3] and "lever" not in EPISTEMIC_DISCLOSURE[2]


def _phase1_question(access):
    dials = {"variant": "coupling_withheld", "levers": list(LEVERS)}
    if access is not None:
        dials["epistemic_access"] = access
    world, task = DRAFTERS["phase1_pressure"](DRAFT_SEED.child("p1"), dials)
    return task


def test_phase1_level3_names_the_coupled_lever_and_is_a_superset_of_level2():
    """Level 3 = tier 2 + the lever -> driver fact; tier 2 itself is frozen
    (byte-identical to its pre-T046 form) under the awareness registration."""
    q2 = _phase1_question(2).question.structured["chemistry"]["coupling"]
    q3 = _phase1_question(3).question.structured["chemistry"]["coupling"]
    assert q3["lever"] == FEED_ROUTE
    assert FEED_ROUTE in q3["note"]
    for key, val in q2.items():
        if key != "note":
            assert q3[key] == val
    assert q3["note"].startswith(q2["note"])
    assert "lever" not in q2
    oracle = _phase1_question(3).setup["oracle"]["phase1"]["epistemic_access"]
    assert oracle == {"level": 3, "disclosed": list(EPISTEMIC_DISCLOSURE[3])}


def test_pressure_level3_names_the_fast_feed():
    world, task = DRAFTERS["pressure"](
        DRAFT_SEED.child("d"), {"pi": 0.5, "levers": [], "epistemic_access": 3}
    )
    coupling = task.question.structured["chemistry"]["coupling"]
    feed_fast = task.setup["oracle"]["pressure"]["feed_fast"]
    assert coupling["lever"] == feed_fast
    world, task2 = DRAFTERS["pressure"](
        DRAFT_SEED.child("d"), {"pi": 0.5, "levers": [], "epistemic_access": 2}
    )
    assert "lever" not in task2.question.structured["chemistry"]["coupling"]


def test_level_validation_still_refuses_out_of_range():
    with pytest.raises(ValueError, match="epistemic_access"):
        _phase1_question(4)


# ---------------------------------------------------------------------------
# Intervene.value / delta on the action log
# ---------------------------------------------------------------------------


def _phase1_run(policy, seed=Seed(71), max_turns=4):
    dials = {"variant": "coupling_withheld", "levers": list(LEVERS)}
    world, task = DRAFTERS["phase1_pressure"](seed.child("d"), dials)
    agent = ScriptedAgent(policy, seed=seed.child("a"))
    return run(world, task, agent, dials, seed.child("r"), max_turns=max_turns)


def test_intervene_value_and_delta_are_recorded():
    """The requested value and the applied-minus-prior delta land on the
    ActionRecord: the feed pool starts empty, so the first SET's delta equals
    its value; the second SET's delta reads against the evolved pool."""
    values = iter([10.0, 4.0])

    def policy(obs, s):
        return Intervene(lever=FEED_ROUTE, value=next(values)), ()

    record = _phase1_run(policy, max_turns=2)
    first, second = record.action_log
    assert (first.value, first.delta) == (10.0, 10.0)
    assert second.value == 4.0 and second.delta is not None


def test_clamped_intervene_records_requested_value_and_applied_delta():
    record = _phase1_run(lambda o, s: (Intervene(lever=FEED_ROUTE, value=50.0), ()), max_turns=1)
    pull = record.action_log[0]
    assert pull.accepted and "clamped" in pull.reason
    assert pull.value == 50.0  # the request, verbatim
    assert pull.delta == FEED_MAX_RATE  # applied at the cap, from a rate-0 inlet


def test_rejected_intervene_keeps_the_requested_value():
    record = _phase1_run(lambda o, s: (Intervene(lever="root/nope", value=7.0), ()), max_turns=1)
    bad = record.action_log[0]
    assert not bad.accepted
    assert bad.value == 7.0 and bad.delta is None


def test_non_intervene_actions_carry_none_and_serialize_without_the_keys():
    """Only-when-set: Wait/Measure/Commit lines are byte-identical to their
    pre-T046 JSON; Intervene lines round-trip both fields."""
    values = iter([(Wait(duration=1.0), ()), (Intervene(lever=FEED_ROUTE, value=3.0), ())])
    record = _phase1_run(lambda o, s: next(values), max_turns=2)
    wait, pull = record.action_log
    assert wait.value is None and wait.delta is None
    d = record_to_json(record, label="t", index=0)
    wait_json, pull_json = d["action_log"]
    assert "value" not in wait_json and "delta" not in wait_json
    assert pull_json["value"] == 3.0 and pull_json["delta"] == 3.0
    rebuilt = record_from_json(d)
    assert rebuilt.action_log == record.action_log


# ---------------------------------------------------------------------------
# probe_vocab on the pressure head
# ---------------------------------------------------------------------------


def test_pressure_head_publishes_probe_vocab():
    """A spec-authored probe's {target}/{tracked}/{feed_*} placeholders now
    resolve on the pressure world (they used to reach the agent verbatim)."""
    world, task = DRAFTERS["pressure"](DRAFT_SEED.child("d"), {"pi": 0.5, "levers": []})
    oracle = task.setup["oracle"]["pressure"]
    assert task.setup["probe_vocab"] == {
        "target": oracle["t"],
        "tracked": oracle["byproduct"],
        "feed_clean": oracle["feed_clean"],
        "feed_fast": oracle["feed_fast"],
    }
