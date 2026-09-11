"""API key and configuration management for alienbio.

This module provides configuration management for LLM providers:
- Config file at ~/.config/alienbio/config.yaml
- API key storage and retrieval (env vars take precedence)
- Default agent and model settings per provider

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
    "default_agent": None,
    "providers": {
        "anthropic": {
            "default_model": "claude-sonnet-5",
        },
        "openai": {
            "default_model": "gpt-4o",
        },
    },
}


def get_config_path() -> Path:
    """Return the config file path."""
    return CONFIG_FILE


def ensure_config_dir() -> None:
    """Ensure the config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    """Load config from file, creating default if missing.

    Returns:
        Config dict with api_keys, default_agent, providers
    """
    # A deep copy, never `.copy()`: the setters below mutate the returned dict
    # in place, and a shallow copy shared its nested dicts with DEFAULT_CONFIG,
    # so `set_api_key` with no file on disk wrote the key INTO the module
    # constant and kept serving it after the file was deleted (T054 #8).
    if not CONFIG_FILE.exists():
        return copy.deepcopy(DEFAULT_CONFIG)

    with open(CONFIG_FILE) as f:
        config = yaml.safe_load(f) or {}

    return _merge(copy.deepcopy(DEFAULT_CONFIG), config)


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """``override`` onto ``base``, recursing through nested dicts so a partial
    ``providers:`` block adds to the defaults instead of replacing the whole
    sub-dict (a file naming only anthropic used to drop openai's default model)."""
    for key, value in override.items():
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
    with open(CONFIG_FILE, "w") as f:
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
    config = load_config()
    return config.get("api_keys", {}).get(provider)


def set_api_key(provider: str, key: str) -> None:
    """Set API key for a provider in config file.

    Args:
        provider: Provider name
        key: API key value
    """
    config = load_config()
    if "api_keys" not in config:
        config["api_keys"] = {}
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
    if provider in config.get("api_keys", {}):
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
    providers = set(config.get("api_keys", {}).keys())

    # Also check env vars
    for provider, env_vars in PROVIDER_ENV_VARS.items():
        for env_var in env_vars:
            if os.environ.get(env_var):
                providers.add(provider)
                break

    return sorted(providers)


def get_default_agent() -> Optional[str]:
    """Get the default agent provider.

    Returns:
        Default provider name or None
    """
    config = load_config()
    return config.get("default_agent")


def set_default_agent(provider: str) -> None:
    """Set the default agent provider.

    Args:
        provider: Provider name
    """
    config = load_config()
    config["default_agent"] = provider
    save_config(config)


def get_default_model(provider: str) -> Optional[str]:
    """Get the default model for a provider.

    Args:
        provider: Provider name

    Returns:
        Default model name or None
    """
    config = load_config()
    return config.get("providers", {}).get(provider, {}).get("default_model")


def set_default_model(provider: str, model: str) -> None:
    """Set the default model for a provider.

    Args:
        provider: Provider name
        model: Model name
    """
    config = load_config()
    if "providers" not in config:
        config["providers"] = {}
    if provider not in config["providers"]:
        config["providers"][provider] = {}
    config["providers"][provider]["default_model"] = model
    save_config(config)


def test_api_key(provider: str) -> tuple[bool, str]:
    """Test if an API key is valid by making a minimal API call.

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
            client.messages.create(
                model=get_default_model(provider) or "claude-sonnet-5",
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
