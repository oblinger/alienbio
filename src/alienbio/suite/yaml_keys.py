"""The one duplicate-key check every hand-written YAML the suite reads goes
through: the registration registry and every experiment file (T088
registration 1, T091 B5/B12).

PyYAML's loaders keep the LAST value of a repeated mapping key, so a second
``arm:`` axis block silently replaced the first, and a second
``trials_per_condition:`` ran instead of the one a reviewer reads first. The
check walks the composed node graph (no constructor runs, so the Expr tags
need no special handling) and refuses two equal explicit keys in one
mapping. A ``<<:`` merge key is not a duplicate: YAML's merge lets an
explicit key override a merged one, so merge keys are skipped and only the
mapping's own keys are compared.
"""

from __future__ import annotations

from typing import Any

import yaml

_MERGE_TAG = "tag:yaml.org,2002:merge"
_STANDARD_TAG_PREFIX = "tag:yaml.org,2002:"


def _key_identity(node: yaml.Node) -> Any:
    """What makes two key nodes the same key: a standard scalar's
    constructed value (``1`` and ``0x1`` are one int key), any other scalar's
    ``(tag, text)``; a non-scalar key is compared by nothing (``None``)."""
    if not isinstance(node, yaml.ScalarNode):
        return None
    if node.tag.startswith(_STANDARD_TAG_PREFIX) and len(node.value) <= 4096:
        # A longer standard scalar is compared by its text: constructing a
        # huge int key here would bypass the Expr loader's int cap (T091 AP4).
        return ("std", yaml.SafeLoader("").construct_object(node))
    return (node.tag, node.value)


def _walk(node: yaml.Node, seen: set[int]) -> None:
    if id(node) in seen:
        return
    seen.add(id(node))
    if isinstance(node, yaml.MappingNode):
        keys: dict[Any, int] = {}
        for key_node, value_node in node.value:
            if key_node.tag != _MERGE_TAG:
                ident = _key_identity(key_node)
                if ident is not None:
                    line = key_node.start_mark.line + 1
                    if ident in keys:
                        raise ValueError(
                            f"duplicate key {key_node.value!r} at line {line} "
                            f"(first at line {keys[ident]}) — YAML would keep only the last"
                        )
                    keys[ident] = line
            _walk(key_node, seen)
            _walk(value_node, seen)
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            _walk(item, seen)


def refuse_duplicate_nodes(node: yaml.Node) -> None:
    """Raise ``ValueError`` naming the key and its lines when any mapping in
    the composed ``node`` tree repeats a key — the check on a tree a loader
    already composed, so the document is parsed once (T091 AP7)."""
    _walk(node, set())


def refuse_duplicate_keys(text: str, loader: type) -> None:
    """Raise ``ValueError`` naming the key and its lines when any mapping in
    ``text`` (composed by ``loader``) repeats a key. A YAML syntax error
    propagates as the parser's ``yaml.YAMLError``. (The Expr loader runs the
    same walk on its own single parse: ``expr.yaml_tags.load_text``.)"""
    node = yaml.compose(text, Loader=loader)  # noqa: S506 — compose builds nodes, runs no constructor
    if node is not None:
        refuse_duplicate_nodes(node)
