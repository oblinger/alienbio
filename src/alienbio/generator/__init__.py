"""Generator module for template-based scenario generation.

This module provides:
- Template: Reusable scenario fragments with parameters and ports
- Port: Connection points for wiring templates together
- TemplateRegistry: Storage and lookup for named templates
- expand(): Template expansion with namespace prefixing
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

__all__ = [
    # Core classes
    "Template",
    "Port",
    "TemplateRegistry",
    # Expansion
    "expand",
    "ExpandedTemplate",
    # Exceptions
    "TemplateNotFoundError",
    "PortTypeMismatchError",
    "PortNotFoundError",
    "GuardViolation",
    "MissingParameterError",
    "CircularReferenceError",
]
