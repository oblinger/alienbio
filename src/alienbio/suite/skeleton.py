"""Skeleton subsystem core (F013) — the recursive composition machinery.

A :class:`Skeleton` is a **recursive tree of `SkeletonBlock`s**, woven two ways:
**horizontally**, by sharing **pool-ports** (a :class:`PoolBinding` names two
ports as one shared pool); and **vertically**, a block's ``realize`` expands
into its ``children``, binding its own ports down to theirs. From that tree the
skeleton **constructs a `ChemistryImpl`** and every block keeps **provenance** —
links to the exact reactions/containers it produced — so ``oracle`` can climb
the tree to read ground truth. All types are frozen dataclasses; construction
is pure and seed-deterministic (see :mod:`alienbio.suite.dist`).

This module builds ONLY the core: :class:`Port` / :class:`PoolBinding`, the
:class:`SkeletonBlock` abstract base, and the :class:`Skeleton` composite with
``materialize`` / ``validate`` / ``oracle`` / ``indirection_depth``. It carries
**no concrete `…Block` catalog** — that is F014. ``SkeletonBlock``'s default
``realize`` returns an empty :class:`Fragment` (a pure composition/"pattern"
node whose content lives entirely in its children); primitive blocks override
``realize`` to emit actual reactions (see the ``…Block`` roster,
[[ABIO Skeleton Block Catalog]]).

Ratified decisions this module follows (F013 § Open Questions):

- **Q1=A** — pool binding is an explicit ``pool_bindings`` list carried by the
  parent block; each :class:`PoolBinding` pairs two **local** refs of the form
  ``"self.<port>"`` (this block's own port) or ``"<child_name>.<port>"`` (a
  named direct child's port) — resolved top-down, one level at a time, during
  :func:`_realize_tree`.
- **Q2=B** — ``crux`` / ``control_surface`` reference their targets by a
  stable, ``/``-separated **path of block names from the root**
  (:data:`BlockRef`), with ports appended as ``.port_name`` (:data:`PortRef`) —
  never an object handle, so a ``dataclasses.replace`` during construction
  cannot silently invalidate a stored reference.
- **Q3=A** — :class:`Skeleton` is a thin **wrapper** (``root``, ``chemistry``,
  ``control_surface``, ``crux``), not a subclass of the root block.
- **Q4=A** — functional only: authoring/editing a tree goes through
  ``dataclasses.replace``; no mutable builder yet.

Two deliberate, documented extensions beyond the literal Data Model field
tables (both additive, both needed to make ``oracle``/``validate`` work without
re-deriving information the frozen ``Provenance`` 2-tuple ``(reaction_id,
container_id)`` cannot recover on its own):

- ``SkeletonBlock.pool_bindings`` — the Q1 representation must live somewhere;
  it lives on the block doing the binding (its parent), per Q1=A.
- ``SkeletonBlock.resolved_ports`` — ``own port name -> resolved molecule id``,
  populated by :func:`_realize_tree` alongside ``provenance`` at materialize
  time. A crux-bearing block's ``ground_truth(timeline)`` needs to know *which*
  molecule its own port resolved to; ``provenance`` alone (reaction + container)
  cannot answer that without re-walking the assembled chemistry, so this small
  sibling field is populated the same way, at the same time.

``Skeleton.materialize`` is the one **impure** corner: because it must return a
``WorldImpl`` (not a new ``Skeleton``) while also "storing" ``chemistry`` and
the provenance-populated tree onto ``self`` (per the Data Model field table),
it caches both onto the frozen instance via ``object.__setattr__`` — the same
escape hatch :class:`alienbio.infra.graph_ops.GraphView` already uses for
derived/cached state on a frozen dataclass. Authoring a skeleton (building or
editing the tree before materialization) stays purely functional (Q4=A).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import TYPE_CHECKING, Any, Mapping, Optional, cast

from ..bio.chemistry import ChemistryImpl
from ..bio.conservation import ConservationError, validate_conservation
from ..bio.molecule import MoleculeImpl
from ..bio.reaction import ReactionImpl
from ..bio.world import Compartment, NodeId, WorldImpl
from ..infra.mk import mk
from .dist import Seed
from .types import Tags, Timeline
from .verify import SimConfig, simulate

if TYPE_CHECKING:
    from ..bio.world_state import WorldStateImpl

#: A stable path of block names from the root, e.g. ``"root/sink"`` (Q2).
BlockRef = str

#: A stable path to a port: a :data:`BlockRef` + ``"." + port_name``, e.g.
#: ``"root/source.out"`` (Q2).
PortRef = str


class SkeletonError(ValueError):
    """A skeleton well-formedness violation.

    Raised by internal helpers (e.g. a malformed pool-binding ref, an unknown
    child, a namespace collision); *returned* (not raised) by
    :meth:`Skeleton.validate`, matching its documented ``None | SkeletonError``
    signature.
    """


class PortDir(Enum):
    """A port either consumes (``IN``) or produces (``OUT``) its pool."""

    IN = "in"
    OUT = "out"


class Role(Enum):
    """A block's purpose (Data Model — used for authoring/introspection only;
    nothing in this module branches on it)."""

    SUPPLY = "supply"
    SINK = "sink"
    CRUX = "crux"
    SIGNALING = "signaling"
    TRANSPORT = "transport"
    PRESSURE = "pressure"


@dataclass(frozen=True)
class Port:
    """A pool: a (molecule, container) a block binds to as producer or consumer.

    There is exactly one port kind (S7) — the old species/control split is
    gone. ``container=None`` means "the block's default / inherited-from-parent
    container" (resolved to a concrete container at materialize time).
    """

    name: str
    container: Optional[NodeId]
    direction: PortDir


@dataclass(frozen=True)
class PoolBinding:
    """Names two ports as one shared pool — a parent block's concern (Q1=A).

    Each side is a **local** ref relative to the block that owns this binding:
    ``"self.<port>"`` for one of the block's own ports, or
    ``"<child_name>.<port>"`` for a named direct child's port. Resolved
    top-down, one tree level at a time, in :func:`_realize_tree` — so a chain
    of bindings across several levels threads one pool through the whole tree.
    """

    a: str
    b: str


@dataclass(frozen=True)
class Provenance:
    """A block -> chemistry link: one reaction, in one container, a block
    produced (the oracle's climb-the-tree handle)."""

    reaction_id: str
    container_id: NodeId


@dataclass(frozen=True)
class Fragment:
    """The accumulator the realize recursion emits and merges.

    ``molecules`` / ``reactions`` are keyed by id (name); ``initial`` maps
    ``(container_id, molecule_id) -> concentration`` for blocks that need to
    seed a non-zero starting state. :meth:`merge` is the collision-checked
    union two sibling fragments (or a block's own fragment + its children's)
    combine through.
    """

    molecules: Mapping[str, MoleculeImpl] = field(default_factory=dict)
    reactions: Mapping[str, ReactionImpl] = field(default_factory=dict)
    compartments: tuple[Compartment, ...] = ()
    initial: Mapping[tuple[NodeId, str], float] = field(default_factory=dict)
    provenance: tuple[Provenance, ...] = ()

    def merge(self, other: "Fragment") -> "Fragment":
        """Union two fragments; raise :class:`SkeletonError` on a real collision.

        A molecule id present in both sides is fine **iff** it is the same
        object (a deliberately shared, bound pool) — the object-vs-name
        aliasing invariant this subsystem exists to enforce. A reaction id
        collision is always an error (namespaces are supposed to be
        collision-free by construction).
        """
        for name in set(self.molecules) & set(other.molecules):
            if self.molecules[name] is not other.molecules[name]:
                raise SkeletonError(
                    f"molecule id {name!r} collides across blocks with two "
                    f"different objects — a namespace collision, not a shared pool"
                )
        dup_rxn = set(self.reactions) & set(other.reactions)
        if dup_rxn:
            raise SkeletonError(f"reaction id collision: {sorted(dup_rxn)}")
        return Fragment(
            molecules={**self.molecules, **other.molecules},
            reactions={**self.reactions, **other.reactions},
            compartments=self.compartments + other.compartments,
            initial={**self.initial, **other.initial},
            provenance=self.provenance + other.provenance,
        )


@dataclass(frozen=True)
class SkeletonBlock:
    """Abstract base: one node of the recursive block tree (S9 — blocks are
    causal *pathways*, not bare reactions).

    A block is both a tree node and a template: it holds its params, its child
    blocks, its pool-ports, and — after :meth:`Skeleton.materialize` —
    ``provenance`` + ``resolved_ports``. ``realize``'s default returns an empty
    :class:`Fragment`: a bare ``SkeletonBlock`` (or a subclass that does not
    override ``realize``) is a pure composition node whose content lives
    entirely in its ``children`` — recursion into ``children`` and pool-binding
    resolution is handled *generically*, once, by :func:`_realize_tree` (called
    from :meth:`Skeleton.materialize`), so a pattern needs no boilerplate
    override. A **primitive** overrides ``realize`` to emit its own reaction(s)
    over its (already-resolved) ports.
    """

    name: str
    role: Role
    ports: tuple[Port, ...] = ()
    params: Tags = field(default_factory=dict)
    children: tuple["SkeletonBlock", ...] = ()
    provenance: tuple[Provenance, ...] = ()
    #: Q1 representation — this block's pool bindings (see :class:`PoolBinding`).
    pool_bindings: tuple[PoolBinding, ...] = ()
    #: Own port name -> resolved molecule id; populated by materialize
    #: alongside ``provenance`` (documented module-level extension).
    resolved_ports: Mapping[str, str] = field(default_factory=dict)

    def realize(
        self, seed: Seed, ns: str, bound: Mapping[str, MoleculeImpl]
    ) -> Fragment:
        """Emit THIS block's own reaction(s) over its resolved ports.

        ``bound`` maps every one of this block's own port names to the
        concrete :class:`MoleculeImpl` object it resolves to (already unified
        across any bound sibling/parent port — the object-vs-name aliasing
        fix). Children are handled by the driver, not by this method.
        """
        return Fragment()

    def walk(self):
        """Pre-order tree walk (self, then each child's walk) — how the oracle
        (and path resolution) climbs the skeleton."""
        yield self
        for child in self.children:
            yield from child.walk()

    def ground_truth(self, timeline: Timeline) -> Any:
        """Read this (crux-bearing) block's answer off a simulated Timeline.

        Base implementation raises — only blocks meant to serve as a
        ``Skeleton.crux`` need to override this.
        """
        raise NotImplementedError(
            f"{type(self).__name__} ({self.name!r}) is not crux-bearing "
            f"(no ground_truth implementation)"
        )


def final_amount(timeline: Timeline, molecule_id: str) -> float:
    """Total final amount of ``molecule_id`` across all compartments.

    Reads ``timeline.states[-1]`` (a self-describing ``WorldStateImpl``),
    locates the molecule on its id axis, and sums that column of ``as_array()``
    over every compartment. Mirrors ``arch_intervene._final_concentration`` —
    the same reading a crux-bearing block's ``ground_truth`` uses.

    Raises:
        ValueError: if the timeline has no states, or the final state carries
            no ``molecule_ids`` axis.
        KeyError: if ``molecule_id`` is absent from the state's molecule axis.
    """
    if not timeline.states:
        raise ValueError("timeline has no states to read ground truth from")
    state = cast("WorldStateImpl", timeline.states[-1])
    mol_ids = state.molecule_ids
    if mol_ids is None:
        raise ValueError(
            "final timeline state is not self-describing (no molecule_ids); "
            "cannot locate the target molecule"
        )
    try:
        j = mol_ids.index(molecule_id)
    except ValueError:
        raise KeyError(
            f"molecule id {molecule_id!r} is not on the state's molecule axis"
        ) from None
    arr = state.as_array()
    return float(sum(row[j] for row in arr))


# ═══════════════════════════════════════════════════════════════════════════
# Internal plumbing: local-ref parsing, union-find, and the recursive
# materialize driver.
# ═══════════════════════════════════════════════════════════════════════════


def _split_ref(ref: str) -> tuple[str, str]:
    """Split a local :class:`PoolBinding` side ``"who.port"`` -> ``(who, port)``."""
    who, sep, port = ref.partition(".")
    if not sep:
        raise SkeletonError(f"malformed pool-binding ref {ref!r}; expected 'who.port'")
    return who, port


class _UnionFind:
    """Tiny path-compressing union-find over string keys."""

    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self._parent.setdefault(x, x)
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[x] != root:
            self._parent[x], x = root, self._parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb


def _resolve_own_ports(
    block: SkeletonBlock, ns: str, bound: Mapping[str, MoleculeImpl]
) -> dict[str, MoleculeImpl]:
    """Own port name -> resolved MoleculeImpl: ``bound`` wins; else mint fresh
    (a private, namespaced pool nobody else is wired to)."""
    resolved: dict[str, MoleculeImpl] = {}
    for port in block.ports:
        if port.name in bound:
            resolved[port.name] = bound[port.name]
        else:
            mol_id = f"{ns}/{port.name}"
            resolved[port.name] = cast(MoleculeImpl, mk.M(mol_id))
    return resolved


def _realize_tree(
    block: SkeletonBlock, seed: Seed, ns: str, bound: Mapping[str, MoleculeImpl]
) -> tuple[Fragment, SkeletonBlock]:
    """Recursively realize ``block``: resolve its ports, emit its own fragment,
    resolve its ``pool_bindings`` into each child's incoming ``bound``, recurse,
    and merge everything into one :class:`Fragment` + a realized copy of
    ``block`` (``provenance`` + ``resolved_ports`` populated, ``children``
    replaced by their own realized copies).

    Pool-binding resolution is a **local**, one-level union-find over this
    block's own ports (``"self.<port>"``) and its direct children's ports
    (``"<child>.<port>"``) — Q1=A: binding is the parent's concern. A shared
    pool spanning several tree levels threads through because each level's
    resolved molecule is handed down as that child's incoming ``bound``.
    """
    own_bound = _resolve_own_ports(block, ns, bound)

    uf = _UnionFind()
    for pb in block.pool_bindings:
        uf.union(pb.a, pb.b)

    child_names = {c.name for c in block.children}
    comp_mol: dict[str, MoleculeImpl] = {}
    for pb in block.pool_bindings:
        for ref in (pb.a, pb.b):
            who, port = _split_ref(ref)
            if who != "self":
                continue
            if port not in own_bound:
                raise SkeletonError(
                    f"{block.name!r}: pool binding references unknown own port {port!r}"
                )
            comp_mol.setdefault(uf.find(ref), own_bound[port])

    child_bound: dict[str, dict[str, MoleculeImpl]] = {name: {} for name in child_names}
    for pb in block.pool_bindings:
        for ref in (pb.a, pb.b):
            who, port = _split_ref(ref)
            if who == "self":
                continue
            if who not in child_names:
                raise SkeletonError(
                    f"{block.name!r}: pool binding references unknown child {who!r}"
                )
            root = uf.find(ref)
            if root not in comp_mol:
                mol_id = f"{ns}/{root}".replace(".", "_")
                comp_mol[root] = cast(MoleculeImpl, mk.M(mol_id))
            child_bound[who][port] = comp_mol[root]

    own_fragment = block.realize(seed, ns, own_bound)

    fragment = own_fragment
    realized_children: list[SkeletonBlock] = []
    for child in block.children:
        child_fragment, realized_child = _realize_tree(
            child, seed.child(child.name), f"{ns}/{child.name}", child_bound[child.name]
        )
        fragment = fragment.merge(child_fragment)
        realized_children.append(realized_child)

    realized_block = replace(
        block,
        children=tuple(realized_children),
        provenance=own_fragment.provenance,
        resolved_ports={name: mol.name for name, mol in own_bound.items()},
    )
    return fragment, realized_block


def _seed_initial(
    compartments: tuple[Compartment, ...],
    initial: Mapping[tuple[NodeId, str], float],
) -> tuple[Compartment, ...]:
    """Fold a ``(container_id, molecule_id) -> value`` map onto compartments."""
    by_container: dict[NodeId, dict[str, float]] = {}
    for (container, mol), value in initial.items():
        by_container.setdefault(container, {})[mol] = value
    result: list[Compartment] = []
    for comp in compartments:
        extra = by_container.get(comp.id)
        if extra:
            result.append(replace(comp, concentrations={**comp.concentrations, **extra}))
        else:
            result.append(comp)
    return tuple(result)


def _block_by_path(root: SkeletonBlock, path: BlockRef) -> SkeletonBlock:
    """Resolve a ``/``-separated :data:`BlockRef` by walking from ``root`` (Q2)."""
    parts = path.split("/")
    if not parts or parts[0] != root.name:
        raise SkeletonError(f"block path {path!r} does not start at root {root.name!r}")
    node = root
    for part in parts[1:]:
        match = next((c for c in node.children if c.name == part), None)
        if match is None:
            raise SkeletonError(
                f"no child named {part!r} under {node.name!r} (path {path!r})"
            )
        node = match
    return node


def _ref_block_path(ref: str) -> str:
    """The block-path portion of a :data:`PortRef` (strip the trailing ``.port``)."""
    block_path, sep, _port = ref.rpartition(".")
    if not sep:
        raise SkeletonError(f"malformed port ref {ref!r}; expected 'block/path.port'")
    return block_path


def _globalize(ref: str, path: str) -> str:
    """A block's local :class:`PoolBinding` side -> a global :data:`PortRef`."""
    who, port = _split_ref(ref)
    if who == "self":
        return f"{path}.{port}"
    return f"{path}/{who}.{port}"


def _collect_global_edges(block: SkeletonBlock, path: str) -> list[tuple[str, str]]:
    """Every pool-binding edge tree-wide, translated to global :data:`PortRef`s."""
    edges = [(_globalize(pb.a, path), _globalize(pb.b, path)) for pb in block.pool_bindings]
    for child in block.children:
        edges.extend(_collect_global_edges(child, f"{path}/{child.name}"))
    return edges


def _global_ports(block: SkeletonBlock, path: str) -> dict[str, Port]:
    """Every port tree-wide, keyed by its global :data:`PortRef`."""
    result = {f"{path}.{p.name}": p for p in block.ports}
    for child in block.children:
        result.update(_global_ports(child, f"{path}/{child.name}"))
    return result


def _bfs_distance(adjacency: Mapping[str, set[str]], start: str, goal: str) -> Optional[int]:
    """Shortest hop count from ``start`` to ``goal`` in an undirected graph."""
    if start == goal:
        return 0
    seen = {start}
    frontier = [start]
    dist = 0
    while frontier:
        dist += 1
        nxt: list[str] = []
        for node in frontier:
            for neighbor in adjacency.get(node, ()):
                if neighbor == goal:
                    return dist
                if neighbor not in seen:
                    seen.add(neighbor)
                    nxt.append(neighbor)
        frontier = nxt
    return None


@dataclass(frozen=True)
class Skeleton:
    """The composite: a root block + the chemistry it constructs (Q3=A — a
    thin wrapper, not a ``SkeletonBlock`` subclass).

    ``chemistry`` starts ``None`` and is populated by :meth:`materialize`
    (which also replaces ``root`` with its realized, provenance-populated
    copy — see the module docstring's note on this method's one impurity).
    """

    root: SkeletonBlock
    chemistry: Optional[ChemistryImpl] = None
    control_surface: tuple[PortRef, ...] = ()
    crux: BlockRef = ""

    def materialize(self, seed: Seed) -> WorldImpl:
        """Recursively realize ``root`` into one ``ChemistryImpl`` + a default
        single compartment, assemble a ``WorldImpl``, and cache the result.

        Runs the three passes from the architecture doc: instantiate + resolve
        bindings (both inside :func:`_realize_tree`, which unifies every bound
        pool onto one shared ``MoleculeImpl``), then assemble (merge into one
        ``ChemistryImpl``, place compartments, seed initial concentrations).
        """
        fragment, realized_root = _realize_tree(self.root, seed.child(self.root.name), self.root.name, {})
        chem = cast(
            ChemistryImpl,
            mk.C(
                f"{self.root.name}_chem",
                list(fragment.molecules.values()),
                list(fragment.reactions.values()),
            ),
        )
        compartments = fragment.compartments or (Compartment("cell", None, "cell", 1.0),)
        if fragment.initial:
            compartments = _seed_initial(compartments, fragment.initial)
        world = WorldImpl(chem, compartments)

        # Cache: frozen dataclass, so this is the one deliberate escape hatch
        # (see module docstring) — materialize "stores" chemistry + the
        # provenance-populated tree per the Data Model contract.
        object.__setattr__(self, "root", realized_root)
        object.__setattr__(self, "chemistry", chem)
        return world

    def validate(self) -> Optional[SkeletonError]:
        """Well-formedness: returns ``None`` if clean, else a ``SkeletonError``
        describing every violation found (never raises for a *content*
        violation — only for a usage error, e.g. calling before materialize).

        Checks, tree-wide: every pool (a pool-binding connected component, or a
        lone unbound port) has both a producer (an ``OUT`` port) and a bounded
        fate (an ``IN`` port) — bound-port type-match folds into this same
        direction check, since ``Port`` carries no other type tag to mismatch
        on. Namespace-collision-freedom is enforced *by construction* —
        :meth:`materialize` already raised if two blocks collided — so it is
        not re-checked here. Internal reactions are atom-balanced via the F012
        gate (:func:`alienbio.bio.conservation.validate_conservation`).
        """
        if self.chemistry is None:
            raise SkeletonError("validate() requires materialize() to run first")

        errors: list[str] = []
        ports = _global_ports(self.root, self.root.name)
        edges = _collect_global_edges(self.root, self.root.name)
        uf = _UnionFind()
        for a, b in edges:
            uf.union(a, b)

        components: dict[str, list[str]] = {}
        for ref in ports:
            components.setdefault(uf.find(ref), []).append(ref)

        for refs in components.values():
            directions = {ports[r].direction for r in refs}
            if PortDir.OUT not in directions:
                errors.append(f"pool {sorted(refs)} has no producer (no OUT port)")
            if PortDir.IN not in directions:
                errors.append(
                    f"pool {sorted(refs)} has no bounded fate (no IN port ever consumes it)"
                )

        try:
            validate_conservation(self.chemistry)
        except ConservationError as exc:
            errors.append(str(exc))

        if errors:
            return SkeletonError("; ".join(errors))
        return None

    def oracle(self, seed: Seed, sim_cfg: SimConfig = SimConfig()) -> Any:
        """Materialize, simulate, climb to ``crux``, and read its ground truth.

        Deterministic given ``seed`` (both materialize and simulate are pure
        functions of it) — ground-truth-by-construction, by-simulation.
        """
        world = self.materialize(seed)
        timeline = simulate(world, sim_cfg, seed.child("oracle-sim"))
        crux_block = _block_by_path(self.root, self.crux)
        return crux_block.ground_truth(timeline)

    def indirection_depth(self) -> int:
        """Min pool-graph distance from any ``control_surface`` lever to
        ``crux`` — the difficulty dial (subsumes M28.1 network-size).

        Builds the tree-wide pool graph from every block's ``pool_bindings``
        (works whether or not ``materialize`` has run yet — bindings are
        authored structure, not a simulation result), then BFS's from each
        lever's owning block to the crux's owning block over "these two blocks
        share a pool" adjacency.
        """
        if not self.control_surface:
            raise SkeletonError("indirection_depth() requires a non-empty control_surface")

        edges = _collect_global_edges(self.root, self.root.name)
        uf = _UnionFind()
        for a, b in edges:
            uf.union(a, b)

        component_blocks: dict[str, set[str]] = {}
        for a, b in edges:
            for ref in (a, b):
                component_blocks.setdefault(uf.find(ref), set()).add(_ref_block_path(ref))

        adjacency: dict[str, set[str]] = {}
        for blocks in component_blocks.values():
            for block_path in blocks:
                adjacency.setdefault(block_path, set()).update(blocks - {block_path})

        best: Optional[int] = None
        for lever_ref in self.control_surface:
            lever_path = _ref_block_path(lever_ref)
            dist = _bfs_distance(adjacency, lever_path, self.crux)
            if dist is not None and (best is None or dist < best):
                best = dist
        if best is None:
            raise SkeletonError("no control-surface lever reaches the crux via any pool")
        return best
