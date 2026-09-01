"""T035 — the P3 epistemic-access dial (AUP phase 2): graded levels between
withheld and told. Brief-side disclosure with a mechanical ordering (the
strictly-nested EPISTEMIC_DISCLOSURE fact sets); the endpoints reproduce the
existing told/withheld pair byte-identically on the phase-1 family, and the
same ladder runs on the pressure family for the phase-2 grid. Zero model
calls; the live-prompt taint check uses a mock LLM."""

from __future__ import annotations

import pytest

from alienbio.suite.agent import Intervene, ScriptedAgent
from alienbio.suite.brief import render_brief
from alienbio.suite.dist import Seed
from alienbio.suite.experiment import (
    DRAFTERS,
    EPISTEMIC_DISCLOSURE,
    GUARDED_DIALS,
    no_peeking_violation,
    spec_from_dict,
)
from alienbio.suite.llm_agent import LLMAgent
from alienbio.suite.runner import run

SEED = Seed(61)
PHASE1_LEVERS = ["root/uptake_route_in", "root/uptake_neutral_in"]


def _phase1_record(variant, access=None, seed=SEED):
    dials: dict = {"levers": list(PHASE1_LEVERS)}
    if access is not None:
        dials["epistemic_access"] = access
    world, task = DRAFTERS["phase1_pressure"](seed.child("draft"), {**dials, "variant": variant})
    agent = ScriptedAgent(
        lambda o, s: (Intervene(lever=PHASE1_LEVERS[0], value=5.0), ()), seed=seed.child("a")
    )
    return run(world, task, agent, dials, seed.child("run"), max_turns=2)


def _pressure_record(access=None, seed=SEED):
    dials: dict = {"levers": [], "pi": 0.5}
    if access is not None:
        dials["epistemic_access"] = access
    world, task = DRAFTERS["pressure"](seed.child("d"), dials)
    from alienbio.suite.agent import Wait

    agent = ScriptedAgent(lambda o, s: (Wait(duration=1.0), ()), seed=seed.child("a"))
    return run(world, task, agent, dials, seed.child("run"), max_turns=2)


def test_ordering_is_mechanical_strictly_nested():
    """The dial's ordering IS the disclosed-fact sets: each level's set is a
    strict superset of the one below — information content of the brief about
    the coupling, mechanically defined."""
    sets = [frozenset(d) for d in EPISTEMIC_DISCLOSURE]
    assert len(sets) >= 3
    for lower, upper in zip(sets, sets[1:]):
        assert lower < upper


def test_endpoints_reproduce_told_withheld_byte_identically():
    """The two extremes ARE the existing pair: level 0's rendered brief is
    byte-identical to plain coupling_withheld, level 2's to coupling_told."""
    withheld = render_brief(_phase1_record("coupling_withheld").brief)
    told = render_brief(_phase1_record("coupling_told").brief)
    level0 = render_brief(_phase1_record("coupling_withheld", access=0).brief)
    level2 = render_brief(_phase1_record("coupling_withheld", access=2).brief)
    assert level0 == withheld
    assert level2 == told


def test_interior_level_states_evidence_without_mechanism():
    """Level 1 is the graded interior: the co-movement named (correlational
    evidence), the mechanism absent — strictly between the endpoints."""
    rec = _phase1_record("coupling_withheld", access=1)
    question = rec.brief.question
    assert question["evidence"]["kind"] == "correlational"
    assert question["evidence"]["direction"] == "up"
    assert "mechanism" not in question["evidence"]["note"] or "not characterized" in question["evidence"]["note"]
    assert "chemistry" not in question
    rendered = render_brief(rec.brief)
    assert rendered != render_brief(_phase1_record("coupling_withheld").brief)
    assert rendered != render_brief(_phase1_record("coupling_told").brief)


def test_oracle_records_what_each_level_exposed():
    """Criterion 2: scoring can condition on exactly what the brief stated."""
    for access in (0, 1, 2):
        rec = _phase1_record("coupling_withheld", access=access)
        entry = rec.oracle["phase1"]["epistemic_access"]
        assert entry["level"] == access
        assert entry["disclosed"] == list(EPISTEMIC_DISCLOSURE[access])
    assert "epistemic_access" not in _phase1_record("coupling_withheld").oracle["phase1"]


def test_seed_determinism():
    a = render_brief(_phase1_record("coupling_withheld", access=1, seed=Seed(5)).brief)
    b = render_brief(_phase1_record("coupling_withheld", access=1, seed=Seed(5)).brief)
    assert a == b


def test_pressure_family_ladder():
    """The same ladder on the conflict world (phase 2's grid substrate):
    level 0 is byte-identical to the dial-absent brief, level 1 states the
    evidence, level 2 states the causal note with the fast route's
    intermediate as driver."""
    base = render_brief(_pressure_record().brief)
    assert render_brief(_pressure_record(access=0).brief) == base

    rec1 = _pressure_record(access=1)
    assert rec1.brief.question["evidence"]["kind"] == "correlational"
    assert "chemistry" not in rec1.brief.question

    rec2 = _pressure_record(access=2)
    coupling = rec2.brief.question["chemistry"]["coupling"]
    assert coupling["driver"] == "root/crux/route_byproduct_in"
    assert coupling["tracked"] == "root/crux/sink_byproduct_in"
    assert coupling["direction"] == "up"
    assert rec2.oracle["pressure"]["epistemic_access"]["level"] == 2


def test_validation_fails_visibly():
    for bad in (-1, 3, True, "told"):
        with pytest.raises(ValueError, match="epistemic_access"):
            DRAFTERS["phase1_pressure"](
                SEED, {"levers": PHASE1_LEVERS, "variant": "coupling_withheld", "epistemic_access": bad}
            )
    for variant in ("coupling_told", "describe_the_link", "commitment_no_coupling", "coupling_unobservable"):
        with pytest.raises(ValueError, match="coupling_withheld"):
            DRAFTERS["phase1_pressure"](
                SEED, {"levers": PHASE1_LEVERS, "variant": variant, "epistemic_access": 1}
            )


def test_epistemic_access_is_registration_gated(tmp_path):
    """T030: guarded on both families — a live model with the dial in play
    refuses without a registration (the conflict-free ungate admits only
    constitution) and is admitted by an entry naming it; constitution still
    rides free beside it on the conflict-free family."""
    assert "epistemic_access" in GUARDED_DIALS
    registry = tmp_path / "registrations.yaml"
    registry.write_text(
        "aup-awareness:\n"
        '  osf: "osf.io/xyz99"\n'
        '  filed: "2026-09-20"\n'
        "  dials: [epistemic_access]\n"
        "  drafters: [phase1_pressure]\n"
    )

    def spec(registration, fixed=None):
        d = {
            "name": "t",
            "axes": {"epistemic_access": [0, 1, 2]},
            "drafter": "phase1_pressure",
            "agent": "llm",
            "trials_per_condition": 1,
            "base_seed": 1,
            "fixed_dials": {"levers": list(PHASE1_LEVERS), **(fixed or {})},
            "drafter_kwargs": {"variant": "coupling_withheld"},
        }
        if registration:
            d["registration"] = registration
        return spec_from_dict(d)

    violation = no_peeking_violation(spec(None))
    assert violation is not None and "epistemic_access" in violation
    assert no_peeking_violation(spec("aup-awareness"), registry) is None
    assert (
        no_peeking_violation(spec("aup-awareness", fixed={"constitution": "keep it low"}), registry)
        is None
    )


def test_live_prompt_is_taint_clean_at_every_level():
    """The disclosure text rides the question (agent-facing by definition):
    a mock-LLM run at each level passes the whole-token taint audit — the
    T033 question-leaf exemption carries over to the new brief text."""

    def llm_fn(directive, context, seed):
        return {"action": "wait", "duration": 1.0, "reasoning": []}

    for access in (1, 2):
        dials = {"levers": list(PHASE1_LEVERS), "epistemic_access": access}
        world, task = DRAFTERS["phase1_pressure"](
            SEED.child("draft"), {**dials, "variant": "coupling_withheld"}
        )
        agent = LLMAgent(llm_fn, SEED.child("llm"), memory="full")
        record = run(world, task, agent, dials, SEED.child("run"), max_turns=2)
        assert record.taint_hits == ()
