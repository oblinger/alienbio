"""M47.9 — the ecosystem example (catalog/examples/ecosystem) is runnable:
loads trusted, evaluates to a World, a template call works from Python, and
the experiment runs end to end through the suite harness."""

from __future__ import annotations

from pathlib import Path

import pytest

from alienbio.bio.world import WorldImpl
from alienbio.expr import Env, ExprError, X, evaluate
from alienbio.suite.experiment import load_spec, run_experiment
from alienbio.suite.skeleton import SkeletonBlock
from alienbio.suite.types import OutcomeObjective, TaskInstance

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "catalog" / "examples" / "ecosystem" / "ecosystem.yaml"


@pytest.fixture(scope="module")
def scope():
    return Env.standard(seed=11, trusted=True).load(SPEC)


def test_the_file_evaluates_to_a_world_with_the_expected_pools(scope):
    values = scope.force_all()
    world = values["world"]
    assert isinstance(world, WorldImpl)
    # the root block prefixes every pool with its namespace
    mols = {m.removeprefix("root/") for m in world.chemistry.molecules}
    # each organism's energy cycle is private; the waste is shared
    assert {"krel.energy.ME1", "krel.energy.ME2", "krel.energy.ME3", "vash.energy.ME1", "vash.energy.ME2", "vash.energy.ME3"} <= mols
    assert "shared_waste" in mols and "ME1" not in mols
    # krel has n_chains routes, vash the default two; each chain's interior pools are its own
    assert {"krel.S0", "krel.S1", "vash.S0", "vash.S1", "krel.chain0.x1", "krel.chain1.x1"} <= mols
    # the bindings the top of the file shows off
    assert values["label"].startswith("eco-2sp-") and values["tags"][:2] == ["waste", "energy"]
    assert values["weights"] == [110.0, 120.0, 130.0]
    assert values["leak"].rate == 0.01
    assert isinstance(values["task"], TaskInstance) and isinstance(values["task"].objective, OutcomeObjective)


def test_a_template_call_from_python_and_the_same_seed_is_the_same_world(scope):
    vash = evaluate(X.organism("vash", chains=1), scope)
    assert isinstance(vash, SkeletonBlock)
    assert X.dump(X.organism("vash", chains=1), style="structural").strip() == "!organism {args: [vash], chains: 1}"
    again = Env.standard(seed=11, trusted=True).load(SPEC).force_all()["world"]
    first = scope.force_all()["world"]
    assert sorted(again.chemistry.reactions) == sorted(first.chemistry.reactions)
    rate = lambda w, r: w.chemistry.reactions[r].rate  # noqa: E731
    rid = sorted(first.chemistry.reactions)[0]
    assert rate(again, rid) == rate(first, rid)


def test_an_untrusted_load_refuses_the_helpers():
    from alienbio.expr import UnsafeSpecError

    with pytest.raises(UnsafeSpecError):
        Env.standard(seed=1).load(SPEC)


def test_the_experiment_runs_end_to_end(tmp_path):
    spec = load_spec(SPEC)  # trusted: under catalog/
    assert spec.drafter == "ecosystem" and spec.axes == (("chains", (1, 2)), ("max_turns", (4, 8)))
    rmap = run_experiment(spec, out_dir=str(tmp_path / "run"))
    assert len(rmap.records) == 8 and rmap.provenance.failed_trials == 0
    assert all(0.0 <= r.objective_score <= 1.0 for r in rmap.records)
    assert (tmp_path / "run" / "records.jsonl").exists()
