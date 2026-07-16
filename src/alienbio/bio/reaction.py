"""Reaction: entities representing chemical transformations."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING, Self, Union

from ..infra.entity import Entity

if TYPE_CHECKING:
    from dvc_dat import Dat
    from .molecule import Molecule, MoleculeImpl
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
    - modifiers: catalysts/regulators acting on the reaction WITHOUT being
      consumed (enzymes, inhibitors), each mapped to an opaque role tag
    - rate: constant or function determining reaction speed

    Example:
        # A + 2B -> C, catalyzed by enzyme E, with rate 0.1
        reaction = ReactionImpl(
            "r1",
            reactants={mol_a: 1, mol_b: 2},
            products={mol_c: 1},
            modifiers={enzyme_e: "catalyst"},
            rate=0.1,
            parent=chemistry,
        )
    """

    __slots__ = ("_reactants", "_products", "_modifiers", "_rate")

    def __init__(
        self,
        name: str,
        *,
        reactants: Optional[Dict[Molecule, float]] = None,
        products: Optional[Dict[Molecule, float]] = None,
        modifiers: Optional[Dict[Molecule, str]] = None,
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
            modifiers: Dict mapping catalyst/regulator molecules (not consumed)
                to an opaque role tag (e.g. "catalyst", "inhibitor")
            rate: Reaction rate (constant float or function of State)
            parent: Link to containing entity
            dat: DAT anchor for root reactions
            description: Human-readable description
        """
        super().__init__(name, parent=parent, dat=dat, description=description)
        self._reactants: Dict[Molecule, float] = reactants.copy() if reactants else {}
        self._products: Dict[Molecule, float] = products.copy() if products else {}
        self._modifiers: Dict[Molecule, str] = modifiers.copy() if modifiers else {}
        self._rate: RateValue = rate

    @classmethod
    def hydrate(
        cls,
        data: dict[str, Any],
        *,
        molecules: dict[str, "MoleculeImpl"],
        dat: Optional[Dat] = None,
        parent: Optional[Entity] = None,
        local_name: Optional[str] = None,
    ) -> Self:
        """Create a Reaction from a dict.

        Args:
            data: Dict with keys: reactants, products, rate, name, description
            molecules: Dict mapping molecule names to MoleculeImpl instances
            dat: DAT anchor (if root entity)
            parent: Parent entity (if child)
            local_name: Override name (defaults to data key)

        Returns:
            New ReactionImpl instance
        """
        from ..infra.entity import MockDat

        name = local_name or data.get("name", "reaction")

        # Create mock dat if needed
        if dat is None and parent is None:
            dat = MockDat(f"rxn/{name}")

        # Build reactants dict: {MoleculeImpl: coefficient}
        reactants: Dict[Molecule, float] = {}
        for r in data.get("reactants", []):
            if isinstance(r, str):
                # Just a name, coefficient 1
                if r not in molecules:
                    raise KeyError(
                        f"Reaction {name!r}: unknown reactant molecule {r!r} "
                        f"(not in chemistry molecules)"
                    )
                reactants[molecules[r]] = 1
            elif isinstance(r, dict):
                # {name: coef} format
                for mol_name, coef in r.items():
                    if mol_name not in molecules:
                        raise KeyError(
                            f"Reaction {name!r}: unknown reactant molecule {mol_name!r} "
                            f"(not in chemistry molecules)"
                        )
                    reactants[molecules[mol_name]] = coef

        # Build products dict: {MoleculeImpl: coefficient}
        products: Dict[Molecule, float] = {}
        for p in data.get("products", []):
            if isinstance(p, str):
                # Just a name, coefficient 1
                if p not in molecules:
                    raise KeyError(
                        f"Reaction {name!r}: unknown product molecule {p!r} "
                        f"(not in chemistry molecules)"
                    )
                products[molecules[p]] = 1
            elif isinstance(p, dict):
                # {name: coef} format
                for mol_name, coef in p.items():
                    if mol_name not in molecules:
                        raise KeyError(
                            f"Reaction {name!r}: unknown product molecule {mol_name!r} "
                            f"(not in chemistry molecules)"
                        )
                    products[molecules[mol_name]] = coef

        # Build modifiers dict: {MoleculeImpl: role}.  Accepts the canonical
        # {name: role} mapping (attributes() output) or a bare list of names
        # (role defaults to "", mirroring the reactant/product list form).
        modifiers: Dict[Molecule, str] = {}
        raw_modifiers = data.get("modifiers", {})
        if isinstance(raw_modifiers, dict):
            mod_items = raw_modifiers.items()
        else:
            mod_items = (
                (m, "") if isinstance(m, str) else next(iter(m.items()))
                for m in raw_modifiers
            )
        for mol_name, role in mod_items:
            if mol_name not in molecules:
                raise KeyError(
                    f"Reaction {name!r}: unknown modifier molecule {mol_name!r} "
                    f"(not in chemistry molecules)"
                )
            modifiers[molecules[mol_name]] = role

        # Get rate (function or constant)
        rate = data.get("rate", 1.0)

        return cls(
            name,
            reactants=reactants,
            products=products,
            modifiers=modifiers,
            rate=rate,
            parent=parent,
            dat=dat,
            description=data.get("description", ""),
        )

    @property
    def reactants(self) -> Dict[Molecule, float]:
        """Reactant molecules and their stoichiometric coefficients."""
        return self._reactants.copy()

    @property
    def products(self) -> Dict[Molecule, float]:
        """Product molecules and their stoichiometric coefficients."""
        return self._products.copy()

    @property
    def modifiers(self) -> Dict[Molecule, str]:
        """Catalyst/regulator molecules (not consumed) mapped to a role tag."""
        return self._modifiers.copy()

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

    def add_modifier(self, molecule: Molecule, role: str = "") -> None:
        """Add a catalyst/regulator (not stoichiometrically consumed)."""
        self._modifiers[molecule] = role

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

        # Serialize modifiers as {molecule_name: role} (catalysts/regulators)
        if self._modifiers:
            result["modifiers"] = {
                mol.local_name: role for mol, role in self._modifiers.items()
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
        arrow = "->"
        if self._modifiers:
            mod_str = ", ".join(
                f"{m.local_name}:{role}" if role else m.local_name
                for m, role in self._modifiers.items()
            )
            arrow = f"-[{mod_str}]->"
        return f"ReactionImpl({self._local_name}: {reactant_str} {arrow} {product_str}, rate={rate_str})"
