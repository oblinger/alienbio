"""Structural spelling: the Expr YAML tags (M47.1).

``!x <text>`` — the inline form, parsed; ``!q <text|node>`` — a quoted form;
``!ref <name>`` — a name lookup; ``!<head> <mapping>`` — a call with keyword
arguments (positionals under the reserved key ``args:``); ``!<head> [..]`` —
positional arguments; ``!<head> <scalar>`` — one positional argument.
Untagged YAML is data. ``!include`` / ``!py`` are load-time forms
(:class:`~alienbio.expr.form.Include` / :class:`~alienbio.expr.form.PyRef`),
resolved by :mod:`alienbio.expr.include` before evaluation (M47.5); ``!ev`` /
``!_`` / ``!quote`` are the legacy spellings and are removed at G4 close
(M47.7).
"""

from __future__ import annotations

import io
from typing import Any

import yaml

from .env import ExprError
from .form import Call, Include, Name, PyRef, Quoted
from .parse import dump as dump_inline
from .parse import parse

RESERVED_TAGS: frozenset[str] = frozenset({"x", "q", "ref", "include", "py", "ev", "_", "quote"})


class ExprLoader(yaml.SafeLoader):
    """``yaml.SafeLoader`` plus the Expr tags. A subclass, so the global
    SafeLoader (and every other loader in the process) is untouched."""


def _x_constructor(loader: yaml.Loader, node: yaml.Node) -> Any:
    if not isinstance(node, yaml.ScalarNode):
        raise ExprError("!x takes a string (the inline expression)", _mark(node))
    return parse(str(loader.construct_scalar(node)), path=_mark(node))


def _q_constructor(loader: yaml.Loader, node: yaml.Node) -> Any:
    if isinstance(node, yaml.ScalarNode):
        return Quoted(parse(str(loader.construct_scalar(node)), path=_mark(node)))
    return Quoted(_construct_node(loader, node))


def _ref_constructor(loader: yaml.Loader, node: yaml.Node) -> Any:
    if not isinstance(node, yaml.ScalarNode):
        raise ExprError("!ref takes a name", _mark(node))
    return Name(str(loader.construct_scalar(node)))


def _include_constructor(loader: yaml.Loader, node: yaml.Node) -> Any:
    if not isinstance(node, yaml.ScalarNode):
        raise ExprError("!include takes a path", _mark(node))
    return Include(str(loader.construct_scalar(node)))


def _py_constructor(loader: yaml.Loader, node: yaml.Node) -> Any:
    if not isinstance(node, yaml.ScalarNode):
        raise ExprError("!py takes a dotted module.attr path", _mark(node))
    return PyRef(str(loader.construct_scalar(node)))


def _construct_node(loader: yaml.Loader, node: yaml.Node) -> Any:
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)  # type: ignore[call-arg]
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)  # type: ignore[call-arg]
    return _scalar(loader, node)


def _scalar(loader: yaml.Loader, node: yaml.Node) -> Any:
    """A tagged scalar's value with YAML's implicit typing (``3`` -> int)."""
    assert isinstance(node, yaml.ScalarNode)
    text = str(loader.construct_scalar(node))
    if node.style is not None:  # quoted in the source: a string
        return text
    tag = loader.resolve(yaml.ScalarNode, text, (True, False))  # type: ignore[arg-type]
    plain = yaml.ScalarNode(tag, text)
    return loader.construct_object(plain)


def _call_constructor(loader: yaml.Loader, tag_suffix: str, node: yaml.Node) -> Any:
    head = tag_suffix
    if head in RESERVED_TAGS:
        raise ExprError(f"!{head} is a reserved tag", _mark(node))
    if not head or not all(part.isidentifier() for part in head.replace(":", ".").split(".")):
        raise ExprError(f"!{head}: a head must be an identifier", _mark(node))
    if isinstance(node, yaml.MappingNode):
        mapping = loader.construct_mapping(node, deep=True)  # type: ignore[call-arg]
        args = mapping.pop("args", [])
        if not isinstance(args, (list, tuple)):
            raise ExprError(f"!{head}: args must be a list", _mark(node))
        bad = [k for k in mapping if not (isinstance(k, str) and k.isidentifier())]
        if bad:
            raise ExprError(f"!{head}: keyword names must be identifiers, got {bad}", _mark(node))
        return Call(head, tuple(args), {str(k): v for k, v in mapping.items()})
    if isinstance(node, yaml.SequenceNode):
        return Call(head, tuple(loader.construct_sequence(node, deep=True)))  # type: ignore[call-arg]
    value = _scalar(loader, node)
    if value is None or value == "":
        return Call(head)
    return Call(head, (value,))


def _mark(node: yaml.Node) -> str:
    m = node.start_mark
    return f"line {m.line + 1}"


ExprLoader.add_constructor("!x", _x_constructor)
ExprLoader.add_constructor("!q", _q_constructor)
ExprLoader.add_constructor("!ref", _ref_constructor)
ExprLoader.add_constructor("!include", _include_constructor)
ExprLoader.add_constructor("!py", _py_constructor)
ExprLoader.add_multi_constructor("!", _call_constructor)


def load_text(text: str) -> Any:
    """YAML text -> forms (data with Name / Call / Quoted where tagged)."""
    try:
        return yaml.load(text, Loader=ExprLoader)  # noqa: S506 - ExprLoader is a SafeLoader
    except yaml.YAMLError as exc:
        raise ExprError(f"YAML error: {exc}") from None


# ---------------------------------------------------------------------------
# dump (structural)
# ---------------------------------------------------------------------------


class ExprDumper(yaml.SafeDumper):
    pass


def _represent_call(dumper: "ExprDumper", call: Call) -> yaml.Node:
    tag = f"!{call.head}"
    if call.kwargs or not call.args:
        mapping: dict[str, Any] = {}
        if call.args:
            mapping["args"] = list(call.args)
        mapping.update(call.kwargs)
        node = dumper.represent_mapping(tag, mapping, flow_style=True)
        return node
    if len(call.args) == 1 and isinstance(call.args[0], (str, int, float, bool)):
        return dumper.represent_scalar(tag, str(call.args[0]), style='"' if isinstance(call.args[0], str) else None)
    return dumper.represent_sequence(tag, list(call.args), flow_style=True)


def _represent_name(dumper: "ExprDumper", name: Name) -> yaml.Node:
    return dumper.represent_scalar("!ref", name.path)


def _represent_quoted(dumper: "ExprDumper", q: Quoted) -> yaml.Node:
    # always quoted: an inline expression may hold commas / braces that a YAML
    # flow context would otherwise split
    return dumper.represent_scalar("!q", dump_inline(q.form), style='"')


ExprDumper.add_representer(Call, _represent_call)
ExprDumper.add_representer(Name, _represent_name)
ExprDumper.add_representer(Quoted, _represent_quoted)


def dump_structural(form: Any) -> str:
    """Form -> YAML text in the structural spelling (loads back to an equal form)."""
    buf = io.StringIO()
    yaml.dump(form, buf, Dumper=ExprDumper, sort_keys=False, default_flow_style=None, allow_unicode=True)
    return buf.getvalue()
