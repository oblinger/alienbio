"""What remains of the M1 spec language after M47.7: the pieces the Expr
language stands on — the distribution builtins, the inline-expression
allowlist (``safe_eval``), lexical ``Scope``, and the ``@biotype`` class
registry. The old YAML loader, evaluator, typed keys, rate compiler and
``Bio`` facade are gone; ``alienbio.expr`` is the one language.
"""

from __future__ import annotations

from .builtins import DEFAULT_FUNCTIONS
from .decorators import biotype, biotype_registry, get_biotype
from .safe_eval import UnsafeExpressionError, safe_eval, validate_expression
from .scope import Scope

__all__ = [
    "DEFAULT_FUNCTIONS",
    "Scope",
    "UnsafeExpressionError",
    "biotype",
    "biotype_registry",
    "get_biotype",
    "safe_eval",
    "validate_expression",
]
