"""Structural spelling: the Expr YAML tags (M47.1).

``!x <text>`` — the inline form, parsed; ``!q <text|node>`` — a quoted form;
``!ref <name>`` — a name lookup; ``!<head> <mapping>`` — a call with keyword
arguments (positionals under the reserved key ``args:``); ``!<head> [..]`` —
positional arguments; ``!<head> <scalar>`` — one positional argument.
Untagged YAML is data. ``!include`` / ``!py`` are load-time forms
(:class:`~alienbio.expr.form.Include` / :class:`~alienbio.expr.form.PyRef`),
resolved by :mod:`alienbio.expr.include` before evaluation (M47.5). The
legacy ``!ev`` / ``!_`` / ``!quote`` spellings are gone (M47.7): each is a
load error that names its replacement.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Union

import yaml

from .env import ExprError
from .form import Call, Include, Name, PyRef, Quoted
from .parse import MAX_INT_LITERAL_BITS, check_int_literal
from .parse import dump as dump_inline
from .parse import parse

#: The largest spec (or included YAML / text / ``.py``) file a load reads,
#: in bytes (T091 AP7: PyYAML's pure-Python parser runs ~18 s/MB, so a 3 MB
#: list literal was a minute and 700 MB before any meter saw it). Refused
#: before parsing.
MAX_SPEC_BYTES = 1 << 20

#: The most nodes a parsed document may expand to, every occurrence of an
#: aliased node counted (T091 AP3: ten ``*a9`` aliases per level is a
#: 1.2 KB file whose include resolution, nested-experiment check and
#: evaluation each walk 10^10 nodes). Without aliases a ``MAX_SPEC_BYTES``
#: file stays far below it.
MAX_DOCUMENT_NODES = 1_000_000

RESERVED_TAGS: frozenset[str] = frozenset({"x", "q", "ref", "include", "py"})

#: The M1 spellings and what replaced them (M47.7 — no aliases survive).
LEGACY_TAGS: dict[str, str] = {"ev": "!x", "_": "!q", "quote": "!q"}


class ExprLoader(yaml.SafeLoader):
    """``yaml.SafeLoader`` plus the Expr tags. A subclass, so the global
    SafeLoader (and every other loader in the process) is untouched."""


def _int_constructor(loader: yaml.Loader, node: yaml.Node) -> Any:
    """A YAML int, capped at :data:`MAX_INT_LITERAL_BITS` (T091 AP4). The
    text is bounded first (a third of the bit cap in characters — a decimal
    past 4 300 digits is refused by Python anyway, and base-60 converts
    quadratically), so the conversion itself is never the cost."""
    text = str(getattr(node, "value", ""))
    if len(text) > MAX_INT_LITERAL_BITS // 3:
        raise ExprError(f"integer literal of {len(text)} characters exceeds MAX_INT_LITERAL_BITS={MAX_INT_LITERAL_BITS}", _mark(node))
    value = loader.construct_yaml_int(node)  # type: ignore[attr-defined]
    if value.bit_length() > MAX_INT_LITERAL_BITS:
        check_int_literal(value, _mark(node))
    return value


ExprLoader.add_constructor("tag:yaml.org,2002:int", _int_constructor)


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
    if head in LEGACY_TAGS:
        raise ExprError(f"!{head} is the old spelling — write {LEGACY_TAGS[head]}", _mark(node))
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
    return f"line {m.line + 1}" if m is not None else ""


ExprLoader.add_constructor("!x", _x_constructor)
ExprLoader.add_constructor("!q", _q_constructor)
ExprLoader.add_constructor("!ref", _ref_constructor)
ExprLoader.add_constructor("!include", _include_constructor)
ExprLoader.add_constructor("!py", _py_constructor)
ExprLoader.add_multi_constructor("!", _call_constructor)


def check_spec_size(path: Union[str, Path]) -> None:
    """Refuse a file over :data:`MAX_SPEC_BYTES` before it is read (T091 AP7)."""
    size = Path(path).stat().st_size
    if size > MAX_SPEC_BYTES:
        raise ExprError(f"file of {size} bytes exceeds MAX_SPEC_BYTES={MAX_SPEC_BYTES}", str(path))


def read_spec_text(path: Union[str, Path]) -> str:
    """A spec file's text, size-checked first (:func:`check_spec_size`)."""
    check_spec_size(path)
    return Path(path).read_text()


def _refuse_recursion(data: Any, source: str) -> None:
    """A recursive alias (``a: &a [1, *a]``) builds a cyclic value no Expr
    walk terminates on; refused (each distinct node is visited once)."""
    import dataclasses

    done: set[int] = set()
    active: set[int] = set()
    stack: list[tuple[Any, bool]] = [(data, False)]
    while stack:
        x, leaving = stack.pop()
        if leaving:
            active.discard(id(x))
            done.add(id(x))
            continue
        if id(x) in active:
            raise ExprError("a recursive YAML alias (a node that contains itself) is not a value", source)
        if id(x) in done:
            continue
        if isinstance(x, dict):
            items: Any = [v for kv in x.items() for v in kv]
        elif isinstance(x, (list, tuple, set, frozenset)):
            items = x
        elif dataclasses.is_dataclass(x) and not isinstance(x, type):
            items = [getattr(x, f.name, None) for f in dataclasses.fields(x)]
        else:
            continue
        active.add(id(x))
        stack.append((x, True))
        stack.extend((item, False) for item in items)


def load_text(text: str, *, source: str = "") -> Any:
    """YAML text -> forms (data with Name / Call / Quoted where tagged).

    ONE parse (T091 AP7 — an experiment file was parsed three times): the
    document is composed once, the duplicate-key check
    (:func:`alienbio.suite.yaml_keys.refuse_duplicate_nodes`) walks that node
    tree, and the forms are constructed from it. Text over
    :data:`MAX_SPEC_BYTES` refuses before parsing. Every failure — a syntax
    error, a duplicate key, nesting past Python's stack, an oversized int —
    is an :class:`ExprError` naming ``source`` (T091 AP9), never a raw
    ``yaml.YAMLError`` or ``RecursionError``."""
    from ..suite.yaml_keys import refuse_duplicate_nodes

    if len(text) > MAX_SPEC_BYTES or len(text.encode("utf-8")) > MAX_SPEC_BYTES:
        raise ExprError(f"spec text over MAX_SPEC_BYTES={MAX_SPEC_BYTES} bytes", source)
    loader = ExprLoader(text)
    try:
        node = loader.get_single_node()
        if node is None:
            return None
        refuse_duplicate_nodes(node)
        data = loader.construct_document(node)
    except ExprError as exc:
        if source:
            raise ExprError(exc.message, f"{source}, {exc.path}" if exc.path else source) from None
        raise
    except yaml.YAMLError as exc:
        raise ExprError(f"YAML error: {exc}", source) from None
    except RecursionError:
        # PyYAML composes and constructs recursively, so a deeply nested
        # document overflows Python's stack before any Expr limit can see it
        # (T091 C11). Read as the depth cap it is.
        raise ExprError("YAML nesting deeper than limits.depth allows (Python recursion limit)", source) from None
    except ValueError as exc:  # the duplicate-key check
        raise ExprError(str(exc), source) from None
    finally:
        loader.dispose()
    from .heads import element_bound

    _refuse_recursion(data, source)
    nodes = element_bound(data, MAX_DOCUMENT_NODES)
    if nodes > MAX_DOCUMENT_NODES:
        raise ExprError(f"the document expands to more than MAX_DOCUMENT_NODES={MAX_DOCUMENT_NODES} nodes (YAML aliases repeat what they name)", source)
    return data


# ---------------------------------------------------------------------------
# dump (structural)
# ---------------------------------------------------------------------------


class ExprDumper(yaml.SafeDumper):
    pass


def _represent_call(dumper: "ExprDumper", call: Call) -> yaml.Node:
    tag = f"!{call.head}"
    if "args" in call.kwargs:
        # T088 yaml_tags 2: the mapping form reads an `args` key as the
        # positionals, so a keyword of that name has no structural spelling.
        raise ExprError(f"!{call.head}: a keyword argument named 'args' cannot be written in the structural spelling")
    if call.kwargs or not call.args:
        mapping: dict[str, Any] = {}
        if call.args:
            mapping["args"] = list(call.args)
        mapping.update(call.kwargs)
        node = dumper.represent_mapping(tag, mapping, flow_style=True)
        return node
    if len(call.args) == 1 and isinstance(call.args[0], str) and call.args[0]:
        return dumper.represent_scalar(tag, call.args[0], style='"')
    # T088 yaml_tags 1–2: a lone number or bool written as a tagged scalar
    # came back a string (`!poisson '3'` -> poisson('3')), and a lone "" came
    # back as no argument; a one-element flow sequence keeps its type.
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
