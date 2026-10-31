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
import os
import stat
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


def int_text_refusal(text: str) -> "str | None":
    """Why a YAML int's text may not be converted, else ``None`` (T091 AP4,
    AR5). A base-60 form (``1:59:59``, YAML 1.1 sexagesimal) is refused
    outright: PyYAML converts it digit group by digit group, quadratically
    (a 349k-character literal under the length cap took 8 s). Any other
    form is bounded at a third of the bit cap in characters — hex, octal
    and binary convert linearly, and a decimal past 4 300 digits is refused
    by Python itself — so the conversion is never the cost."""
    if ":" in text:
        return "a base-60 (sexagesimal) integer literal is not accepted; write it in decimal"
    if len(text) > MAX_INT_LITERAL_BITS // 3:
        return f"integer literal of {len(text)} characters exceeds MAX_INT_LITERAL_BITS={MAX_INT_LITERAL_BITS}"
    return None


def _int_constructor(loader: yaml.Loader, node: yaml.Node) -> Any:
    """A YAML int, capped at :data:`MAX_INT_LITERAL_BITS` (T091 AP4); the
    text is judged first (:func:`int_text_refusal`)."""
    text = str(getattr(node, "value", ""))
    refusal = int_text_refusal(text)
    if refusal is not None:
        raise ExprError(refusal, _mark(node))
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


def _regular_file_size(path: Union[str, Path]) -> int:
    """The size of the regular file ``path`` resolves to; a FIFO, a device
    or a symlink to one is refused (T091 AR7: ``st_size`` is 0 for both, so
    a FIFO blocked the read and ``/dev/zero`` read forever)."""
    resolved = Path(os.path.realpath(path))
    st = resolved.stat()
    if not stat.S_ISREG(st.st_mode):
        raise ExprError("not a regular file (a spec is read from a plain file, never a FIFO or a device)", str(path))
    return st.st_size


def check_spec_size(path: Union[str, Path]) -> None:
    """Refuse a non-regular file, or one over :data:`MAX_SPEC_BYTES`, before
    it is read (T091 AP7, AR7)."""
    size = _regular_file_size(path)
    if size > MAX_SPEC_BYTES:
        raise ExprError(f"file of {size} bytes exceeds MAX_SPEC_BYTES={MAX_SPEC_BYTES}", str(path))


def read_spec_text(path: Union[str, Path]) -> str:
    """A spec file's text: size-checked first (:func:`check_spec_size`),
    then read with a hard limit of :data:`MAX_SPEC_BYTES` + 1 bytes, so a
    file that grows between the check and the read still refuses (T091 AR7)."""
    check_spec_size(path)
    with open(os.path.realpath(path), "rb") as fh:
        raw = fh.read(MAX_SPEC_BYTES + 1)
    if len(raw) > MAX_SPEC_BYTES:
        raise ExprError(f"file grew past MAX_SPEC_BYTES={MAX_SPEC_BYTES} while being read", str(path))
    return raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


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


_MERGE_TAG = "tag:yaml.org,2002:merge"


def merge_expansion(node: yaml.Node, limit: int) -> int:
    """The key/value pairs PyYAML's merge-key flattening (``<<:``) builds
    over every distinct mapping node of the composed tree, capped just past
    ``limit`` (T091 AR2). ``flatten_mapping`` concatenates each merged
    mapping's pairs without de-duplicating, so ``L{i}: {<<: [*L{i-1},
    *L{i-1}]}`` doubles per level — an 834-byte file built 2^26 pairs inside
    the constructor, before any node cap. Computed on the nodes, memoized by
    identity, so it costs the distinct structure; a merge cycle adds nothing
    (PyYAML refuses it)."""
    memo: dict[int, int] = {}
    total = 0
    seen: set[int] = set()
    stack: list[tuple[yaml.Node, bool]] = [(node, False)]

    def merged(m: yaml.Node) -> list[yaml.Node]:
        out: list[yaml.Node] = []
        for k, v in m.value:
            if k.tag != _MERGE_TAG:
                continue
            if isinstance(v, yaml.MappingNode):
                out.append(v)
            elif isinstance(v, yaml.SequenceNode):
                out.extend(sub for sub in v.value if isinstance(sub, yaml.MappingNode))
        return out

    while stack:
        x, leaving = stack.pop()
        if leaving:
            n = sum(1 for k, _ in x.value if k.tag != _MERGE_TAG)
            n += sum(memo.get(id(sub), 0) for sub in merged(x))
            memo[id(x)] = min(n, limit + 1)
            total += memo[id(x)]
            if total > limit:
                return total
            continue
        if id(x) in seen:
            continue
        seen.add(id(x))
        if isinstance(x, yaml.MappingNode):
            stack.append((x, True))
            for k, v in x.value:
                stack.append((k, False))
                stack.append((v, False))
        elif isinstance(x, yaml.SequenceNode):
            stack.extend((item, False) for item in x.value)
    return total


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
        if merge_expansion(node, MAX_DOCUMENT_NODES) > MAX_DOCUMENT_NODES:
            raise ExprError(
                f"the document's merge keys (<<:) expand to more than MAX_DOCUMENT_NODES={MAX_DOCUMENT_NODES} key/value pairs"
            )
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
