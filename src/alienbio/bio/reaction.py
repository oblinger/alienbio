"""Reaction: entities representing chemical transformations."""

from __future__ import annotations

import numbers
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, TYPE_CHECKING, Self, Tuple, Union

from ..infra.entity import DatLike, Entity

if TYPE_CHECKING:
    from dvc_dat import Dat
    from .molecule import MoleculeImpl


#: A reaction's rate constant. (A callable rate was the M1 single-compartment
#: simulator's; the world simulator compiles ``rate_law`` trees — T056.)
RateValue = float


@dataclass(frozen=True)
class Modulation:
    """A modifier's effect on its reaction's rate (F015 S2 bidirectional modulation).

    Ship-now form is LINEAR (F015 Q1): an ``"activator"`` (param ``a``) scales the rate
    up via ``(1 + a * [modifier])``; an ``"inhibitor"`` (param ``Ki``) scales it down via
    dividing by ``(1 + [modifier] / Ki)``. Two saturable kinds (M38.3): ``"michaelis"``
    (params ``Vmax``/``K``) and ``"hill"`` (additionally ``n``) — see the field docs
    below and ``WorldSimulatorImpl._modulation_factor``. Any other ``kind`` (including
    the label-only default ``""``) is rate-inert — a pure documentation tag,
    contributing a factor of exactly ``1.0``.

    Frozen + a pure function of the frozen start-of-step state elsewhere (F015 Q4): this
    dataclass only carries the parameters, it has no simulation behavior of its own.
    """

    kind: str = ""
    a: Optional[float] = None
    Ki: Optional[float] = None
    #: Saturable-kind params (F015 M38.3): ``"michaelis"`` uses ``Vmax``/``K``
    #: (``Vmax * [modifier] / (K + [modifier])``); ``"hill"`` additionally uses
    #: the cooperativity exponent ``n`` (``Vmax * [modifier]**n / (K**n +
    #: [modifier]**n)``). Both are keyed off the MODIFIER's own concentration,
    #: same as the linear ``a``/``Ki`` kinds — see
    #: ``WorldSimulatorImpl._modulation_factor``.
    Vmax: Optional[float] = None
    K: Optional[float] = None
    n: Optional[float] = None

    @classmethod
    def from_value(cls, value: "Union[Modulation, str]") -> "Modulation":
        """Coerce a bare ``str`` role tag into a label-only, rate-inert ``Modulation``.

        Backward-compat (F015 Q2): every existing call site passes a bare ``str`` role
        (e.g. ``"catalyst"``); that role becomes ``Modulation(kind=<the string>)``, whose
        factor is exactly ``1.0`` — matching today, where the role never reached the
        simulator.
        """
        if isinstance(value, Modulation):
            return value
        return cls(kind=value)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize non-default fields (for ``attributes()``/``hydrate()`` round-trips)."""
        result: Dict[str, Any] = {"kind": self.kind}
        if self.a is not None:
            result["a"] = self.a
        if self.Ki is not None:
            result["Ki"] = self.Ki
        if self.Vmax is not None:
            result["Vmax"] = self.Vmax
        if self.K is not None:
            result["K"] = self.K
        if self.n is not None:
            result["n"] = self.n
        return result


# A modifier's value: either the new first-class Modulation, or (for backward compat)
# a bare opaque role-tag string, which is inert (factor 1.0) — see Modulation.from_value.
ModifierValue = Union[Modulation, str]


def _numeric_rate(reaction: str, rate: Any) -> RateValue:
    """``rate`` itself when it is a real number; ``ValueError`` otherwise.

    A non-numeric rate (``"abc"``, ``None``, a callable — the M1 simulator's,
    refused since T056) used to be accepted here and fail only when a
    simulator was built from the reaction (module-doc finding, 2026-10).
    """
    if isinstance(rate, numbers.Real) and not isinstance(rate, bool):
        return rate  # type: ignore[return-value]
    raise ValueError(
        f"reaction {reaction!r}: rate must be a number (got {type(rate).__name__}: "
        f"{rate!r}); a rate law is `rate_law`, compiled by rate_expr"
    )


def _side_items(
    reaction: str, role: str, raw: Any, default: Any
) -> List[Tuple[str, Any]]:
    """The ``(molecule name, value)`` pairs of one side of a serialized reaction.

    Two forms: the ``{name: value}`` mapping ``attributes()`` writes, and the
    list ``!Reaction`` builds, whose entries are bare names (value
    ``default``) or ``{name: value}`` dicts (every key kept). Iterating the
    mapping form as a list read its keys alone, so every coefficient
    reloaded as 1 (module-doc finding, 2026-10).
    """
    if isinstance(raw, Mapping):
        return [(str(k), v) for k, v in raw.items()]
    items: List[Tuple[str, Any]] = []
    for entry in raw or ():
        if isinstance(entry, str):
            items.append((entry, default))
        elif isinstance(entry, Mapping):
            items.extend((str(k), v) for k, v in entry.items())
        else:
            raise TypeError(
                f"Reaction {reaction!r}: a {role} entry must be a molecule name or a "
                f"{{name: value}} mapping, got {type(entry).__name__}: {entry!r}"
            )
    return items


def _hydrate_side(
    reaction: str, role: str, raw: Any, molecules: Mapping[str, "MoleculeImpl"]
) -> Dict["MoleculeImpl", float]:
    """``{MoleculeImpl: coefficient}`` for one side; an unknown name refuses."""
    side: Dict[MoleculeImpl, float] = {}
    for mol_name, coef in _side_items(reaction, role, raw, 1):
        if mol_name not in molecules:
            raise KeyError(
                f"Reaction {reaction!r}: unknown {role} molecule {mol_name!r} "
                f"(not in chemistry molecules)"
            )
        side[molecules[mol_name]] = coef
    return side


class ReactionImpl(Entity, head="Reaction"):
    """Implementation: A reaction transforming reactants into products.

    Reactions define transformations in the biological system.
    Each reaction has:
    - reactants: molecules consumed (with stoichiometric coefficients)
    - products: molecules produced (with stoichiometric coefficients)
    - modifiers: catalysts/regulators acting on the reaction WITHOUT being
      consumed (enzymes, inhibitors), each mapped to a ``Modulation`` (or a
      bare opaque role-tag ``str``, for backward compat — see ``Modulation``)
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

    __slots__ = ("_reactants", "_products", "_modifiers", "_rate", "_rate_law")

    def __init__(
        self,
        name: str,
        *,
        reactants: Optional[Dict[MoleculeImpl, float]] = None,
        products: Optional[Dict[MoleculeImpl, float]] = None,
        modifiers: Optional[Mapping[MoleculeImpl, ModifierValue]] = None,
        rate: RateValue = 1.0,
        rate_law: Optional[Any] = None,
        parent: Optional[Entity] = None,
        dat: Optional[DatLike] = None,
        description: str = "",
    ) -> None:
        """Initialize a reaction.

        Args:
            name: Local name within parent
            reactants: Dict mapping molecules to stoichiometric coefficients
            products: Dict mapping molecules to stoichiometric coefficients
            modifiers: Mapping catalyst/regulator molecules (not consumed) to a
                ``Modulation`` (kind + rate params) or a bare opaque role tag
                ``str`` (e.g. "catalyst") — a bare string is inert (factor 1.0)
            rate: Reaction rate (constant float or function of StateImpl)
            rate_law: Optional compiled rate expression (``bio.rate_expr``, species
                by molecule name) — the whole rate when it names a reactant, else the
                factor multiplying mass action; ``rate`` is then unused (M47.10)
            parent: Link to containing entity
            dat: DAT anchor for root reactions
            description: Human-readable description
        """
        super().__init__(name, parent=parent, dat=dat, description=description)
        self._reactants: Dict[MoleculeImpl, float] = reactants.copy() if reactants else {}
        self._products: Dict[MoleculeImpl, float] = products.copy() if products else {}
        self._modifiers: Dict[MoleculeImpl, ModifierValue] = dict(modifiers) if modifiers else {}
        self._rate: RateValue = _numeric_rate(name, rate)
        from .rate_expr import from_json

        self._rate_law: Optional[Any] = from_json(rate_law) if rate_law is not None else None

    @classmethod
    def hydrate(  # type: ignore[override]
        cls,
        data: dict[str, Any],
        *,
        molecules: dict[str, "MoleculeImpl"],
        dat: Optional[DatLike] = None,
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

        reactants = _hydrate_side(name, "reactant", data.get("reactants", ()), molecules)
        products = _hydrate_side(name, "product", data.get("products", ()), molecules)

        # Build modifiers dict: {MoleculeImpl: role}.  Accepts the canonical
        # {name: role} mapping (attributes() output) or a list of names and
        # {name: role} dicts (a bare name's role defaults to "", mirroring the
        # reactant/product list form; a dict contributes every key). A role
        # that is itself a dict is a serialized Modulation (Modulation.to_dict());
        # everything else (a bare str) stays as-is, inert by default.
        modifiers: Dict[MoleculeImpl, ModifierValue] = {}
        for mol_name, role in _side_items(name, "modifier", data.get("modifiers", {}), ""):
            if mol_name not in molecules:
                raise KeyError(
                    f"Reaction {name!r}: unknown modifier molecule {mol_name!r} "
                    f"(not in chemistry molecules)"
                )
            modifiers[molecules[mol_name]] = Modulation(**role) if isinstance(role, dict) else role

        # Get rate (function or constant)
        rate = data.get("rate", 1.0)

        return cls(
            name,
            reactants=reactants,
            products=products,
            modifiers=modifiers,
            rate=rate,
            rate_law=data.get("rate_law"),
            parent=parent,
            dat=dat,
            description=data.get("description", ""),
        )

    @property
    def reactants(self) -> Dict[MoleculeImpl, float]:
        """Reactant molecules and their stoichiometric coefficients."""
        return self._reactants.copy()

    @property
    def products(self) -> Dict[MoleculeImpl, float]:
        """Product molecules and their stoichiometric coefficients."""
        return self._products.copy()

    @property
    def modifiers(self) -> Dict[MoleculeImpl, ModifierValue]:
        """Catalyst/regulator molecules (not consumed) mapped to a ``Modulation``
        (or a bare opaque role-tag ``str``, for backward compat — see ``Modulation``)."""
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

    @property
    def rate_law(self) -> Optional[Any]:
        """The compiled rate expression (``bio.rate_expr`` tree, species by
        name), or ``None`` for plain mass action (M47.10)."""
        return self._rate_law

    def set_rate(self, rate: RateValue) -> None:
        """Set the reaction rate (a number; anything else refuses)."""
        self._rate = _numeric_rate(self._local_name, rate)

    def add_reactant(self, molecule: MoleculeImpl, coefficient: float = 1.0) -> None:
        """Add a reactant to this reaction."""
        self._reactants[molecule] = coefficient

    def add_product(self, molecule: MoleculeImpl, coefficient: float = 1.0) -> None:
        """Add a product to this reaction."""
        self._products[molecule] = coefficient

    def add_modifier(self, molecule: MoleculeImpl, role: ModifierValue = "") -> None:
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

        # Serialize modifiers as {molecule_name: role} (catalysts/regulators). A bare
        # str role round-trips as-is; a Modulation serializes via to_dict() so hydrate()
        # can reconstruct it.
        if self._modifiers:
            result["modifiers"] = {
                mol.local_name: (role.to_dict() if isinstance(role, Modulation) else role)
                for mol, role in self._modifiers.items()
            }

        result["rate"] = self._rate
        if self._rate_law is not None:
            from .rate_expr import to_json

            result["rate_law"] = to_json(self._rate_law)

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
        rate_str = str(self._rate)
        arrow = "->"
        if self._modifiers:
            mod_str = ", ".join(
                f"{m.local_name}:{role}" if role else m.local_name
                for m, role in self._modifiers.items()
            )
            arrow = f"-[{mod_str}]->"
        return f"ReactionImpl({self._local_name}: {reactant_str} {arrow} {product_str}, rate={rate_str})"
