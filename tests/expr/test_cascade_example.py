"""M48.9 example 5 — the cascade: every pattern block on one signalling loop,
an indirection-depth dial, observability narrowing, a diagnose task."""

from __future__ import annotations

from pathlib import Path

import pytest

from alienbio.expr import Env
from alienbio.suite.dist import Seed
from alienbio.suite.experiment import DRAFTERS, load_spec, run_experiment
from alienbio.suite.types import AnswerObjective

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "catalog" / "examples" / "cascade" / "cascade.yaml"


@pytest.fixture(scope="module")
def values():
    return Env.standard(seed=5, trusted=True).load(SPEC).force_all()


def _rxn(world, node):
    return next(r for rid, r in world.chemistry.reactions.items() if rid.endswith(f"/{node}/rxn"))


def test_every_pattern_block_is_on_the_loop(values):
    world = values["world"]
    kinds = {node: [m.kind for m in _rxn(world, node).modifiers.values()] for node in ("receptor", "amp0", "output", "feedback")}
    assert kinds == {"receptor": ["activator"], "amp0": ["michaelis"], "output": ["hill"], "feedback": ["activator"]}
    buffer_rxn = _rxn(world, "buffer")
    unbuffer_rxn = _rxn(world, "unbuffer")
    short = lambda names: {n.rsplit("/", 1)[-1] for n in names}
    assert short(m.name for m in buffer_rxn.reactants) == {"O", "B"}
    assert short(m.name for m in unbuffer_rxn.products) == {"O", "B"}


def test_the_depth_dial_sizes_the_amplification_chain(values):
    del values
    shallow, _ = DRAFTERS["cascade"](Seed(5), {"depth": 1})
    deep, _ = DRAFTERS["cascade"](Seed(5), {"depth": 3})
    n_amp = lambda w: sum(1 for rid in w.chemistry.reactions if "/amp" in rid)
    assert n_amp(shallow) == 1 and n_amp(deep) == 3
    deep_pools = {m.rsplit("/", 1)[-1] for m in deep.chemistry.molecules}
    shallow_pools = {m.rsplit("/", 1)[-1] for m in shallow.chemistry.molecules}
    assert "S3" in deep_pools and "S3" not in shallow_pools


def test_the_diagnose_key_is_the_throttled_steps_product(values):
    task = values["task"]
    assert isinstance(task.objective, AnswerObjective)
    assert task.objective.key.value.endswith("/S1") and task.objective.key.kind == "node_id"
    assert task.objective.key.value in task.question.structured and task.question.kind == "node_set"
    # the perturbation is real: amp0 runs at a quarter of the clean rate
    clean, perturbed = values["world"], values["pworld"]
    assert _rxn(perturbed, "amp0").rate == pytest.approx(_rxn(clean, "amp0").rate * 0.25)


def test_observability_narrows_the_brief_probes(tmp_path):
    spec = load_spec(SPEC)
    assert dict(spec.axes)["observability"] == (1.0, 0.6)
    rmap = run_experiment(spec, out_dir=str(tmp_path / "run"))
    assert rmap.provenance.failed_trials == 0 and len(rmap.records) == 8
    by_obs = {}
    for record in rmap.records:
        obs = dict(record.condition_key)["observability"]
        by_obs.setdefault(obs, set()).add(len(record.brief.affordances.probes))
    assert max(by_obs[0.6]) < min(by_obs[1.0]), f"observability 0.6 must hide molecules: {by_obs}"
