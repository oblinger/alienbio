"""M48.9 example 2 — the organism example is runnable: a compartment tree with
transport, a lattice patch, the energy and boundedness gates, a predict task
computed from the physics, and an experiment over the transport rate."""

from __future__ import annotations

from pathlib import Path

import pytest

from alienbio.bio.world import WorldImpl
from alienbio.expr import Env, ExprError, X, evaluate
from alienbio.suite.experiment import load_spec, run_experiment
from alienbio.suite.types import AnswerObjective
from alienbio.suite.verify import SimConfig, simulate

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "catalog" / "examples" / "organism" / "organism.yaml"


@pytest.fixture(scope="module")
def values():
    return Env.standard(seed=7, trusted=True).load(SPEC).force_all()


def test_the_body_is_a_four_level_tree_with_flows_and_passes_both_gates(values):
    body = values["body"]
    assert isinstance(body, WorldImpl)
    assert [c.id for c in body.compartments] == ["organism", "liver", "hepatocyte", "mitochondrion"]
    assert [c.parent for c in body.compartments] == [None, "organism", "liver", "hepatocyte"]
    assert body.initial_state.tree.num_compartments == 4
    assert len(body.flow_objs) == 4 and {f.rate_law for f in body.flow_objs} == {"gradient", "first_order"}
    # glucose reaches the hepatocyte only by crossing two membranes
    final = simulate(body, SimConfig(dt=0.1, steps=50, sample_every=50)).states[-1]
    mols = list(final.molecule_ids or ())
    comps = list(final.compartment_ids or ())
    assert final.get(comps.index("hepatocyte"), mols.index("pyruvate")) > 0.0
    assert final.get(comps.index("mitochondrion"), mols.index("pyruvate")) > 0.0


def test_the_gates_reject_a_broken_world():
    uphill = SPEC.read_text().replace("lactate:  {formation_energy: -2.5}", "lactate:  {formation_energy: -1.5}")
    with pytest.raises(ExprError, match="rejected by guard energy_valid"):
        Env.standard(seed=7, trusted=True).load(SPEC, text=uphill).force_all()
    unbounded = SPEC.read_text().replace("    clear:      {reactants: [waste], products: [], rate: 0.05}\n", "")
    with pytest.raises(ExprError, match="rejected by guard bounded"):
        Env.standard(seed=7, trusted=True).load(SPEC, text=unbounded).force_all()


def test_oxygen_diffuses_along_the_lattice(values):
    tissue = values["tissue"]
    final = simulate(tissue, SimConfig(dt=0.1, steps=40, sample_every=40)).states[-1]
    mols = list(final.molecule_ids or ())
    oxygen = [i for i, m in enumerate(mols) if m.endswith("oxygen")]
    assert oxygen and final.num_molecules >= 1
    per_cell = [final.get(c, oxygen[0]) for c in range(final.tree.num_compartments)]
    assert len(per_cell) == 4 and per_cell[-1] > 0.0 and per_cell[0] < 4.0


def test_the_predict_key_is_read_from_the_physics(values):
    task = values["task"]
    assert isinstance(task.objective, AnswerObjective) and task.objective.key.kind == "node_id"
    assert task.objective.key.value in ("up", "down", "same")
    assert task.objective.key.value == "down"  # throttling ferment lowers lactate


def test_the_experiment_runs_over_the_transport_rate(tmp_path):
    spec = load_spec(SPEC)
    assert spec.drafter == "organism" and spec.axes == (("transport_rate", (0.1, 0.4)),)
    rmap = run_experiment(spec, out_dir=str(tmp_path / "run"))
    assert len(rmap.records) == 4 and rmap.provenance.failed_trials == 0
    assert evaluate(X.name("feed_rate"), Env.standard(seed=1, trusted=True).load(SPEC)) == 0.5
