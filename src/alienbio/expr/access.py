"""What an Expr expression may read off a value — the sandbox's type allowlist.

Filtering attribute *names* (``spec_lang.safe_eval``: no dunders, no
interpreter internals) does not hold a sandbox on its own: any live framework
object a head hands back is walkable by plain names. ``q.env.standard(
trusted=True).load(...)`` on a quoted form minted a trusted environment from
an untrusted spec and ran ``!py os.system`` (T091 round 4, AG1). So every path
that reads an attribute or calls a method (``op:attr``, ``op:method``, the
dotted-name steps of :meth:`Env.lookup`, a dotted head) also checks the
**receiver's type** against the one list here, under trust too — a trusted
spec reaches Python through ``!py`` explicitly, never by attribute walking.

- **Plain data** (:data:`PLAIN_TYPES`, by exact type — a subclass such as
  ``spec_lang.scope.Scope`` is not plain): attributes and methods, the
  methods still under ``op:method``'s mutation and size checks.
- **Domain values** (:func:`domain_types`): the frozen records the heads hand
  back — distributions, worlds and entities, skeletons and blocks, tasks,
  drafts, trial records. Their **data attributes only**: a method of a domain
  value (``Entity.save``, ``set_parent``, ``Skeleton.materialize``) is Python
  API, not language, and refuses.
- **Everything else** refuses with one :class:`ExprError` naming the type:
  ``Env``, ``Ctx``, ``Registry``, ``Head``, ``QuotedForm``, ``Seed``, modules,
  classes, functions, bound methods, numpy scalars …

A name beginning with ``_`` is refused on every receiver (private state is
not an interface). A mapping's *keys* are data, not attributes, and are read
before any of this applies.

**Calling a bound value** (:func:`check_callable`, T091 AL8): an untrusted
spec calls registered heads only — a Python function that leaks into data (a
constraint predicate, an agent factory) is not callable there. Under trust a
bound callable is never in a denied module (below); what a ``!py`` walk or an
included helper hands back is judged where it is read
(:func:`check_reference`, ``expr.include``), and what a helper function
RETURNS is judged as it returns (:func:`check_returned`, T091 AP1). Every
call of a bound value is judged again at the call
(:func:`callable_code_allowed`, T091 AR3): helper code, allowed framework
code or a domain class, a callable instance by what its ``__call__`` runs.

**Framework code a trusted spec may reach** (T091 AP2). The rule is by
module, not by function, and has two halves:

- **Denied modules** (:data:`DENIED_ENTRY_POINTS`): every name in a module
  that loads a spec, runs an experiment or pytest, writes files, reads keys
  or calls the network — the loaders and the evaluator, the experiment
  runner and store, the report, the models snapshot, config, the CLI. A
  denied name refuses at every door: a ``!py`` step, a name read off an
  included helper, a bound callable, a helper's return value — and a
  ``functools.partial`` or bound method is judged by the function it wraps.
- **Allowed code** (:data:`PY_ALLOWED_MODULES` + the registered heads): a
  ``!py`` reference into ``alienbio`` that lands on a function or class must
  be a registered head's function or live in an allowed module (the
  distributions). Plain data and domain values elsewhere in
  ``alienbio`` stay readable; everything else a spec needs is a head.

What a spec's own included helpers define is the helper author's code, and
is trusted as such: a helper can import ``subprocess`` itself. The rule
keeps a YAML-only trusted spec — no helper — from reaching side effects, and
keeps a helper's imports from leaking through it by reference.
"""

from __future__ import annotations

import functools
import inspect
import types
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from functools import lru_cache
from typing import Any, Optional

from ..spec_lang.safe_eval import UnsafeExpressionError, _check_attr_name

#: Values whose attributes and methods an expression may use, by exact type.
PLAIN_TYPES: frozenset[type] = frozenset(
    {str, bytes, int, float, complex, bool, type(None), list, tuple, dict, set, frozenset}
)

#: The domain classes whose data attributes an expression may read, as
#: ``module:qualname`` (resolved on first use — the classes live above
#: ``expr/`` in the import graph). A subclass counts (``SkeletonBlock`` covers
#: every block; ``Entity`` covers ``ChemistryImpl`` / ``ReactionImpl`` /
#: ``MoleculeImpl`` / ``CompartmentImpl``).
DOMAIN_CLASS_NAMES: tuple[str, ...] = (
    # distributions (a QuotedForm is a Dist too, and is NOT here)
    "alienbio.suite.dist:Constant",
    "alienbio.suite.dist:Uniform",
    "alienbio.suite.dist:Normal",
    "alienbio.suite.dist:LogNormal",
    "alienbio.suite.dist:Choice",
    # worlds and entities
    "alienbio.infra.entity:Entity",
    "alienbio.bio.world:WorldImpl",
    "alienbio.bio.world:Compartment",
    "alienbio.bio.world:Transport",
    "alienbio.bio.world:GrowthLaw",
    "alienbio.bio.world:DeathLaw",
    "alienbio.bio.world:CountFlowSpec",
    "alienbio.bio.reaction:Modulation",
    # skeletons and blocks
    "alienbio.suite.skeleton:Skeleton",
    "alienbio.suite.skeleton:SkeletonBlock",
    "alienbio.suite.skeleton:Fragment",
    "alienbio.suite.skeleton:Port",
    "alienbio.suite.skeleton:PoolBinding",
    "alienbio.suite.skeleton:Provenance",
    "alienbio.suite.skeleton:PortDir",
    "alienbio.suite.skeleton:Role",
    "alienbio.suite.blocks:PoissonSchedule",
    # tasks, questions, objectives, suites
    "alienbio.suite.types:Timeline",
    "alienbio.suite.types:RoleSlot",
    "alienbio.suite.types:Motif",
    "alienbio.suite.types:CarveResult",
    "alienbio.suite.types:FeatureSet",
    "alienbio.suite.types:Answer",
    "alienbio.suite.types:Question",
    "alienbio.suite.types:GraderSpec",
    "alienbio.suite.types:AnswerObjective",
    "alienbio.suite.types:OutcomeObjective",
    "alienbio.suite.types:TaskArchetype",
    "alienbio.suite.types:TaskInstance",
    "alienbio.suite.types:SuiteSpec",
    "alienbio.suite.types:Suite",
    # drafts and trial records
    "alienbio.suite.drafters:Draft",
    "alienbio.suite.trial:TrialRecord",
    "alienbio.suite.trial:ProbeRecord",
)


@lru_cache(maxsize=1)
def domain_types() -> tuple[type, ...]:
    """The classes :data:`DOMAIN_CLASS_NAMES` names (a missing one is an
    import error, never a silently shorter list)."""
    import importlib

    out: list[type] = []
    for entry in DOMAIN_CLASS_NAMES:
        module, _, qualname = entry.partition(":")
        obj: Any = importlib.import_module(module)
        for part in qualname.split("."):
            obj = getattr(obj, part)
        if not isinstance(obj, type):
            raise TypeError(f"expr.access: {entry} is not a class")
        out.append(obj)
    return tuple(out)


#: Modules whose every name is refused wherever a trusted spec could reach
#: it — a ``!py`` walk, an included helper's namespace, a callable bound in
#: data, a helper's return value (T091 AL3, reorganized by module in AP2:
#: ``!py alienbio.report.example_rows`` ran every catalog example, and
#: ``resolve_source_path`` + ``write_models_snapshot`` wrote any file). An
#: entry is ``module:*`` (the module and everything in or under it).
DENIED_ENTRY_POINTS: tuple[str, ...] = (
    # loading and evaluating specs, executing helper code
    "alienbio.expr.include:*",
    "alienbio.expr.interp:*",
    "alienbio.expr.yaml_tags:*",
    "alienbio.expr.env:*",
    "alienbio.suite.spec:*",  # load_spec, resolve_source_path, the spec codec
    "alienbio.suite.expr_experiment:*",  # load_experiment
    # running experiments and writing their results
    "alienbio.suite.experiment:*",
    "alienbio.suite.store:*",
    "alienbio.suite.mass_trial:*",
    "alienbio.suite.runner:*",
    # the live model, its key and its snapshot (network, files)
    "alienbio.suite.llm_agent:*",  # fetch_models_snapshot, write_models_snapshot
    # the report (pytest, every catalog example), config, the CLI
    "alienbio.report:*",
    "alienbio._report_plugin:*",
    "alienbio.capabilities:*",
    "alienbio.config:*",
    "alienbio.commands:*",
    "alienbio.cli:*",
)

#: The ``alienbio`` modules whose functions and classes a ``!py`` reference
#: may land on, beside the registered heads' own functions (T091 AP2).
#: ``alienbio.bio.makers`` was listed and is not (T091 AR8): every public
#: name in it is an import judged by its owner module or the ``mk``
#: ``Pegboard`` instance, which :func:`check_reference` refuses as not plain
#: data — so ``mk.M`` / ``mk.anchor`` were never reachable through it.
PY_ALLOWED_MODULES: tuple[str, ...] = ("alienbio.suite.dist",)


def _unwrap(obj: Any) -> Any:
    """The function a ``functools.partial`` or bound method wraps (T091 AP1:
    a partial has no ``__qualname__``, so ``partial(load_spec, …)`` passed)."""
    for _ in range(100):
        if isinstance(obj, functools.partial):
            obj = obj.func
        elif isinstance(obj, types.MethodType):
            obj = obj.__func__
        else:
            break
    return obj


def _owner(obj: Any) -> Optional[str]:
    """The module ``obj`` (a module, class or callable) belongs to; ``None``
    for a data value (an instance's class module does not make data code)."""
    obj = _unwrap(obj)
    if isinstance(obj, types.ModuleType):
        return obj.__name__
    if isinstance(obj, type) or callable(obj):
        module = getattr(obj, "__module__", None)
        if isinstance(module, str):
            return module
        self_ = getattr(obj, "__self__", None)  # a builtin method: its receiver's module
        if isinstance(self_, types.ModuleType):
            return self_.__name__
    return None


def _in_module(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def denied_entry_point(obj: Any) -> Optional[str]:
    """The :data:`DENIED_ENTRY_POINTS` entry ``obj`` (a module, class,
    function, method or partial — unwrapped) falls under, else ``None``."""
    module = _owner(obj)
    if module is None:
        return None
    for entry in DENIED_ENTRY_POINTS:
        if _in_module(module, entry.partition(":")[0]):
            return entry
    return None


def allowed_framework_code(obj: Any) -> bool:
    """``obj`` (a function or class under ``alienbio``) is code a spec may
    reach by reference: a registered head's function or a name in
    :data:`PY_ALLOWED_MODULES` (T091 AP2)."""
    from .registry import registry

    target = _unwrap(obj)
    if registry.has_fn(target):
        return True
    module = _owner(target)
    return module is not None and any(_in_module(module, m) for m in PY_ALLOWED_MODULES)


def _call_target(obj: Any) -> Any:
    """The code calling ``obj`` runs: the function a partial or bound method
    wraps, else — for a callable instance — its class's ``__call__``, a
    ``staticmethod`` / ``classmethod`` unwrapped (T091 AR4: ``__call__ =
    staticmethod(os.getcwd)`` on a helper's class ran ``os.getcwd``)."""
    target = _unwrap(obj)
    if target is None or isinstance(target, (type, types.FunctionType, types.BuiltinFunctionType, types.ModuleType)):
        return target
    call = inspect.getattr_static(type(target), "__call__", None)
    if isinstance(call, (staticmethod, classmethod)):
        call = call.__func__
    return _unwrap(call)


def callable_code_allowed(obj: Any) -> bool:
    """``obj`` is code a trusted spec may call (T091 AR3/AR4): the spec's own
    included helper code, allowed framework code
    (:func:`allowed_framework_code`), or a domain class (a constructor such
    as ``MoleculeImpl``, an ``Entity`` — the classes
    ``spec_lang.biotype_registry`` holds are all domain classes). A callable
    instance is judged by the code its ``__call__`` runs, never by the
    module of its class. Anything else — a framework function that is not a
    head, ``os.getcwd``, a slot wrapper — is not callable from a spec,
    whoever bound it (a Python caller exposes a function by registering a
    head)."""
    from .include import INCLUDE_MODULE_PREFIX

    target = _call_target(obj)
    if isinstance(target, type) and issubclass(target, domain_types()):
        return True
    module = _owner(target) if target is not None else None
    if module is None:
        return False
    if module.startswith(INCLUDE_MODULE_PREFIX):
        return True
    return _in_module(module, "alienbio") and allowed_framework_code(target)


def check_reference(value: Any, what: str) -> None:
    """A Python object a trusted spec obtains by reference (a ``!py`` walk's
    result, a name read off an included helper): a callable (the caller
    checks its owner), plain data or a domain value — never a module, a
    ``Path``, a logger, a ``Registry``, an ``Env`` (T091 AL3) — and never a
    denied entry point."""
    entry = denied_entry_point(value)
    if entry is not None:
        raise UnsafeExpressionError(f"{what}: {_type_name(value)} is a framework entry point that loads or executes code ({entry})")
    if isinstance(value, types.ModuleType):
        raise UnsafeExpressionError(f"{what}: {_type_name(value)} is a module, not a value")
    if callable(value) or is_plain(value) or is_domain(value):
        return
    raise UnsafeExpressionError(f"{what}: {_type_name(value)} is not plain data or a domain value")


def check_returned(value: Any, what: str) -> None:
    """What a trusted bound callable (an included helper's function, a
    ``!py`` function) returned (T091 AP1): judged like a reference, and a
    callable or class in it must be code a spec may call
    (:func:`callable_code_allowed`) — never a module, a function from
    outside those roots (``subprocess.run``), or a partial or bound method
    wrapping a denied one. Plain containers are walked; so is an instance of
    the helper's own class that is a mapping, sequence or set (T091 AR4: a
    helper's ``Box(dict)`` holding ``os.getcwd`` was skipped as inert, and
    ``b.cwd()`` called it), and a callable one is judged by its ``__call__``."""
    from .include import INCLUDE_MODULE_PREFIX

    seen: set[int] = set()
    stack = [value]
    while stack:
        x = stack.pop()
        if id(x) in seen:
            continue
        seen.add(id(x))
        if type(x) in (list, tuple, set, frozenset):
            stack.extend(x)
            continue
        if type(x) is dict:
            stack.extend(x.keys())
            stack.extend(x.values())
            continue
        if not isinstance(x, type) and type(x).__module__.startswith(INCLUDE_MODULE_PREFIX):
            # an instance of the helper's own class: its data is walked, and
            # what calling it runs is judged (access.py stops its methods)
            if isinstance(x, Mapping):
                stack.extend(dict.keys(x) if isinstance(x, dict) else x.keys())
                stack.extend(dict.values(x) if isinstance(x, dict) else x.values())
            elif isinstance(x, (Sequence, AbstractSet)) and not isinstance(x, (str, bytes, bytearray)):
                stack.extend(x)
            if callable(x) and not callable_code_allowed(x):
                raise UnsafeExpressionError(
                    f"{what}: returned a callable {_type_name(x)} whose __call__ runs code outside the spec's helpers"
                )
            continue
        check_reference(x, what)
        if (isinstance(x, type) or callable(x)) and not callable_code_allowed(x):
            raise UnsafeExpressionError(
                f"{what}: returned {_type_name(x)} from {_owner(_call_target(x))!r}, outside the spec's helpers and the "
                f"allowed framework code (registered heads, domain classes, {list(PY_ALLOWED_MODULES)})"
            )


def _type_name(value: Any) -> str:
    if isinstance(value, types.ModuleType):
        return f"module {value.__name__!r}"
    if isinstance(value, type):
        return f"class {value.__qualname__!r}"
    t = type(value)
    return t.__qualname__ if t.__module__ == "builtins" else f"{t.__module__}.{t.__qualname__}"


def is_plain(value: Any) -> bool:
    return type(value) in PLAIN_TYPES


def is_domain(value: Any) -> bool:
    # A class object is never a domain *value*, even a domain class itself.
    return not isinstance(value, type) and isinstance(value, domain_types())


def check_name(name: str) -> None:
    """The attribute-name rule: no dunders / interpreter internals (the AST
    validator's rule), and no private name."""
    _check_attr_name(name)
    if name.startswith("_"):
        raise UnsafeExpressionError(f"attribute {name!r} is private and not readable from a spec expression")


def read_attr(value: Any, name: str) -> Any:
    """``value.name`` for an expression (not a mapping key — the caller reads
    those first). The receiver's type is judged before the attribute is
    looked up: :class:`UnsafeExpressionError` names a refused type,
    ``AttributeError`` a missing attribute on an allowed one."""
    check_name(name)
    if is_plain(value):
        result = getattr(value, name)  # AttributeError: the caller's "no attribute"
    elif is_domain(value):
        result = getattr(value, name)
        if callable(result) and not is_domain(result):
            raise UnsafeExpressionError(
                f"{name!r} on {_type_name(value)} is a method; a domain value's methods are not callable from a spec"
            )
        return result
    else:
        raise UnsafeExpressionError(f"attribute access on {_type_name(value)} is not allowed in a spec expression")
    if callable(result) and not is_plain(result):
        raise UnsafeExpressionError(
            f"{name!r} on {_type_name(value)} is a method; call it ({name}(...)), it is not a value"
        )
    return result


def method(value: Any, name: str) -> Any:
    """The bound method ``value.name`` for ``op:method``: plain receivers only."""
    check_name(name)
    if not is_plain(value):
        if is_domain(value):
            raise UnsafeExpressionError(
                f"method {name!r} on {_type_name(value)}: a domain value's methods are not callable from a spec"
            )
        raise UnsafeExpressionError(f"method call on {_type_name(value)} is not allowed in a spec expression")
    return getattr(value, name)


def check_callable(func: Any, *, trusted: bool) -> None:
    """A bound value that is not a registered head, called as one (``f(...)``,
    ``h.f(...)`` through a mapping). Untrusted: never (T091 AL8 — untrusted
    YAML cannot define a function, so every function it can reach leaked out
    of framework data, and the rule must not admit whatever a future head
    leaks). Trusted: never a denied entry point (T091 AL3), and only code
    :func:`callable_code_allowed` admits — judged at the call, so a function
    reached through a plain container a ``!py`` walk landed on refuses here
    (T091 AR3)."""
    if not trusted:
        raise UnsafeExpressionError(
            f"calling {_type_name(func)} is not allowed in an untrusted spec (only registered heads and templates are callable)"
        )
    entry = denied_entry_point(func)
    if entry is not None:
        raise UnsafeExpressionError(f"{_type_name(func)} is a framework entry point that loads or executes code ({entry})")
    if not callable_code_allowed(func):
        raise UnsafeExpressionError(
            f"calling {_type_name(func)} ({_owner(_call_target(func))!r}): only the spec's included helpers, registered "
            f"heads, domain classes and {list(PY_ALLOWED_MODULES)} are callable — a function reached through data is "
            "judged when it is called (T091 AR3)"
        )


__all__ = [
    "DENIED_ENTRY_POINTS",
    "DOMAIN_CLASS_NAMES",
    "PLAIN_TYPES",
    "PY_ALLOWED_MODULES",
    "allowed_framework_code",
    "callable_code_allowed",
    "check_callable",
    "check_name",
    "check_reference",
    "check_returned",
    "denied_entry_point",
    "domain_types",
    "is_domain",
    "is_plain",
    "method",
    "read_attr",
]
