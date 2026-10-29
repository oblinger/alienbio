"""M48.9 example 3 — the microcosm example is runnable: populations as counts
on one resource, coupled growth / death / maturation, an intervene task on
the carrying capacity, an experiment over the feed rate."""

from __future__ import annotations

from pathlib import Path

import pytest

from alienbio.bio.world import WorldImpl
from alienbio.expr import Env
from alienbio.suite.experiment import load_spec, run_experiment
from alienbio.suite.types import OutcomeObjective
from alienbio.suite.verify import SimConfig, simulate

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "catalog" / "examples" / "microcosm" / "microcosm.yaml"


@pytest.fixture(scope="module")
def values():
    return Env.standard(seed=5, trusted=True).load(SPEC).force_all()


def test_the_world_carries_counts_and_the_five_population_laws(values):
    world = values["world"]
    assert isinstance(world, WorldImpl)
    assert [c.multiplicity for c in world.compartments] == [1.0, 20.0, 5.0, 8.0]
    assert len(world.population_laws) == 5 and len(world.population_law_objs) == 5


def test_counts_move_and_the_food_is_drawn_down_and_returned(values):
    world = values["world"]
    tl = simulate(world, SimConfig(dt=0.1, steps=100, sample_every=100))
    first, last = tl.states[0], tl.states[-1]
    comps = list(last.compartment_ids or ())
    mols = list(last.molecule_ids or ())
    j, a, r, pond = (comps.index(n) for n in ("juveniles", "adults", "rivals", "pond"))
    assert last.get_multiplicity(a) > first.get_multiplicity(a)  # juveniles matured
    assert last.get_multiplicity(j) != first.get_multiplicity(j)
    assert last.get_multiplicity(r) > 0.0
    food = mols.index("food")
    assert 0.0 < last.get(pond, food) and last.get(pond, food) != first.get(pond, food)
    assert last.get(pond, mols.index("detritus")) > 0.0  # adults died and released mass


def test_the_intervene_task_scores_the_carrying_capacity(values):
    task = values["task"]
    assert isinstance(task.objective, OutcomeObjective) and task.objective.target == 6.0
    assert task.skeleton.binding == {"target": "food"}
    tl = simulate(values["world"], SimConfig(dt=0.1, steps=20, sample_every=20))
    score = task.objective.scorer(tl)
    assert 0.0 < score <= 1.0


def test_the_experiment_runs_over_the_feed_rate(tmp_path):
    spec = load_spec(SPEC)
    assert spec.drafter == "microcosm" and spec.axes == (("feed_rate", (0.3, 0.9)),)
    rmap = run_experiment(spec, out_dir=str(tmp_path / "run"))
    assert len(rmap.records) == 4 and rmap.provenance.failed_trials == 0
    assert all(0.0 < r.objective_score <= 1.0 for r in rmap.records)
    # T091 E2: the score reads the pond's food, the one compartment that holds
    # it. Feed 0.9 brings the pond nearer the goal of 6.0 (5.29 vs 4.15), so it
    # scores higher; summed over compartments it scored 0.18 vs 0.90.
    by_feed = {dict(r.condition_key)["feed_rate"]: r for r in rmap.records}
    pond_food = {feed: r.final_state["pond"]["food"] for feed, r in by_feed.items()}
    assert abs(6.0 - pond_food[0.9]) < abs(6.0 - pond_food[0.3])
    assert by_feed[0.9].objective_score > by_feed[0.3].objective_score
    assert by_feed[0.9].objective_score == pytest.approx(1.0 / (1.0 + abs(pond_food[0.9] - 6.0)))


def test_the_intervene_scorer_reads_one_compartment_and_refuses_an_ambiguous_one():
    """T091 E2: the target is read in the one compartment the binding names or
    that holds it; a target held in several and named in none refuses at draft."""
    from alienbio.bio.world import Compartment
    from alienbio.suite.arch_intervene import target_compartment

    world = Env.standard(seed=5, trusted=True).load(SPEC).force_all()["world"]
    assert target_compartment(world, "food") == "pond"
    assert target_compartment(world, "food", "adults") == "adults"
    with pytest.raises(ValueError, match="not a compartment"):
        target_compartment(world, "food", "lake")
    two = WorldImpl(
        world.chemistry,
        (Compartment("pond", None, "environment", 10.0, concentrations={"food": 4.0}),
         Compartment("cove", "pond", "environment", 1.0, concentrations={"food": 1.0})),
    )
    with pytest.raises(ValueError, match=r"held in \['pond', 'cove'\]"):
        target_compartment(two, "food")
