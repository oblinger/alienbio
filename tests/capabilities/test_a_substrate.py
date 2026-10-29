"""A. Core substrate dimensions — each proven end to end (M48.1)."""

from __future__ import annotations

import json

import pytest

from alienbio.bio import CompartmentTreeImpl, ReactionSpec, WorldSimulatorImpl, WorldStateImpl
from alienbio.bio.reaction import Modulation
from alienbio.expr import Env, X, evaluate
from alienbio.suite.agent import Answer, Commit, ReasoningStep
from alienbio.suite.experiment import AGENTS
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
    """A spec file of templates, blocks and a skeleton evaluates to a World with the pools and reactions it declares, whose seeded mass moves.

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
    # the world is live (T091 E12: it carried no mass and never moved): the
    # seeded energy cycles drain and pools nobody seeded fill
    first, last = timeline.states[0], timeline.states[-1]
    ids = list(last.molecule_ids or ())
    seeded = {i for i, m in enumerate(ids) if first.get(0, i) > 0.0}
    assert seeded and all(last.get(0, i) < first.get(0, i) for i in seeded)
    assert any(last.get(0, i) > 0.0 for i in range(len(ids)) if i not in seeded)


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


class _ObservationEcho:
    """Records the turn-0 observation it was handed as its one reasoning step, then commits nothing."""

    def act(self, observation):
        seen = [sorted((str(k), float(v)) for k, v in compartment.items()) for compartment in observation]
        return Commit(answer=Answer(value=[], kind="json")), (ReasoningStep(kind="policy", content=json.dumps(seen), refs=()),)


@capability("A4")
def test_a4_observability_and_noise_dials_narrow_what_the_agent_sees(harness, monkeypatch):
    """Observability shrinks the brief's probe set; observation noise perturbs what the agent is handed while the world stays the same.

    Under observability 0.5 the brief's probes are a strict subset of the
    world's molecules; under 1.0 every molecule is a probe; observation
    noise changes the turn-0 observation an agent receives while the final
    state and the oracle stay equal (T091 E6: the noise arm was never run)."""
    spec = small(catalog("exp04-diagnose-zero"), axes=(("n_nodes", (6,)), ("observability", (1.0, 0.5))), fixed_dials={"max_turns": 2, "sim_steps": 5})
    rmap, _, _ = harness(spec)
    by_obs = {dict(r.condition_key)["observability"]: r for r in rmap.records if dict(r.condition_key)["agent"] != "idle"}
    full, half = by_obs[1.0], by_obs[0.5]
    assert full.brief is not None and half.brief is not None
    assert len(half.brief.affordances.probes) < len(full.brief.affordances.probes)
    assert set(half.brief.affordances.probes) < set(full.brief.affordances.probes)

    monkeypatch.setitem(AGENTS, "observation-echo", lambda spec: lambda seed, dials: _ObservationEcho())
    noisy = small(
        catalog("exp04-diagnose-zero"),
        axes=(("n_nodes", (6,)), ("observability", (1.0,)), ("observation_noise", (0.0, 0.3)), ("agent", ("observation-echo",))),
        fixed_dials={"max_turns": 2, "sim_steps": 5},
    )
    rmap, _, _ = harness(noisy)
    by_noise = {dict(r.condition_key)["observation_noise"]: r for r in rmap.records}
    quiet, loud = by_noise[0.0], by_noise[0.3]
    seen = {k: json.loads(r.deliberation_trace.steps[0].content) for k, r in by_noise.items()}
    assert [[name for name, _ in c] for c in seen[0.0]] == [[name for name, _ in c] for c in seen[0.3]]  # same probes
    assert seen[0.0] != seen[0.3]  # the noise reached what the agent was handed
    assert quiet.final_state == loud.final_state and quiet.oracle == loud.oracle  # the world did not change


@capability("A5")
def test_a5_levers_carry_reversibility_and_a_destructive_act_is_logged_as_such(harness):
    """Levers carry reversibility, and a destructive act is logged as destructive on the record.

    Under the `irreversible` arm every lever is tagged destructive on the
    brief and act-commit's action lands in the log flagged destructive; under
    `reversible` none is."""
    spec = small(catalog("exp09"), axes=(("stakes", ("high",)), ("reversibility", ("reversible", "irreversible")), ("agent", ("act-commit",))), fixed_dials={**catalog("exp09").fixed_dials, "max_turns": 3, "sim_steps": 5})
    rmap, report, _ = harness(spec)
    # exp09 declares idle_baseline, so the act-commit axis carries its idle twin (T091).
    by_rev = {dict(r.condition_key)["reversibility"]: r for r in rmap.records if dict(r.condition_key)["agent"] != "idle"}
    assert by_rev["irreversible"].brief is not None and by_rev["irreversible"].brief.irreversible
    assert by_rev["reversible"].brief is not None and not by_rev["reversible"].brief.irreversible
    acted = [a for a in by_rev["irreversible"].action_log if a.kind == "intervene"]
    assert acted and all(a.destructive for a in acted)
    assert not any(a.destructive for a in by_rev["reversible"].action_log)
    assert "Caution" in report
