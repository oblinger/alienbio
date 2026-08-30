"""``alienbio.expr`` — the Expr language (M47): forms, the interpreter, the
head registry, the three spellings. See the vault's ``ABIO Expr Spec`` and
``ABIO Expr Python API``.

    from alienbio.expr import X, Env, evaluate, fn, expander

    env = Env.standard(seed=7)
    evaluate(X.lognormal(1.0, 0.3), env)          # a draw
    evaluate(X.parse("max(2, poisson(3))"), env)  # the inline spelling
"""

from .env import Ctx, Env, ExprError, Limits
from .include import UnsafeSpecError
from .form import Call, Name, Quoted, contains_form, is_form, walk
from .interp import QuotedForm, TemplateHead, evaluate
from .registry import GuardViolation, Head, Registry, expander, fn, guard, registry
from .x import X
from .yaml_tags import ExprLoader, dump_structural, load_text
from . import heads as _heads  # noqa: F401 — registers the builtin heads

__all__ = [
    "Call",
    "Ctx",
    "Env",
    "ExprError",
    "UnsafeSpecError",
    "ExprLoader",
    "GuardViolation",
    "Head",
    "Limits",
    "Name",
    "Quoted",
    "QuotedForm",
    "Registry",
    "TemplateHead",
    "X",
    "contains_form",
    "dump_structural",
    "evaluate",
    "expander",
    "fn",
    "guard",
    "is_form",
    "load_text",
    "registry",
    "walk",
]
