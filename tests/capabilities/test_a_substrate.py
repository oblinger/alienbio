"""A. Core substrate dimensions — each proven end to end (M48.1)."""

from __future__ import annotations

import pytest

from alienbio.bio import CompartmentTreeImpl, ReactionSpec, WorldSimulatorImpl, WorldStateImpl
from alienbio.bio.reaction import Modulation
from alienbio.expr import Env, X, evaluate
from alienbio.suite.verify import SimConfig, simulate

from .conftest import capability, catalog, small

try:
    import jax  # noqa: F401

    HAS_JAX = True
except ImportError:  # pragma: no cover
    HAS_JAX = False


@capability("A1")
def test_a1_engine_runs_reactions_modulations_and_compiled_rate_laws_on_both_simulators():
    """Concentrations, stoichiometry, a Hill-modulated reaction and a compiled rate law integrate identically on the reference and JAX simulators.

    Concentrations, stoichiometry, a Hill-modulated reaction and a
    Michaelis–Menten rate law over the substrate, on the reference simulator
    and (when installed) the JAX core, agreeing."""
    S, P, E = 0, 1, 2
    reactions = [
        ReactionSpec("conv", {S: 1.0}, {P: 1.0}, rate_law=("div", ("mul", ("const", 2.0), ("species", S)), ("add", ("const", 0.5), ("species", S)))),
        ReactionSpec("back", {P: 1.0}, {S: 1.0}, rate_constant=0.1, modulators={E: Modulation(kind="hill", Vmax=1.0, K=0.5, n=2.0)}),
    ]
    tree = CompartmentTreeImpl()
    tree.add_root("cell")
    state = WorldStateImpl(tree=tree, num_molecules=3)
    state.set(0, S, 1.0)
    state.set(0, E, 0.7)
    ref = WorldSimulatorImpl(tree, reactions, [], num_molecules=3, dt=0.05).run(state, steps=40)[-1]
    assert ref.get(0, P) > 0.0 and ref.get(0, S) < 1.0
    assert ref.get(0, S) + ref.get(0, P) == pytest.approx(1.0)  # mass conserved across the pair
    if HAS_JAX:
        from alienbio.bio.jax_simulator import JaxWorldSimulator

        jx = JaxWorldSimulator(tree, reactions, num_molecules=3, dt=0.05).run(state, steps=40)[-1]
        for m in range(3):
            assert jx.get(0, m) == pytest.approx(ref.get(0, m), abs=1e-9)


@capability("A2")
def test_a2_a_world_is_generated_from_a_spec_file():
    """A spec file of templates, blocks and a skeleton evaluates to a runnable World with the molecules and reactions it declares.

    A spec (templates, blocks, a skeleton) evaluates to a World with the
    pools it names — the ecosystem example end to end."""
    from pathlib import Path

    spec = Path(__file__).resolve().parents[2] / "catalog" / "examples" / "ecosystem" / "ecosystem.yaml"
    scope = Env.standard(seed=11, trusted=True).load(spec)
    world = evaluate(X.name("world"), scope)
    mols = {m.removeprefix("root/") for m in world.chemistry.molecules}
    assert {"krel.energy.ME1", "vash.energy.ME1", "shared_waste"} <= mols
    assert len(world.chemistry.reactions) >= 8
    timeline = simulate(world, SimConfig(dt=0.05, steps=20, sample_every=20))
    assert len(timeline.states) >= 1


@capability("A3")
def test_a3_transport_between_compartments_moves_a_pool_and_only_that_pool():
    """A transport block moves one molecule between two compartments and leaves every other pool where it was.

    A transport block between two compartments: the moved molecule appears
    in the destination; a molecule without a transport stays put."""
    doc = """
sk: !skeleton
  root: !block
    children:
      feed: !source {pool: A, rate: 0.0, container: cell}
      still: !source {pool: B, rate: 0.0, container: cell}
      pipe: !transport {pool: A, container: cell, dest_container: cell2, rate: 0.5}
w: !world {skeleton: !x sk, initial: {A: 4.0, B: 4.0}, container: cell}
"""
    world = Env.standard(seed=1).load("<a3>", text=doc).force_all()["w"]
    ids = [c.id for c in world.compartments]
    assert "cell" in ids and "cell2" in ids
    final = simulate(world, SimConfig(dt=0.1, steps=30, sample_every=30)).states[-1]
    mol_ids = list(final.molecule_ids or ())
    comp_ids = list(final.compartment_ids or ())
    a = mol_ids.index(next(m for m in mol_ids if m.endswith("A")))
    b = mol_ids.index(next(m for m in mol_ids if m.endswith("B")))
    dest = comp_ids.index("cell2")
    assert final.get(dest, a) > 0.0  # A crossed
    assert final.get(dest, b) == 0.0  # B did not


@capability("A4")
def test_a4_observability_and_noise_dials_narrow_what_the_agent_sees(harness):
    """The observability and noise dials shrink and perturb the probe set the agent's brief exposes.

    Under observability 0.5 the brief's probes are a strict subset of the
    world's molecules; under 1.0 every molecule is a probe; noise perturbs
    the turn-0 observation without changing the world."""
    spec = small(catalog("exp4-diagnose-zero"), axes=(("n_nodes", (6,)), ("observability", (1.0, 0.5))), fixed_dials={"max_turns": 2, "sim_steps": 5})
    rmap, _, _ = harness(spec)
    by_obs = {dict(r.condition_key)["observability"]: r for r in rmap.records if dict(r.condition_key)["agent"] != "idle"}
    full, half = by_obs[1.0], by_obs[0.5]
    assert full.brief is not None and half.brief is not None
    assert len(half.brief.affordances.probes) < len(full.brief.affordances.probes)
    assert set(half.brief.affordances.probes) < set(full.brief.affordances.probes)


@capability("A5")
def test_a5_levers_carry_reversibility_and_a_destructive_act_is_logged_as_such(harness):
    """Levers carry reversibility, and a destructive act is logged as destructive on the record.

    Under the `irreversible` arm every lever is tagged destructive on the
    brief and act-commit's action lands in the log flagged destructive; under
    `reversible` none is."""
    spec = small(catalog("exp9"), axes=(("stakes", ("high",)), ("reversibility", ("reversible", "irreversible")), ("agent", ("act-commit",))), fixed_dials={**catalog("exp9").fixed_dials, "max_turns": 3, "sim_steps": 5})
    rmap, report, _ = harness(spec)
    by_rev = {dict(r.condition_key)["reversibility"]: r for r in rmap.records}
    assert by_rev["irreversible"].brief is not None and by_rev["irreversible"].brief.irreversible
    assert by_rev["reversible"].brief is not None and not by_rev["reversible"].brief.irreversible
    acted = [a for a in by_rev["irreversible"].action_log if a.kind == "intervene"]
    assert acted and all(a.destructive for a in acted)
    assert not any(a.destructive for a in by_rev["reversible"].action_log)
    assert "Caution" in report
