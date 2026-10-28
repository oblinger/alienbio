"""Expr forms — the abstract syntax (M47.1).

Five things, and only five: a **literal** (a plain Python scalar), a
:class:`Name` (a lookup in the environment, dotted = a path), **data** (a
``list`` / ``dict`` whose elements are forms), a :class:`Call` (a head with
positional and keyword arguments) and a :class:`Quoted` form (a form held as
a value, evaluated later). Everything generative in alienbio is a tree of
these; the interpreter (:mod:`.interp`) is the only thing that gives them
meaning. See ``ABIO Expr`` / ``ABIO Expr Spec`` in the vault.

Forms are frozen and compare by value, so a test can assert on them directly.
A :class:`Call`'s keyword arguments are a read-only mapping (T088 form 1: a
plain ``dict`` let ``call.kwargs[k] = v`` edit every tree sharing the call),
and a call hashes whenever its arguments do — one nesting a ``list`` or
``dict`` of data does not, as that data is mutable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping


@dataclass(frozen=True)
class Name:
    """A lookup: ``path`` is ``ident(.ident)*`` — the first segment resolves in
    the scope chain, each further segment steps into the value (mapping key,
    then attribute, then sequence index)."""

    path: str

    def __repr__(self) -> str:
        return f"Name({self.path!r})"


class FrozenKwargs(dict):  # type: ignore[type-arg]
    """A :class:`Call`'s keyword arguments: a ``dict`` that refuses every
    mutation after construction, hashes by its sorted items, and pickles and
    deep-copies as itself (``mappingproxy`` would refuse both)."""

    def _refuse(self, *args: Any, **kwargs: Any) -> Any:
        raise TypeError("a Call's kwargs are read-only; build a new Call")

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = _refuse  # type: ignore[assignment]
    __ior__ = _refuse  # type: ignore[assignment]

    def __hash__(self) -> int:  # type: ignore[override]
        return hash(tuple(sorted(self.items())))

    def __reduce__(self) -> Any:
        return (FrozenKwargs, (dict(self),))


@dataclass(frozen=True)
class Call:
    """``head(*args, **kwargs)`` as data. ``head`` names a registered function,
    expander, template or special form; the arguments are forms."""

    head: str
    args: tuple[Any, ...] = ()
    kwargs: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "args", tuple(self.args))
        object.__setattr__(self, "kwargs", FrozenKwargs(self.kwargs))

    def __hash__(self) -> int:
        return hash((self.head, self.args, self.kwargs))

    def __repr__(self) -> str:
        parts = [repr(a) for a in self.args] + [f"{k}={v!r}" for k, v in self.kwargs.items()]
        return f"{self.head}({', '.join(parts)})"


@dataclass(frozen=True)
class Quoted:
    """A form held as a value. Evaluating a ``Quoted`` yields a
    :class:`~alienbio.expr.interp.QuotedForm` — the form closed over the
    environment it was written in, sampleable as a ``Dist``."""

    form: Any

    def __repr__(self) -> str:
        return f"Quoted({self.form!r})"


@dataclass(frozen=True)
class Include:
    """``!include path`` — resolved at load time (hydration), before any
    evaluation: a ``.yaml`` merges in place as forms, ``.md``/``.txt`` reads as
    text, ``.py`` executes under a trusted load so its decorators register
    heads. Never reaches the interpreter."""

    path: str

    def __repr__(self) -> str:
        return f"Include({self.path!r})"


@dataclass(frozen=True)
class PyRef:
    """``!py module.attr`` — a Python object as a value, resolved at load time
    under a trusted load only. Not a head: bind it (``let``) to call it."""

    path: str

    def __repr__(self) -> str:
        return f"PyRef({self.path!r})"


Form = Any  # Name | Call | Quoted | list[Form] | dict[str, Form] | scalar


def is_form(value: Any) -> bool:
    """True for the three tagged shapes — a literal or data is "a form" too, but
    only these three carry meaning beyond their Python value."""
    return isinstance(value, (Name, Call, Quoted))


def contains_form(value: Any) -> bool:
    """True if ``value`` is, or contains anywhere inside data, a tagged form."""
    return any(True for _ in walk(value) if is_form(_))


def walk(value: Any) -> Iterator[Any]:
    """Pre-order walk over a form tree, yielding every node (data included)."""
    yield value
    if isinstance(value, Call):
        for a in value.args:
            yield from walk(a)
        for v in value.kwargs.values():
            yield from walk(v)
    elif isinstance(value, Quoted):
        yield from walk(value.form)
    elif isinstance(value, dict):
        for v in value.values():
            yield from walk(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from walk(v)
