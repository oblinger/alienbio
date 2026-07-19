"""Unit tests for the F013 Skeleton subsystem core.

Exercises ``Skeleton.materialize`` / ``validate`` / ``oracle`` /
``indirection_depth`` end-to-end via ONE minimal, in-test concrete
``SkeletonBlock`` subclass (``_BoundaryBlock`` — a boundary reaction over its
own single port, ``∅ -> pool`` for an OUT port, ``pool -> ∅`` for an IN port).
Used twice: as a source (SUPPLY) and as a sink/crux (SINK) that shares one pool
with the source via a :class:`PoolBinding` on the root — the "two-primitive
skeleton" the F013 plan calls for (source -> shared pool <- sink). The real
block catalog is F014; this is a smoke test of the recursive core only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, cast

import pytest

from alienbio.bio.molecule import MoleculeImpl
from alienbio.bio.reaction import ReactionImpl
from alienbio.infra.mk import mk
from alienbio.suite.dist import Seed
from alienbio.suite.skeleton import (
    Fragment,
    Port,
    PortDir,
    PoolBinding,
    Provenance,
    Role,
    Skeleton,
    SkeletonBlock,
    SkeletonError,
    final_amount,
)
from alienbio.suite.types import Timeline
from alienbio.suite.verify import SimConfig


@dataclass(frozen=True)
class _BoundaryBlock(SkeletonBlock):
    """Test-only primitive (not part of the F014 catalog): one boundary
    reaction over its own single port. An OUT port emits ``∅ -> pool`` (a
    source); an IN port emits ``pool -> ∅`` (a sink). Crux-bearing:
    ``ground_truth`` reads the final amount of its own pool.
    """

    rate: float = 1.0

    def realize(self, seed: Seed, ns: str, bound: Mapping[str, MoleculeImpl]) -> Fragment:
        port = self.ports[0]
        molecule = bound[port.name]
        container = port.container or "cell"
        rxn_id = f"{ns}/flow"
        if port.direction is PortDir.OUT:
            reaction = cast(ReactionImpl, mk.R(rxn_id, {}, {molecule: 1.0}, rate=self.rate))
        else:
            reaction = cast(ReactionImpl, mk.R(rxn_id, {molecule: 1.0}, {}, rate=self.rate))
        return Fragment(
            molecules={molecule.name: molecule},
            reactions={rxn_id: reaction},
            provenance=(Provenance(rxn_id, container),),
        )

    def ground_truth(self, timeline: Timeline) -> Any:
        if not self.resolved_ports:
            raise SkeletonError(f"{self.name!r} has no resolved_ports; call materialize() first")
        mol_id = self.resolved_ports[self.ports[0].name]
        return final_amount(timeline, mol_id)


def _build_skeleton(*, source_rate: float = 5.0, sink_rate: float = 0.5) -> Skeleton:
    """A tiny two-primitive skeleton: source -> shared pool <- sink."""
    source = _BoundaryBlock(
        name="source",
        role=Role.SUPPLY,
        ports=(Port("out", None, PortDir.OUT),),
        rate=source_rate,
    )
    sink = _BoundaryBlock(
        name="sink",
        role=Role.SINK,
        ports=(Port("in", None, PortDir.IN),),
        rate=sink_rate,
    )
    root = SkeletonBlock(
        name="root",
        role=Role.SUPPLY,
        children=(source, sink),
        pool_bindings=(PoolBinding("source.out", "sink.in"),),
    )
    return Skeleton(
        root=root,
        control_surface=("root/source.out",),
        crux="root/sink",
    )


def test_materialize_builds_a_world_with_one_shared_pool() -> None:
    skeleton = _build_skeleton()
    world = skeleton.materialize(Seed(1))

    # Exactly one shared pool -> one molecule; two boundary reactions.
    assert len(world.chemistry.molecules) == 1
    assert len(world.chemistry.reactions) == 2
    assert skeleton.chemistry is world.chemistry


def test_bound_ports_resolve_to_one_shared_molecule_object() -> None:
    """The object-vs-name aliasing fix: source's and sink's reactions must
    reference the exact same MoleculeImpl, not two same-named objects."""
    skeleton = _build_skeleton()
    skeleton.materialize(Seed(2))

    source_block, sink_block = skeleton.root.children
    source_rxn = next(iter(source_block.provenance))
    sink_rxn = next(iter(sink_block.provenance))
    chem = skeleton.chemistry
    assert chem is not None
    source_mol = next(iter(chem.reactions[source_rxn.reaction_id].products))
    sink_mol = next(iter(chem.reactions[sink_rxn.reaction_id].reactants))
    assert source_mol is sink_mol

    # resolved_ports agree on the same molecule id from both sides.
    assert source_block.resolved_ports["out"] == sink_block.resolved_ports["in"]


def test_validate_passes_on_a_well_formed_skeleton() -> None:
    skeleton = _build_skeleton()
    skeleton.materialize(Seed(3))
    assert skeleton.validate() is None


def test_validate_requires_materialize_first() -> None:
    skeleton = _build_skeleton()
    with pytest.raises(SkeletonError):
        skeleton.validate()


def test_validate_flags_a_producer_with_no_consumer() -> None:
    """A lone, unbound OUT port has no bounded fate -> validate() reports it."""
    source_only = SkeletonBlock(
        name="root",
        role=Role.SUPPLY,
        children=(
            _BoundaryBlock(
                name="source",
                role=Role.SUPPLY,
                ports=(Port("out", None, PortDir.OUT),),
            ),
        ),
    )
    skeleton = Skeleton(root=source_only)
    skeleton.materialize(Seed(4))
    error = skeleton.validate()
    assert error is not None
    assert "bounded fate" in str(error)


def test_oracle_reads_the_crux_ground_truth() -> None:
    skeleton = _build_skeleton(source_rate=5.0, sink_rate=0.5)
    answer = skeleton.oracle(Seed(5), SimConfig(dt=0.1, steps=200, sample_every=10))

    assert isinstance(answer, float)
    assert answer > 0.0

    # The crux's ground truth must equal reading the same pool directly off
    # the simulated timeline (the oracle isn't reinventing a different number).
    from alienbio.suite.verify import simulate

    world = skeleton.materialize(Seed(5))
    timeline = simulate(world, SimConfig(dt=0.1, steps=200, sample_every=10), Seed(5).child("oracle-sim"))
    mol_id = next(iter(world.chemistry.molecules))
    assert answer == pytest.approx(final_amount(timeline, mol_id))


def test_oracle_is_deterministic_in_seed() -> None:
    skeleton_a = _build_skeleton()
    skeleton_b = _build_skeleton()
    assert skeleton_a.oracle(Seed(6)) == pytest.approx(skeleton_b.oracle(Seed(6)))


def test_indirection_depth_of_directly_bound_source_and_sink_is_one() -> None:
    skeleton = _build_skeleton()
    assert skeleton.indirection_depth() == 1


def test_indirection_depth_requires_control_surface() -> None:
    source = _BoundaryBlock(
        name="source", role=Role.SUPPLY, ports=(Port("out", None, PortDir.OUT),)
    )
    sink = _BoundaryBlock(name="sink", role=Role.SINK, ports=(Port("in", None, PortDir.IN),))
    root = SkeletonBlock(
        name="root",
        role=Role.SUPPLY,
        children=(source, sink),
        pool_bindings=(PoolBinding("source.out", "sink.in"),),
    )
    skeleton = Skeleton(root=root, crux="root/sink")  # no control_surface
    with pytest.raises(SkeletonError):
        skeleton.indirection_depth()


def test_walk_is_pre_order() -> None:
    skeleton = _build_skeleton()
    names = [b.name for b in skeleton.root.walk()]
    assert names == ["root", "source", "sink"]


def test_base_block_ground_truth_not_implemented() -> None:
    plain = SkeletonBlock(name="root", role=Role.SUPPLY)
    with pytest.raises(NotImplementedError):
        plain.ground_truth(Timeline(times=(), states=()))
