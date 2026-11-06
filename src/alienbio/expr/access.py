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
code or a domain class, a callable instance by what its ``__call__`` runs,
a helper class also by what its metaclass ``__call__`` runs (the same code
test, plus the stdlib enum metaclass, T091 AV1).

**Framework code a trusted spec may reach** (T091 AP2). The rule is by
module, not by function, and has two halves:

- **Denied modules** (:data:`DENIED_ENTRY_POINTS`): every name in a module
  that loads a spec, runs an experiment or pytest, writes files, reads keys
  or calls the network — the loaders and the evaluator, the experiment
  runner and store, the report, the models snapshot, config, the CLI. A
  denied name refuses at every door: a ``!py`` step, a name read off an
  included helper, a bound callable, a helper's return value — and a
  ``functools.partial``, a bound method or a ``functools.lru_cache`` /
  ``functools.cache`` wrapper is judged by the function it wraps (T091 BC;
  no other ``__wrapped__`` is followed: a ``functools.wraps`` decorator's
  wrapper is the code that runs).
- **Allowed code** (:data:`PY_ALLOWED_MODULES` + the registered heads): a
  ``!py`` reference into ``alienbio`` that lands on a function or class must
  be a registered head's function or live in an allowed module (the
  distributions). Plain data and domain values elsewhere in
  ``alienbio`` stay readable; everything else a spec needs is a head.

What a spec's own included helpers define is the helper author's code, and
is trusted as such: a helper can import ``subprocess`` itself. The rule
keeps a YAML-only trusted spec — no helper — from reaching side effects, and
keeps a helper's imports from leaking through it by reference.

**Where the boundary sits** (T091 AX2). The guard stops a YAML author
reaching foreign code the helper author wrote no code for: a name in the
helper's namespace, a value a helper returns, a value called and its
``__call__`` chain. A helper author who wires a foreign function into their
own class's other protocol hooks — subscript (``__getitem__``),
``__class_getitem__``, an operator dunder, an Enum's ``_missing_``, a
constructor inherited from a foreign base — has written that code, the same
as a ``def`` that calls it, and it runs as helper code. A ``__call__``
that is a descriptor (its type defines ``__get__``: a property, a
``partialmethod``, a helper class with a ``__get__``) is refused whether or
not it is itself callable, since Python calls what ``__get__`` returns and
the guard cannot know that before it runs (T091 AZ6).
"""

from __future__ import annotations

import enum
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


#: The type of a ``functools.lru_cache`` / ``functools.cache`` wrapper (the C
#: ``functools._lru_cache_wrapper``), read off a real wrapper rather than
#: named by its private path.
_LRU_CACHE_WRAPPER: type = type(functools.lru_cache(maxsize=None)(lambda: None))


def _uncache(obj: Any) -> Any:
    """The function an ``lru_cache`` / ``cache`` wrapper caches (its
    ``__wrapped__``), else ``obj`` (T091 BC). Calling the wrapper runs that
    function, so it is judged by it: a helper's cached function is helper
    code, ``lru_cache(os.getcwd)`` is still ``posix`` code. Only this C
    wrapper type is followed — a ``functools.wraps`` decorator's wrapper is
    the code that runs, and is judged itself."""
    for _ in range(100):
        if not isinstance(obj, _LRU_CACHE_WRAPPER):
            break
        obj = obj.__wrapped__
    return obj


def _unwrap(obj: Any) -> Any:
    """The function a ``functools.partial``, a bound method or an
    ``lru_cache`` wrapper wraps (T091 AP1: a partial has no
    ``__qualname__``, so ``partial(load_spec, …)`` passed; T091 BC: a cached
    helper function was refused as a descriptor)."""
    for _ in range(100):
        if isinstance(obj, functools.partial):
            obj = obj.func
        elif isinstance(obj, types.MethodType):
            obj = obj.__func__
        elif isinstance(obj, _LRU_CACHE_WRAPPER):
            obj = _uncache(obj)
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


#: How many ``__call__`` levels :func:`_call_target` follows: a chain of
#: exactly this many levels down to a function is callable, one more is
#: refused, and the refusal names this bound (T091 AT3, AV6).
MAX_CALL_DEPTH = 8

#: What calling a class runs when its metaclass adds nothing.
_TYPE_CALL = inspect.getattr_static(type, "__call__")

#: The stdlib enum metaclass's ``__call__``: allowed on a helper's own
#: ``Enum`` / ``IntEnum`` / ``Flag`` class (T091 AV1). ``E(1)`` looks a member
#: up by value. The functional API (``Base('X', 'a b')``) instead builds a new
#: enum class, which is refused on return unless its module is allowed code,
#: and whose members :func:`check_returned` refuses (T091 AX4).
ENUM_METACLASS_CALL = inspect.getattr_static(enum.EnumType, "__call__")

#: C-level callables whose code the guard cannot judge by module: a slot
#: wrapper (``object.__repr__``), a method-wrapper (``object().__repr__``),
#: a method descriptor (``str.join``) and a classmethod descriptor. Calling
#: one runs C code chosen by the object it wraps (T091 AZ5).
_C_WRAPPERS: tuple[type, ...] = (
    types.WrapperDescriptorType,
    types.MethodWrapperType,
    types.MethodDescriptorType,
    types.ClassMethodDescriptorType,
)

_MISSING = object()


class _NoCode:
    """What :func:`_call_target` returns when a link of the ``__call__``
    chain is no code it can judge: ``what`` says what that link is, and
    ``level`` which link (``-1`` the object itself, ``0`` its ``__call__``,
    ``1`` that one's ``__call__`` …). Refused, with :meth:`phrase` as the
    reason (T091 AZ4-AZ6)."""

    __slots__ = ("what", "level")

    def __init__(self, what: str, level: int) -> None:
        self.what = what
        self.level = level

    def phrase(self, subject: str) -> str:
        """The reason, naming the link from ``subject`` (``"it"`` or, for a
        metaclass, ``"its metaclass M.__call__"``)."""
        if self.level < 0:
            return f"{subject} {self.what}"
        first = "its __call__" if subject == "it" else f"{subject}.__call__"
        return f"{first}{'.__call__' * self.level} {self.what}"


#: The reason text for a descriptor ``__call__`` (T091 AX5, AZ6).
_DESCRIPTOR_WHAT = (
    "is a property or other descriptor (its type defines __get__, so a call runs whatever __get__ returns, "
    "which the guard cannot know before it runs), not a function or a callable instance"
)


def _link_refusal(value: Any, level: int) -> Optional[_NoCode]:
    """Why ``value`` — an object called, or a ``__call__`` attribute read
    statically off a class (a ``staticmethod`` / ``classmethod`` already
    unwrapped) — is no code to judge or follow, else ``None``. A C wrapper
    names itself; a value whose type defines ``__get__`` and is not a
    function, builtin or class is a descriptor, callable or not, since what
    Python calls is what its ``__get__`` returns (T091 AZ6: a callable
    descriptor's ``__get__`` returned ``os.getcwd``, and the guard judged its
    ``__call__``, which never ran); anything else not callable (``None``,
    ``5``) is named as not callable."""
    if isinstance(value, _C_WRAPPERS):
        qualname = getattr(value, "__qualname__", None) or getattr(value, "__name__", "?")
        return _NoCode(f"is a C {type(value).__name__} ({qualname}), which runs no code the guard can judge", level)
    if not isinstance(value, (type, types.FunctionType, types.BuiltinFunctionType)) and hasattr(type(value), "__get__"):
        return _NoCode(_DESCRIPTOR_WHAT, level)
    if not callable(value):
        return _NoCode(f"is {'None' if value is None else _type_name(value)}, which is not callable", level)
    return None


def _call_target(obj: Any) -> Any:
    """The code calling ``obj`` runs: the function a partial, bound method
    or ``lru_cache`` wrapper wraps, else — for a callable instance — its
    class's ``__call__``, a ``staticmethod`` / ``classmethod`` and an
    ``lru_cache`` wrapper unwrapped (T091 AR4: ``__call__ =
    staticmethod(os.getcwd)`` on a helper's class ran ``os.getcwd``),
    followed again while it is itself a callable instance (T091 AT3:
    ``Outer.__call__ = Inner()`` reached ``os.getcwd`` one level down).
    ``None`` when the chain does not reach a function, a builtin or a class
    within :data:`MAX_CALL_DEPTH` ``__call__`` levels, and a :class:`_NoCode`
    when a link is a C wrapper, a descriptor or not callable — either is
    refused."""
    target = _unwrap(obj)
    if not isinstance(target, (type, types.FunctionType, types.BuiltinFunctionType, types.ModuleType)):
        no_code = _link_refusal(target, -1)
        if no_code is not None:
            return no_code
    for level in range(MAX_CALL_DEPTH + 1):  # the last pass only tests the eighth level's target
        if isinstance(target, (type, types.FunctionType, types.BuiltinFunctionType, types.ModuleType)):
            return target
        call = inspect.getattr_static(type(target), "__call__", _MISSING)
        if call is _MISSING:
            return _NoCode("is missing (the object is not callable)", level)
        if isinstance(call, (staticmethod, classmethod)):
            call = call.__func__
        call = _uncache(call)  # a cached ``__call__`` runs the function it caches
        no_code = _link_refusal(call, level)
        if no_code is not None:
            return no_code
        target = _unwrap(call)
    return None


def _code_refusal(target: Any, subject: str = "it") -> Optional[str]:
    """Why ``target`` (what :func:`_call_target` resolved; not a class) is
    not code a spec may call, else ``None``: the spec's own included helper
    code and allowed framework code pass."""
    from .include import INCLUDE_MODULE_PREFIX

    if target is None:
        chain = "its __call__ chain" if subject == "it" else f"the __call__ chain of {subject}"
        return f"{chain} does not reach a function within MAX_CALL_DEPTH={MAX_CALL_DEPTH} levels"
    if isinstance(target, _NoCode):
        return target.phrase(subject)
    module = _owner(target)
    if module is not None and (
        module.startswith(INCLUDE_MODULE_PREFIX) or (_in_module(module, "alienbio") and allowed_framework_code(target))
    ):
        return None
    runner = "it runs" if subject == "it" else f"{subject} runs"
    return (
        f"{runner} code from {module!r}: only the spec's included helpers, registered heads, domain classes and "
        f"{list(PY_ALLOWED_MODULES)} are callable"
    )


def _metaclass_refusal(cls: type, depth: int) -> Optional[str]:
    """Calling ``cls`` runs its metaclass's ``__call__`` first (T091 AT3: a
    metaclass ``__call__`` returning ``os.getcwd`` was never judged). A
    metaclass that adds no ``__call__`` runs ``type.__call__`` (``__new__`` /
    ``__init__``, judged with the class). One that does is judged by the
    same code test as any callable — the spec's helper code and allowed
    framework code pass, a foreign function (``__call__ =
    staticmethod(os.getcwd)``) refuses — plus :data:`ENUM_METACLASS_CALL`,
    allowed here because the caller has already found ``cls`` to be helper
    code (T091 AV1). The ``__call__`` attribute itself is judged first (T091
    AZ4): a property, a descriptor or a non-callable set directly on the
    metaclass gets that reason, not the module of what it would return."""
    meta = type(cls)
    meta_call = inspect.getattr_static(meta, "__call__", None)
    if meta_call is _TYPE_CALL or meta_call is ENUM_METACLASS_CALL:
        return None
    if isinstance(meta_call, (staticmethod, classmethod)):
        meta_call = meta_call.__func__
    meta_call = _uncache(meta_call)
    subject = f"its metaclass {meta.__qualname__}.__call__"
    no_code = _link_refusal(meta_call, -1)
    if no_code is not None:
        return no_code.phrase(subject)
    target = _call_target(meta_call)
    if isinstance(target, type):
        reason = callable_code_refusal(target, _depth=depth + 1)
        return None if reason is None else f"{subject} calls class {target.__qualname__!r}: {reason}"
    reason = _code_refusal(target, subject)
    if reason is None or target is None or isinstance(target, _NoCode):
        return reason
    return f"{subject} runs code from {_owner(target)!r}, outside the spec's helpers and the allowed framework code"


def callable_code_refusal(obj: Any, *, _depth: int = 0) -> Optional[str]:
    """Why ``obj`` is not code a trusted spec may call, else ``None`` (T091
    AR3/AR4/AV1). Callable: the spec's own included helper code, allowed
    framework code (:func:`allowed_framework_code`), or a domain class (a
    constructor such as ``MoleculeImpl``, an ``Entity`` — the classes
    ``spec_lang.biotype_registry`` holds are all domain classes, judged
    first, whatever their metaclass). A helper class is judged by its module
    and by what its metaclass ``__call__`` runs (:func:`_metaclass_refusal`).
    A callable instance is judged by the code its ``__call__`` runs, never
    by the module of its class. Anything else — a framework function that is
    not a head, ``os.getcwd``, a slot wrapper — is not callable from a spec,
    whoever bound it (a Python caller exposes a function by registering a
    head)."""
    if _depth > MAX_CALL_DEPTH:
        return f"its metaclass __call__ chain is deeper than MAX_CALL_DEPTH={MAX_CALL_DEPTH} levels"
    target = _call_target(obj)
    if isinstance(target, type):
        if issubclass(target, domain_types()):
            return None
        reason = _code_refusal(target)
        return reason if reason is not None else _metaclass_refusal(target, _depth)
    return _code_refusal(target)


def callable_code_allowed(obj: Any) -> bool:
    """``obj`` is code a trusted spec may call (:func:`callable_code_refusal`
    gives the reason when it is not)."""
    return callable_code_refusal(obj) is None


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
            reason = callable_code_refusal(x) if callable(x) else None
            if reason is not None:
                raise UnsafeExpressionError(
                    f"{what}: returned a callable {_type_name(x)} whose __call__ runs code outside the spec's helpers ({reason})"
                )
            continue
        check_reference(x, what)
        reason = callable_code_refusal(x) if (isinstance(x, type) or callable(x)) else None
        if reason is not None:
            raise UnsafeExpressionError(
                f"{what}: returned {_type_name(x)} from {_owner(_call_target(x))!r}, outside the spec's helpers and the "
                f"allowed framework code (registered heads, domain classes, {list(PY_ALLOWED_MODULES)}): {reason}"
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
    reason = callable_code_refusal(func)
    if reason is not None:
        raise UnsafeExpressionError(
            f"calling {_type_name(func)}: {reason} — a function reached through data is judged when it is called (T091 AR3)"
        )


__all__ = [
    "DENIED_ENTRY_POINTS",
    "DOMAIN_CLASS_NAMES",
    "PLAIN_TYPES",
    "PY_ALLOWED_MODULES",
    "allowed_framework_code",
    "callable_code_allowed",
    "callable_code_refusal",
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
