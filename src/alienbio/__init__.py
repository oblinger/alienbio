"""Alien Biology: A framework for testing agentic AI reasoning."""

from dvc_dat import Dat

from .infra import imports  # noqa: F401 - ensures do-referenced modules are loaded

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
    "Dat",
    "_ctx",
    "ctx",
    "set_context",
    "do",
    "create",
    "load",
    "save",
    "o",
]
