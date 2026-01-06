"""Import collector for do-system module references.

This module imports all modules that might be referenced via dotted names
in the do system. This ensures they're available in sys.modules when referenced.
"""

# Import test fixtures module (optional - only available in development)
try:
    from tests import fixtures  # noqa: F401
except ImportError:
    pass
