"""Alien Biology: A framework for testing agentic AI reasoning."""

from .infra.context import (
    Context,
    _ctx,
    ctx,
    set_context,
    do,
    create,
    load,
    save,
    o,
)

__version__ = "0.1.0"

__all__ = [
    "Context",
    "_ctx",
    "ctx",
    "set_context",
    "do",
    "create",
    "load",
    "save",
    "o",
]
