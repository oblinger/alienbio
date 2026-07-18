"""Register the biology entity makers on the ``mk`` pegboard.

Importing this module wires the short maker keys ``M`` / ``R`` / ``C`` to the
molecule / reaction / chemistry implementations, so callers can write
``mk.M("A")`` instead of ``MoleculeImpl("A", name="A", dat=MockDat("mol/A"))``.
The anchor prefixes (``mol`` / ``rxn`` / ``chem``) match the conventions already
used by each class's ``hydrate`` mock-dat fallback.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from ..infra.entity import Entity
from ..infra.mk import mk
from .chemistry import ChemistryImpl
from .molecule import MoleculeImpl
from .reaction import ReactionImpl


def _named_dict(items: Any) -> dict[str, Any]:
    """Coerce a list of entities (keyed by ``local_name``) or a dict into a dict.

    ``None`` -> ``{}``; a ``Mapping`` passes through (copied); an iterable of
    entities becomes ``{entity.local_name: entity}`` — the derivation that lets
    ``mk.C("world", [a, b], [r])`` drop the ``{"A": a, ...}`` boilerplate.
    """
    if items is None:
        return {}
    if isinstance(items, Mapping):
        return dict(items)
    if isinstance(items, Iterable):
        result: dict[str, Any] = {}
        for entity in items:
            if not isinstance(entity, Entity):
                raise TypeError(
                    f"mk.C list entries must be entities with a local_name; got {entity!r}"
                )
            result[entity.local_name] = entity
        return result
    raise TypeError(f"expected None, a Mapping, or an iterable of entities; got {items!r}")


def _build_molecule(local_name: str, anchor: dict[str, Any], **kwargs: Any) -> MoleculeImpl:
    return MoleculeImpl(local_name, **anchor, **kwargs)


def _build_reaction(
    local_name: str,
    anchor: dict[str, Any],
    reactants: Any = None,
    products: Any = None,
    **kwargs: Any,
) -> ReactionImpl:
    return ReactionImpl(
        local_name, reactants=reactants, products=products, **anchor, **kwargs
    )


def _build_chemistry(
    local_name: str,
    anchor: dict[str, Any],
    molecules: Any = None,
    reactions: Any = None,
    **kwargs: Any,
) -> ChemistryImpl:
    return ChemistryImpl(
        local_name,
        molecules=_named_dict(molecules),
        reactions=_named_dict(reactions),
        **anchor,
        **kwargs,
    )


mk.register("M", prefix="mol", build=_build_molecule)
mk.register("R", prefix="rxn", build=_build_reaction)
mk.register("C", prefix="chem", build=_build_chemistry)
