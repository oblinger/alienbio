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
    locus = values["locus"]
    product = {"receptor": "S0", "amp0": "S1", "amp1": "S2", "output": "O"}[locus]
    assert task.objective.key.value.endswith(f"/{product}") and task.objective.key.kind == "node_id"
    assert task.objective.key.value in task.question.structured and task.question.kind == "node_set"
    # the perturbation is real: the drawn stage runs at a quarter of its clean rate
    clean, perturbed = values["world"], values["pworld"]
    assert _rxn(perturbed, locus).rate == pytest.approx(_rxn(clean, locus).rate * 0.25)
    for other in {"receptor", "amp0", "amp1", "output"} - {locus}:
        assert _rxn(perturbed, other).rate == pytest.approx(_rxn(clean, other).rate)


def test_the_locus_is_drawn_from_the_seed_over_every_stage():
    """T096: the throttled stage was amp0 (key S1) on every seed; it is drawn
    over the receptor, each amplification step and the output, so a blind
    commit of the modal key is right about one time in depth + 2."""
    keys = [DRAFTERS["cascade"](Seed(s), {"depth": 1})[1].objective.key.value.rsplit("/", 1)[-1] for s in range(60)]
    counts = {k: keys.count(k) for k in set(keys)}
    assert set(counts) == {"S0", "S1", "O"}, counts
    assert max(counts.values()) <= 30, counts
    deep = {DRAFTERS["cascade"](Seed(s), {"depth": 3})[1].objective.key.value.rsplit("/", 1)[-1] for s in range(60)}
    assert deep == {"S0", "S1", "S2", "S3", "O"}


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
