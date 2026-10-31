"""Inline spelling: Python-expression text <-> forms (M47.1).

``parse(text)`` validates ``text`` against the spec sandbox's AST allowlist
(``spec_lang.safe_eval``) and converts the tree to forms: names and dotted
attribute chains become :class:`Name`; calls become :class:`Call`; operators,
subscripts, f-strings and method calls become calls of the ``op:*`` builtin
heads; comprehensions become the ``each`` special form; ``a if c else b``
becomes ``if``; ``and`` / ``or`` become the short-circuit ``op:and`` /
``op:or``. Lambdas are refused (D2: no closures in the language).

``dump(form)`` renders a form back to inline text.
"""

from __future__ import annotations

import ast
from typing import Any, Mapping, Optional

from ..spec_lang.safe_eval import UnsafeExpressionError, validate_expression
from .env import ExprError
from .form import Call, Name, Quoted

#: The largest integer literal, in bits, a spec may write — inline here,
#: in YAML in :mod:`.yaml_tags` (T091 AP4: a 2 MB hex literal was an
#: 8 M-bit int, free, and one ``%`` on it ran 40 s). Equal to
#: ``heads.MAX_POW_RESULT_BITS``: no integer a spec holds is bigger than one
#: it could compute.
MAX_INT_LITERAL_BITS = 1 << 20


def check_int_literal(value: int, path: str = "") -> int:
    """``value`` if it fits :data:`MAX_INT_LITERAL_BITS`, else an :class:`ExprError`."""
    bits = value.bit_length()
    if bits > MAX_INT_LITERAL_BITS:
        raise ExprError(f"integer literal of {bits} bits exceeds MAX_INT_LITERAL_BITS={MAX_INT_LITERAL_BITS}", path)
    return value


_BINOPS: dict[type, str] = {
    ast.Add: "add",
    ast.Sub: "sub",
    ast.Mult: "mul",
    ast.Div: "div",
    ast.FloorDiv: "floordiv",
    ast.Mod: "mod",
    ast.Pow: "pow",
}
_UNARY: dict[type, str] = {ast.USub: "neg", ast.UAdd: "pos", ast.Not: "not"}
_CMP: dict[type, str] = {
    ast.Eq: "eq",
    ast.NotEq: "ne",
    ast.Lt: "lt",
    ast.LtE: "le",
    ast.Gt: "gt",
    ast.GtE: "ge",
    ast.In: "in",
    ast.NotIn: "notin",
    ast.Is: "is",
    ast.IsNot: "isnot",
}
_BINOP_TEXT = {v: k for k, v in {"+": "add", "-": "sub", "*": "mul", "/": "div", "//": "floordiv", "%": "mod", "**": "pow"}.items()}
_CMP_TEXT = {v: k for k, v in {"==": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge", "in": "in", "not in": "notin", "is": "is", "is not": "isnot"}.items()}


def parse(text: str, *, path: str = "") -> Any:
    """Inline text -> form. Raises :class:`ExprError` on bad syntax or a
    construct outside the sandbox allowlist."""
    try:
        tree = validate_expression(text)
    except SyntaxError as exc:
        raise ExprError(f"syntax error in {text!r}: {exc.msg}", path) from None
    except (RecursionError, MemoryError):
        raise ExprError(f"expression too deeply nested: {text[:40]!r}…", path) from None
    except UnsafeExpressionError as exc:
        raise ExprError(f"unsafe expression {text!r}: {exc}", path) from None
    return _convert(tree.body, path)


def _name_path(node: ast.AST) -> str | None:
    """``a.b.c`` as a dotted path when every link is a Name/Attribute."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name_path(node.value)
        return None if base is None else f"{base}.{node.attr}"
    return None


def _convert(node: ast.AST, path: str) -> Any:  # noqa: C901 - one switch, on purpose
    if isinstance(node, ast.Constant):
        if isinstance(node.value, int) and not isinstance(node.value, bool):
            return check_int_literal(node.value, path)
        return node.value
    if isinstance(node, ast.Name):
        return Name(node.id)
    if isinstance(node, ast.Attribute):
        dotted = _name_path(node)
        if dotted is not None:
            return Name(dotted)
        return Call("op:attr", (_convert(node.value, path), node.attr))
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_convert(e, path) for e in node.elts]
    if isinstance(node, ast.Set):
        return Call("op:set", ([_convert(e, path) for e in node.elts],))
    if isinstance(node, ast.Dict):
        out: dict[Any, Any] = {}
        for k, v in zip(node.keys, node.values):
            if k is None:
                raise ExprError("dict unpacking (**) is not allowed", path)
            key = _convert(k, path)
            if not isinstance(key, (str, int, float, bool)) or key is None:
                raise ExprError("dict keys in an inline expression must be literals", path)
            out[key] = _convert(v, path)
        return out
    if isinstance(node, ast.BinOp):
        op = _BINOPS.get(type(node.op))
        if op is None:
            raise ExprError(f"unsupported operator {type(node.op).__name__}", path)
        return Call(f"op:{op}", (_convert(node.left, path), _convert(node.right, path)))
    if isinstance(node, ast.UnaryOp):
        op = _UNARY.get(type(node.op))
        if op is None:
            raise ExprError(f"unsupported operator {type(node.op).__name__}", path)
        return Call(f"op:{op}", (_convert(node.operand, path),))
    if isinstance(node, ast.BoolOp):
        head = "op:and" if isinstance(node.op, ast.And) else "op:or"
        return Call(head, tuple(_convert(v, path) for v in node.values))
    if isinstance(node, ast.Compare):
        return _compare(_convert(node.left, path), list(zip(node.ops, node.comparators)), path, 0)
    if isinstance(node, ast.IfExp):
        return Call("if", (), {"cond": _convert(node.test, path), "then": _convert(node.body, path), "else": _convert(node.orelse, path)})
    if isinstance(node, ast.JoinedStr):
        return Call("op:fstr", tuple(_convert(v, path) for v in node.values))
    if isinstance(node, ast.FormattedValue):
        spec: Any = _convert(node.format_spec, path) if node.format_spec is not None else ""
        if isinstance(spec, Call) and spec.head == "op:fstr" and all(isinstance(p, str) for p in spec.args):
            spec = "".join(spec.args)  # a literal format spec such as 02d
        conv = chr(node.conversion) if node.conversion != -1 else ""
        return Call("op:fmt", (_convert(node.value, path), spec, conv))
    if isinstance(node, ast.Subscript):
        return Call("op:item", (_convert(node.value, path), _convert(node.slice, path)))
    if isinstance(node, ast.Slice):
        parts = tuple(_convert(p, path) if p is not None else None for p in (node.lower, node.upper, node.step))
        return Call("op:slice", parts)
    if isinstance(node, ast.Call):
        args = tuple(_convert(a, path) for a in node.args)
        kwargs = {}
        for kw in node.keywords:
            if kw.arg is None:
                raise ExprError("keyword unpacking (**) is not allowed", path)
            kwargs[kw.arg] = _convert(kw.value, path)
        if isinstance(node.func, ast.Name):
            if node.func.id == "quote" and len(args) == 1 and not kwargs:
                return Quoted(args[0])  # `quote(f)` inline IS the Quoted form (one tree, three spellings)
            return Call(node.func.id, args, kwargs)
        if isinstance(node.func, ast.Attribute):
            # a.b.c(...) is always a method call on the value a.b names; no inline
            # text calls a dotted head (use the structural `!a.b` tag or X.call)
            return Call("op:method", (_convert(node.func.value, path), node.func.attr) + args, kwargs)
        raise ExprError("only a named function or a method may be called", path)
    if isinstance(node, (ast.ListComp, ast.GeneratorExp, ast.SetComp, ast.DictComp)):
        return _comprehension(node, path)
    if isinstance(node, ast.Lambda):
        raise ExprError("lambda is not part of the language — register a Python function instead", path)
    raise ExprError(f"unsupported syntax {type(node).__name__}", path)


#: The name a chained comparison binds a shared operand to (T088 parse 1);
#: it scopes only the rest of that chain, and dumps and parses back as text.
_CMP_TEMP = "__cmp{}"
_CMP_LEFT_TEMP = "__cmpl{}"


def _compare(left: Any, rest: list[tuple[ast.cmpop, ast.expr]], path: str, depth: int) -> Any:
    """``a < b < c`` as Python evaluates it: ``b`` once, ``c`` only if
    ``a < b`` held (T088 parse 1 — the middle operand was emitted twice, so a
    draw or a counting head ran twice and the two comparisons saw different
    values). A shared operand that is a literal or a name is safe to repeat
    (a name is a cached lookup) and keeps the plain ``op:and`` form; any
    other is bound once by a ``let`` scoping the rest of the chain."""
    op, right_node = rest[0]
    name = _CMP.get(type(op))
    if name is None:
        raise ExprError(f"unsupported comparison {type(op).__name__}", path)
    right = _convert(right_node, path)
    if len(rest) == 1:
        return Call(f"op:{name}", (left, right))
    if isinstance(right, (Name, str, int, float, bool)) or right is None:
        tail = _compare(right, rest[1:], path, depth + 1)
        terms = tail.args if isinstance(tail, Call) and tail.head == "op:and" else (tail,)
        return Call("op:and", (Call(f"op:{name}", (left, right)),) + tuple(terms))
    temp = _CMP_TEMP.format(depth)
    shared = Name(temp)
    bindings: dict[str, Any] = {}
    if not (isinstance(left, (Name, str, int, float, bool)) or left is None):
        # ``let`` evaluates its bindings before its body, so a non-simple left
        # operand is bound first: operands evaluate left to right, as in
        # Python (T091 C12 — ``(0 < f(1) < 2) < f(5) < 9`` ran f(5) first).
        left_temp = _CMP_LEFT_TEMP.format(depth)
        bindings[left_temp] = left
        left = Name(left_temp)
    bindings[temp] = right
    body = Call("op:and", (Call(f"op:{name}", (left, shared)), _compare(shared, rest[1:], path, depth + 1)))
    return Call("let", (), {"bindings": bindings, "body": body})


def _comprehension(node: ast.AST, path: str) -> Any:
    gens = list(getattr(node, "generators"))
    if isinstance(node, ast.DictComp) and len(gens) > 1:
        # T088 parse 2: the key went on the innermost ``each`` and the outer
        # ones built a LIST of per-row dicts. Refused rather than given a
        # merge rule the single-``for`` form does not have (``each`` with
        # ``key=`` refuses a duplicate; Python's comprehension overwrites).
        raise ExprError(
            "a dict comprehension takes one 'for' — iterate a flattened list "
            "of pairs, or nest each(...) explicitly",
            path,
        )
    if isinstance(node, ast.DictComp):
        key_form: Any = _convert(node.key, path)
        body: Any = _convert(node.value, path)
    else:
        key_form = None
        body = _convert(getattr(node, "elt"), path)
    # innermost generator wraps the body; outer ones wrap that
    form: Any = None
    for depth, gen in enumerate(reversed(gens)):
        if gen.is_async:
            raise ExprError("async comprehensions are not allowed", path)
        if not isinstance(gen.target, ast.Name):
            raise ExprError("comprehension targets must be a single name", path)
        kwargs: dict[str, Any] = {"over": _convert(gen.iter, path), "as": gen.target.id}
        if gen.ifs:
            conds = tuple(_convert(c, path) for c in gen.ifs)
            kwargs["where"] = conds[0] if len(conds) == 1 else Call("op:and", conds)
        innermost = depth == 0
        if innermost:
            if key_form is not None:
                kwargs["key"] = key_form
            kwargs["body"] = body
        else:
            kwargs["body"] = form
        form = Call("each", (), kwargs)
        if not innermost and key_form is None:
            form = Call("op:flatten", (form,))
    if isinstance(node, ast.SetComp):
        form = Call("op:set", (form,))
    return form


# ---------------------------------------------------------------------------
# dump
# ---------------------------------------------------------------------------


def dump(form: Any) -> str:
    """Form -> inline text (parses back to an equal form for the constructs
    the inline spelling can express)."""
    if isinstance(form, Name):
        return form.path
    if isinstance(form, Quoted):
        return f"quote({dump(form.form)})"
    if isinstance(form, Call):
        return _dump_call(form)
    if isinstance(form, dict):
        return "{" + ", ".join(f"{k!r}: {dump(v)}" for k, v in form.items()) + "}"
    if isinstance(form, (list, tuple)):
        return "[" + ", ".join(dump(v) for v in form) + "]"
    return repr(form)


def _dump_call(form: Call) -> str:
    head = form.head
    if head.startswith("op:"):
        op = head[3:]
        a = form.args
        if op in _BINOP_TEXT and len(a) == 2:
            return f"({dump(a[0])} {_BINOP_TEXT[op]} {dump(a[1])})"
        if op in _CMP_TEXT and len(a) == 2:
            return f"({dump(a[0])} {_CMP_TEXT[op]} {dump(a[1])})"
        if op in ("and", "or"):
            return "(" + f" {op} ".join(dump(x) for x in a) + ")"
        if op == "neg":
            return f"(-{dump(a[0])})"
        if op == "pos":
            return f"(+{dump(a[0])})"
        if op == "not":
            return f"(not {dump(a[0])})"
        if op == "attr":
            return f"{dump(a[0])}.{a[1]}"
        if op == "item":
            return f"{dump(a[0])}[{dump(a[1])}]"
        if op == "slice":
            return ":".join("" if x is None else dump(x) for x in a)
        if op == "method":
            rest = [dump(x) for x in a[2:]] + [f"{k}={dump(v)}" for k, v in form.kwargs.items()]
            return f"{dump(a[0])}.{a[1]}({', '.join(rest)})"
        if op == "fstr":
            return _dump_fstr(form)
    comp = _dump_comprehension(form)
    if comp is not None:
        return comp
    if head == "op:set" and len(form.args) == 1 and not form.kwargs and isinstance(form.args[0], list) and form.args[0]:
        return "{" + ", ".join(dump(x) for x in form.args[0]) + "}"
    if head == "if" and set(form.kwargs) >= {"cond", "then"} and not form.args:
        other = form.kwargs.get("else")
        return f"({dump(form.kwargs['then'])} if {dump(form.kwargs['cond'])} else {dump(other)})"
    parts = [dump(x) for x in form.args] + [f"{k}={dump(v)}" for k, v in form.kwargs.items()]
    return f"{head}({', '.join(parts)})"


def _each_clause(form: Any) -> Optional[tuple[str, Mapping[str, Any]]]:
    """``for x in xs [if c]`` for a keyword-spelled ``each`` call, else ``None``."""
    if not (isinstance(form, Call) and form.head == "each" and not form.args):
        return None
    kw = form.kwargs
    var = kw.get("as")
    if not (set(kw) <= {"over", "as", "body", "key", "where"} and {"over", "as", "body"} <= set(kw)):
        return None
    if not (isinstance(var, str) and var.isidentifier()):
        return None
    clause = f"for {var} in {dump(kw['over'])}"
    if "where" in kw:
        clause += f" if {dump(kw['where'])}"
    return clause, kw


def _dump_comprehension(form: Call) -> Optional[str]:
    """A comprehension's inline text, for exactly the shapes :func:`_comprehension`
    emits (T088 parse 3: ``dump`` wrote ``each(over=…, as=…)`` — ``as`` is a
    Python keyword — and ``op:set(...)`` / ``op:flatten(...)``, none of which
    parse back, so a quoted comprehension did not survive the structural
    dump). ``None`` for any other shape."""
    wrap_set = form.head == "op:set" and len(form.args) == 1 and not form.kwargs
    inner: Any = form.args[0] if wrap_set else form
    clauses: list[str] = []
    flattened = isinstance(inner, Call) and inner.head == "op:flatten" and len(inner.args) == 1 and not inner.kwargs
    cur: Any = inner.args[0] if flattened else inner
    while True:
        part = _each_clause(cur)
        if part is None:
            return None
        clause, kw = part
        clauses.append(clause)
        body = kw["body"]
        if not flattened:
            break
        if "key" in kw:
            return None  # a key under a flatten is no shape the parser emits
        if isinstance(body, Call) and body.head == "op:flatten" and len(body.args) == 1 and not body.kwargs:
            cur = body.args[0]
            continue
        flattened = False
        cur = body
    if "key" in kw:
        if wrap_set or len(clauses) > 1:
            return None
        return "{" + f"{dump(kw['key'])}: {dump(body)} " + " ".join(clauses) + "}"
    text = f"{dump(body)} " + " ".join(clauses)
    return "{" + text + "}" if wrap_set else "[" + text + "]"


def _dump_fstr(form: Call) -> str:
    out = 'f"'
    for part in form.args:
        if isinstance(part, str):
            out += part.replace("{", "{{").replace("}", "}}").replace('"', '\\"')
        elif isinstance(part, Call) and part.head == "op:fmt":
            value, spec, conv = part.args
            out += "{" + dump(value) + (f"!{conv}" if conv else "") + (f":{spec}" if spec else "") + "}"
        else:
            out += "{" + dump(part) + "}"
    return out + '"'
