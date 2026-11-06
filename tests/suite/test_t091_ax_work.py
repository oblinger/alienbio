"""T091 round AY — verifier AX's findings on simulation work and the drafters.

AX1: ``verify.sim_work`` counts what a simulator step does (each reaction's
fan-in, fan-out, modulators and rate-law nodes in every compartment, the
state copy, flows, population laws), and ``predict_q`` / ``verify`` charge
both simulations they run. AX3: a 0-d numpy size dial is capped. AX6: a
mapping ``sim_cfg`` is a config refusal at preflight.
"""

from __future__ import annotations

import importlib
import time

import numpy as np
import pytest

from alienbio.expr import Env, ExprError, fn
from alienbio.suite.dist import Seed
from alienbio.suite.drafters import DRAFTERS, MAX_N_NODES
from alienbio.suite.expr_experiment import load_experiment
from alienbio.suite.guards import draft_violation

V = importlib.import_module("alienbio.suite.verify")

_RC = """
R: {R}
C: {C}
mols: {{m0: {{}}, m1: {{}}}}
rxns: !x "dict([[f'r{{i}}', {{'reactants': ['m0'], 'products': ['m1'], 'rate': 0.001}}] for i in range(R)])"
chem: !Chemistry {{molecules: !x mols, reactions: !x rxns}}
comps: !x "[Compartment(id='c0', volume=1.0, concentrations={{'m0': 5.0}})] + [Compartment(id=f'c{{i}}', parent='c0', volume=1.0, concentrations={{'m0': 5.0}}) for i in range(1, C)]"
w: !World {{chemistry: !x chem, compartments: !x comps}}
"""

_FANIN = """
M: 300
names: !x "[f'm{i}' for i in range(M)]"
mols: !x "dict([[x, {}] for x in names])"
rxns: !x "dict([[f'r{i}', {'reactants': names, 'products': ['m0'], 'rate': 0.0001}] for i in range(M)])"
chem: !Chemistry {molecules: !x mols, reactions: !x rxns}
w: !World {chemistry: !x chem, compartments: [!Compartment {id: c0, volume: 1.0, concentrations: !x "dict([[x, 5.0] for x in names])"}]}
"""


def _predict(steps: int) -> str:
    return (
        "q: !predict_q {world: !x w, reaction_id: r1, target_id: m1, factor: 0.25, compartment: c0,\n"
        f"  sim: !sim {{dt: 0.1, steps: {steps}, sample_every: {steps}}}}}\n"
    )


def _load(text: str):
    return Env.standard(seed=0, trusted=False).load("t.yaml", text=text).force_all()


@pytest.mark.parametrize(
    "text",
    [
        _RC.format(R=1000, C=1000) + _predict(20),
        _FANIN + _predict(200),
        _RC.format(R=2, C=4096) + _predict(244),
    ],
    ids=["rc_1000_1000_20", "fanin", "rc_2_4096_244"],
)
def test_ax1_the_verifiers_repros_refuse_in_under_a_second(text):
    """AX's three repros (72 s, 25 s and 10 s of CPU before) refuse on MAX_EXPR_SIM_WORK in under 1 s of CPU."""
    t = time.process_time()
    with pytest.raises(ExprError, match=f"MAX_EXPR_SIM_WORK={V.MAX_EXPR_SIM_WORK}"):
        _load(text)
    assert time.process_time() - t < 1.0


def test_ax1_step_work_counts_fan_in_modulators_rate_law_nodes_and_compartments():
    """``step_work`` is Σ reactions (1 + reactants + products + modulators + rate-law nodes) × compartments + molecules × compartments + flows + population laws."""
    text = """
mols: {a: {}, b: {}, c: {}, d: {}}
rxns:
  r0: {reactants: [a, b], products: [c], modifiers: {d: activator}, rate: 0.1}
  r1: {reactants: [c], products: [a, b], rate_law: [mul, [const, 0.2], [species, c]]}
chem: !Chemistry {molecules: !x mols, reactions: !x rxns}
w: !World {chemistry: !x chem, compartments: [!Compartment {id: p, volume: 1.0}, !Compartment {id: q, parent: p, volume: 1.0}, !Compartment {id: s, parent: p, volume: 1.0}]}
"""
    w = _load(text)["w"]
    # r0: 1 + 2 + 1 + 1 = 5; r1: 1 + 1 + 2 + 3 law nodes = 7; molecules 4; three compartments
    assert V.step_work(w) == (5 + 7) * 3 + 4 * 3
    assert V.sim_work(w, V.SimConfig(steps=10)) == 10 * V.step_work(w)


def test_ax1_predict_q_charges_both_simulations():
    """A world whose one simulation fits the cap but whose two do not refuses before either runs."""
    w = _load(_RC.format(R=2, C=100))["w"]
    steps = V.MAX_EXPR_SIM_WORK // (2 * V.step_work(w)) + 1
    assert V.sim_work(w, V.SimConfig(steps=steps)) <= V.MAX_EXPR_SIM_WORK
    t = time.process_time()
    with pytest.raises(ExprError, match="2 simulation"):
        _load(_RC.format(R=2, C=100) + _predict(steps))
    assert time.process_time() - t < 1.0


_PERTURBED: list[object] = []


@fn(name="t091ax_same")
def _same(w):  # type: ignore[no-untyped-def]
    _PERTURBED.append(w)
    return w


@fn(name="t091ax_ok")
def _ok(a, b):  # type: ignore[no-untyped-def]
    return True


def test_ax1_verify_charges_both_simulations_before_the_first_runs():
    """``!verify`` refuses a world whose base and perturbed simulations together pass the cap before simulating or perturbing it."""
    w = _load(_RC.format(R=2, C=100))["w"]
    steps = V.MAX_EXPR_SIM_WORK // (2 * V.step_work(w)) + 1
    text = _RC.format(R=2, C=100).replace("w: !World", "w0: !World") + (
        "v: !verify {world: !x w0, perturb: t091ax_same, valid: t091ax_ok, "
        f"sim: !sim {{dt: 0.1, steps: {steps}, sample_every: {steps}}}}}\n"
    )
    _PERTURBED.clear()
    t = time.process_time()
    with pytest.raises(ExprError, match="verify: 2 simulation"):
        _load(text)
    assert time.process_time() - t < 1.0 and not _PERTURBED


def test_ax3_a_zero_d_numpy_size_dial_is_capped():
    """A 0-d numpy array size dial is judged by its item; past the cap it refuses before the generator runs."""
    t = time.process_time()
    with pytest.raises(ValueError, match=f"exceeds its cap {MAX_N_NODES}"):
        DRAFTERS["predict"](Seed(3), {"n_nodes": np.array(20000)})
    assert time.process_time() - t < 1.0


def test_ax6_a_mapping_sim_cfg_is_a_config_refusal_at_preflight():
    """A plain mapping ``sim_cfg`` in ``drafter_kwargs`` refuses at preflight as a config error naming the head and ``!sim``."""
    spec = load_experiment(
        "<m>",
        text=(
            "!experiment\nname: m\ntask: !q predict()\n"
            "drafter_kwargs:\n  sim_cfg: {dt: 0.1, steps: 10, sample_every: 5}\n"
            "agent: idle\ntrials_per_condition: 1\nbase_seed: 3\n"
        ),
    )
    reason = draft_violation(spec)
    assert reason is not None and "drafts no world" in reason and "predict: sim_cfg must be a SimConfig" in reason
    assert "!sim" in reason and "drafter fault" not in reason
