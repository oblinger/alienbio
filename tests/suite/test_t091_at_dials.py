"""T091 AT1 — the dials that held ``bio suite run --dry`` past the clock: the
drafter heads' size dials, the horizon a drafter simulates to derive its
goal, ``bury_commitment``'s filler and the condition count, each capped
where it is read and refused by name before any work."""

from __future__ import annotations

import time

import pytest

from alienbio.suite import brief as brief_mod
from alienbio.suite import drafters as dr
from alienbio.suite.brief import MAX_BURY_COMMITMENT, neutral_padding
from alienbio.suite.dist import Seed
from alienbio.suite.experiment import DRAFTERS, spec_from_dict
from alienbio.suite.guards import preflight
from alienbio.suite.spec import MAX_CONDITIONS

SEED = Seed(3)

#: (drafter, the dial, the other dials it needs, the largest value in use).
SIZE_DIALS = [
    ("diagnose", "n_nodes", {}, 6),
    ("diagnose", "distractor_count", {}, 6),
    ("predict", "n_nodes", {}, 6),
    ("intervene", "n_nodes", {}, 6),
    ("identify_pathway", "pathway_length", {}, 5),
    ("identify_pathway", "distractor_count", {}, 6),
    ("discover", "pathway_length", {}, 5),
    ("discover", "distractor_count", {}, 6),
    ("pressure", "complexity", {"pi": 0.5}, 6),
    ("commit_the_link", "complexity", {"pi": 0.5}, 6),
    ("describe_the_world", "complexity", {"pi": 0.5}, 6),
    ("pressure_w2", "depth", {"pi": 0.5}, 4),
    ("pressure_w2", "fan_out", {"pi": 0.5}, 3),
    ("pressure_w2", "distractor_depth", {"pi": 0.5}, 3),
]


@pytest.mark.parametrize("drafter,dial,base,in_use", SIZE_DIALS)
def test_a_size_dial_past_its_cap_refuses_by_name_before_any_work(drafter, dial, base, in_use):
    """Each size dial one past its cap refuses at once, naming the head, the dial, the value and the cap."""
    cap = dr.SIZE_DIAL_CAPS[dial]
    assert cap >= 4 * in_use
    t = time.process_time()
    with pytest.raises(ValueError, match=rf"{drafter}: dial {dial}={cap + 1} exceeds its cap {cap}"):
        DRAFTERS[drafter](SEED, {**base, dial: cap + 1})
    assert time.process_time() - t < 0.5


@pytest.mark.parametrize(
    "drafter,dials,generator",
    [
        ("diagnose", {"n_nodes": dr.MAX_N_NODES, "distractor_count": dr.MAX_DISTRACTOR_COUNT}, {}),
        ("intervene", {"n_nodes": dr.MAX_N_NODES}, {}),
        ("identify_pathway", {"pathway_length": dr.MAX_PATHWAY_LENGTH, "distractor_count": dr.MAX_DISTRACTOR_COUNT}, {}),
        ("pressure", {"pi": 0.5, "complexity": dr.MAX_COMPLEXITY}, {}),
        (
            "pressure_w2",
            {"pi": 0.5, "depth": dr.MAX_W2_DEPTH, "fan_out": dr.MAX_W2_FAN_OUT, "distractor_depth": dr.MAX_W2_DISTRACTOR_DEPTH},
            {"hop_delay_s": 1.0},
        ),
    ],
)
def test_a_draft_at_the_caps_stays_cheap(drafter, dials, generator):
    """A world drafted with every size dial at its cap costs well under 2 s of CPU."""
    t = time.process_time()
    DRAFTERS[drafter](SEED, dials, **generator)
    assert time.process_time() - t < 2.0


def test_the_derivation_horizon_is_capped_on_phase1():
    """phase1_pressure derives v_target over the episode's horizon; one turn past MAX_DRAFT_SIM_STEPS refuses by name."""
    # 1000 turns x 10 steps x 0.1 s over the generator's 0.05 s step = 20 000 steps.
    DRAFTERS["phase1_pressure"](SEED, {"variant": "coupling_told", "max_turns": 1000})
    with pytest.raises(ValueError, match="MAX_DRAFT_SIM_STEPS=20000"):
        DRAFTERS["phase1_pressure"](SEED, {"variant": "coupling_told", "max_turns": 1001})
    with pytest.raises(ValueError, match="MAX_DRAFT_SIM_STEPS"):
        DRAFTERS["phase1_pressure"](SEED, {"variant": "coupling_told", "sim_dt": 100000.0})


@pytest.mark.parametrize(
    "drafter,dials",
    [
        ("intervene", {"max_turns": 1_000_000}),
        ("intervene", {"intervene_horizon": 1_000_000}),
        ("diagnose", {"hazard": True, "hazard_horizon": 10_000_000}),
        ("phase1_pressure", {"variant": "coupling_withheld", "max_turns": 8, "sim_steps": 10**9}),
    ],
)
def test_a_long_horizon_refuses_before_simulating(drafter, dials):
    """A horizon dial that would make the draft simulate millions of steps refuses at once, naming the cap."""
    t = time.process_time()
    with pytest.raises(ValueError, match="MAX_DRAFT_SIM_STEPS"):
        DRAFTERS[drafter](SEED, dials)
    assert time.process_time() - t < 0.5


def test_the_horizons_in_use_still_draft():
    """The longest horizons the catalog and AUP use draft unchanged under the cap."""
    DRAFTERS["phase1_pressure"](SEED, {"variant": "coupling_told", "max_turns": 40, "sim_steps": 10})
    DRAFTERS["intervene"](SEED, {"max_turns": 12, "intervene_horizon": 12})
    DRAFTERS["diagnose"](SEED, {"n_nodes": 6, "hazard": True, "hazard_threshold": 3.0, "hazard_horizon": 12})


def _old_padding(n_tokens: int, seed: Seed) -> str:
    """The pre-AT1 (quadratic) padding loop, verbatim but for the names."""
    rng = seed.rng()
    sentences: list[str] = []
    text = ""
    while len(text) // 4 < n_tokens:
        subject = brief_mod._PADDING_SUBJECTS[int(rng.integers(len(brief_mod._PADDING_SUBJECTS)))]
        verb = brief_mod._PADDING_VERBS[int(rng.integers(len(brief_mod._PADDING_VERBS)))]
        obj = brief_mod._PADDING_OBJECTS[int(rng.integers(len(brief_mod._PADDING_OBJECTS)))]
        tail = brief_mod._PADDING_TAILS[int(rng.integers(len(brief_mod._PADDING_TAILS)))]
        sentences.append(f"{subject.capitalize()} {verb} {obj} {tail}.")
        text = " ".join(sentences)
    return text


@pytest.mark.parametrize("n", [1, 7, 100, 400, 4000])
def test_the_linear_padding_is_byte_identical_to_the_old_loop(n):
    """Keeping the joined length as the loop runs writes exactly the text the quadratic loop wrote."""
    assert neutral_padding(n, Seed(11)) == _old_padding(n, Seed(11))


def test_bury_commitment_past_its_cap_refuses_and_the_cap_is_cheap():
    """A burial past MAX_BURY_COMMITMENT refuses by name; one at the cap is built in well under a second."""
    assert MAX_BURY_COMMITMENT >= 4 * 20_000
    with pytest.raises(ValueError, match="MAX_BURY_COMMITMENT"):
        neutral_padding(MAX_BURY_COMMITMENT + 1, Seed(1))
    t = time.process_time()
    text = neutral_padding(MAX_BURY_COMMITMENT, Seed(1))
    assert time.process_time() - t < 1.0
    assert len(text) // 4 >= MAX_BURY_COMMITMENT


def _spec(axes, drafter="pressure", fixed=None):
    return spec_from_dict(
        {
            "name": "at1",
            "axes": axes,
            "drafter": drafter,
            "agent": "survey-commit",
            "trials_per_condition": 1,
            "base_seed": 3,
            "fixed_dials": fixed or {"levers": []},
        }
    )


def test_a_grid_past_max_conditions_refuses_at_construction():
    """More than MAX_CONDITIONS conditions refuses before any level is compared or drafted."""
    assert MAX_CONDITIONS >= 4 * 27  # AUP's largest grid: phase 2's cube
    _spec({"pi": [i / 128 for i in range(MAX_CONDITIONS)]})
    t = time.process_time()
    with pytest.raises(ValueError, match="MAX_CONDITIONS"):
        _spec({"pi": [i / 1000 for i in range(100_000)]})
    with pytest.raises(ValueError, match="MAX_CONDITIONS"):
        _spec({"pi": [0.0, 0.5], "complexity": list(range(65))})
    assert time.process_time() - t < 0.5


def test_the_verifier_repro_refuses_in_preflight(tmp_path):
    """AT's C2 repro (diagnose n_nodes=20000) is a draft refusal naming the dial, not a 21 s preflight: ok."""
    spec = _spec({"n_nodes": [20000]}, drafter="diagnose", fixed={"distractor_count": 4, "max_turns": 4, "sim_steps": 5})
    t = time.process_time()
    result = preflight(spec, out_dir=str(tmp_path / "out"))
    assert time.process_time() - t < 2.0
    verdicts = dict(result.checks)
    assert "n_nodes=20000 exceeds its cap 64" in (verdicts["draft"] or "")
