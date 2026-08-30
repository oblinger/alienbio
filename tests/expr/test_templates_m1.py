"""M47.5 — the M1 generator DSL is subsumed: the Generator Spec's example worlds
(energy cycle, anabolic chain, producer metabolism, mutualism) written as
``!template``s evaluate to exactly what M1's ``build.apply_template`` expanded
them to — pinned in ``m1_golden.json`` from the last commit that still carried
the ``build/`` package (M47.7 deleted it) — the proof the M1 DSL (``_params_`` / ``_instantiate_`` / ``_as_`` /
``{i in 1..n}`` / port wiring) is expressible with ``template`` / ``each`` /
``let`` / ``if`` plus one explicit namespacing head.

What M1 did implicitly — prefixing molecule and reaction ids with the instance
namespace and rewriting the template's own molecule references — is the one
piece of *logic* here, so it is a Python head (``m1_namespaced``), registered
below exactly as a user's ``helpers.py`` would. M1 never resolved a reference
to another instance's molecule (it left the dotted name as written); the
mutualism template reproduces that verbatim. Distribution-valued parameters
are fixed to numbers here: M1 and Expr draw from different streams, and the
draws are covered by the core tests.

Also here: template-instance pool namespacing on the block heads
(``Env.pool``), which is what makes two instances of one template distinct
worlds while a pool passed in as an argument is shared.
"""

from __future__ import annotations

from typing import Any, Mapping

import pytest

import json
from pathlib import Path

from alienbio.expr import Env, X, evaluate, fn
from alienbio.expr.yaml_tags import load_text

# ---------------------------------------------------------------------------
# the one explicit head: M1's implicit namespacing
# ---------------------------------------------------------------------------


@fn(summary="M1's namespacing: m.<ns>.<mol>, r.<ns>.<rxn>, own molecule refs rewritten")
def m1_namespaced(ns: str, molecules: Mapping[str, Any] = {}, reactions: Mapping[str, Any] = {}, children: Any = ()) -> dict[str, Any]:
    own = set(molecules)

    def ref(x: Any) -> Any:
        if isinstance(x, str):
            return f"m.{ns}.{x}" if x in own else x
        if isinstance(x, list):
            return [ref(v) for v in x]
        if isinstance(x, dict):
            return {k: ref(v) for k, v in x.items()}
        return x

    out: dict[str, Any] = {
        "molecules": {f"m.{ns}.{k}": dict(v) for k, v in molecules.items()},
        "reactions": {f"r.{ns}.{k}": ref(dict(v)) for k, v in reactions.items()},
    }
    for child in children:
        out["molecules"].update(child["molecules"])
        out["reactions"].update(child["reactions"])
    return out


# ---------------------------------------------------------------------------
# the four worlds, M1 side — the templates whose expansions m1_golden.json pins
# ---------------------------------------------------------------------------

M1_ENERGY_CYCLE = {
    "_params_": {"carrier_count": 3, "base_rate": 0.1},
    "molecules": {"ME{i in 1..3}": {"role": "energy"}},
    "reactions": {
        "activation": {"reactants": ["ME1", "ME1"], "products": ["ME2"], "rate": "!ref base_rate"},
        "work": {"reactants": ["ME2"], "products": ["ME3"]},
        "regeneration": {"reactants": ["ME3"], "products": ["ME1"]},
    },
    "_ports_": {"reactions.work": "energy.out"},
}

# M1's key loops (``MS{i in 1..3}``) expand, but M1 never substituted the loop
# variable inside VALUES — the Generator Spec's ``reactants: [MS{i}]`` example
# produced the literal string "MS{i}". So the M1 side spells its reactions
# out; the Expr side loops, as the Spec promised.


def _m1_chain(length: int) -> dict:
    return {
        "_params_": {"chain_length": length, "build_rate": 0.05},
        "molecules": {f"MS{{i in 1..{length}}}": {"role": "structural"}},
        "reactions": {
            f"build{i}": {"reactants": [f"MS{i}"], "products": [f"MS{i + 1}"], "rate": "!ref build_rate"}
            for i in range(1, length)
        },
        "_ports_": {"reactions.build1": "energy.in"},
    }


M1_ANABOLIC_CHAIN = _m1_chain(3)

M1_PRODUCER = {
    "_params_": {"chain_count": 2},
    "_instantiate_": {
        "_as_ energy": {"_template_": "energy_cycle", "carrier_count": 3},
        "_as_ chain{i in 1..chain_count}": {"_template_": "anabolic_chain", "reactions.build1": "energy.reactions.work"},
    },
}

M1_MUTUALISM = {
    "molecules": {"MW1": {"role": "waste"}},
    "reactions": {
        "krel_excretes": {"reactants": ["krel.energy.ME3"], "products": ["MW1"]},
        "vash_consumes": {"reactants": ["MW1"], "products": ["vash.chain1.MS1"]},
    },
    "_instantiate_": {
        "_as_ krel": {"_template_": "producer_metabolism"},
        "_as_ vash": {"_template_": "producer_metabolism", "chain_count": 1},
    },
}


M1_GOLDEN: dict[str, Any] = json.loads((Path(__file__).with_name("m1_golden.json")).read_text())


# ---------------------------------------------------------------------------
# the four worlds, Expr side — one document
# ---------------------------------------------------------------------------

EXPR_DOC = """
energy_cycle: !template
  positional: [ns]
  params: {carrier_count: 3, base_rate: 0.1}
  body: !m1_namespaced
    ns: !x ns
    molecules: !each
      over: !x range(1, carrier_count + 1)
      as: i
      key: !x f"ME{i}"
      body: {role: energy}
    reactions:
      activation: {reactants: [ME1, ME1], products: [ME2], rate: !x base_rate}
      work: {reactants: [ME2], products: [ME3]}
      regeneration: {reactants: [ME3], products: [ME1]}

anabolic_chain: !template
  positional: [ns]
  params: {chain_length: 3, build_rate: 0.05, energy_source: null}
  body: !m1_namespaced
    ns: !x ns
    molecules: !each
      over: !x range(1, chain_length + 1)
      as: i
      key: !x f"MS{i}"
      body: {role: structural}
    reactions: !each
      over: !x range(1, chain_length)
      as: i
      key: !x f"build{i}"
      body: !if
        cond: !x i == 1 and energy_source is not None
        then:
          reactants: !x '[f"MS{i}"]'
          products: !x '[f"MS{i + 1}"]'
          rate: !x build_rate
          energy_source: !x energy_source
        else:
          reactants: !x '[f"MS{i}"]'
          products: !x '[f"MS{i + 1}"]'
          rate: !x build_rate

producer_metabolism: !template
  positional: [ns]
  params: {chain_count: 2}
  body: !m1_namespaced
    ns: !x ns
    children: !let
      bindings:
        energy: !x 'energy_cycle(f"{ns}.energy", carrier_count=3)'
      body: !x '[energy] + [anabolic_chain(f"{ns}.chain{i}", energy_source=f"r.{ns}.energy.work") for i in range(1, chain_count + 1)]'

mutualism: !template
  positional: [ns]
  body: !m1_namespaced
    ns: !x ns
    molecules: {MW1: {role: waste}}
    reactions:
      krel_excretes: {reactants: [krel.energy.ME3], products: [MW1]}
      vash_consumes: {reactants: [MW1], products: [vash.chain1.MS1]}
    children: !x '[producer_metabolism(f"{ns}.krel"), producer_metabolism(f"{ns}.vash", chain_count=1)]'

krel_energy: !energy_cycle [krel]
krel_chain: !anabolic_chain {args: [krel], chain_length: 4}
krel: !producer_metabolism [krel]
eco: !mutualism [eco]
"""


@pytest.fixture
def expr_values() -> dict[str, Any]:
    return Env.standard(seed=0).load("<m1>", text=EXPR_DOC).force_all()


def test_energy_cycle_template_equals_its_m1_expansion(expr_values):
    m1 = M1_GOLDEN["energy_cycle"]
    assert expr_values["krel_energy"] == m1
    assert set(m1["molecules"]) == {"m.krel.ME1", "m.krel.ME2", "m.krel.ME3"}
    assert m1["reactions"]["r.krel.activation"]["rate"] == 0.1


def test_anabolic_chain_template_equals_its_m1_expansion_with_loops(expr_values):
    # M1's loops were fixed at parse time, so a longer chain was its own M1
    # template; the Expr side is one parametric template.
    m1 = M1_GOLDEN["anabolic_chain_4"]
    assert expr_values["krel_chain"] == m1
    assert set(m1["reactions"]) == {"r.krel.build1", "r.krel.build2", "r.krel.build3"}
    assert m1["reactions"]["r.krel.build2"]["reactants"] == ["m.krel.MS2"]


def test_producer_metabolism_template_equals_its_m1_expansion_with_nesting_and_ports(expr_values):
    m1 = M1_GOLDEN["producer_metabolism"]
    assert expr_values["krel"] == m1
    assert "m.krel.energy.ME1" in m1["molecules"] and "m.krel.chain2.MS3" in m1["molecules"]
    # the port connection: every chain's first build reaction names the energy source
    assert m1["reactions"]["r.krel.chain1.build1"]["energy_source"] == "r.krel.energy.work"
    assert m1["reactions"]["r.krel.chain2.build1"]["energy_source"] == "r.krel.energy.work"
    assert "energy_source" not in m1["reactions"]["r.krel.chain2.build2"]


def test_mutualism_template_equals_its_m1_expansion(expr_values):
    m1 = M1_GOLDEN["mutualism"]
    assert expr_values["eco"] == m1
    assert "m.eco.krel.chain2.MS1" in m1["molecules"] and "m.eco.vash.chain2.MS1" not in m1["molecules"]
    # M1 left cross-instance references as written; the template reproduces that
    assert m1["reactions"]["r.eco.krel_excretes"]["reactants"] == ["krel.energy.ME3"]


def test_two_instances_are_independent_and_defaults_evaluate_per_call():
    doc = """
cell: !template
  params:
    n: 2
    k: !x 'uniform(0, 1)'
  body:
    n: !x n
    k: !x k
    ids: !x '[f"m{i}" for i in range(n)]'
a: !cell {}
b: !cell {n: 3}
"""
    values = Env.standard(seed=5).load("<t>", text=doc).force_all()
    assert values["a"]["ids"] == ["m0", "m1"] and values["b"]["ids"] == ["m0", "m1", "m2"]
    assert values["a"]["k"] != values["b"]["k"]  # per-call child seeds


# ---------------------------------------------------------------------------
# pool namespacing on the block heads
# ---------------------------------------------------------------------------

BLOCK_DOC = """
cycle: !template
  positional: [waste]
  params: {rate: 1.0}
  body: !block
    children:
      feed: !source {pool: A, rate: !x rate}
      burn: !reaction {reactants: [A], products: [B]}
      dump: !reaction {reactants: [B], products: [!x waste]}
eco: !block
  children:
    krel: !cycle [shared_waste]
    vash: !cycle {args: [shared_waste], rate: 2.0}
    drain: !sink {pool: shared_waste, rate: 0.5}
sk: !skeleton {root: !x eco}
w: !world {skeleton: !x sk}
"""


def test_template_instances_namespace_their_pools_and_share_what_was_passed_in():
    values = Env.standard(seed=2).load("<blocks>", text=BLOCK_DOC).force_all()
    ports = set(values["sk"].root.resolved_ports)
    assert {"krel.A", "krel.B", "vash.A", "vash.B", "shared_waste"} <= ports
    assert "A" not in ports and "B" not in ports
    molecules = set(values["w"].chemistry.molecules)
    assert len(molecules) == 5  # two A, two B, one shared waste
    # outside a template a pool is just its name
    assert evaluate(X.source(pool="X"), Env.standard()).ports[0].name == "X"


def test_load_text_keeps_template_forms_as_data_until_evaluated():
    doc = load_text(EXPR_DOC)
    assert doc["energy_cycle"].head == "template"
    assert doc["krel_energy"].args == ("krel",)
