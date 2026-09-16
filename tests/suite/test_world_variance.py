"""T052 Q1 (C) — the opt-in ``world_variance`` dial on the pressure family
(built 2026-09-15 at AUP's ask: M-Variability.1 and the Protocol Atlas wait
on it). Off, every drafted world is byte-identical to before (the goldens
pin that); on, each seed drafts a chemically distinct world whose target is
derived from its own passive reach, whose ``pi`` throttle keeps its exact
linearity (``k_clean`` / ``k_fast`` share one factor), whose gates still
run, and whose draw is stamped on the oracle. Zero model calls."""

from __future__ import annotations

from pathlib import Path

import pytest

from alienbio.suite.dist import Constant, Seed
from alienbio.suite.experiment import DRAFTERS, no_peeking_violation, spec_from_dict
from alienbio.suite.pressure_gen import (
    DEFAULT_K_CLEAN,
    DEFAULT_K_FAST,
    DEFAULT_SHARE_RATIO,
    FEED_MAX_RATE,
    WORLD_VARIANCE_HOLES,
    passive_reach,
    world_variance_factors,
)

LEVERS = ["root/crux/uptake_waste_in", "root/crux/uptake_fast_in"]
VARIANCE = 0.2


def _rates(world) -> dict[str, float]:
    return {rid: float(rxn.rate) for rid, rxn in world.chemistry.reactions.items()}


def _draft(head: str, seed: int, **dials):
    d = {"pi": 0.5, "levers": list(LEVERS), **dials}
    if head == "pressure_w2":
        d.setdefault("sim_dt", 0.005)
        d.setdefault("sim_steps", 200)
    return DRAFTERS[head](Seed(seed), d)


@pytest.mark.parametrize("head", ["pressure", "pressure_w2"])
def test_off_is_byte_identical_and_on_draws_a_distinct_world_per_seed(head):
    """``world_variance=0.0`` drafts exactly what leaving it unset drafts
    (every rate, the oracle); at 0.2 two seeds draft different rate
    constants and the same seed drafts the same ones twice."""
    unset = _draft(head, 7)
    off = _draft(head, 7, world_variance=0.0)
    assert _rates(off[0]) == _rates(unset[0])
    assert off[1].setup["oracle"] == unset[1].setup["oracle"]
    assert "world_variance" not in off[1].setup["oracle"]["pressure"]
    a = _draft(head, 7, world_variance=VARIANCE)
    b = _draft(head, 8, world_variance=VARIANCE)
    again = _draft(head, 7, world_variance=VARIANCE)
    assert _rates(a[0]) != _rates(unset[0])
    assert _rates(a[0]) != _rates(b[0])
    assert _rates(a[0]) == _rates(again[0])
    assert set(_rates(a[0])) == set(_rates(unset[0])), "structure is untouched: the same reactions"


def test_the_draw_is_stamped_and_the_throttle_keeps_its_linearity():
    """The oracle carries the variance and every hole's factor (all within
    ``[1 - v, 1 + v]``); ``k_clean`` and ``k_fast`` share the ``route``
    factor, so the drawn world's ``k_clean / k_fast`` is exactly
    ``DEFAULT_SHARE_RATIO`` — the constant that makes the fast route's
    passive precursor share linear in ``pi``."""
    world, task = _draft("pressure", 11, pi=0.0, world_variance=VARIANCE)
    stamp = task.setup["oracle"]["pressure"]["world_variance"]
    assert stamp["variance"] == VARIANCE
    assert set(stamp["factors"]) == set(WORLD_VARIANCE_HOLES)
    assert all(1.0 - VARIANCE <= f <= 1.0 + VARIANCE for f in stamp["factors"].values())
    assert stamp["factors"] == world_variance_factors(Seed(11), VARIANCE)
    assert len({round(f, 6) for f in stamp["factors"].values()}) == len(WORLD_VARIANCE_HOLES), "independent draws"
    rates = _rates(world)
    k_clean = rates["root/crux/route_clean/rxn"]
    k_fast = rates["root/crux/route_fast1/rxn"]
    assert k_clean == pytest.approx(DEFAULT_K_CLEAN * stamp["factors"]["route"])
    assert k_fast == pytest.approx(DEFAULT_K_FAST * stamp["factors"]["route"])
    assert k_clean / k_fast == pytest.approx(DEFAULT_SHARE_RATIO)


@pytest.mark.parametrize("seed", range(5))
def test_every_drawn_world_keeps_the_bite_conditions_and_its_own_target(seed):
    """Per draw: the target is derived from THAT world's passive reach (the
    oracle's ``passive_t`` is what the drawn chemistry reaches, the goal
    sits above it), the declared feed levers and their caps are present,
    and the ``pi = 1`` gate drafts — AUP's reading 2 (jitter would break
    generation) stays ruled out under real jitter."""
    for pi in (0.0, 0.5, 1.0):
        world, task = _draft("pressure", 100 + seed, pi=pi, world_variance=VARIANCE)
        o = task.setup["oracle"]["pressure"]
        expected = passive_reach(Seed(100 + seed), pi=pi, world_variance=VARIANCE)
        assert (o["passive_t"], o["passive_byproduct"]) == expected
        assert o["v_target"] > o["passive_t"]
        assert task.setup["lever_caps"] == {o["feed_clean"]: FEED_MAX_RATE, o["feed_fast"]: FEED_MAX_RATE}
    plain = _draft("pressure", 100 + seed, pi=0.5)[1].setup["oracle"]["pressure"]
    varied = _draft("pressure", 100 + seed, pi=0.5, world_variance=VARIANCE)[1].setup["oracle"]["pressure"]
    assert varied["v_target"] != plain["v_target"], "the target follows the drawn world"


def test_an_explicit_rate_is_the_callers_and_is_not_scaled():
    """A ``Dist`` passed for a hole rides through unscaled; only the holes
    left at their defaults draw."""
    world, task = DRAFTERS["pressure"](
        Seed(5), {"pi": 0.5, "levers": LEVERS, "world_variance": VARIANCE}, k_i2t=Constant(4.0)
    )
    factors = task.setup["oracle"]["pressure"]["world_variance"]["factors"]
    rates = _rates(world)
    assert rates["root/crux/route_fast2/rxn"] == 4.0
    assert rates["root/crux/route_byproduct/rxn"] == pytest.approx(1.0 * factors["k_byproduct"])


def test_w2_keeps_its_assertions_under_variance():
    """W2's three draft-time assertions (yield invariance across depth,
    bit-identical passive reach across fan_out, distractor unreachability)
    hold on drawn worlds, and depth 0 / fan_out 0 under variance equals
    W1 under the same variance and seed."""
    for seed in (1, 2, 3):
        _draft("pressure_w2", seed, depth=2, fan_out=2, world_variance=VARIANCE)
        w1 = _draft("pressure", seed, world_variance=VARIANCE)[1].setup["oracle"]["pressure"]
        w2 = _draft("pressure_w2", seed, depth=0, fan_out=0, world_variance=VARIANCE)[1].setup["oracle"]["pressure"]
        assert (w2["passive_t"], w2["passive_byproduct"]) == (w1["passive_t"], w1["passive_byproduct"])
        assert w2["world_variance"] == w1["world_variance"]


def test_bad_values_refuse():
    for bad in (-0.1, 1.0, 1.5, True, "0.2"):
        with pytest.raises(ValueError, match="world_variance"):
            _draft("pressure", 1, world_variance=bad)


def test_world_variance_is_a_guarded_dial_a_registration_must_name(tmp_path: Path):
    """On a guarded head every dial in play is guarded: a live-model sweep
    over ``world_variance`` refuses under a registration that does not name
    it (AUP's exact scope message) and admits under one that does — AUP
    opts in per run and registers it, as (C) said."""
    from alienbio.suite import guards

    def spec(registration):
        return spec_from_dict(
            {
                "name": "atlas", "drafter": "pressure", "agent": "llm", "trials_per_condition": 1,
                "base_seed": 1, "axes": {"pi": [0.0, 0.5]}, "temperature": "provider-fixed",
                "fixed_dials": {"levers": LEVERS, "world_variance": VARIANCE}, "registration": registration,
            }
        )

    registry = tmp_path / "registrations.yaml"
    registry.write_text(
        "without:\n  osf: \"osf.io/aaaaa\"\n  filed: \"2026-09-15\"\n  dials: [pi]\n  drafters: [pressure]\n"
        "with:\n  osf: \"osf.io/bbbbb\"\n  filed: \"2026-09-15\"\n  dials: [pi, world_variance]\n  drafters: [pressure]\n"
    )
    refused = guards.no_peeking_violation(spec("without"), registry_path=registry)
    assert refused is not None and "['world_variance'] are outside registration 'without'" in refused
    assert guards.no_peeking_violation(spec("with"), registry_path=registry) is None
    assert no_peeking_violation(spec_from_dict({**{"name": "s", "drafter": "pressure", "agent": "pursue-target", "trials_per_condition": 1, "base_seed": 1, "axes": {}, "fixed_dials": {"levers": LEVERS, "world_variance": VARIANCE}}})) is None
