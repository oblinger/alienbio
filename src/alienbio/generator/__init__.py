"""Generator module for template-based scenario generation.

This module provides:
- parse_template(): Parse template data to dict
- parse_port(), ports_compatible(): Port handling functions
- TemplateRegistry: Storage and lookup for templates
- apply_template(): Apply template to produce namespaced molecules/reactions
- Guards: Validation system for generated content
- Visibility: Opaque name generation and partial visibility
"""

from __future__ import annotations

from .template import (
    parse_template,
    parse_port,
    ports_compatible,
    TemplateRegistry,
    # Backwards compatibility (deprecated)
    Template,
    Port,
)
from .expand import (
    apply_template,
    # Backwards compatibility (deprecated)
    expand,
    ExpandedTemplate,
)
from .exceptions import (
    TemplateNotFoundError,
    PortTypeMismatchError,
    PortNotFoundError,
    GuardViolation,
    MissingParameterError,
    CircularReferenceError,
)
from .guards import (
    guard,
    make_guard_context,
    run_guard,
    apply_template_with_guards,
    no_new_species_dependencies,
    no_new_cycles,
    no_essential,
    get_species_from_path,
    build_dependency_graph,
    detect_cycles,
    # Backwards compatibility (deprecated)
    GuardContext,
    expand_with_guards,
)
from .visibility import (
    generate_opaque_names,
    apply_fraction_known,
    generate_visibility_mapping,
    apply_visibility,
    # Backwards compatibility (deprecated)
    VisibleScenario,
)

__all__ = [
    # Template parsing (new API)
    "parse_template",
    "parse_port",
    "ports_compatible",
    "TemplateRegistry",
    # Template application (new API)
    "apply_template",
    # Guards (new API)
    "guard",
    "make_guard_context",
    "run_guard",
    "apply_template_with_guards",
    "no_new_species_dependencies",
    "no_new_cycles",
    "no_essential",
    "get_species_from_path",
    "build_dependency_graph",
    "detect_cycles",
    # Visibility (new API)
    "generate_opaque_names",
    "apply_fraction_known",
    "generate_visibility_mapping",
    "apply_visibility",
    # Exceptions
    "TemplateNotFoundError",
    "PortTypeMismatchError",
    "PortNotFoundError",
    "GuardViolation",
    "MissingParameterError",
    "CircularReferenceError",
    # Backwards compatibility (deprecated)
    "Template",
    "Port",
    "expand",
    "ExpandedTemplate",
    "GuardContext",
    "expand_with_guards",
    "VisibleScenario",
]
