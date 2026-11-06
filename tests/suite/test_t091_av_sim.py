"""T091 round AW — verifier AV's simulation step counts (AV2, AV3), the
other spec-given counts that held a load past the clock, and the two lows
(AV4 numpy size dials, AV5 mixed hashable / unhashable axis levels)."""

from __future__ import annotations

import time

import numpy as np
import pytest

from alienbio.expr import Env, ExprError
from alienbio.suite import drafters as dr
from alienbio.suite.blocks import MAX_LATTICE_CELLS, MAX_POISSON_EVENTS, PoissonSchedule, SpatialLatticeBlock
from alienbio.suite.carve import MAX_CARVE_VISITS
from alienbio.suite.dist import Seed
from alienbio.suite.experiment import DRAFTERS
from alienbio.suite.expr_experiment import MAX_COVER_ITEMS, load_experiment
from alienbio.suite.spec import _validate_axes
from alienbio.suite.verify import MAX_EXPR_SIM_WORK, SimConfig
from alienbio.suite.skeleton import SkeletonError

SEED = Seed(3)
HUGE = SimConfig(dt=0.05, steps=2_000_000, sample_every=1_000_000)

#: AV2's five drafters (and the rest that take a generator ``sim_cfg``).
SIM_CFG_DRAFTERS = [
    ("phase1_pressure", {"variant": "coupling_told"}),
    ("pressure", {"pi": 0.5}),
    ("delta", {}),
    ("pressure_w2", {"pi": 0.5}),
    ("intervene", {}),
    ("conflict", {"rung": "A"}),
    ("identify_pathway", {}),
    ("predict", {}),
    ("diagnose", {}),
]


def _load(tmp_path, text: str):
    path = tmp_path / "t.yaml"
    path.write_text(text)
    return Env.standard(seed=3).load(str(path)).force_all()


def test_the_sim_head_refuses_steps_past_the_cap_naming_value_and_cap(tmp_path):
    """``!sim`` past MAX_DRAFT_SIM_STEPS refuses at load, naming the value and the cap, in well under 2 s of CPU."""
    t = time.process_time()
    with pytest.raises(ExprError, match=rf"steps=2000000 exceeds the cap MAX_DRAFT_SIM_STEPS={dr.MAX_DRAFT_SIM_STEPS}"):
        _load(tmp_path, "s: !sim {dt: 0.05, steps: 2000000, sample_every: 1000000}\n")
    assert time.process_time() - t < 2.0
    assert _load(tmp_path, f"s: !sim {{steps: {dr.MAX_DRAFT_SIM_STEPS}}}\n")["s"].steps == dr.MAX_DRAFT_SIM_STEPS


@pytest.mark.parametrize(("drafter", "dials"), SIM_CFG_DRAFTERS, ids=[d for d, _ in SIM_CFG_DRAFTERS])
def test_a_python_callers_sim_cfg_is_held_to_the_draft_horizon(drafter, dials):
    """A ``SimConfig`` a Python caller passes through ``**generator`` refuses past MAX_DRAFT_SIM_STEPS before the generator simulates."""
    t = time.process_time()
    with pytest.raises(ValueError, match=f"MAX_DRAFT_SIM_STEPS={dr.MAX_DRAFT_SIM_STEPS}"):
        DRAFTERS[drafter](SEED, dials, sim_cfg=HUGE)
    assert time.process_time() - t < 2.0


def test_a_sim_cfg_that_is_not_a_simconfig_refuses_by_type():
    """A mapping in place of a ``SimConfig`` refuses as a config error, naming the head (T091 AX6)."""
    with pytest.raises(ValueError, match="pressure: sim_cfg must be a SimConfig"):
        DRAFTERS["pressure"](SEED, {"pi": 0.5}, sim_cfg={"steps": 10})


def test_av2_the_expr_drafter_kwargs_sim_cfg_refuses_at_load():
    """AV2's ``drafter_kwargs`` ``!sim`` of 2 000 000 steps refuses at load in under 2 s of CPU."""
    text = (
        "!experiment\nname: b\ntask: !q phase1_pressure(variant=\"coupling_told\")\nbrief: !q brief(levers=[])\n"
        "drafter_kwargs: {sim_cfg: !sim {dt: 0.05, steps: 2000000, sample_every: 1000000}}\n"
        "episode: !q episode(max_turns=4, sim_steps=5)\nagent: idle\ntrials_per_condition: 1\nbase_seed: 3\n"
    )
    t = time.process_time()
    with pytest.raises(ExprError, match="MAX_DRAFT_SIM_STEPS"):
        load_experiment("<b>", text=text)
    assert time.process_time() - t < 2.0


def test_the_world_heads_hold_the_drafter_caps(tmp_path):
    """``prediction_world`` / ``pressure_world`` keywords pass the same size-dial caps as the drafter heads."""
    with pytest.raises(ExprError, match=f"n_nodes=2000000 exceeds its cap {dr.MAX_N_NODES}"):
        _load(tmp_path, "a: !prediction_world {n_nodes: 2000000}\n")
    with pytest.raises(ExprError, match=f"complexity=5000 exceeds its cap {dr.MAX_COMPLEXITY}"):
        _load(tmp_path, "a: !pressure_world {pi: 0.5, complexity: 5000}\n")


_BIG_CHEM = """n: {n}
mols: !x "dict([[f'm{{i}}', {{}}] for i in range(n + 1)])"
rxns: !x "dict([[f'r{{i}}', {{'reactants': [f'm{{i}}'], 'products': [f'm{{i+1}}'], 'rate': 0.3}}] for i in range(n)])"
chem: !Chemistry {{molecules: !x mols, reactions: !x rxns}}
w: !World
  chemistry: !x chem
  compartments: [!Compartment {{id: c, volume: 1.0, concentrations: {{m0: 5.0}}}}]
q: !predict_q {{world: !x w, reaction_id: r1, target_id: m2, factor: 0.25, compartment: c,
  sim: !sim {{dt: 0.1, steps: 20000, sample_every: 20000}}}}
"""


def test_predict_q_refuses_a_simulation_past_the_work_cap(tmp_path):
    """A comprehension-built 3 000-reaction world under a 20 000-step ``!sim`` refuses on MAX_EXPR_SIM_WORK before simulating."""
    t = time.process_time()
    with pytest.raises(ExprError, match=f"MAX_EXPR_SIM_WORK={MAX_EXPR_SIM_WORK}"):
        _load(tmp_path, _BIG_CHEM.format(n=3000))
    assert time.process_time() - t < 2.0


def test_lattice_and_poisson_counts_are_capped():
    """A lattice past MAX_LATTICE_CELLS and a Poisson schedule past MAX_POISSON_EVENTS expected insults refuse at construction."""
    with pytest.raises(SkeletonError, match=f"MAX_LATTICE_CELLS={MAX_LATTICE_CELLS}"):
        SpatialLatticeBlock.make("lat", k=MAX_LATTICE_CELLS + 1)
    SpatialLatticeBlock.make("lat", k=MAX_LATTICE_CELLS)
    with pytest.raises(SkeletonError, match=f"MAX_POISSON_EVENTS={MAX_POISSON_EVENTS}"):
        PoissonSchedule(lam=1e9, horizon=1e9)
    PoissonSchedule(lam=float(MAX_POISSON_EVENTS) / 20.0, horizon=20.0)


def test_cover_refuses_past_its_item_cap(tmp_path):
    """``!cover`` over more than MAX_COVER_ITEMS items refuses before the solver runs."""
    text = f"c: !cover {{features: !x \"[{{'k': 'nonempty'}} for i in range({MAX_COVER_ITEMS + 1})]\"}}\n"
    t = time.process_time()
    with pytest.raises(ExprError, match=f"MAX_COVER_ITEMS={MAX_COVER_ITEMS}"):
        _load(tmp_path, text)
    assert time.process_time() - t < 2.0


def test_carve_refuses_a_dead_branch_search_past_its_visit_cap(tmp_path):
    """A 6-role motif whose one edge joins its first and last role, over 60 unlinked molecules, refuses on MAX_CARVE_VISITS inside the evaluation clock."""
    text = (
        "n: 60\nmols: !x \"dict([[f'm{i}', {}] for i in range(n)])\"\nchem: !Chemistry {molecules: !x mols}\n"
        "pat: !pattern {roles: {a: molecule, b: molecule, c: molecule, d: molecule, e: molecule, f: molecule}, "
        "edges: [[a, f, reacts_to]]}\nc: !carve {host: !x chem, pattern: !x pat, allow_add: False}\n"
    )
    t = time.process_time()
    with pytest.raises(ExprError, match=f"MAX_CARVE_VISITS={MAX_CARVE_VISITS}"):
        _load(tmp_path, text)
    assert time.process_time() - t < 10.0


@pytest.mark.parametrize("value", [np.int64(20000), np.int32(20000), np.float64(2e4), np.uint16(20000)])
def test_av4_numpy_size_dials_are_capped(value):
    """A numpy integer or float size dial past its cap refuses like a Python number."""
    with pytest.raises(ValueError, match="exceeds its cap"):
        DRAFTERS["predict"](SEED, {"n_nodes": value})


def test_av4_a_bool_size_dial_still_passes_the_cap():
    """A bool is not judged by the cap (the generator reads it as 1), as before."""
    dr.check_size_dials("predict", n_nodes=True)


def test_av5_a_set_and_a_frozenset_level_are_one_level():
    """``{1}`` and ``frozenset({1})`` on one axis refuse as a repeated level, in either order."""
    for levels in (({1}, frozenset({1})), (frozenset({1}), {1})):
        msgs: list[str] = []
        _validate_axes((("a", levels),), refuse=msgs.append)
        assert len(msgs) == 1 and "repeats level" in msgs[0]
