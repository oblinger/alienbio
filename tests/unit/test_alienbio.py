"""The top-level ``alienbio`` package: what it exports after M47.7."""

from __future__ import annotations


def test_infra_exports():
    from alienbio import Dat, Entity, IO, Pegboard, mk

    assert Entity and IO and Dat and mk and Pegboard


def test_bio_exports():
    from alienbio import Chemistry, ChemistryImpl, Molecule, MoleculeImpl, Reaction, ReactionImpl, Simulator, WorldSimulatorImpl, WorldStateImpl

    assert Molecule and Reaction and Chemistry and Simulator
    assert MoleculeImpl and ReactionImpl and ChemistryImpl and WorldSimulatorImpl and WorldStateImpl


def test_the_m1_runtime_is_gone():
    import alienbio
    import alienbio.bio as bio

    for name in ("Bio", "run", "Evaluable", "hydrate", "eval_node", "expand_defaults", "action", "measurement"):
        assert not hasattr(alienbio, name), name
    # T056: the M1 single-compartment simulator, its bundle and the agent/task
    # layer went too — one runtime, one physics.
    for name in ("ReferenceSimulatorImpl", "SimulatorBase", "BioSystem", "StateImpl", "State", "MembraneFlow",
                 "AgentInterface", "Task", "run_experiment", "run_to_equilibrium", "generate_organism"):
        assert not hasattr(bio, name), name
        assert not hasattr(alienbio, name), name
