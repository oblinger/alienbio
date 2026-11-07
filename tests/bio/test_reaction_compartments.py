"""T091 Q2 — a reaction confined to named compartments.

``compartments:`` on a reaction is a whitelist of compartment ids; without
the key (``None``) the reaction runs in every compartment, exactly as before.
The scope is set by name at every spec-facing layer (``ReactionImpl``,
``mk.R``, ``!Chemistry``/``!Reaction``, the ``reaction`` head and its
``ReactionBlock``/``RateLawBlock``), mapped to the tree's integer ids by
``reaction_compartment_ids`` (``WorldImpl`` at draft time,
``WorldSimulatorImpl.from_chemistry`` for both simulators), and carried by
every rebuild of a reaction.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from alienbio.bio.chemistry import ChemistryImpl
from alienbio.bio.molecule import MoleculeImpl
from alienbio.bio.rate_expr import parity_agrees
from alienbio.bio.reaction import ReactionImpl, rebuild_reaction
from alienbio.bio.world import Compartment, WorldImpl
from alienbio.bio.world_simulator import WorldSimulatorImpl, reaction_compartment_ids
from alienbio.expr import Env, ExprError
from alienbio.infra.mk import mk
from alienbio.suite.verify import SimConfig, simulate

try:
    from alienbio.bio.jax_simulator import JaxWorldSimulator

    HAS_JAX = True
except ImportError:  # pragma: no cover - depends on the extra
    HAS_JAX = False

needs_jax = pytest.mark.skipif(not HAS_JAX, reason="JAX not installed")


def _mols() -> tuple[MoleculeImpl, MoleculeImpl]:
    return cast(MoleculeImpl, mk.M("food")), cast(MoleculeImpl, mk.M("waste"))


def _world(scope: Any = None, **extra: Any) -> WorldImpl:
    """A pond with two child compartments; ``supply`` (∅ → food) scoped by
    ``scope``, ``spoil`` (food → waste) everywhere."""
    food, waste = _mols()
    supply = mk.R("supply", {}, {food: 1.0}, rate=0.5, compartments=scope, **extra)
    spoil = mk.R("spoil", {food: 1.0}, {waste: 1.0}, rate=0.1)
    chem = cast(ChemistryImpl, mk.C("chem", [food, waste], [supply, spoil]))
    comps = (
        Compartment("pond", None, "environment", 10.0, concentrations={"food": 1.0}),
        Compartment("fish", "pond", "population", 0.2, multiplicity=3.0),
        Compartment("weed", "pond", "population", 0.1),
    )
    return WorldImpl(chem, comps)


def _final(world: WorldImpl, steps: int = 30):
    return simulate(world, SimConfig(dt=0.1, steps=steps, sample_every=steps)).states[-1]


# ---- the record ------------------------------------------------------------


def test_the_default_is_every_compartment_and_serializes_as_before():
    food, _ = _mols()
    rxn = cast(ReactionImpl, mk.R("r", {}, {food: 1.0}, rate=0.5))
    assert rxn.compartments is None
    assert "compartments" not in rxn.attributes()
    assert "compartments" not in repr(rxn)


def test_a_string_is_one_id_and_the_scope_round_trips():
    food, _ = _mols()
    rxn = cast(ReactionImpl, mk.R("r", {}, {food: 1.0}, rate=0.5, compartments="pond"))
    assert rxn.compartments == ("pond",)
    attrs = rxn.attributes()
    assert attrs["compartments"] == ["pond"]
    back = ReactionImpl.hydrate(attrs, molecules={"food": food}, local_name="r")
    assert back.compartments == ("pond",)
    assert "compartments=['pond']" in repr(rxn)


@pytest.mark.parametrize(
    ("scope", "match"),
    [([], "compartments is empty"), (["pond", 3], "compartment ids"), (["pond", "pond"], "repeats an id")],
)
def test_an_empty_a_non_string_or_a_repeated_scope_refuses(scope, match):
    food, _ = _mols()
    with pytest.raises(ValueError, match=match):
        mk.R("r", {}, {food: 1.0}, rate=0.5, compartments=scope)


def test_rebuilds_carry_the_scope():
    world = _world(["pond"])
    supply = world.chemistry.reactions["supply"]
    assert rebuild_reaction(supply, rate=2.0).compartments == ("pond",)
    assert rebuild_reaction(supply, compartments=None).compartments is None
    sub = world.chemistry.subgraph({"food", "supply"})
    assert sub.reactions["supply"].compartments == ("pond",)

    from alienbio.suite.perturbations import perturb_rate

    assert perturb_rate(world, "supply", 2.0).chemistry.reactions["supply"].compartments == ("pond",)


# ---- the mapping -----------------------------------------------------------


def test_names_map_to_the_trees_ids_and_an_unknown_one_refuses_at_the_world():
    assert reaction_compartment_ids("r", None, {"pond": 0}) is None
    assert reaction_compartment_ids("r", ("fish", "pond"), {"pond": 0, "fish": 1}) == [1, 0]
    with pytest.raises(ValueError, match=r"reaction 'supply' is confined to compartment 'lake'"):
        _world(["lake"])
    world = _world(["fish"])
    sim = WorldSimulatorImpl.from_chemistry(world.chemistry, world.initial_state.tree)
    by_name = {spec.name: spec for spec in sim._reactions}
    assert by_name["supply"].compartments == [1] and by_name["spoil"].compartments is None
    # from_chemistry runs the same check against a tree that lacks the id
    other = WorldImpl(world.chemistry.subgraph({"food", "spoil"}), (Compartment("lake", None, "environment", 1.0),))
    with pytest.raises(ValueError, match=r"reaction 'supply' is confined to compartment 'fish'"):
        WorldSimulatorImpl.from_chemistry(world.chemistry, other.initial_state.tree)


# ---- the dynamics ----------------------------------------------------------


def test_a_scoped_reaction_runs_only_where_it_is_named():
    final = _final(_world(["pond"]))
    comps = list(final.compartment_ids or ())
    food = list(final.molecule_ids or ()).index("food")
    assert final.get(comps.index("pond"), food) > 1.0
    assert final.get(comps.index("fish"), food) == 0.0
    assert final.get(comps.index("weed"), food) == 0.0


def test_naming_every_compartment_is_the_default_bit_for_bit():
    every = _final(_world(None))
    named = _final(_world(["pond", "fish", "weed"]))
    assert every._concentrations == named._concentrations


@needs_jax
def test_a_scoped_world_agrees_on_the_reference_and_jax():
    world = _world(["fish", "weed"])
    tree = world.initial_state.tree
    ref_sim = WorldSimulatorImpl.from_chemistry(world.chemistry, tree, dt=0.1)
    ref = ref_sim.run(world.initial_state.copy(), steps=40)[-1]
    jx = JaxWorldSimulator(tree, ref_sim._reactions, num_molecules=2, dt=0.1).run(world.initial_state.copy(), steps=40)[-1]
    for c in range(tree.num_compartments):
        for m in range(2):
            assert parity_agrees(jx.get(c, m), ref.get(c, m)), (c, m, jx.get(c, m), ref.get(c, m))
    assert ref.get(0, 0) < 1.0  # the pond only loses food: the supply runs in the children


# ---- the spec surface ------------------------------------------------------

DOC = """
chem: !Chemistry
  molecules: [food]
  reactions:
    supply: {reactants: [], products: [food], rate: 0.5, compartments: [pond]}
one: !Reaction {reactants: [], products: [food], rate: 0.5, compartments: pond}
world: !World
  chemistry: !x chem
  compartments:
    - !Compartment {id: pond, kind: environment}
    - !Compartment {id: fish, parent: pond, kind: population}
"""


def test_the_chemistry_mapping_form_and_the_reaction_constructor_take_the_key():
    values = Env.standard(seed=1).load("<scope>", text=DOC).force_all()
    assert values["chem"].reactions["supply"].compartments == ("pond",)
    assert values["one"].compartments == ("pond",)
    final = _final(values["world"], steps=10)
    assert final.get(1, 0) == 0.0 and final.get(0, 0) > 0.0


def test_an_unknown_compartment_in_a_spec_refuses_at_load():
    with pytest.raises((ExprError, ValueError), match="confined to compartment 'lake'"):
        Env.standard(seed=1).load("<scope>", text=DOC.replace("compartments: [pond]", "compartments: [lake]")).force_all()


SKELETON_DOC = """
sk: !skeleton
  root: !block
    children:
      feed: !reaction {products: [S], rate: 1.0, compartments: cell}
      gate: !reaction {reactants: [S], products: [P], rate: !q '0.3 * hill(M, 0.5, n=2)', compartments: [cell]}
      plain: !reaction {reactants: [P], products: [Q], rate: 0.2}
w: !world {skeleton: !x sk}
"""


def test_the_reaction_head_scopes_both_its_blocks():
    world = Env.standard(seed=3).load("<blocks>", text=SKELETON_DOC).force_all()["w"]
    scopes = {rid.split("/")[1]: r.compartments for rid, r in world.chemistry.reactions.items()}
    assert scopes == {"feed": ("cell",), "gate": ("cell",), "plain": None}
    assert world.chemistry.reactions["root/gate/rxn"].modifiers  # the RateLawBlock path
    with pytest.raises(ExprError, match="compartments is empty"):
        Env.standard(seed=3).load("<blocks>", text=SKELETON_DOC.replace("compartments: cell", "compartments: []")).force_all()

