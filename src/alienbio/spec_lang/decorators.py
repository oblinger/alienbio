"""Decorators for registering types and functions in the ABIO system."""

from __future__ import annotations
from typing import Any, Callable, TypeVar, overload
from functools import wraps

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


# Global registries
biotype_registry: dict[str, type] = {}


def clear_registries() -> None:
    """Clear the biotype registry (for tests)."""
    biotype_registry.clear()


# --- Biotype decorator ---


@overload
def biotype(cls: type[T], /) -> type[T]: ...


@overload
def biotype(name: str, /) -> Callable[[type[T]], type[T]]: ...


def biotype(arg: type[T] | str | None = None, /) -> type[T] | Callable[[type[T]], type[T]]:
    """Register a class for hydration from YAML.

    Usage:
        @biotype
        class Chemistry: ...

        @biotype("custom_name")
        class World: ...
    """

    def decorator(cls: type[T]) -> type[T]:
        type_name = arg if isinstance(arg, str) else cls.__name__.lower()
        biotype_registry[type_name] = cls
        # Add _biotype_name attribute for dehydration
        cls._biotype_name = type_name  # type: ignore
        return cls

    if isinstance(arg, type):
        # Called as @biotype without parens
        return decorator(arg)
    else:
        # Called as @biotype("name") or @biotype()
        return decorator


def get_biotype(name: str) -> type:
    """Get a biotype class by name.

    Raises:
        KeyError: If name not registered
    """
    if name not in biotype_registry:
        raise KeyError(f"Unknown biotype: {name}")
    return biotype_registry[name]


# --- Function decorators ---


class FnMeta:
    """Metadata container for decorated functions."""

    def __init__(self, func: Callable, **kwargs: Any):
        self.func = func
        self.meta = kwargs

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.func(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        if name in ("func", "meta"):
            return super().__getattribute__(name)
        return getattr(self.func, name)
