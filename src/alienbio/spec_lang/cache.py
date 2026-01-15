"""ORM-style caching for DAT objects.

Ensures the same DAT path returns the same object instance,
providing consistent state across multiple references.
"""

from __future__ import annotations

from typing import Any


class DatCache:
    """Cache for loaded DAT objects.

    Implements the ORM pattern: same path always returns same object.
    Cache key is the resolved filesystem path.

    Usage:
        cache = DatCache()
        cache.set("/path/to/dat", loaded_data)
        data = cache.get("/path/to/dat")  # returns same object
        cache.clear()                      # force reload from disk
    """

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        """Get cached value for key, or None if not cached."""
        return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        """Store value in cache."""
        self._cache[key] = value

    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()

    def __contains__(self, key: str) -> bool:
        """Check if key is in cache."""
        return key in self._cache


# Global cache instance (shared across all Bio instances)
_global_cache = DatCache()


def get_global_cache() -> DatCache:
    """Get the global DAT cache instance."""
    return _global_cache


def clear_global_cache() -> None:
    """Clear the global DAT cache."""
    _global_cache.clear()
