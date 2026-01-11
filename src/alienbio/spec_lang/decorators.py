"""Decorators for registering types and functions in the ABIO system."""

from __future__ import annotations
from typing import Any, Callable, TypeVar, overload
from functools import wraps

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


# Global registries
biotype_registry: dict[str, type] = {}
action_registry: dict[str, Callable] = {}
measurement_registry: dict[str, Callable] = {}
scoring_registry: dict[str, Callable] = {}
rate_registry: dict[str, Callable] = {}


def clear_registries() -> None:
    """Clear all registries. Useful for testing."""
    biotype_registry.clear()
    action_registry.clear()
    measurement_registry.clear()
    scoring_registry.clear()
    rate_registry.clear()


# --- Biotype decorator ---


@overload
def biotype(cls: type[T]) -> type[T]: ...


@overload
def biotype(name: str) -> Callable[[type[T]], type[T]]: ...


def biotype(arg: type[T] | str | None = None) -> type[T] | Callable[[type[T]], type[T]]:
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


def fn(
    summary: str | None = None,
    range: tuple[float, float] | None = None,
    **kwargs: Any,
) -> Callable[[F], F]:
    """Base decorator for all functions. Stores metadata.

    Args:
        summary: Short description for plots/tables
        range: Expected output range
        **kwargs: Additional metadata
    """

    def decorator(func: F) -> F:
        wrapped = FnMeta(func, summary=summary, range=range, **kwargs)
        wraps(func)(wrapped)
        return wrapped  # type: ignore

    return decorator


def scoring(
    summary: str | None = None,
    range: tuple[float, float] = (0.0, 1.0),
    higher_is_better: bool = True,
    **kwargs: Any,
) -> Callable[[F], F]:
    """Decorator for scoring functions.

    Registers function in scoring_registry.
    """

    def decorator(func: F) -> F:
        wrapped = FnMeta(
            func,
            summary=summary,
            range=range,
            higher_is_better=higher_is_better,
            **kwargs,
        )
        wraps(func)(wrapped)
        scoring_registry[func.__name__] = wrapped
        return wrapped  # type: ignore

    return decorator


def action(
    summary: str | None = None,
    targets: str | None = None,
    reversible: bool = False,
    cost: float = 1.0,
    **kwargs: Any,
) -> Callable[[F], F]:
    """Decorator for action functions.

    Registers function in action_registry.
    """

    def decorator(func: F) -> F:
        wrapped = FnMeta(
            func,
            summary=summary,
            targets=targets,
            reversible=reversible,
            cost=cost,
            **kwargs,
        )
        wraps(func)(wrapped)
        action_registry[func.__name__] = wrapped
        return wrapped  # type: ignore

    return decorator


def measurement(
    summary: str | None = None,
    targets: str | None = None,
    cost: str = "none",
    **kwargs: Any,
) -> Callable[[F], F]:
    """Decorator for measurement functions.

    Registers function in measurement_registry.
    """

    def decorator(func: F) -> F:
        wrapped = FnMeta(
            func,
            summary=summary,
            targets=targets,
            cost=cost,
            **kwargs,
        )
        wraps(func)(wrapped)
        measurement_registry[func.__name__] = wrapped
        return wrapped  # type: ignore

    return decorator


def rate(
    summary: str | None = None,
    range: tuple[float, float] = (0.0, float("inf")),
    **kwargs: Any,
) -> Callable[[F], F]:
    """Decorator for rate functions.

    Registers function in rate_registry.
    """

    def decorator(func: F) -> F:
        wrapped = FnMeta(
            func,
            summary=summary,
            range=range,
            **kwargs,
        )
        wraps(func)(wrapped)
        rate_registry[func.__name__] = wrapped
        return wrapped  # type: ignore

    return decorator


# --- Registry access functions ---


def get_action(name: str) -> Callable:
    """Get an action by name.

    Raises:
        KeyError: If name not registered
    """
    if name not in action_registry:
        raise KeyError(f"Unknown action: {name}")
    return action_registry[name]


def get_measurement(name: str) -> Callable:
    """Get a measurement by name.

    Raises:
        KeyError: If name not registered
    """
    if name not in measurement_registry:
        raise KeyError(f"Unknown measurement: {name}")
    return measurement_registry[name]


def get_scoring(name: str) -> Callable:
    """Get a scoring function by name.

    Raises:
        KeyError: If name not registered
    """
    if name not in scoring_registry:
        raise KeyError(f"Unknown scoring function: {name}")
    return scoring_registry[name]


def get_rate(name: str) -> Callable:
    """Get a rate function by name.

    Raises:
        KeyError: If name not registered
    """
    if name not in rate_registry:
        raise KeyError(f"Unknown rate function: {name}")
    return rate_registry[name]
