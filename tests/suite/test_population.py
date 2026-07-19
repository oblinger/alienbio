"""Tests for F017 — PopulationBlock + count-based rate laws: modeling
biological populations as COUNTS on the compartment ``multiplicity`` axis.

Three tiers: (1) the engine core — hand-built worlds exercising
``PerCapitaGrowth`` / ``PerCapitaDeath`` / ``CountFlow`` directly (the
acceptance gate: multiplicity actually moves, the no-population-laws fast
path is byte-identical, coupled growth conserves ``total_quantity`` while
uncoupled growth trips the F012 amount-canary, growth self-limits as the
resource pool draws down, count flow conserves headcount); (2)
``PopulationBlock`` materialized/validated/simulated via the oracle; (3) one
end-to-end ``suite.runner.run`` regression guard confirming population
dynamics survive ``_world_from_state``'s per-turn rebuild.
"""

from __future__ import annotations

import pytest

from alienbio.bio.compartment_tree import CompartmentTreeImpl
from alienbio.bio.conservation import total_quantity
from alienbio.bio.population import CountFlow, PerCapitaDeath, PerCapitaGrowth
from alienbio.bio.world_simulator import WorldSimulatorImpl
from alienbio.bio.world_state import WorldStateImpl
from alienbio.suite.agent import Commit, ScriptedAgent, Wait
from alienbio.suite.blocks import PopulationBlock
from alienbio.suite.dist import Constant, Seed
from alienbio.suite.runner import run
from alienbio.suite.skeleton import Role, Skeleton, SkeletonBlock
from alienbio.suite.types import (
    Answer,
    CarveResult,
    Motif,
    OutcomeObjective,
    Question,
    TaskInstance,
)
from alienbio.suite.verify import SimConfig

_SIM_CFG = SimConfig(dt=0.05, steps=200, sample_every=50)


# ═══════════════════════════════════════════════════════════════════════════
# Engine core (the acceptance gate) — hand-built PerCapitaGrowth/Death/
# CountFlow, no skeleton
# ═══════════════════════════════════════════════════════════════════════════


def _growth_sim(
    rate_constant: float,
    stoich: float,
    resource_conc: float = 1000.0,
    biomass_conc: float = 0.0,
    pop_mult: float = 5.0,
    dt: float = 0.1,
) -> tuple[WorldSimulatorImpl, WorldStateImpl, int, int]:
    """A two-compartment (``pop`` -> ``pool``) fixture: molecule 0 is the
    population's own fixed-per-instance ``biomass`` (born-full, Q4=A), molecule
    1 is the ``resource`` pool ``pop``'s growth draws from."""
    tree = CompartmentTreeImpl()
    pop = tree.add_root("pop")
    pool = tree.add_child(pop, "pool")
    state = WorldStateImpl(
        tree=tree, num_molecules=2, compartment_ids=["pop", "pool"], molecule_ids=["biomass", "resource"]
    )
    state.set_multiplicity(pop, pop_mult)
    state.set(pop, 0, biomass_conc)
    state.set(pool, 1, resource_conc)
    growth = PerCapitaGrowth(
        compartment=pop, resource_compartment=pool, resource=1, stoich=stoich, rate_constant=rate_constant
    )
    sim = WorldSimulatorImpl(
        tree=tree, reactions=[], flows=[], num_molecules=2, dt=dt, population_laws=[growth]
    )
    return sim, state, pop, pool


def test_per_capita_growth_grows_multiplicity_over_a_run() -> None:
    """The first-ever multiplicity mutation: growth increases it monotonically
    while the resource is plentiful."""
    sim, state, pop, _pool = _growth_sim(rate_constant=0.01, stoich=0.0, resource_conc=1000.0, pop_mult=5.0)
    history = sim.run(state, steps=50, sample_every=10)
    mults = [s.get_multiplicity(pop) for s in history]

    assert mults[-1] > mults[0]
    assert all(b >= a - 1e-9 for a, b in zip(mults, mults[1:]))


def test_per_capita_death_shrinks_multiplicity() -> None:
    tree = CompartmentTreeImpl()
    pop = tree.add_root("pop")
    state = WorldStateImpl(tree=tree, num_molecules=1, compartment_ids=["pop"], molecule_ids=["biomass"])
    state.set_multiplicity(pop, 20.0)
    death = PerCapitaDeath(compartment=pop, rate_constant=0.05)
    sim = WorldSimulatorImpl(tree=tree, reactions=[], flows=[], num_molecules=1, dt=0.1, population_laws=[death])

    history = sim.run(state, steps=50, sample_every=10)
    mults = [s.get_multiplicity(pop) for s in history]

    assert mults[-1] < mults[0]
    assert all(b <= a + 1e-9 for a, b in zip(mults, mults[1:]))
    assert mults[-1] >= 0.0


def test_no_population_laws_is_a_noop_regression() -> None:
    """Existing (population-law-free) worlds: multiplicity stays static —
    the fast path every pre-F017 world must keep taking."""
    tree = CompartmentTreeImpl()
    a = tree.add_root("a")
    state = WorldStateImpl(tree=tree, num_molecules=1, compartment_ids=["a"], molecule_ids=["x"])
    state.set_multiplicity(a, 7.0)
    state.set(a, 0, 3.0)
    sim = WorldSimulatorImpl(tree=tree, reactions=[], flows=[], num_molecules=1, dt=1.0)

    new_state = sim.step(state)

    assert new_state.get_multiplicity(a) == 7.0
    assert new_state.get(a, 0) == 3.0


# ═══════════════════════════════════════════════════════════════════════════
# Conservation red-then-green — the key gate (F017 Q3/Q4)
# ═══════════════════════════════════════════════════════════════════════════


def _per_index() -> list[dict[str, float]]:
    """Both molecules (biomass, resource) carry the SAME conserved label."""
    return [{"n": 1.0}, {"n": 1.0}]


def test_conservation_coupled_growth_keeps_total_quantity_invariant() -> None:
    """stoich == volume * biomass_conc (both default to 1.0): every new
    instance's biomass is exactly funded by the resource draw."""
    sim, state, _pop, _pool = _growth_sim(
        rate_constant=0.02, stoich=1.0, resource_conc=200.0, biomass_conc=1.0, pop_mult=5.0, dt=0.05
    )
    history = sim.run(state, steps=200, sample_every=20)
    totals = [total_quantity(s, _per_index())["n"] for s in history]

    assert all(t == pytest.approx(totals[0], abs=1e-6) for t in totals)


def test_conservation_uncoupled_growth_trips_the_amount_canary() -> None:
    """stoich == 0.0: growth still happens (biomass accrues at ``pop``) but
    nothing funds it from ``pool`` — matter created from nothing."""
    sim, state, _pop, _pool = _growth_sim(
        rate_constant=0.02, stoich=0.0, resource_conc=200.0, biomass_conc=1.0, pop_mult=5.0, dt=0.05
    )
    history = sim.run(state, steps=200, sample_every=20)
    totals = [total_quantity(s, _per_index())["n"] for s in history]

    assert totals[-1] > totals[0] + 1e-6


def test_growth_plateaus_as_resource_pool_draws_down() -> None:
    """Logistic boundedness from nutrient limitation alone — no arbitrary cap."""
    sim, state, pop, pool = _growth_sim(
        rate_constant=0.05, stoich=1.0, resource_conc=20.0, biomass_conc=1.0, pop_mult=2.0, dt=0.05
    )
    history = sim.run(state, steps=3000, sample_every=100)
    mults = [s.get_multiplicity(pop) for s in history]
    resources = [s.get(pool, 1) for s in history]

    assert mults[-1] > mults[0]  # it did grow
    tail_growth = (mults[-1] - mults[-2]) / max(mults[-2], 1e-9)
    assert tail_growth < 0.01  # plateaued
    assert resources[-1] < resources[0]  # resource drew down
    assert resources[-1] >= -1e-6  # never negative


# ═══════════════════════════════════════════════════════════════════════════
# CountFlow — size-class headcount conservation (F017 Q2=A)
# ═══════════════════════════════════════════════════════════════════════════


def test_count_flow_conserves_headcount_between_size_classes() -> None:
    tree = CompartmentTreeImpl()
    juvenile = tree.add_root("juvenile")
    adult = tree.add_child(juvenile, "adult")
    state = WorldStateImpl(
        tree=tree, num_molecules=1, compartment_ids=["juvenile", "adult"], molecule_ids=["x"]
    )
    state.set_multiplicity(juvenile, 100.0)
    state.set_multiplicity(adult, 0.0)
    maturation = CountFlow(origin=juvenile, dest=adult, rate_constant=0.05)
    sim = WorldSimulatorImpl(
        tree=tree, reactions=[], flows=[], num_molecules=1, dt=0.5, population_laws=[maturation]
    )

    history = sim.run(state, steps=50, sample_every=10)
    totals = [s.get_multiplicity(juvenile) + s.get_multiplicity(adult) for s in history]

    assert all(t == pytest.approx(totals[0], abs=1e-9) for t in totals)
    assert history[-1].get_multiplicity(adult) > 0.0
    assert history[-1].get_multiplicity(juvenile) < 100.0


def test_count_flow_is_seed_deterministic() -> None:
    """No randomness involved, but the fixture is built twice to prove the
    same deterministic trajectory (mirrors the transport determinism guard)."""

    def _run() -> list[float]:
        tree = CompartmentTreeImpl()
        a = tree.add_root("a")
        b = tree.add_child(a, "b")
        state = WorldStateImpl(tree=tree, num_molecules=1, compartment_ids=["a", "b"], molecule_ids=["x"])
        state.set_multiplicity(a, 50.0)
        flow = CountFlow(origin=a, dest=b, rate_constant=0.1)
        sim = WorldSimulatorImpl(
            tree=tree, reactions=[], flows=[], num_molecules=1, dt=0.2, population_laws=[flow]
        )
        history = sim.run(state, steps=20, sample_every=5)
        return [s.get_multiplicity(b) for s in history]

    assert _run() == _run()


# ═══════════════════════════════════════════════════════════════════════════
# PopulationBlock — materialize / validate / oracle
# ═══════════════════════════════════════════════════════════════════════════


def _build_population_skeleton(
    growth_stoich: float = 1.0, growth_rate: float = 0.02, death_rate: float = 0.0
) -> Skeleton:
    colony = PopulationBlock.make(
        "colony",
        initial_multiplicity=5.0,
        resource_initial=500.0,
        growth_rate=Constant(growth_rate),
        growth_stoich=growth_stoich,
        death_rate=Constant(death_rate),
    )
    root = SkeletonBlock(name="root", role=Role.POPULATION, children=(colony,))
    return Skeleton(root=root, crux="root/colony")


def test_population_block_materializes_and_validates() -> None:
    skeleton = _build_population_skeleton()
    skeleton.materialize(Seed(1))
    assert skeleton.validate() is None


def test_population_block_records_provenance_with_a_population_law_id() -> None:
    skeleton = _build_population_skeleton()
    skeleton.materialize(Seed(1))
    colony = next(c for c in skeleton.root.children if c.name == "colony")

    assert len(colony.provenance) == 1
    prov = colony.provenance[0]
    assert prov.container_id == "root/colony/pop"
    assert prov.population_law_id  # non-empty: this block's causal handle is a population law
    assert prov.reaction_id == ""


def test_population_block_oracle_reads_grown_multiplicity() -> None:
    skeleton = _build_population_skeleton(growth_stoich=1.0, growth_rate=0.02)
    result = skeleton.oracle(Seed(2), sim_cfg=SimConfig(dt=0.05, steps=400, sample_every=100))
    assert result > 5.0


def test_population_block_is_deterministic_for_a_given_seed() -> None:
    s1 = _build_population_skeleton().oracle(Seed(7), sim_cfg=SimConfig(dt=0.05, steps=200, sample_every=50))
    s2 = _build_population_skeleton().oracle(Seed(7), sim_cfg=SimConfig(dt=0.05, steps=200, sample_every=50))
    assert s1 == s2


def test_population_block_conserves_total_quantity_when_coupled() -> None:
    """End-to-end conservation gate through the block: default
    growth_stoich=1.0 matches volume(1.0) * biomass_conc(1.0)."""
    skeleton = _build_population_skeleton(growth_stoich=1.0, growth_rate=0.02)
    world = skeleton.materialize(Seed(3))
    from alienbio.suite.verify import simulate

    timeline = simulate(world, SimConfig(dt=0.05, steps=200, sample_every=20))
    mol_ids = timeline.states[-1].molecule_ids
    assert mol_ids is not None
    per_index = [{"n": 1.0} for _ in mol_ids]
    totals = [total_quantity(s, per_index)["n"] for s in timeline.states]
    assert all(t == pytest.approx(totals[0], abs=1e-6) for t in totals)


def test_population_block_uncoupled_growth_trips_the_amount_canary() -> None:
    skeleton = _build_population_skeleton(growth_stoich=0.0, growth_rate=0.02)
    world = skeleton.materialize(Seed(3))
    from alienbio.suite.verify import simulate

    timeline = simulate(world, SimConfig(dt=0.05, steps=200, sample_every=20))
    mol_ids = timeline.states[-1].molecule_ids
    assert mol_ids is not None
    per_index = [{"n": 1.0} for _ in mol_ids]
    totals = [total_quantity(s, per_index)["n"] for s in timeline.states]
    assert totals[-1] > totals[0] + 1e-6


# ═══════════════════════════════════════════════════════════════════════════
# End-to-end: population dynamics survive suite.runner.run's per-turn rebuild
# ═══════════════════════════════════════════════════════════════════════════


def test_population_persists_across_scenario_runner_turns() -> None:
    """Regression guard for the ``_world_from_state`` population_laws-carry-
    forward fix: if population_laws weren't threaded through the per-turn
    rebuild, growth would silently stop after turn 0."""
    skeleton = _build_population_skeleton(growth_stoich=0.0, growth_rate=0.05)
    world = skeleton.materialize(Seed(11))

    task = TaskInstance(
        archetype="population_probe",
        world="world0",
        skeleton=CarveResult(motif=Motif(roles=(), edges=()), binding={}),
        objective=OutcomeObjective(scorer=lambda trace: 1.0, target=None),
        question=Question(structured=set(), kind="node_set"),
        setup={},
    )
    policy = (
        Wait(duration=1.0),
        Wait(duration=1.0),
        Wait(duration=1.0),
        Commit(answer=Answer(value=0.0, kind="scalar")),
    )
    agent = ScriptedAgent(policy, seed=Seed(0))
    record = run(
        world, task, agent, {}, Seed(12), sim_cfg=SimConfig(dt=0.05, steps=5, sample_every=5)
    )

    assert record.terminal_reason == "committed"
    states = record.final_timeline.states
    mults = []
    for s in states:
        assert s.compartment_ids is not None
        ci = s.compartment_ids.index("root/colony/pop")
        mults.append(s.get_multiplicity(ci))

    # Strictly increasing across every sampled point, INCLUDING the last two
    # turn boundaries — if growth had died after turn 0/1, the tail would be
    # flat instead of still climbing.
    assert all(b > a for a, b in zip(mults, mults[1:]))
    assert mults[-1] > mults[-2] > mults[-3]
