"""The Expr environment — bindings, heads, context (M47.1).

``Env`` is three things: a scope chain of **bindings** (the existing
``spec_lang.scope.Scope``), the head **registry** (plus any head bound
locally — a YAML ``!template`` is a value in scope), and the run's
**context** (``Ctx``: seed, node path, trust, limits). Every named node
evaluates under ``parent_seed.child(key)``, so editing one node never
re-rolls another's draws.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Optional, Union

import numpy as np

from ..spec_lang.scope import Scope
from ..suite.dist import Seed
from .registry import Head, Registry, registry as _default_registry


class ExprError(Exception):
    """Every Expr failure, with the path of the node that failed."""

    def __init__(self, message: str, path: str = "") -> None:
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}" if path else message)


@dataclass(frozen=True)
class Limits:
    """Caps the interpreter enforces — exceeding one is an error, never a truncation."""

    entities: int = 1_000_000  # elements a single `each` may produce (build/expand.py's MAX_ENTITY_COUNT)
    depth: int = 200  # evaluation nesting
    attempts: int = 8  # guard retries (M47.5)


@dataclass(frozen=True)
class Ctx:
    """The per-node context: seed, path (for messages), trust, limits."""

    seed: Seed
    path: str = ""
    trusted: bool = False
    limits: Limits = field(default_factory=Limits)

    @property
    def rng(self) -> np.random.Generator:
        return self.seed.rng()

    def child(self, label: str) -> "Ctx":
        path = f"{self.path}.{label}" if self.path else label
        return replace(self, seed=self.seed.child(label), path=path)


class Lazy:
    """A top-level binding whose form is evaluated on first lookup (a name may
    refer to any binding in its file regardless of position; a cycle is an error)."""

    __slots__ = ("form", "env", "state", "value")

    def __init__(self, form: Any, env: "Env") -> None:
        self.form = form
        self.env = env
        self.state = "pending"
        self.value: Any = None


class Env:
    """Bindings + heads + context. Immutable in spirit: every ``child`` /
    ``bind`` / ``with_*`` returns a new ``Env`` sharing what is unchanged."""

    def __init__(self, bindings: Scope, registry: Registry, ctx: Ctx, ns: str = "", depth: int = 0) -> None:
        self.bindings = bindings
        self.registry = registry
        self.ctx = ctx
        self.ns = ns
        self.depth = depth

    # ---- construction -----------------------------------------------------

    @classmethod
    def standard(
        cls,
        seed: Union[int, Seed] = 0,
        *,
        trusted: bool = False,
        registry: Optional[Registry] = None,
        limits: Optional[Limits] = None,
        bindings: Optional[Mapping[str, Any]] = None,
    ) -> "Env":
        """An environment over the default registry with root seed ``seed``."""
        from . import heads as _heads  # noqa: F401  (registers the builtin heads)
        from ..suite import expr_heads as _suite_heads  # noqa: F401  (layers 0-2: blocks, worlds)

        root_seed = seed if isinstance(seed, Seed) else Seed(int(seed))
        ctx = Ctx(seed=root_seed, trusted=trusted, limits=limits or Limits())
        return cls(Scope(dict(bindings or {}), name="root"), registry or _default_registry, ctx)

    def child(self, label: str) -> "Env":
        """The env for a named sub-node: same scope, child seed, extended path."""
        return Env(self.bindings, self.registry, self.ctx.child(str(label)), self.ns, self.depth + 1)

    def bind(self, **values: Any) -> "Env":
        """A child scope holding ``values`` (already evaluated)."""
        return Env(self.bindings.child(dict(values)), self.registry, self.ctx, self.ns, self.depth)

    def scope(self, data: Optional[Mapping[str, Any]] = None, parent: Optional[Scope] = None) -> "Env":
        """A child scope over ``parent`` (default: this env's bindings)."""
        base = parent if parent is not None else self.bindings
        return Env(base.child(dict(data or {})), self.registry, self.ctx, self.ns, self.depth)

    def with_seed(self, seed: Seed) -> "Env":
        return Env(self.bindings, self.registry, replace(self.ctx, seed=seed), self.ns, self.depth)

    def with_ctx(self, ctx: Ctx) -> "Env":
        return Env(self.bindings, self.registry, ctx, self.ns, self.depth)

    def with_ns(self, ns: str) -> "Env":
        return Env(self.bindings, self.registry, self.ctx, ns, self.depth)

    @property
    def path(self) -> str:
        return self.ctx.path

    def error(self, message: str) -> ExprError:
        return ExprError(message, self.ctx.path)

    # ---- lookup -----------------------------------------------------------

    def lookup(self, path: str) -> Any:
        """Resolve a dotted name: first segment in the scope chain, then steps."""
        first, *rest = path.split(".")
        try:
            value = self.bindings[first]
        except KeyError:
            raise self.error(f"unbound name {first!r}") from None
        value = self._force(first, value)
        for step in rest:
            value = self._step(value, step, path)
        return value

    def _force(self, name: str, value: Any) -> Any:
        if not isinstance(value, Lazy):
            return value
        if value.state == "done":
            return value.value
        if value.state == "evaluating":
            raise self.error(f"cyclic definition of {name!r}")
        value.state = "evaluating"
        from .interp import evaluate

        value.value = evaluate(value.form, value.env.child(name))
        value.state = "done"
        return value.value

    def _step(self, value: Any, step: str, path: str) -> Any:
        from ..spec_lang.safe_eval import UnsafeExpressionError, _check_attr_name

        if isinstance(value, Mapping) and step in value:
            return value[step]
        if isinstance(value, (list, tuple)) and step.isdigit():
            try:
                return value[int(step)]
            except IndexError:
                raise self.error(f"index {step} out of range in {path!r}") from None
        try:
            _check_attr_name(step)
        except UnsafeExpressionError as exc:
            raise self.error(str(exc)) from None
        if hasattr(value, step):
            return getattr(value, step)
        raise self.error(f"{path!r}: no key or attribute {step!r} on {type(value).__name__}")

    def head(self, name: str) -> Head:
        """A head by name: a locally bound head (a YAML template) shadows the registry."""
        first = name.split(".")[0]
        if first in self.bindings:
            value = self.bindings[first]
            # A binding shadows a registered head only when it IS a head — a
            # template already evaluated, or a not-yet-forced `!template` form.
            # A document key that merely shares a head's name (`world: !world
            # {...}`) must not be forced here: that would evaluate the very
            # node being evaluated (a false "cyclic definition").
            if isinstance(value, Lazy):
                if value.state == "done" and isinstance(value.value, Head):
                    return value.value
                if value.state == "pending":
                    from .form import Call as _Call

                    if isinstance(value.form, _Call) and value.form.head == "template":
                        forced = self._force(first, value)
                        if isinstance(forced, Head):
                            return forced
            elif isinstance(value, Head):
                return value
        try:
            return self.registry.get(name)
        except KeyError:
            raise self.error(f"unknown head {name!r}") from None

    # ---- files ------------------------------------------------------------

    def load(self, source: Union[str, Path], *, text: Optional[str] = None) -> "Env":
        """Evaluate a YAML document into a child scope: every top-level key
        becomes a (lazy) binding. Returns the env whose scope holds them."""
        from .yaml_tags import load_text

        if text is None:
            text = Path(source).read_text()
        data = load_text(text)
        if not isinstance(data, Mapping):
            raise ExprError("a spec file must be a mapping at the top level", str(source))
        env = self.scope({}, parent=self.bindings)
        for key, form in data.items():
            env.bindings[str(key)] = Lazy(form, env)
        return env

    def force_all(self) -> dict[str, Any]:
        """Evaluate every lazy binding in this scope (not parents); returns them."""
        out: dict[str, Any] = {}
        for key in list(self.bindings.local_keys()):
            out[key] = self._force(key, self.bindings[key])
        return out
