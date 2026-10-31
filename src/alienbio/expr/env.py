"""The Expr environment — bindings, heads, context (M47.1).

``Env`` is three things: a scope chain of **bindings** (the existing
``spec_lang.scope.Scope``), the head **registry** (plus any head bound
locally — a YAML ``!template`` is a value in scope), and the run's
**context** (``Ctx``: seed, node path, trust, limits). Every named node
evaluates under ``parent_seed.child(key)``, so editing one node never
re-rolls another's draws.
"""

from __future__ import annotations

import contextlib
import threading
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional, Union

import numpy as np

from ..spec_lang.scope import Scope
from ..suite.dist import Seed
from .registry import Head, Registry, registry as _default_registry


class ExprError(ValueError):
    """Every Expr failure, with the path of the node that failed. A
    ``ValueError``: a document that fails to evaluate is an invalid value."""

    def __init__(self, message: str, path: str = "") -> None:
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}" if path else message)


class Meter:
    """A cumulative allocation count for one evaluation session (M48.5): every
    ``each`` iteration, ``range`` / ``list`` element and sequence repetition
    is charged here, so a bomb that is cheap per step and ruinous in total
    (``[[0] * 10**5 for _ in range(10**5)]``) is refused when the running
    total crosses ``limits.entities``, not after the memory is gone."""

    __slots__ = ("allocated", "clock")

    def __init__(self) -> None:
        self.allocated = 0
        #: The wall-clock deadline of the evaluation in progress (T091 AL6),
        #: per thread (concurrent trials share a closure env's meter):
        #: ``clock.deadline`` is set when an outermost clock begins — a
        #: document load (:meth:`Limits.running`, T091 AP5: ``Env.load``,
        #: ``Env.force_all``, ``load_experiment``) or an outermost
        #: :func:`~alienbio.expr.interp.evaluate` outside one — and
        #: ``clock.active`` counts the nesting. One document load is one
        #: ``limits.seconds``; a quoted task drawn per trial, evaluated
        #: after the load, gets its own.
        self.clock = threading.local()


@dataclass(frozen=True)
class Limits:
    """Caps the interpreter enforces — exceeding one is an error, never a truncation."""

    entities: int = 1_000_000  # elements one `each`/`range`/`list` may produce, and in total per session
    depth: int = 100  # evaluation nesting (T051 box 4: one template level is ~5.5 Python frames, so 200 sat above the interpreter's own limit and could never fire)
    attempts: int = 8  # guard retries (M47.5)
    #: Wall-clock seconds one document load may run, parse, includes and
    #: every binding together (T091 AP5 — per binding, a file of N bindings
    #: each just under the limit ran N times it); an evaluation outside a
    #: load (a quoted task drawn per trial) gets its own. Checked at every
    #: head call and after it returns, every ``each`` iteration, guard retry
    #: and include; past it the load raises :class:`ExprError`. One Python
    #: operation is not interrupted — the size caps (``MAX_POW_RESULT_BITS``,
    #: ``MAX_INT_LITERAL_BITS``, ``MAX_SPEC_BYTES``, the comparison charge)
    #: keep each one short; this bounds a chain of them.
    seconds: float = 10.0
    meter: Meter = field(default_factory=Meter, compare=False, repr=False)

    def tick(self, path: str) -> None:
        """Raise when the evaluation in progress has run past ``seconds``."""
        deadline = getattr(self.meter.clock, "deadline", None)
        if deadline is not None and time.monotonic() > deadline:
            raise ExprError(f"evaluation exceeded limits.seconds={self.seconds:g}", path)

    @contextlib.contextmanager
    def running(self, path: str = "") -> Iterator[None]:
        """One ``seconds`` clock over the block (T091 AP5): the outermost
        ``running`` / :func:`~alienbio.expr.interp.evaluate` starts it, every
        nested one shares it, and a block that finishes past the deadline
        raises (its last operation was not interrupted)."""
        clock = self.meter.clock
        if getattr(clock, "active", 0):
            clock.active += 1
            try:
                yield
            finally:
                clock.active -= 1
            return
        clock.active, clock.deadline = 1, time.monotonic() + self.seconds
        try:
            yield
            self.tick(path)
        finally:
            clock.active, clock.deadline = 0, None

    def charge(self, n: int, path: str, what: str) -> None:
        """Count ``n`` elements against the session total; raise past the cap."""
        if n > self.entities:
            raise ExprError(f"{what}: {n} elements exceeds limits.entities={self.entities}", path)
        self.meter.allocated += n
        if self.meter.allocated > self.entities:
            raise ExprError(
                f"{what}: {self.meter.allocated} elements allocated in this evaluation exceeds limits.entities={self.entities}",
                path,
            )


@dataclass(frozen=True)
class Ctx:
    """The per-node context: seed, path (for messages), trust, limits."""

    seed: Seed
    path: str = ""
    trusted: bool = False
    limits: Limits = field(default_factory=Limits)
    #: Template instance name -> the document path that claimed it; shared by
    #: every child ctx of one load (``replace`` copies the reference), so a
    #: second path claiming a name refuses (T054 #5).
    instances: dict[str, str] = field(default_factory=dict)

    @property
    def rng(self) -> np.random.Generator:
        return self.seed.rng()

    def child(self, label: str) -> "Ctx":
        path = f"{self.path}.{label}" if self.path else label
        return replace(self, seed=self.seed.child(label), path=path)


#: The hidden bindings a template instance carries (see :meth:`Env.pool`):
#: argument string -> the pool name it denotes in the caller's scope, and the
#: instance's own namespace.
PASSED_KEY = "__passed__"
INSTANCE_KEY = "__instance__"


def _callable_head(name: str, func: Any, ctx: "Ctx") -> Head:
    """A bound Python callable (``!py``, a ``let``-bound function) as a
    function head, so ``!x name(...)`` can call it (M47.5). Untrusted, only a
    plain Python function qualifies (T091 AG1, :func:`.access.check_callable`)."""
    from ..spec_lang.safe_eval import UnsafeExpressionError
    from . import access
    from .registry import _injects

    try:
        access.check_callable(func, trusted=ctx.trusted)
    except UnsafeExpressionError as exc:
        raise ExprError(f"{name!r}: {exc}", ctx.path) from None

    return Head(name=name, kind="fn", fn=func, meta={"summary": f"bound callable {name}"}, injects=_injects(func))


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
        from ..suite import expr_experiment as _suite_experiment  # noqa: F401  (layers 3-6: tasks, experiments, agents)

        root_seed = seed if isinstance(seed, Seed) else Seed(int(seed))
        # A passed ``limits`` gets its own meter: the meter rode the Limits
        # object, so one Limits handed to three envs summed their
        # allocations (T088 expr/env 3).
        ctx = Ctx(seed=root_seed, trusted=trusted, limits=replace(limits, meter=Meter()) if limits is not None else Limits())
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

        # A binding evaluates in its own scope, one level below whichever is
        # deeper — its definition or the lookup forcing it — so a chain of
        # names (``a0: a1 + 1``, ``a1: a2 + 1`` …) counts toward
        # ``limits.depth`` and stops at the cap rather than at Python's
        # recursion limit (T091 C11).
        scope = value.env.child(name)
        if self.depth + 1 > scope.depth:
            scope = Env(scope.bindings, scope.registry, scope.ctx, scope.ns, self.depth + 1)
        try:
            value.value = evaluate(value.form, scope)
        except RecursionError:
            value.state = "pending"
            # Belt to the depth cap's braces: whatever shape slips past
            # ``limits.depth`` still surfaces as the spec's error, not a
            # Python traceback (T051 box 4).
            raise self.error(f"evaluation of {name!r} too deep (Python recursion limit); raise nothing above limits.depth") from None
        except BaseException:
            # A failed evaluation leaves the binding pending, so the next
            # lookup re-raises ITS error — not "cyclic definition" forever
            # after (T088 expr/env 1).
            value.state = "pending"
            raise
        value.state = "done"
        return value.value

    def _step(self, value: Any, step: str, path: str) -> Any:
        """One segment of a dotted name: a mapping key, a sequence index, else
        an attribute — on a receiver type :mod:`.access` allows (T091 AG1)."""
        from ..spec_lang.safe_eval import UnsafeExpressionError
        from . import access

        if isinstance(value, Mapping) and step in value:
            return value[step]
        if isinstance(value, (list, tuple)) and step.isdigit():
            try:
                return value[int(step)]
            except IndexError:
                raise self.error(f"index {step} out of range in {path!r}") from None
        try:
            return access.read_attr(value, step)
        except UnsafeExpressionError as exc:
            raise self.error(f"{path!r}: {exc}") from None
        except AttributeError:
            raise self.error(f"{path!r}: no key or attribute {step!r} on {type(value).__name__}") from None

    def head(self, name: str) -> Head:
        """A head by name: a locally bound head (a YAML template) shadows the registry.

        A dotted name resolves its WHOLE path through the scope (a head or a
        callable at the end of it), else falls to the registry — matching only
        its first segment made ``!t.anything {}`` call template ``t`` (T088
        expr/env 2)."""
        first = name.split(".")[0]
        if "." in name and first in self.bindings:
            try:
                target = self.lookup(name)
            except ExprError:
                target = None
            if isinstance(target, Head):
                return target
            if target is not None and callable(target):
                return _callable_head(name, target, self.ctx)
        elif first in self.bindings:
            value = self.bindings[first]
            # A binding shadows a registered head only when it IS a head — a
            # template already evaluated, or a not-yet-forced `!template` form.
            # A document key that merely shares a head's name (`world: !world
            # {...}`) must not be forced here: that would evaluate the very
            # node being evaluated (a false "cyclic definition").
            if isinstance(value, Lazy):
                if value.state == "done" and isinstance(value.value, Head):
                    return value.value
                if value.state == "done" and callable(value.value):
                    return _callable_head(first, value.value, self.ctx)
                if value.state == "pending":
                    from .form import Call as _Call, is_form as _is_form

                    if isinstance(value.form, _Call) and value.form.head == "template":
                        forced = self._force(first, value)
                        if isinstance(forced, Head):
                            return forced
                    # a resolved !py object / a .py include's function: plain
                    # data that happens to be callable — never a form, so
                    # forcing it evaluates nothing.
                    elif not _is_form(value.form) and not isinstance(value.form, (dict, list)) and callable(value.form):
                        return _callable_head(first, self._force(first, value), self.ctx)
                    # T091 AL10: a binding no registered head shares a name
                    # with (`c: !x ...` then `!x c(1)`) is forced here, so a
                    # callable binding works as a head whatever the document
                    # order. A registered head's name is not forced: a key
                    # that merely shares it (`world: !world {...}`) is the
                    # node being evaluated.
                    elif name not in self.registry:
                        forced = self._force(first, value)
                        if isinstance(forced, Head):
                            return forced
                        if callable(forced):
                            return _callable_head(first, forced, self.ctx)
                        raise self.error(f"{first!r} is bound to a {type(forced).__name__}, not a head or a callable")
            elif isinstance(value, Head):
                return value
            elif callable(value):
                return _callable_head(first, value, self.ctx)
        try:
            return self.registry.get(name)
        except KeyError:
            raise self.error(f"unknown head {name!r}") from None

    # ---- files ------------------------------------------------------------

    def load(
        self,
        source: Union[str, Path],
        *,
        text: Optional[str] = None,
        base: Optional[Union[str, Path]] = None,
        data: Any = None,
    ) -> "Env":
        """Load a YAML document into a child scope: every top-level key becomes
        a (lazy) binding. Includes and ``!py`` references are resolved first
        (:mod:`alienbio.expr.include`) relative to ``base`` — the file's own
        directory by default — under this env's trust. ``data`` is the
        document already parsed (``load_experiment`` parses once, T091 AP7);
        else ``text``, else the file, capped at ``MAX_SPEC_BYTES``. The load
        runs under one ``limits.seconds`` clock and one include budget
        (T091 AP5/AP6). Returns the env whose scope holds the bindings."""
        from .include import hydrate, include_bindings, include_session
        from .yaml_tags import load_text, read_spec_text

        # T091 AL1: one resolution of the file decides the text read and the
        # include base. The base is the RESOLVED file's directory — a symlink
        # to a catalog spec from an outside folder used to load trusted with
        # that folder's `helpers.py` as its `_includes_`.
        resolved = Path(source).resolve()
        is_file = resolved.is_file()
        base_dir = Path(base).resolve() if base is not None else (resolved.parent if is_file else Path.cwd())
        seen = frozenset({resolved}) if is_file else frozenset()
        limits = self.ctx.limits
        with limits.running(str(source)), include_session(limits):
            if data is None:
                if text is None:
                    text = read_spec_text(resolved)
                data = load_text(text, source=str(source))
            if not isinstance(data, Mapping):
                raise ExprError("a spec file must be a mapping at the top level", str(source))
            data = dict(data)
            entries = data.pop("_includes_", None)
            included: dict[str, Any] = {}
            modules: dict[str, Mapping[str, Any]] = {}
            if entries is not None:
                included, modules = include_bindings(entries, base_dir, trusted=self.ctx.trusted, seen=seen)
            data = hydrate(data, base=base_dir, trusted=self.ctx.trusted, seen=seen, modules=modules)
        for key, form in included.items():
            data.setdefault(str(key), form)
        env = self.scope({}, parent=self.bindings)
        for key, form in data.items():
            env.bindings[str(key)] = Lazy(form, env)
        return env

    def hydrate(self, data: Any, *, base: Optional[Union[str, Path]] = None) -> Any:
        """Resolve includes / ``!py`` references inside already-loaded forms."""
        from .include import hydrate

        return hydrate(data, base=Path(base).resolve() if base is not None else Path.cwd(), trusted=self.ctx.trusted)

    # ---- pools ------------------------------------------------------------

    def pool(self, name: Any) -> str:
        """A pool name as seen from this scope (M47.5): inside a template
        instance a name is namespaced by the instance (``krel.ME1``) unless it
        arrived as an argument, in which case it is whatever the caller's
        scope called it — that is how a parent wires its children. Outside any
        template the name is itself."""
        text = str(name)
        passed = self.bindings.get(PASSED_KEY)
        if isinstance(passed, Mapping) and text in passed:
            return str(passed[text])
        instance = self.bindings.get(INSTANCE_KEY)
        return f"{instance}.{text}" if instance else text

    def force_all(self) -> dict[str, Any]:
        """Evaluate every lazy binding in this scope (not parents); returns
        them. One ``limits.seconds`` clock covers them all (T091 AP5), or the
        enclosing load's when one is running."""
        out: dict[str, Any] = {}
        with self.ctx.limits.running(self.ctx.path):
            for key in list(self.bindings.local_keys()):
                out[key] = self._force(key, self.bindings[key])
        return out
