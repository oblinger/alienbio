"""The head registry — how Python enters the Expr environment (M47.1).

One kind-tagged table mapping a head name to a :class:`Head`; populated at
import time by :func:`fn`, :func:`expander` and :func:`guard` (the old
``@rate`` / ``@scoring`` / ``@action`` / ``@measurement`` decorators become
``@fn(kind=...)`` aliases in M47.7). A registered name is the *only* way a
spec reaches Python: that is the sandbox. :meth:`Registry.view` narrows the
table for consumers that should see less (the rate compiler's math view).
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Iterable, Optional


class GuardViolation(Exception):
    """Raised by a guard to reject what a call produced."""


#: Head kinds. ``special`` heads are the interpreter's own (they receive forms
#: and return a *value*); ``expander`` heads receive forms and return a *form*;
#: every other kind is a function whose arguments arrive evaluated.
FUNCTION_KINDS: frozenset[str] = frozenset(
    {"fn", "dist", "math", "rate", "scoring", "action", "measurement", "guard", "constructor", "op"}
)


@dataclass
class Head:
    name: str
    kind: str
    fn: Callable[..., Any]
    meta: dict[str, Any] = field(default_factory=dict)
    guarded: bool = False
    guarded_params: frozenset[str] = frozenset()
    #: which of ``ctx`` / ``env`` the callable declares (keyword-only) and so
    #: receives by injection — computed at registration.
    injects: frozenset[str] = frozenset()

    @property
    def is_special(self) -> bool:
        return self.kind == "special"

    @property
    def is_expander(self) -> bool:
        return self.kind in ("expander", "template")

    @property
    def is_function(self) -> bool:
        return self.kind in FUNCTION_KINDS


def _injects(func: Callable[..., Any]) -> frozenset[str]:
    try:
        params = inspect.signature(func).parameters
    except (TypeError, ValueError):
        return frozenset()
    return frozenset(
        name
        for name in ("ctx", "env")
        if name in params
        and params[name].kind in (inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    )


class Registry:
    """A name → :class:`Head` table with kind-filtered views."""

    def __init__(self, heads: Optional[dict[str, Head]] = None, *, kinds: Optional[Collection[str]] = None) -> None:
        self._heads: dict[str, Head] = heads if heads is not None else {}
        self._kinds: Optional[frozenset[str]] = frozenset(kinds) if kinds is not None else None

    def register(self, head: Head, *, replace: bool = False) -> Head:
        if self._kinds is not None:
            raise ValueError("cannot register into a registry view")
        if head.name in self._heads and not replace:
            existing = self._heads[head.name]
            if existing.fn is not head.fn:
                raise ValueError(f"head {head.name!r} is already registered ({existing.kind})")
        self._heads[head.name] = head
        return head

    def get(self, name: str) -> Head:
        head = self._heads.get(name)
        if head is None or (self._kinds is not None and head.kind not in self._kinds and not head.is_special):
            raise KeyError(name)
        return head

    def __contains__(self, name: object) -> bool:
        try:
            self.get(str(name))
            return True
        except KeyError:
            return False

    def names(self) -> list[str]:
        return sorted(n for n in self._heads if n in self)

    def view(self, kinds: Iterable[str]) -> "Registry":
        """A registry showing only ``kinds`` (special forms always show)."""
        return Registry(self._heads, kinds=set(kinds))

    def describe(self) -> list[dict[str, Any]]:
        out = []
        for name in self.names():
            h = self._heads[name]
            try:
                sig = str(inspect.signature(h.fn))
            except (TypeError, ValueError):
                sig = "(...)"
            out.append({"name": name, "kind": h.kind, "signature": sig, "summary": h.meta.get("summary", "")})
        return out


#: The one registry.
registry = Registry()


def _decorate(
    kind: str,
    _f: Optional[Callable[..., Any]],
    *,
    name: Optional[str],
    guarded: bool,
    guarded_params: Collection[str],
    into: Registry,
    meta: dict[str, Any],
) -> Any:
    def wrap(func: Callable[..., Any]) -> Callable[..., Any]:
        head = Head(
            name=name or func.__name__,
            kind=kind,
            fn=func,
            meta=dict(meta),
            guarded=guarded,
            guarded_params=frozenset(guarded_params),
            injects=_injects(func),
        )
        into.register(head, replace=True)
        try:
            setattr(func, "head", head)
        except (AttributeError, TypeError):
            pass  # builtins / lambdas cannot carry the attribute; the registry is the record
        return func

    return wrap(_f) if _f is not None else wrap


def fn(
    _f: Optional[Callable[..., Any]] = None,
    *,
    name: Optional[str] = None,
    kind: str = "fn",
    guarded: bool = False,
    guarded_params: Collection[str] = (),
    into: Registry = registry,
    **meta: Any,
) -> Any:
    """Register a function head: its arguments arrive **evaluated**. A
    keyword-only ``ctx`` / ``env`` parameter is injected, never passed by the
    spec. ``kind`` is the flavor tag (``dist``, ``rate``, ``scoring``, ...)."""
    if kind not in FUNCTION_KINDS:
        raise ValueError(f"@fn: unknown kind {kind!r}; expected one of {sorted(FUNCTION_KINDS)}")
    return _decorate(kind, _f, name=name, guarded=guarded, guarded_params=guarded_params, into=into, meta=meta)


def expander(
    _f: Optional[Callable[..., Any]] = None,
    *,
    name: Optional[str] = None,
    guarded: bool = False,
    guarded_params: Collection[str] = (),
    into: Registry = registry,
    **meta: Any,
) -> Any:
    """Register an expander head: ``fn(args, kwargs, env)`` receives the
    argument **forms** (unevaluated) and returns a form the interpreter then
    evaluates under the call's seed."""
    return _decorate("expander", _f, name=name, guarded=guarded, guarded_params=guarded_params, into=into, meta=meta)


def guard(
    _f: Optional[Callable[..., Any]] = None,
    *,
    name: Optional[str] = None,
    into: Registry = registry,
    **meta: Any,
) -> Any:
    """Register a guard: ``fn(expanded, ctx, **params)`` raises
    :class:`GuardViolation` to reject what a call produced (M47.5 wires the
    ``guards:`` / ``on_fail:`` keywords; registration lands here)."""
    return _decorate("guard", _f, name=name, guarded=False, guarded_params=(), into=into, meta=meta)


def special(name: str, func: Callable[..., Any], *, into: Registry = registry, **meta: Any) -> Head:
    """Register a special form (interpreter-internal): ``func(args, kwargs, env) -> value``."""
    head = Head(name=name, kind="special", fn=func, meta=dict(meta))
    return into.register(head, replace=True)
