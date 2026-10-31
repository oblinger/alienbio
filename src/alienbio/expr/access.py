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
bound callable is never one of :data:`DENIED_ENTRY_POINTS` — the framework
functions that load specs or execute code (T091 AL3: ``!py
alienbio.expr.include.run_python_file`` ran any ``.py`` on disk); what a
``!py`` walk or an included helper hands back is judged where it is read
(:func:`check_reference`, ``expr.include``).
"""

from __future__ import annotations

import types
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


#: Framework entry points that load a spec or execute code, refused by name
#: wherever a spec could reach them — a ``!py`` walk, an included helper's
#: namespace, a callable bound in data — under trust too (T091 AL3). An
#: entry is ``module:qualname`` (a class covers its methods: ``Env`` covers
#: ``Env.load`` / ``Env.standard``) or ``module:*`` (the module and every
#: submodule and name in it).
DENIED_ENTRY_POINTS: tuple[str, ...] = (
    "alienbio.expr.include:*",  # run_python_file, load_include, include_bindings, hydrate, resolve_py
    "alienbio.expr.interp:*",  # evaluate and the special-form evaluators
    "alienbio.expr.yaml_tags:load_text",
    "alienbio.expr.env:Env",  # Env.load, Env.standard, Env.hydrate
    "alienbio.suite.spec:load_spec",
    "alienbio.suite.expr_experiment:load_experiment",
    "alienbio.suite.experiment:run_experiment",
    "alienbio.report:run_pytest",
    "alienbio.commands:*",
    "alienbio.cli:*",
)


def denied_entry_point(obj: Any) -> Optional[str]:
    """The :data:`DENIED_ENTRY_POINTS` entry ``obj`` (a module, class,
    function or method) falls under, else ``None``."""
    if isinstance(obj, types.ModuleType):
        module: Any = obj.__name__
        qualname: Any = ""
    else:
        module = getattr(obj, "__module__", None)
        qualname = getattr(obj, "__qualname__", "")
    if not isinstance(module, str):
        return None
    for entry in DENIED_ENTRY_POINTS:
        mod, _, qual = entry.partition(":")
        if qual == "*":
            if module == mod or module.startswith(mod + "."):
                return entry
        elif module == mod and isinstance(qualname, str) and (qualname == qual or qualname.startswith(qual + ".")):
            return entry
    return None


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
    leaks). Trusted: whatever the trusted author bound (``!py`` and an
    included helper are judged where they are read), except a denied entry
    point (T091 AL3)."""
    if not trusted:
        raise UnsafeExpressionError(
            f"calling {_type_name(func)} is not allowed in an untrusted spec (only registered heads and templates are callable)"
        )
    entry = denied_entry_point(func)
    if entry is not None:
        raise UnsafeExpressionError(f"{_type_name(func)} is a framework entry point that loads or executes code ({entry})")


__all__ = [
    "DENIED_ENTRY_POINTS",
    "DOMAIN_CLASS_NAMES",
    "PLAIN_TYPES",
    "check_callable",
    "check_name",
    "check_reference",
    "denied_entry_point",
    "domain_types",
    "is_domain",
    "is_plain",
    "method",
    "read_attr",
]
