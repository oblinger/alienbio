"""World: a runnable biology world (chemistry + compartment topology + initial state).

F007 coord-PR2 — the input/world side of the unified protocol model. This module
mints the biology :class:`WorldImpl` that replaces the retired neutral coordinate
shadows (``suite.types.World`` / ``Topology`` / ``Compartment`` / ``StateVector``):

- :class:`Compartment` is the topology-spec record. The compartment *tree* is
  carried as a flat tuple where each node names its ``parent`` id (root =
  ``parent is None``) — so there is no separate ``Topology`` wrapper; the tree is
  reconstructed on demand by the :func:`build_tree` free helper.
- Each :class:`Compartment` also carries its own initial ``concentrations`` (and
  ``multiplicity``), exactly as the entity-level :class:`~alienbio.bio.compartment.CompartmentImpl`
  already does. Folding the initial condition onto the compartments is what lets
  the neutral ``StateVector`` be retired with nothing lost.
- :class:`WorldImpl` bundles ``{chemistry, compartments}`` and *derives* its
  ``initial_state`` — a self-describing bio :class:`~alienbio.bio.world_state.WorldStateImpl`
  (real id axes, on a concrete :class:`~alienbio.bio.compartment_tree.CompartmentTreeImpl`)
  — at construction. Deriving (rather than storing a hand-built state) makes
  network growth correct by construction: rebuilding against a larger chemistry
  gives every added molecule an initial concentration of 0.

The molecule index order is the one :meth:`WorldSimulatorImpl.from_chemistry`
establishes (``chemistry.molecules.keys()``), so ``initial_state`` and the
simulator agree on indices without any positional reload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional

from .chemistry import ChemistryImpl
from .compartment_tree import CompartmentTreeImpl
from .flow import Flow, TransportFlux
from .world_state import WorldStateImpl

# A compartment id (a readable string, e.g. ``"cell"`` / ``"c0"``).
NodeId = str


@dataclass(frozen=True)
class Compartment:
    """One node of a world's compartment tree (root has ``parent is None``).

    The tree is expressed as a flat tuple of these records — each names its
    ``parent`` id — so no separate topology wrapper is needed. Initial condition
    rides along on the record: ``concentrations`` maps molecule name -> initial
    value, and ``multiplicity`` is the instance count (default 1.0).
    """

    id: NodeId
    parent: Optional[NodeId]
    kind: str
    volume: float
    concentrations: Mapping[str, float] = field(default_factory=dict)
    multiplicity: float = 1.0


@dataclass(frozen=True)
class Transport:
    """A cross-compartment flux spec, in real (string) ids (F016/S3).

    Blocks (e.g. ``suite.blocks.TransportBlock``) author these at ``realize``
    time, when only NodeId container refs and molecule NAMES are known (the
    concrete int-indexed tree doesn't exist yet — it's built by
    :func:`build_tree` inside :class:`WorldImpl`'s own constructor). ``WorldImpl``
    resolves each ``Transport`` into an int-indexed
    :class:`~alienbio.bio.flow.TransportFlux` using the SAME ``comp_to_int``/
    molecule-index mapping :func:`build_tree` and the molecule axis establish,
    so a flux's references always line up with however the tree is (re)built.
    """

    origin: NodeId
    dest: NodeId
    stoichiometry: Mapping[str, float]
    driver_molecule: str
    rate_constant: float = 1.0
    rate_law: str = "gradient"  # "gradient" | "first_order"
    name: str = ""


def build_tree(
    compartments: tuple[Compartment, ...],
) -> tuple[CompartmentTreeImpl, dict[NodeId, int]]:
    """Build a concrete int-indexed compartment tree from a flat compartment list.

    Returns the tree plus a ``compartment id -> CompartmentId(int)`` map. The
    single root (``parent is None``) becomes id 0; the rest are added in
    topological order (a parent is always added before its children).

    Raises:
        ValueError: if there is not exactly one root, or the parent links do not
            form a tree rooted at that node (unreachable or cyclic compartments).
    """
    roots = [c for c in compartments if c.parent is None]
    if len(roots) != 1:
        raise ValueError(
            f"a world requires exactly one root compartment (parent=None); "
            f"found {len(roots)}"
        )

    tree = CompartmentTreeImpl()
    comp_to_int: dict[NodeId, int] = {}
    root = roots[0]
    comp_to_int[root.id] = tree.add_root(root.id)

    remaining = [c for c in compartments if c.parent is not None]
    while remaining:
        still = []
        progressed = False
        for c in remaining:
            if c.parent in comp_to_int:
                comp_to_int[c.id] = tree.add_child(comp_to_int[c.parent], c.id)
                progressed = True
            else:
                still.append(c)
        if not progressed:
            raise ValueError(
                "compartment topology is not a tree rooted at the parent=None "
                "node (unreachable or cyclic compartments)"
            )
        remaining = still

    return tree, comp_to_int


class WorldImpl:
    """A runnable biology world: a :class:`ChemistryImpl` + a compartment tree.

    ``initial_state`` is derived at construction: the flat ``compartments`` list is
    turned into a concrete :class:`CompartmentTreeImpl` (:func:`build_tree`) and a
    self-describing :class:`WorldStateImpl` is populated from each compartment's
    ``concentrations`` / ``multiplicity``. The state's molecule axis is
    ``chemistry.molecules.keys()`` — the same order the simulator uses.
    """

    __slots__ = ("_chemistry", "_compartments", "_initial_state", "_flows", "_flow_objs")

    def __init__(
        self,
        chemistry: ChemistryImpl,
        compartments: tuple[Compartment, ...],
        flows: tuple[Transport, ...] = (),
    ) -> None:
        self._chemistry = chemistry
        self._compartments = tuple(compartments)

        tree, comp_to_int = build_tree(self._compartments)
        n_comp = tree.num_compartments
        int_to_comp = {v: k for k, v in comp_to_int.items()}
        comp_axis = [int_to_comp[i] for i in range(n_comp)]

        mol_ids = list(chemistry.molecules.keys())
        mol_to_int = {name: i for i, name in enumerate(mol_ids)}

        state = WorldStateImpl(
            tree=tree,
            num_molecules=len(mol_ids),
            compartment_ids=comp_axis,
            molecule_ids=mol_ids,
        )
        for c in self._compartments:
            ci = comp_to_int[c.id]
            if c.multiplicity != 1.0:
                state.set_multiplicity(ci, c.multiplicity)
            if c.volume != 1.0:
                state.set_volume(ci, c.volume)
            for mol_name, value in c.concentrations.items():
                if mol_name not in mol_to_int:
                    raise KeyError(
                        f"compartment {c.id!r} sets a concentration for molecule "
                        f"{mol_name!r}, which is not in the chemistry"
                    )
                state.set(ci, mol_to_int[mol_name], value)
        self._initial_state = state

        # Resolve each string-id Transport spec into an int-indexed
        # TransportFlux, using the SAME comp_to_int / mol_to_int mapping just
        # built above (F016/S3). ``flows`` defaults to empty, so a world that
        # never sets it is byte-identical to before this field existed.
        self._flows = tuple(flows)
        resolved_flows: list[Flow] = []
        for tr in self._flows:
            if tr.origin not in comp_to_int:
                raise KeyError(
                    f"transport {tr.name!r} references unknown origin compartment "
                    f"{tr.origin!r}"
                )
            if tr.dest not in comp_to_int:
                raise KeyError(
                    f"transport {tr.name!r} references unknown dest compartment "
                    f"{tr.dest!r}"
                )
            if tr.driver_molecule not in mol_to_int:
                raise KeyError(
                    f"transport {tr.name!r} references unknown driver molecule "
                    f"{tr.driver_molecule!r}"
                )
            stoich_int: dict[int, float] = {}
            for mol_name2, count in tr.stoichiometry.items():
                if mol_name2 not in mol_to_int:
                    raise KeyError(
                        f"transport {tr.name!r} references unknown molecule "
                        f"{mol_name2!r}"
                    )
                stoich_int[mol_to_int[mol_name2]] = count
            resolved_flows.append(
                TransportFlux(
                    origin=comp_to_int[tr.origin],
                    dest=comp_to_int[tr.dest],
                    stoichiometry=stoich_int,
                    driver_molecule=mol_to_int[tr.driver_molecule],
                    rate_constant=tr.rate_constant,
                    rate_law=tr.rate_law,
                    name=tr.name,
                )
            )
        self._flow_objs = tuple(resolved_flows)

    @property
    def chemistry(self) -> ChemistryImpl:
        """The chemistry defining molecules and reactions."""
        return self._chemistry

    @property
    def compartments(self) -> tuple[Compartment, ...]:
        """The flat compartment-tree spec (root has ``parent is None``)."""
        return self._compartments

    @property
    def initial_state(self) -> WorldStateImpl:
        """The derived self-describing initial :class:`WorldStateImpl`."""
        return self._initial_state

    @property
    def flows(self) -> tuple[Transport, ...]:
        """The raw, string-id :class:`Transport` specs this world was built
        with — the shape a fresh :class:`WorldImpl` reconstruction (e.g.
        ``suite.runner._world_from_state``) re-threads through the
        constructor, so cross-compartment flux survives a per-turn rebuild."""
        return self._flows

    @property
    def flow_objs(self) -> tuple[Flow, ...]:
        """The int-indexed, simulator-ready :class:`~alienbio.bio.flow.Flow`
        objects resolved from :attr:`flows` — what
        ``WorldSimulatorImpl.from_chemistry`` expects for its ``flows=`` arg."""
        return self._flow_objs

    def __repr__(self) -> str:
        return (
            f"WorldImpl(chemistry={self._chemistry.local_name!r}, "
            f"compartments={len(self._compartments)})"
        )
