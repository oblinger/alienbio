"""M47.6 — constructors: every registered Entity head is a head by its head
name (``!Molecule`` / ``!Reaction`` / ``!Chemistry``), ``!Compartment`` /
``!World`` build the world records, and ``{_type: X, ...}`` is the untagged
spelling of ``!X {...}`` (kept for saved worlds)."""

from __future__ import annotations

import pytest

from alienbio.bio.chemistry import ChemistryImpl
from alienbio.bio.molecule import MoleculeImpl
from alienbio.bio.reaction import ReactionImpl
from alienbio.bio.world import Compartment, WorldImpl
from alienbio.expr import Env, ExprError, X, evaluate, registry
from alienbio.infra.entity import get_registered_heads
from alienbio.suite.verify import SimConfig, simulate


def test_every_registered_entity_head_is_a_constructor_head():
    Env.standard()  # registers the suite heads
    for name in get_registered_heads():
        if name == "Entity":
            continue
        assert registry.get(name).kind == "constructor", name
    assert registry.get("World").kind == "constructor"


def test_molecule_reaction_chemistry_by_tag():
    env = Env.standard(seed=1)
    a = evaluate(X.Molecule(name="A", bdepth=2), env)
    assert isinstance(a, MoleculeImpl) and a.local_name == "A" and a.bdepth == 2
    r = evaluate(X.Reaction(reactants=["A", "A"], products=[{"B": 2.0}], rate=0.3, name="dimer"), env)
    assert isinstance(r, ReactionImpl) and r.local_name == "dimer" and r.rate == 0.3
    assert {m.local_name: c for m, c in r.reactants.items()} == {"A": 2.0}
    assert {m.local_name: c for m, c in r.products.items()} == {"B": 2.0}
    chem = evaluate(
        X.Chemistry(
            molecules=["A", "B"],
            reactions={"r1": {"reactants": ["A"], "products": ["B"], "rate": 0.1}, "r2": {"reactants": ["B"], "products": ["C"]}},
            name="host",
        ),
        env,
    )
    assert isinstance(chem, ChemistryImpl)
    assert set(chem.molecules) == {"A", "B", "C"}  # C minted from the reaction that names it
    assert chem.reactions["r1"].rate == 0.1


def test_chemistry_accepts_constructed_objects_and_the_node_key_names_them():
    doc = (
        "A: !Molecule {}\n"
        "B: !Molecule {bdepth: 1}\n"
        "leak: !Reaction {reactants: [!x A], products: [], rate: 0.01}\n"
        "host: !Chemistry\n"
        "  molecules: [!x A, !x B]\n"
        "  reactions: [!x leak]\n"
    )
    values = Env.standard(seed=1).load("<c>", text=doc).force_all()
    assert values["A"].local_name == "A" and values["B"].bdepth == 1
    assert values["leak"].local_name == "leak"
    chem = values["host"]
    assert chem.local_name == "host" and set(chem.molecules) == {"A", "B"} and chem.reactions["leak"].rate == 0.01


def test_compartment_and_world_records_simulate():
    doc = (
        "chem: !Chemistry\n"
        "  molecules: [A, B]\n"
        "  reactions: {r: {reactants: [A], products: [B], rate: 0.5}}\n"
        "cell: !Compartment {kind: cell, volume: 1.0, concentrations: {A: 2.0}}\n"
        "w: !World {chemistry: !x chem, compartments: [!x cell]}\n"
    )
    values = Env.standard(seed=1).load("<w>", text=doc).force_all()
    cell = values["cell"]
    assert isinstance(cell, Compartment) and cell.id == "cell" and cell.concentrations == {"A": 2.0}
    w = values["w"]
    assert isinstance(w, WorldImpl)
    timeline = simulate(w, SimConfig(dt=0.1, steps=20, sample_every=20))
    assert len(timeline.states) >= 1


def test_type_key_is_the_untagged_spelling():
    env = Env.standard(seed=1)
    r = evaluate({"_type": "Reaction", "name": "r", "reactants": ["A"], "products": ["B"], "rate": 0.2}, env)
    assert isinstance(r, ReactionImpl) and r.rate == 0.2
    tagged = evaluate(X.Reaction(name="r", reactants=["A"], products=["B"], rate=0.2), env)
    assert tagged.attributes() == r.attributes()
    with pytest.raises(ExprError, match="unknown head 'Nope'"):
        evaluate({"_type": "Nope"}, env)
    with pytest.raises(ExprError, match="_type must name a head"):
        evaluate({"_type": 3}, env)


def test_constructor_errors_carry_the_node_path():
    env = Env.standard(seed=1)
    with pytest.raises(ExprError, match="World: concentrations name molecules not in the chemistry"):
        evaluate(
            X.World(chemistry=X.Chemistry(molecules=["A"]), compartments=[X.Compartment(id="c", concentrations={"Z": 1.0})]),
            env,
        )
    with pytest.raises(ExprError, match="Reaction.reactants: expected"):
        evaluate(X.Reaction(reactants=[3]), env)
    with pytest.raises(ExprError, match="World: chemistry must be a Chemistry"):
        evaluate(X.World(chemistry="host"), env)


def test_typed_key_convention_is_gone():
    import alienbio
    import alienbio.spec_lang as spec_lang

    assert not hasattr(alienbio, "transform_typed_keys")
    assert not hasattr(spec_lang, "transform_typed_keys")
