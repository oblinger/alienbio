"""The top-level ``alienbio`` package: what it exports after M47.7."""

from __future__ import annotations


def test_infra_exports():
    from alienbio import Dat, Entity, IO, Pegboard, mk

    assert Entity and IO and Dat and mk and Pegboard


def test_bio_exports():
    from alienbio import Chemistry, ChemistryImpl, Molecule, MoleculeImpl, Reaction, ReactionImpl, Simulator, State

    assert Molecule and Reaction and Chemistry and State and Simulator
    assert MoleculeImpl and ReactionImpl and ChemistryImpl


def test_the_m1_runtime_is_gone():
    import alienbio

    for name in ("Bio", "run", "Evaluable", "hydrate", "eval_node", "expand_defaults", "action", "measurement"):
        assert not hasattr(alienbio, name), name
