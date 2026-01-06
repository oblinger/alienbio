"""Spec Language Module.

YAML tags, decorators, and Bio class for loading/saving biology specifications.
See docs: [[Spec Language]], [[Decorators]], [[Bio]]
"""

from .bio import Bio, bio
from .decorators import biotype, fn, scoring, action, measurement, rate
from .decorators import get_biotype, get_action, get_measurement, get_scoring, get_rate
from .decorators import biotype_registry, action_registry, measurement_registry
from .decorators import scoring_registry, rate_registry
from .tags import EvTag, RefTag, IncludeTag
from .loader import load_spec, transform_typed_keys, expand_defaults
from .scope import Scope

__all__ = [
    # Bio singleton and class
    "bio",
    "Bio",
    # Decorators
    "biotype",
    "fn",
    "scoring",
    "action",
    "measurement",
    "rate",
    # Registry access
    "get_biotype",
    "get_action",
    "get_measurement",
    "get_scoring",
    "get_rate",
    # Registries (for testing)
    "biotype_registry",
    "action_registry",
    "measurement_registry",
    "scoring_registry",
    "rate_registry",
    # Tags
    "EvTag",
    "RefTag",
    "IncludeTag",
    # Loader functions
    "load_spec",
    "transform_typed_keys",
    "expand_defaults",
    # Scope
    "Scope",
]
