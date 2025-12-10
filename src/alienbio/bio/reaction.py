"""Reaction: entities representing chemical transformations."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING, Union

from ..infra.entity import Entity

if TYPE_CHECKING:
    from dvc_dat import Dat
    from .molecule import Molecule
    from .state import State

# Rate can be a constant or a function of state
RateFunction = Callable[["State"], float]
RateValue = Union[float, RateFunction]


class ReactionImpl(Entity, head="Reaction"):
    """Implementation: A reaction transforming reactants into products.

    Reactions define transformations in the biological system.
    Each reaction has:
    - reactants: molecules consumed (with stoichiometric coefficients)
    - products: molecules produced (with stoichiometric coefficients)
    - rate: constant or function determining reaction speed

    Example:
        # A + 2B -> C with rate 0.1
        reaction = ReactionImpl(
            "r1",
            reactants={mol_a: 1, mol_b: 2},
            products={mol_c: 1},
            rate=0.1,
            parent=chemistry,
        )
    """

    __slots__ = ("_reactants", "_products", "_rate")

    def __init__(
        self,
        name: str,
        *,
        reactants: Optional[Dict[Molecule, float]] = None,
        products: Optional[Dict[Molecule, float]] = None,
        rate: RateValue = 1.0,
        parent: Optional[Entity] = None,
        dat: Optional[Dat] = None,
        description: str = "",
    ) -> None:
        """Initialize a reaction.

        Args:
            name: Local name within parent
            reactants: Dict mapping molecules to stoichiometric coefficients
            products: Dict mapping molecules to stoichiometric coefficients
            rate: Reaction rate (constant float or function of State)
            parent: Link to containing entity
            dat: DAT anchor for root reactions
            description: Human-readable description
        """
        super().__init__(name, parent=parent, dat=dat, description=description)
        self._reactants: Dict[Molecule, float] = reactants.copy() if reactants else {}
        self._products: Dict[Molecule, float] = products.copy() if products else {}
        self._rate: RateValue = rate

    @property
    def reactants(self) -> Dict[Molecule, float]:
        """Reactant molecules and their stoichiometric coefficients."""
        return self._reactants.copy()

    @property
    def products(self) -> Dict[Molecule, float]:
        """Product molecules and their stoichiometric coefficients."""
        return self._products.copy()

    @property
    def rate(self) -> RateValue:
        """Reaction rate (constant or function)."""
        return self._rate

    @property
    def name(self) -> str:
        """Human-readable name (same as local_name)."""
        return self._local_name

    @property
    def symbol(self) -> str:
        """Formula string: 'glucose + ATP -> G6P + ADP'."""
        reactant_str = " + ".join(
            f"{c}{m.name}" if c != 1 else m.name
            for m, c in self._reactants.items()
        )
        product_str = " + ".join(
            f"{c}{m.name}" if c != 1 else m.name
            for m, c in self._products.items()
        )
        return f"{reactant_str} -> {product_str}"

    def set_rate(self, rate: RateValue) -> None:
        """Set the reaction rate."""
        self._rate = rate

    def get_rate(self, state: State) -> float:
        """Get the effective rate for a given state.

        Args:
            state: Current system state

        Returns:
            Rate value (calls rate function if rate is callable)
        """
        if callable(self._rate):
            return self._rate(state)
        return self._rate

    def add_reactant(self, molecule: Molecule, coefficient: float = 1.0) -> None:
        """Add a reactant to this reaction."""
        self._reactants[molecule] = coefficient

    def add_product(self, molecule: Molecule, coefficient: float = 1.0) -> None:
        """Add a product to this reaction."""
        self._products[molecule] = coefficient

    def attributes(self) -> Dict[str, Any]:
        """Semantic content of this reaction."""
        result = super().attributes()

        # Serialize reactants as {molecule_name: coefficient}
        if self._reactants:
            result["reactants"] = {
                mol.local_name: coef for mol, coef in self._reactants.items()
            }
        if self._products:
            result["products"] = {
                mol.local_name: coef for mol, coef in self._products.items()
            }

        # Only serialize rate if it's a constant
        if not callable(self._rate):
            result["rate"] = self._rate

        return result

    def __repr__(self) -> str:
        """Full representation."""
        reactant_str = " + ".join(
            f"{c}{m.local_name}" if c != 1 else m.local_name
            for m, c in self._reactants.items()
        )
        product_str = " + ".join(
            f"{c}{m.local_name}" if c != 1 else m.local_name
            for m, c in self._products.items()
        )
        rate_str = "<fn>" if callable(self._rate) else str(self._rate)
        return f"ReactionImpl({self._local_name}: {reactant_str} -> {product_str}, rate={rate_str})"
