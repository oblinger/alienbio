"""Exceptions for the generator module."""

from __future__ import annotations

from typing import Any


class TemplateNotFoundError(Exception):
    """Raised when a template is not found in the registry."""

    def __init__(self, name: str, registry_names: list[str] | None = None):
        self.name = name
        self.registry_names = registry_names or []
        msg = f"Template not found: '{name}'"
        if self.registry_names:
            msg += f". Available templates: {', '.join(sorted(self.registry_names)[:5])}"
            if len(self.registry_names) > 5:
                msg += f" ... ({len(self.registry_names)} total)"
        super().__init__(msg)


class PortTypeMismatchError(Exception):
    """Raised when connecting ports with incompatible types."""

    def __init__(
        self,
        source_port: str,
        source_type: str,
        target_port: str,
        target_type: str,
    ):
        self.source_port = source_port
        self.source_type = source_type
        self.target_port = target_port
        self.target_type = target_type
        msg = (
            f"Port type mismatch: cannot connect '{source_port}' ({source_type}) "
            f"to '{target_port}' ({target_type})"
        )
        super().__init__(msg)


class PortNotFoundError(Exception):
    """Raised when a port reference cannot be resolved."""

    def __init__(self, port_path: str, context: str | None = None):
        self.port_path = port_path
        self.context = context
        msg = f"Port not found: '{port_path}'"
        if context:
            msg += f" in {context}"
        super().__init__(msg)


class GuardViolation(Exception):
    """Raised when a guard constraint is violated."""

    def __init__(
        self,
        guard_name: str,
        message: str,
        details: dict[str, Any] | None = None,
        prune_list: list[str] | None = None,
    ):
        self.guard_name = guard_name
        self.details = details or {}
        self.prune_list = prune_list or []
        full_msg = f"Guard '{guard_name}' violated: {message}"
        super().__init__(full_msg)


class MissingParameterError(Exception):
    """Raised when a required parameter is not provided."""

    def __init__(self, param_name: str, template_name: str | None = None):
        self.param_name = param_name
        self.template_name = template_name
        msg = f"Missing required parameter: '{param_name}'"
        if template_name:
            msg += f" for template '{template_name}'"
        super().__init__(msg)


class CircularReferenceError(Exception):
    """Raised when circular template references are detected."""

    def __init__(self, cycle: list[str]):
        self.cycle = cycle
        cycle_str = " -> ".join(cycle)
        msg = f"Circular template reference detected: {cycle_str}"
        super().__init__(msg)
