"""API key and configuration management for alienbio.

This module provides configuration management for LLM providers:
- Config file at ~/.config/alienbio/config.yaml, written 0600 (it holds keys)
- API key storage and retrieval (env vars take precedence; the documented
  setup keeps the key in the macOS Keychain and exports it into the shell)

The model a run uses comes from its spec or ``suite.llm_agent.PINNED_MODEL``;
there is no default agent or default model setting (the ``default_agent`` /
``providers.*.default_model`` keys were read by nothing that runs and were
removed, T088 config 3).

Example usage:
    from alienbio.config import get_api_key, set_api_key, get_config

    # Get API key (checks env var first, then config file)
    key = get_api_key("anthropic")

    # Set API key in config file
    set_api_key("anthropic", "sk-ant-...")

    # Get full config
    config = get_config()
"""

import copy
from pathlib import Path
from typing import Any, Optional
import os

import yaml


# Default config location
CONFIG_DIR = Path.home() / ".config" / "alienbio"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

# Environment variable prefix for API keys
ENV_PREFIX = "ALIENBIO_"

# Provider-specific env var names (for common conventions)
PROVIDER_ENV_VARS = {
    "anthropic": ["ANTHROPIC_API_KEY", "ALIENBIO_ANTHROPIC_API_KEY"],
    "openai": ["OPENAI_API_KEY", "ALIENBIO_OPENAI_API_KEY"],
    "google": ["GOOGLE_API_KEY", "ALIENBIO_GOOGLE_API_KEY"],
}

# Default config structure
DEFAULT_CONFIG: dict[str, Any] = {
    "api_keys": {},
}

#: Group/other permission bits: a config file carrying any of them is
#: readable by other users of the machine and is tightened on read.
_LOOSE_BITS = 0o077


def get_config_path() -> Path:
    """Return the config file path."""
    return CONFIG_FILE


def ensure_config_dir() -> None:
    """Ensure the config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    """Load config from file, creating default if missing.

    Returns:
        Config dict with api_keys (and whatever else the file holds)
    """
    # A deep copy, never `.copy()`: the setters below mutate the returned dict
    # in place, and a shallow copy shared its nested dicts with DEFAULT_CONFIG,
    # so `set_api_key` with no file on disk wrote the key INTO the module
    # constant and kept serving it after the file was deleted (T054 #8).
    if not CONFIG_FILE.exists():
        return copy.deepcopy(DEFAULT_CONFIG)

    _tighten_permissions()
    with open(CONFIG_FILE) as f:
        config = yaml.safe_load(f) or {}
    if not isinstance(config, dict):
        raise ValueError(
            f"{CONFIG_FILE}: the top level must be a mapping, got {type(config).__name__}"
        )

    return _merge(copy.deepcopy(DEFAULT_CONFIG), config)


def _tighten_permissions() -> None:
    """Make an existing config file 0600, warning once when it was looser.

    It holds API keys; an older ``save_config`` wrote it with the default
    mode (0644 — world-readable, T088 config 2)."""
    import stat
    import warnings

    mode = stat.S_IMODE(CONFIG_FILE.stat().st_mode)
    if mode & _LOOSE_BITS:
        os.chmod(CONFIG_FILE, 0o600)
        warnings.warn(
            f"{CONFIG_FILE} was readable by other users (mode {mode:o}); "
            "tightened to 600",
            stacklevel=3,
        )


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """``override`` onto ``base``, recursing through nested dicts so a partial
    ``providers:`` block adds to the defaults instead of replacing the whole
    sub-dict (a file naming only anthropic used to drop openai's default model)."""
    for key, value in override.items():
        if value is None and isinstance(base.get(key), dict):
            # ``api_keys:`` with nothing under it — what deleting the last key
            # by hand leaves — means "none", not "replace the dict with null"
            # (every reader did ``.get`` on it and raised, T088 config 1).
            continue
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def save_config(config: dict[str, Any]) -> None:
    """Save config to file.

    Args:
        config: Config dict to save
    """
    ensure_config_dir()
    os.chmod(CONFIG_DIR, 0o700)
    # Created 0600 (never world-readable for an instant), and tightened if it
    # already existed with a looser mode.
    fd = os.open(CONFIG_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.chmod(CONFIG_FILE, 0o600)
    with os.fdopen(fd, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False)


def get_config() -> dict[str, Any]:
    """Get the current config.

    Returns:
        Config dict
    """
    return load_config()


def get_api_key(provider: str) -> Optional[str]:
    """Get API key for a provider.

    Checks in order:
    1. Provider-specific environment variables (e.g., ANTHROPIC_API_KEY)
    2. Generic alienbio env var (e.g., ALIENBIO_ANTHROPIC_API_KEY)
    3. Config file

    Args:
        provider: Provider name (anthropic, openai, google, etc.)

    Returns:
        API key string or None if not found
    """
    # Check provider-specific env vars first
    env_vars = PROVIDER_ENV_VARS.get(provider, [])
    for env_var in env_vars:
        key = os.environ.get(env_var)
        if key:
            return key

    # Check generic alienbio env var
    generic_env = f"{ENV_PREFIX}{provider.upper()}_API_KEY"
    key = os.environ.get(generic_env)
    if key:
        return key

    # Fall back to config file
    return _api_keys(load_config()).get(provider)


def _api_keys(config: dict[str, Any]) -> dict[str, Any]:
    """The ``api_keys`` mapping, refusing a non-mapping with the file named."""
    keys = config.get("api_keys") or {}
    if not isinstance(keys, dict):
        raise ValueError(f"{CONFIG_FILE}: api_keys must be a mapping, got {type(keys).__name__}")
    return keys


def set_api_key(provider: str, key: str) -> None:
    """Set API key for a provider in config file.

    Args:
        provider: Provider name
        key: API key value
    """
    config = load_config()
    config["api_keys"] = _api_keys(config)
    config["api_keys"][provider] = key
    save_config(config)


def remove_api_key(provider: str) -> bool:
    """Remove API key for a provider from config file.

    Args:
        provider: Provider name

    Returns:
        True if key was removed, False if not found
    """
    config = load_config()
    if provider in _api_keys(config):
        del config["api_keys"][provider]
        save_config(config)
        return True
    return False


def list_providers() -> list[str]:
    """List all providers with API keys configured.

    Returns:
        List of provider names
    """
    config = load_config()
    providers = set(_api_keys(config).keys())

    # Also check env vars
    for provider, env_vars in PROVIDER_ENV_VARS.items():
        for env_var in env_vars:
            if os.environ.get(env_var):
                providers.add(provider)
                break

    return sorted(providers)


def check_api_key(provider: str) -> tuple[bool, str]:
    """Check an API key by making a minimal API call — a BILLED one for
    anthropic (one ``messages.create``, ``max_tokens=1``).

    Named ``check_``, not ``test_``: a test module importing it by name would
    have pytest collect and run it against the real key (T088 config 4).

    Args:
        provider: Provider name

    Returns:
        Tuple of (success, message)
    """
    key = get_api_key(provider)
    if not key:
        return False, f"No API key found for {provider}"

    if provider == "anthropic":
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=key)
            # Make a minimal API call
            from alienbio.suite.llm_agent import PINNED_MODEL

            client.messages.create(
                model=PINNED_MODEL,
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}]
            )
            return True, "API key is valid"
        except ImportError:
            return False, "anthropic package not installed"
        except Exception as e:
            return False, f"API key test failed: {e}"

    elif provider == "openai":
        try:
            import openai  # type: ignore[import-not-found]
            client = openai.OpenAI(api_key=key)
            # Make a minimal API call
            client.models.list()
            return True, "API key is valid"
        except ImportError:
            return False, "openai package not installed"
        except Exception as e:
            return False, f"API key test failed: {e}"

    else:
        return False, f"API key testing not implemented for {provider}"
