"""Compartment: entity representing a biological compartment.

A Compartment defines a region in the biological hierarchy (organism, organ, cell, organelle)
with its initial state, membrane flows, and active reactions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..infra.entity import Entity

if TYPE_CHECKING:
    from dvc_dat import Dat
    from .flow import GeneralFlow
    from .chemistry import ChemistryImpl


class CompartmentImpl(Entity, head="Compartment"):
    """Implementation: A compartment in the biological hierarchy.

    Compartments represent biological regions: organisms, organs, cells, organelles.
    Each compartment can contain child compartments, forming a tree structure.

    The compartment entity specifies:
    - Structure: kind and child compartments
    - Initial state: multiplicity and concentrations
    - Behavior: membrane flows and active reactions

    This entity tree serves as both the initial WorldState specification and
    the complete simulation configuration.

    Attributes:
        kind: Type of compartment ("organism", "organ", "cell", "organelle", etc.)
        multiplicity: Number of instances (default 1.0)
        volume: Volume of each instance in arbitrary units (default 1.0)
        concentrations: Initial molecule concentrations {molecule_name: value}
        membrane_flows: Flows across this compartment's membrane
        active_reactions: Reactions active here (None = all from chemistry)
        children: Child compartments

    Example:
        # Define an organism with cells
        organism = CompartmentImpl(
            "body",
            volume=70000,  # 70 liters in mL
            kind="organism",
            concentrations={"glucose": 5.0, "oxygen": 2.0},
        )

        liver = CompartmentImpl(
            "liver",
            volume=1500,  # 1.5 liters in mL
            parent=organism,
            kind="organ",
        )

        hepatocyte = CompartmentImpl(
            "hepatocyte",
            volume=3e-9,  # ~3000 cubic microns in mL
            parent=liver,
            kind="cell",
            multiplicity=1e9,  # 1 billion liver cells
            concentrations={"glucose": 1.0},
            membrane_flows=[glucose_uptake_flow],
            active_reactions=["glycolysis", "gluconeogenesis"],
        )
    """

    __slots__ = (
        "_kind",
        "_multiplicity",
        "_volume",
        "_concentrations",
        "_membrane_flows",
        "_active_reactions",
        "_children",
    )

    def __init__(
        self,
        local_name: str,
        *,
        volume: float,
        parent: Optional[Entity] = None,
        dat: Optional[Dat] = None,
        description: str = "",
        kind: str = "compartment",
        multiplicity: float = 1.0,
        concentrations: Optional[Dict[str, float]] = None,
        membrane_flows: Optional[List[GeneralFlow]] = None,
        active_reactions: Optional[List[str]] = None,
    ) -> None:
        """Initialize a compartment.

        Args:
            local_name: Local name within parent (used as entity identifier)
            volume: Volume of each instance (required - no default, scale depends on use case)
            parent: Parent compartment (or None for root)
            dat: DAT anchor for root compartments
            description: Human-readable description
            kind: Type of compartment ("organism", "organ", "cell", "organelle")
            multiplicity: Number of instances of this compartment (default 1.0)
            concentrations: Initial molecule concentrations {name: value}
            membrane_flows: Flows across this compartment's membrane
            active_reactions: Reaction names active here (None = all from chemistry)
        """
        super().__init__(local_name, parent=parent, dat=dat, description=description)
        self._kind = kind
        self._multiplicity = multiplicity
        self._volume = volume
        self._concentrations: Dict[str, float] = (
            concentrations.copy() if concentrations else {}
        )
        self._membrane_flows: List[GeneralFlow] = (
            list(membrane_flows) if membrane_flows else []
        )
        self._active_reactions: Optional[List[str]] = (
            list(active_reactions) if active_reactions else None
        )
        self._children: List[CompartmentImpl] = []

        # Register with parent
        if parent is not None and isinstance(parent, CompartmentImpl):
            parent._children.append(self)

    @property
    def kind(self) -> str:
        """Type of compartment: 'organism', 'organ', 'cell', 'organelle'."""
        return self._kind

    @property
    def multiplicity(self) -> float:
        """Number of instances of this compartment."""
        return self._multiplicity

    @property
    def volume(self) -> float:
        """Volume of each instance in arbitrary units."""
        return self._volume

    @property
    def concentrations(self) -> Dict[str, float]:
        """Initial molecule concentrations {name: value}."""
        return self._concentrations.copy()

    @property
    def membrane_flows(self) -> List[GeneralFlow]:
        """Flows across this compartment's membrane."""
        return list(self._membrane_flows)

    @property
    def active_reactions(self) -> Optional[List[str]]:
        """Reaction names active in this compartment (None = all)."""
        return list(self._active_reactions) if self._active_reactions else None

    @property
    def children(self) -> List[CompartmentImpl]:
        """Child compartments."""
        return list(self._children)

    def add_child(self, child: CompartmentImpl) -> None:
        """Add a child compartment."""
        if child not in self._children:
            self._children.append(child)

    def add_flow(self, flow: GeneralFlow) -> None:
        """Add a membrane flow."""
        self._membrane_flows.append(flow)

    def set_concentration(self, molecule: str, value: float) -> None:
        """Set initial concentration for a molecule."""
        self._concentrations[molecule] = value

    def set_multiplicity(self, value: float) -> None:
        """Set the multiplicity (instance count)."""
        self._multiplicity = value

    def set_volume(self, value: float) -> None:
        """Set the volume of each instance."""
        self._volume = value

    def set_active_reactions(self, reactions: Optional[List[str]]) -> None:
        """Set active reactions (None = all from chemistry)."""
        self._active_reactions = list(reactions) if reactions else None

    # ── Tree traversal ────────────────────────────────────────────────────────

    def all_descendants(self) -> List[CompartmentImpl]:
        """Get all descendant compartments (depth-first)."""
        result = []
        stack = list(self._children)
        while stack:
            child = stack.pop()
            result.append(child)
            stack.extend(child._children)
        return result

    def all_compartments(self) -> List[CompartmentImpl]:
        """Get self and all descendants."""
        return [self] + self.all_descendants()

    def depth(self) -> int:
        """Get depth in tree (root = 0)."""
        d = 0
        current = self._parent
        while current is not None and isinstance(current, CompartmentImpl):
            d += 1
            current = current._parent
        return d

    # ── Serialization ─────────────────────────────────────────────────────────

    def attributes(self) -> Dict[str, Any]:
        """Semantic content for serialization."""
        result: Dict[str, Any] = {
            "kind": self._kind,
            "volume": self._volume,  # Always include - required field
        }
        if self._multiplicity != 1.0:
            result["multiplicity"] = self._multiplicity
        if self._concentrations:
            result["concentrations"] = self._concentrations.copy()
        if self._active_reactions is not None:
            result["active_reactions"] = self._active_reactions.copy()
        # Note: membrane_flows and children serialized separately
        return result

    def __repr__(self) -> str:
        """Full representation."""
        return (
            f"CompartmentImpl({self._local_name!r}, kind={self._kind!r}, "
            f"multiplicity={self._multiplicity}, children={len(self._children)})"
        )

    def __str__(self) -> str:
        """Short representation."""
        mult_str = f" x{self._multiplicity:g}" if self._multiplicity != 1.0 else ""
        return f"{self._kind}:{self._local_name}{mult_str}"
