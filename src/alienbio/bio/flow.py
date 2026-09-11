"""Flow: transport between compartments.

Flow hierarchy:
- Flow (abstract base): common interface for all flows
- GeneralFlow: arbitrary state modifications (placeholder, needs general interpreter)
- TransportFlux: cross-compartment flux between ANY two compartments (F016/S3),
  amount-conserving in AMOUNT-space (not concentration) regardless of the two
  compartments' volumes/multiplicities
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from .world_state import WorldStateImpl
    from .compartment_tree import CompartmentTreeImpl

# Type aliases
CompartmentId = int


class Flow(ABC):
    """Abstract base class for all flows.

    Flows move molecules (or instances) between compartments. Each flow is
    anchored to an origin compartment.

    Subclasses:
    - TransportFlux: amount-conserving transport between any two compartments
    - GeneralFlow: arbitrary state modifications (placeholder)

    Common interface:
    - origin: the compartment where this flow is anchored
    - name: human-readable identifier
    - compute_flux(): calculate transfer rate
    - apply(): modify state based on flux
    """

    __slots__ = ("_origin", "_name")

    def __init__(
        self,
        origin: CompartmentId,
        name: str = "",
    ) -> None:
        """Initialize base flow.

        Args:
            origin: The origin compartment (where this flow is anchored)
            name: Human-readable name for this flow
        """
        self._origin = origin
        self._name = name

    @property
    def origin(self) -> CompartmentId:
        """The origin compartment (where this flow is anchored)."""
        return self._origin

    @property
    def name(self) -> str:
        """Human-readable name."""
        return self._name

    @property
    @abstractmethod
    def is_membrane_flow(self) -> bool:
        """True if this is a membrane flow (origin ↔ parent)."""
        ...

    @property
    @abstractmethod
    def is_general_flow(self) -> bool:
        """True if this is a general flow (arbitrary edits)."""
        ...

    @abstractmethod
    def compute_flux(
        self,
        state: WorldStateImpl,
        tree: CompartmentTreeImpl,
    ) -> float:
        """Compute flux for this flow.

        Args:
            state: Current world state with concentrations
            tree: Compartment topology

        Returns:
            Flux value (positive = into origin for membrane flows)
        """
        ...

    @abstractmethod
    def apply(
        self,
        state: WorldStateImpl,
        tree: CompartmentTreeImpl,
        dt: float = 1.0,
    ) -> None:
        """Apply this flow to the state (mutates in place).

        Args:
            state: World state to modify
            tree: Compartment topology
            dt: Time step
        """
        ...

    @abstractmethod
    def attributes(self) -> Dict[str, Any]:
        """Semantic content for serialization."""
        ...


class GeneralFlow(Flow):
    """Arbitrary state modifications (placeholder).

    GeneralFlow is a catch-all for flows that don't fit the TransportFlux pattern.
    This includes:
    - Lateral flows between siblings
    - Instance transfers (RBCs moving between compartments)
    - Any other arbitrary edits to the system

    NOTE: This is currently a placeholder. Full implementation will require
    a more general interpreter to handle arbitrary state modifications
    specified via Expr or similar.

    For now, GeneralFlow stores an apply_fn that takes state and tree
    and performs arbitrary modifications.
    """

    __slots__ = ("_apply_fn", "_description")

    def __init__(
        self,
        origin: CompartmentId,
        apply_fn: Optional[Callable[[WorldStateImpl, CompartmentTreeImpl, float], None]] = None,
        name: str = "",
        description: str = "",
    ) -> None:
        """Initialize a general flow.

        Args:
            origin: The compartment where this flow is conceptually anchored
            apply_fn: Function (state, tree, dt) -> None that modifies state
            name: Human-readable name for this flow
            description: Description of what this flow does

        NOTE: This is a placeholder. Full implementation will need a more
        general interpreter to support Expr-based specifications.
        """
        if not name:
            name = f"general_flow_at_{origin}"
        super().__init__(origin, name)

        self._apply_fn = apply_fn
        self._description = description

    @property
    def description(self) -> str:
        """Description of what this flow does."""
        return self._description

    @property
    def is_membrane_flow(self) -> bool:
        """False - this is not a membrane flow."""
        return False

    @property
    def is_general_flow(self) -> bool:
        """True - this is a general flow."""
        return True

    def compute_flux(
        self,
        state: WorldStateImpl,
        tree: CompartmentTreeImpl,
    ) -> float:
        """General flows don't have a simple flux concept.

        Returns 0.0 as placeholder. The actual work happens in apply().
        """
        return 0.0

    def apply(
        self,
        state: WorldStateImpl,
        tree: CompartmentTreeImpl,
        dt: float = 1.0,
    ) -> None:
        """Apply this flow to the state (mutates in place).

        Args:
            state: World state to modify
            tree: Compartment topology
            dt: Time step
        """
        if self._apply_fn is not None:
            self._apply_fn(state, tree, dt)

    def attributes(self) -> Dict[str, Any]:
        """Semantic content for serialization.

        NOTE: apply_fn cannot be serialized. Full implementation will
        need Expr-based specification that can be serialized.
        """
        return {
            "type": "general",
            "name": self._name,
            "origin": self._origin,
            "description": self._description,
        }

    def __repr__(self) -> str:
        """Full representation."""
        return f"GeneralFlow(origin={self._origin}, name={self._name!r})"

    def __str__(self) -> str:
        """Short representation."""
        return f"GeneralFlow({self._name})"


class TransportFlux(Flow):
    """Cross-compartment flux: moves conserved AMOUNT (not concentration)
    between two independently-addressed compartments (F016/S3, skeleton
    decision S3 / coverage gap G3).

    Unlike the M1 ``MembraneFlow`` it replaced (anchored to a parent-child pair
    via the tree; deleted in T056), ``origin``/``dest`` here are two arbitrary compartments — no tree
    relationship required, which is what lets a :class:`~alienbio.suite.blocks.
    SpatialLatticeBlock` wire an arbitrary neighbor graph.

    Rate law (Q1=C, gradient default) — the event rate is driven by ONE
    ``driver_molecule``'s concentration:

    - ``rate_law="gradient"`` (default): Fickian, ``rate_constant *
      ([X]_origin - [X]_dest)`` — drives the driver species toward equal
      concentration across the two pools (the mechanism a diffusive lattice
      relaxes through).
    - ``rate_law="first_order"``: ``rate_constant * [X]_origin`` — a
      pump/boundary-flavored unidirectional law (no dependence on ``dest``).

    Either law's raw rate is floored at 0: this ONE flux is strictly
    ``origin -> dest``. A reversed local gradient (or a negative first-order
    rate) contributes nothing from THIS flux — wire a second, reversed
    ``TransportFlux`` for true bidirectional equilibration (e.g. a lattice's
    neighbor pair in each direction). This also protects against oscillation:
    once the driver species reaches equality, tiny numerical overshoot floors
    to 0 instead of flip-flopping sign every step.

    ``stoichiometry`` (``{molecule_id: count}``) lets several species move together per event — active
    co-transport needs no new law, just an extra (possibly negative-count,
    counter-direction) entry co-transporting an energy carrier. Every species
    is rationed against the SAME shared event count (so a co-transported group
    moves in lockstep): for each species, the event count is clamped so its
    LOSING compartment's :meth:`WorldStateImpl.amount` never goes negative —
    the amount-conservation invariant (F012 count basis) this class exists to
    guarantee. The identical transferred amount ``Δn`` leaves the losing pool
    and enters the other, so ``Σ amount`` is invariant regardless of the two
    compartments' volumes/multiplicities.
    """

    __slots__ = ("_dest", "_stoichiometry", "_driver_molecule", "_rate_constant", "_rate_law")

    def __init__(
        self,
        origin: CompartmentId,
        dest: CompartmentId,
        stoichiometry: Dict[int, float],
        driver_molecule: int,
        rate_constant: float = 1.0,
        rate_law: str = "gradient",
        name: str = "",
    ) -> None:
        """Initialize a cross-compartment transport flux.

        Args:
            origin: The compartment this flux moves species OUT OF (the "src" pool)
            dest: The compartment this flux moves species INTO (the "dst" pool)
            stoichiometry: Molecule id -> count moved per event (all species move
                together, in lockstep, scaled by the shared event count)
            driver_molecule: Which molecule id's concentration drives the rate law
            rate_constant: ``D`` (gradient law) or ``k`` (first-order law)
            rate_law: ``"gradient"`` (Fickian, default) or ``"first_order"``
            name: Human-readable name for this flow

        Raises:
            ValueError: if ``rate_law`` is not one of the two supported laws.
        """
        if rate_law not in ("gradient", "first_order"):
            raise ValueError(
                f"TransportFlux rate_law must be 'gradient' or 'first_order', "
                f"got {rate_law!r}"
            )
        if not name:
            name = f"transport_{origin}_to_{dest}"
        super().__init__(origin, name)

        self._dest = dest
        self._stoichiometry = dict(stoichiometry)
        self._driver_molecule = driver_molecule
        self._rate_constant = rate_constant
        self._rate_law = rate_law

    @property
    def dest(self) -> CompartmentId:
        """The compartment this flux moves species INTO."""
        return self._dest

    @property
    def stoichiometry(self) -> Dict[int, float]:
        """Molecule id -> count moved per event (shared event count)."""
        return self._stoichiometry.copy()

    @property
    def driver_molecule(self) -> int:
        """Which molecule id's concentration drives the rate law."""
        return self._driver_molecule

    @property
    def rate_constant(self) -> float:
        """``D`` (gradient law) or ``k`` (first-order law)."""
        return self._rate_constant

    @property
    def rate_law(self) -> str:
        """``"gradient"`` (Fickian) or ``"first_order"``."""
        return self._rate_law

    @property
    def is_membrane_flow(self) -> bool:
        """False - this is not a parent-child membrane flow."""
        return False

    @property
    def is_general_flow(self) -> bool:
        """False - this is not an arbitrary-edit general flow."""
        return False

    def compute_flux(
        self,
        state: WorldStateImpl,
        tree: CompartmentTreeImpl,
    ) -> float:
        """Raw (unfloored, unrationed) event rate from the configured rate law.

        Args:
            state: Current world state with concentrations
            tree: Compartment topology (unused — origin/dest need no tree
                relationship)

        Returns:
            Event rate (events per unit time); may be negative (floored to 0
            in :meth:`apply`).
        """
        conc_src = state.get(self._origin, self._driver_molecule)
        if self._rate_law == "first_order":
            return self._rate_constant * conc_src
        # gradient (default): Fickian, driven toward equal concentration
        conc_dst = state.get(self._dest, self._driver_molecule)
        return self._rate_constant * (conc_src - conc_dst)

    def demand(
        self,
        frozen: WorldStateImpl,
        tree: CompartmentTreeImpl,
        dt: float = 1.0,
    ) -> tuple[float, Dict[tuple[CompartmentId, int], float]]:
        """The event count this flux wants this step, read off the FROZEN
        start-of-step state, and the AMOUNT it would draw from each losing
        ``(compartment, molecule)`` at that count (T053).

        The losing pool for a species is origin when its count is positive
        (origin -> dest), else dest (a negative count antiports that species).
        """
        event_count = max(self.compute_flux(frozen, tree) * dt, 0.0)
        draws: Dict[tuple[CompartmentId, int], float] = {}
        if event_count <= 0.0:
            return 0.0, draws
        for mol, count in self._stoichiometry.items():
            if count == 0:
                continue
            losing = self._origin if count > 0 else self._dest
            draws[(losing, mol)] = draws.get((losing, mol), 0.0) + abs(count) * event_count
        return event_count, draws

    def apply_events(
        self,
        state: WorldStateImpl,
        scales: WorldStateImpl,
        event_count: float,
    ) -> None:
        """Move ``event_count`` events' worth of every species (amounts read
        against ``scales``' multiplicity x volume), mutating ``state``."""
        if event_count <= 0.0:
            return
        origin_scale = scales.get_multiplicity(self._origin) * scales.get_volume(self._origin)
        dest_scale = scales.get_multiplicity(self._dest) * scales.get_volume(self._dest)
        for mol, count in self._stoichiometry.items():
            delta_n = event_count * count
            if origin_scale > 0:
                state.set(
                    self._origin, mol, state.get(self._origin, mol) - delta_n / origin_scale
                )
            if dest_scale > 0:
                state.set(self._dest, mol, state.get(self._dest, mol) + delta_n / dest_scale)

    def apply(
        self,
        state: WorldStateImpl,
        tree: CompartmentTreeImpl,
        dt: float = 1.0,
    ) -> None:
        """Apply this flux ALONE to ``state`` (mutates in place): the event
        count read off ``state``, rationed against every transported species'
        available AMOUNT in its losing compartment, then the same clamped
        count moved for each species. The stepper does not call this — it
        runs every flow together through :func:`apply_flows`, which rations
        the SUMMED demand of all flows on each pool; this is the one-flow
        path for callers that step a flux by hand.
        """
        event_count, draws = self.demand(state, tree, dt)
        for (comp, mol), amount in draws.items():
            available = state.amount(comp, mol)
            if amount > available:
                event_count = min(event_count, event_count * available / amount if amount > 0 else 0.0)
        self.apply_events(state, state, max(event_count, 0.0))

    def attributes(self) -> Dict[str, Any]:
        """Semantic content for serialization."""
        return {
            "type": "transport",
            "name": self._name,
            "origin": self._origin,
            "dest": self._dest,
            "stoichiometry": self._stoichiometry.copy(),
            "driver_molecule": self._driver_molecule,
            "rate_constant": self._rate_constant,
            "rate_law": self._rate_law,
        }

    def __repr__(self) -> str:
        """Full representation."""
        stoich_str = ", ".join(f"{m}:{c}" for m, c in self._stoichiometry.items())
        return (
            f"TransportFlux(origin={self._origin}, dest={self._dest}, "
            f"stoich={{{stoich_str}}}, rate={self._rate_constant}, law={self._rate_law!r})"
        )

    def __str__(self) -> str:
        """Short representation."""
        return f"TransportFlux({self._name})"


def apply_flows(
    flows: Sequence[Flow],
    new_state: WorldStateImpl,
    frozen: WorldStateImpl,
    tree: CompartmentTreeImpl,
    dt: float,
) -> None:
    """Apply every flow together, the way the reaction and population passes
    apply theirs (T051 box 4 / T053): each :class:`TransportFlux` reads its
    desired event count off the FROZEN start-of-step state, the draws on
    each losing ``(compartment, molecule)`` are summed across fluxes, every
    flux is scaled by the tightest ``min(1, available / demand)`` over the
    pools it draws, and the scaled events are applied at once. The split is
    then independent of list order (two fluxes over-drawing one pool used to
    give ``a=0.04 b=0.80 c=0.16`` or ``b=0.16 c=0.80`` depending on which came
    first) and no pool goes negative. With no pool over-drawn every ratio is
    exactly 1.0, so non-competing worlds are bit-identical to the old
    sequential pass EXCEPT that a flux now reads the frozen state rather than
    its predecessors' writes — the same operator-splitting rule the other two
    passes already follow. A :class:`GeneralFlow` (an arbitrary edit) cannot
    state a demand; those run sequentially after the fluxes, as before.
    """
    fluxes: list[tuple[TransportFlux, float, Dict[tuple[CompartmentId, int], float]]] = []
    others: list[Flow] = []
    demand: Dict[tuple[CompartmentId, int], float] = {}
    for flow in flows:
        if isinstance(flow, TransportFlux):
            events, draws = flow.demand(frozen, tree, dt)
            fluxes.append((flow, events, draws))
            for key, amount in draws.items():
                demand[key] = demand.get(key, 0.0) + amount
        else:
            others.append(flow)
    ratio: Dict[tuple[CompartmentId, int], float] = {}
    for (comp, mol), dem in demand.items():
        avail = frozen.amount(comp, mol)
        ratio[(comp, mol)] = min(1.0, avail / dem) if dem > 0.0 else 1.0
    for flow, events, draws in fluxes:
        scale = 1.0
        for key in draws:
            scale = min(scale, ratio[key])
        flow.apply_events(new_state, frozen, events * scale)
    for flow in others:
        flow.apply(new_state, tree, dt)
