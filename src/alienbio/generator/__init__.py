"""Generator module for template-based scenario generation.

This module provides:
- Template: Reusable scenario fragments with parameters and ports
- Port: Connection points for wiring templates together
- TemplateRegistry: Storage and lookup for named templates
- expand(): Template expansion with namespace prefixing
- Guards: Validation system for generated content
- Bio.generate(): Full pipeline from spec to scenario
"""

from __future__ import annotations

from .template import Template, Port, TemplateRegistry
from .expand import expand, ExpandedTemplate
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
    GuardContext,
    run_guard,
    expand_with_guards,
    no_new_species_dependencies,
    no_new_cycles,
    no_essential,
    get_species_from_path,
    build_dependency_graph,
    detect_cycles,
)
from .visibility import (
    generate_opaque_names,
    apply_fraction_known,
    generate_visibility_mapping,
    apply_visibility,
    VisibleScenario,
)

__all__ = [
    # Core classes
    "Template",
    "Port",
    "TemplateRegistry",
    # Expansion
    "expand",
    "ExpandedTemplate",
    # Guards
    "guard",
    "GuardContext",
    "run_guard",
    "expand_with_guards",
    "no_new_species_dependencies",
    "no_new_cycles",
    "no_essential",
    "get_species_from_path",
    "build_dependency_graph",
    "detect_cycles",
    # Visibility
    "generate_opaque_names",
    "apply_fraction_known",
    "generate_visibility_mapping",
    "apply_visibility",
    "VisibleScenario",
    # Exceptions
    "TemplateNotFoundError",
    "PortTypeMismatchError",
    "PortNotFoundError",
    "GuardViolation",
    "MissingParameterError",
    "CircularReferenceError",
]
