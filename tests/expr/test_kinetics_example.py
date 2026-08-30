"""M48.9 example 4 — the kinetics kit: every rate-law form on one world, the
reference and the JAX core agreeing, a predict task, an experiment."""

from __future__ import annotations

from pathlib import Path

import pytest

from alienbio.bio.rate_expr import to_text
from alienbio.expr import Env
from alienbio.suite.experiment import load_spec, run_experiment
from alienbio.suite.types import AnswerObjective

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "catalog" / "examples" / "kinetics" / "kinetics.yaml"


@pytest.fixture(scope="module")
def values():
    return Env.standard(seed=3, trusted=True).load(SPEC).force_all()


def _rxn(world, node):
    return next(r for rid, r in world.chemistry.reactions.items() if rid.endswith(f"/{node}/rxn"))


def test_every_rate_law_form_is_on_the_world(values):
    world = values["world"]
    mass = _rxn(world, "r_mass")
    assert mass.rate_law is None and not mass.modifiers and mass.rate == pytest.approx(0.05)
    kinds = {node: [m.kind for m in _rxn(world, node).modifiers.values()] for node in ("r_michaelis", "r_hill", "r_act", "r_inh")}
    assert kinds == {"r_michaelis": ["michaelis"], "r_hill": ["hill"], "r_act": ["activator"], "r_inh": ["inhibitor"]}
    assert _rxn(world, "r_michaelis").rate_law is None  # the product form stays modifiers, not an expression
    mm = _rxn(world, "r_mm")
    assert mm.rate_law is not None and to_text(mm.rate_law).startswith("((1.5 * ")
    alg = _rxn(world, "r_alg")
    assert alg.rate_law is not None and "sqrt" in to_text(alg.rate_law) and "exp" in to_text(alg.rate_law)
    mix = _rxn(world, "r_mix")
    assert mix.rate_law is not None and "hill" in to_text(mix.rate_law) and "inhibitor" in to_text(mix.rate_law)


def test_the_reference_and_jax_agree_on_the_whole_kit(values):
    parity = values["parity"]
    assert parity["steps"] == 200
    if parity["jax"]:
        assert parity["max_abs_diff"] < 1e-9
    else:
        pytest.skip("JAX not installed — nothing to compare")


def test_the_predict_key_is_read_from_the_physics(values):
    task = values["task"]
    assert isinstance(task.objective, AnswerObjective) and task.objective.key.value in ("up", "down", "same")
    assert task.objective.key.value == "down"


def test_the_experiment_runs_over_the_enzyme_level(tmp_path):
    spec = load_spec(SPEC)
    assert spec.drafter == "kinetics" and spec.axes == (("enzyme_level", (0.2, 1.0)),)
    rmap = run_experiment(spec, out_dir=str(tmp_path / "run"))
    assert len(rmap.records) == 4 and rmap.provenance.failed_trials == 0
