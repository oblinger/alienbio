"""T091 round BC — verifier BB's findings on simulation work and on a
spec's ``drafter_kwargs``.

BB1: every compartment costs a step (``W_COMPARTMENT_STEP``), so a world of
empty compartments is no longer one unit a step. BB2: count flows into many
destinations charge every molecule of each distinct destination
(``W_POPULATION_KEY``). BB3 and older surface (a): ``drafter_kwargs`` must be a
mapping, in every spec form and both validation modes. Older surface (c): the
``sim_cfg`` refusal names ``!sim`` for an Expr world head.
"""

from __future__ import annotations

import importlib
import time

import pytest

from alienbio.expr import Env, ExprError
from alienbio.suite.expr_experiment import load_experiment
from alienbio.suite.spec import ExperimentSpec, spec_from_dict

V = importlib.import_module("alienbio.suite.verify")

_ZERO_VERIFY = """
chem: !Chemistry {molecules: {}, reactions: {}}
comps: !x "[Compartment(id='c0', volume=1.0)]
  + [Compartment(id=f'c{i}', parent='c0', volume=1.0)
     for i in range(1, 20000)]"
w: !World {chemistry: !x chem, compartments: !x comps}
v: !verify
  world: !x w
  perturb: constant
  valid: "op:is"
  max_redraws: 0
  sim: !sim {dt: 0.1, steps: 20000, sample_every: 20000}
"""

_CF_FANOUT = """
M: 5000
P: 40
names: !x "[f'm{i}' for i in range(M)]"
mols: !x "dict([[x, {}] for x in names])"
conc: !x "dict([[x, 1.0] for x in names])"
chem: !Chemistry {molecules: !x mols, reactions: {}}
comps: !x "[Compartment(id='root', volume=1.0)]
  + [Compartment(id='a0', parent='root', volume=1.0,
       multiplicity=100.0, concentrations=conc)]
  + [Compartment(id=f'b{i}', parent='root', volume=1.0,
       multiplicity=100.0, concentrations=conc)
     for i in range(P)]"
w: !World
  chemistry: !x chem
  compartments: !x comps
  population_laws: !x "[CountFlow(origin='a0', dest=DEST, rate=0.0001) for i in range(P)]"
v: !verify
  world: !x w
  perturb: constant
  valid: "op:is"
  max_redraws: 0
  sim: !sim {dt: 0.01, steps: 12, sample_every: 12}
"""

# BB's three in-use-sized worlds (L1-L3): they must stay under the cap.
_L_WORLDS = {
    "L1": (
        """
names: !x "[f'm{i}' for i in range(30)]"
mols: !x "dict([[x, {}] for x in names])"
conc: !x "dict([[x, 1.0] for x in names])"
rxns: !x "dict([[f'r{i}', {'reactants': [names[i % 30]], 'products': [names[(i * 7 + 3) % 30]], 'rate': 0.05}] for i in range(40)] + [[f'q{i}', {'reactants': [names[i]], 'products': [names[i + 1]], 'rate_law': ['mul', ['const', 0.1], ['div', ['species', names[i]], ['add', ['const', 0.5], ['species', names[i]]]]]}] for i in range(10)])"
chem: !Chemistry {molecules: !x mols, reactions: !x rxns}
w: !World
  chemistry: !x chem
  compartments: !x "[Compartment(id='cell', volume=1.0, concentrations=conc), Compartment(id='nuc', parent='cell', volume=0.2, concentrations=conc), Compartment(id='mito', parent='cell', volume=0.1, concentrations=conc)]"
""",
        2000,
    ),
    "L2": (
        """
names: !x "[f'm{i}' for i in range(20)]"
mols: !x "dict([[x, {}] for x in names])"
conc: !x "dict([[x, 2.0] for x in names])"
rxns: !x "dict([[f'r{i}', {'reactants': [names[i % 20]], 'products': [names[(i + 1) % 20]], 'rate': 0.1}] for i in range(20)])"
chem: !Chemistry {molecules: !x mols, reactions: !x rxns}
w: !World
  chemistry: !x chem
  compartments: !x "[Compartment(id='pond', volume=10.0, concentrations=conc), Compartment(id='a', parent='pond', volume=1.0, multiplicity=50.0, concentrations=conc), Compartment(id='b', parent='pond', volume=1.0, multiplicity=20.0, concentrations=conc), Compartment(id='c', parent='pond', volume=1.0, concentrations=conc)]"
  flows: !x "[Transport(origin='pond', dest=['a', 'b', 'c'][i % 3], molecule=names[i], rate=0.01) for i in range(10)]"
  population_laws: !x "[GrowthLaw(compartment='a', resource_compartment='pond', resource='m0', rate=0.01, stoich=0.1), DeathLaw(compartment='a', rate=0.005, release_compartment='pond', release_resource='m1', release_stoich=0.1), CountFlow(origin='a', dest='b', rate=0.002)]"
""",
        1500,
    ),
    "L3": (
        """
names: !x "[f'm{i}' for i in range(40)]"
mols: !x "dict([[x, {}] for x in names])"
conc: !x "dict([[x, 1.0] for x in names])"
rxns: !x "dict([[f'r{i}', {'reactants': [names[i % 40]], 'products': [names[(i + 5) % 40]], 'rate': 0.02, 'modifiers': dict([[names[(i + 11) % 40], {'kind': 'michaelis', 'Vmax': 1.0, 'K': 0.5}]])}] for i in range(60)])"
chem: !Chemistry {molecules: !x mols, reactions: !x rxns}
w: !World
  chemistry: !x chem
  compartments: !x "[Compartment(id='cell', volume=1.0, concentrations=conc), Compartment(id='er', parent='cell', volume=0.3, concentrations=conc)]"
""",
        1000,
    ),
}


def _load(text: str) -> dict:
    return Env.standard(seed=0, trusted=False).load("t.yaml", text=text).force_all()


def _world(text: str):
    return Env.standard(seed=0, trusted=False).load("t.yaml", text=text).lookup("w")


def _terms(world) -> dict[str, int]:
    return {what: count * weight for what, count, weight in V.work_terms(world)}


def test_bb1_twenty_thousand_empty_compartments_refuse_in_under_a_second():
    """BB's ``zero_verify`` (20 000 empty compartments x 20 000 steps, 27.8 s of CPU before) refuses on work in under 1 s of CPU."""
    start = time.process_time()
    with pytest.raises(ExprError, match=r"would cost 1600000000 units.*20000 compartments x 2"):
        _load(_ZERO_VERIFY)
    assert time.process_time() - start < 1.0


def test_bb1_every_compartment_costs_a_step_whatever_the_chemistry_holds():
    """An empty chemistry charges ``W_COMPARTMENT_STEP`` per compartment, and the reaction pass's ``W_COMPARTMENT`` stays charged only with reactions."""
    empty = _world("chem: !Chemistry {molecules: {}, reactions: {}}\n"
                   "w: !World {chemistry: !x chem, compartments: [!Compartment {id: p, volume: 1.0}, "
                   "!Compartment {id: q, parent: p, volume: 1.0}]}\n")
    assert V.step_work(empty) == 2 * V.W_COMPARTMENT_STEP
    assert _terms(empty)["compartments with a reaction pass"] == 0


def test_bb2_count_flows_into_forty_destinations_refuse_in_under_a_second():
    """BB's ``cf_wrapped`` (40 count flows from one origin into 40 destinations x 5 000 molecules, 10 s of CPU before) refuses on work in under 1 s of CPU."""
    start = time.process_time()
    with pytest.raises(ExprError, match=r"200000 count-flow destination keys \(destinations x molecules\) x 30"):
        _load(_CF_FANOUT.replace("DEST", "f'b{i}'"))
    assert time.process_time() - start < 1.0


def test_bb2_destination_keys_are_charged_once_per_distinct_destination():
    """Forty count flows into one destination charge one destination's molecules; into forty, forty destinations' molecules."""
    head = _CF_FANOUT.split("v: !verify")[0].replace("M: 5000", "M: 7")
    one = _terms(_world(head.replace("DEST", "'b0'")))
    many = _terms(_world(head.replace("DEST", "f'b{i}'")))
    key = "count-flow destination keys (destinations x molecules)"
    assert one[key] == 1 * 7 * V.W_POPULATION_KEY
    assert many[key] == 40 * 7 * V.W_POPULATION_KEY
    selfish = _terms(_world(head.replace("DEST", "'a0'")))
    assert selfish[key] == 0  # a flow that stays home moves no content


@pytest.mark.parametrize("name", sorted(_L_WORLDS))
def test_bb_the_verifiers_in_use_sized_worlds_stay_under_the_cap(name):
    """BB's L1-L3 (up to 2 000 steps through ``predict_q``'s two simulations) stay under ``MAX_EXPR_SIM_WORK`` with the new weights."""
    text, steps = _L_WORLDS[name]
    w = _world(text)
    assert 2 * V.sim_work(w, V.SimConfig(dt=0.01, steps=steps, sample_every=100)) <= V.MAX_EXPR_SIM_WORK


_BASE = {"name": "s", "axes": {}, "drafter": "predict", "agent": "idle", "trials_per_condition": 1, "base_seed": 3}


@pytest.mark.parametrize("value, kind", [(["ab"], "list"), ("abc", "str"), ([1, 2], "list"), (5, "int")])
@pytest.mark.parametrize("validation", ["run", "recorded"])
def test_bb3_a_non_mapping_drafter_kwargs_refuses_in_the_dict_form(value, kind, validation):
    """``spec_from_dict`` refuses a non-mapping ``drafter_kwargs`` by name in both validation modes (``["ab"]`` was read as ``{'a': 'b'}``)."""
    with pytest.raises(ValueError, match=rf"^experiment spec: drafter_kwargs must be a mapping of keyword to value, got {kind}$"):
        spec_from_dict(dict(_BASE, drafter_kwargs=value), validation=validation)


@pytest.mark.parametrize("value, kind", [("abc", "str"), ([1, 2], "list")])
def test_bb3_a_non_mapping_drafter_kwargs_refuses_in_the_python_form(value, kind):
    """``ExperimentSpec`` refuses a non-mapping ``drafter_kwargs`` by name, not with ``dict()``'s own error."""
    for validation in ("run", "recorded"):
        with pytest.raises(ValueError, match=rf"drafter_kwargs must be a mapping of keyword to value, got {kind}$"):
            ExperimentSpec(name="s", axes=(), drafter="predict", agent="idle", trials_per_condition=1, base_seed=3,
                           drafter_kwargs=value, validation=validation)


def test_bb3_a_non_mapping_drafter_kwargs_refuses_in_the_expr_form_and_a_mapping_or_none_still_reads():
    """The ``!experiment`` form refuses a list ``drafter_kwargs``; a mapping and ``None`` read as before."""
    with pytest.raises(ExprError, match="drafter_kwargs must be a mapping of keyword to value, got list"):
        load_experiment(
            "<e>",
            text="!experiment\nname: a\ntask: !q predict()\ndrafter_kwargs: [ab]\nagent: idle\ntrials_per_condition: 1\nbase_seed: 3\n",
        )
    assert spec_from_dict(dict(_BASE, drafter_kwargs=None)).drafter_kwargs == {}
    assert dict(spec_from_dict(dict(_BASE, drafter_kwargs={"n_nodes": 6})).drafter_kwargs) == {"n_nodes": 6}


def test_a_world_heads_sim_cfg_refusal_names_sim():
    """An Expr world head given a mapping ``sim_cfg`` refuses asking for a SimConfig and naming ``!sim``."""
    with pytest.raises(ExprError, match=r"sim_cfg must be a SimConfig, got dict — pass a suite\.verify\.SimConfig \(in an Expr world head, build it with !sim\)"):
        _load("w: !pressure_world {sim_cfg: {dt: 0.1, steps: 10, sample_every: 5}}\n")
