"""Config command: manage API keys and settings.

Usage:
    bio config set-key <provider> <key>      Set API key for provider
    bio config list-keys                     List configured providers
    bio config set-default-agent <provider>  Set default agent provider
    bio config test-key <provider>           Test if API key works
    bio config show                          Show current config

Examples:
    bio config set-key anthropic sk-ant-api03-...
    bio config list-keys
    bio config set-default-agent anthropic
    bio config test-key anthropic
"""

from typing import Any


def config_command(args: list[str], verbose: bool = False) -> int:
    """Execute config subcommand.

    Args:
        args: Command arguments [subcommand, ...]
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success)
    """
    from alienbio import config

    if not args:
        print("Usage: bio config <subcommand>")
        print("Subcommands: set-key, list-keys, set-default-agent, test-key, show")
        return 1

    subcommand = args[0]
    subargs = args[1:]

    if subcommand == "set-key":
        return _set_key(subargs, verbose)
    elif subcommand == "list-keys":
        return _list_keys(verbose)
    elif subcommand == "set-default-agent":
        return _set_default_agent(subargs, verbose)
    elif subcommand == "test-key":
        return _test_key(subargs, verbose)
    elif subcommand == "show":
        return _show_config(verbose)
    else:
        print(f"Unknown subcommand: {subcommand}")
        print("Subcommands: set-key, list-keys, set-default-agent, test-key, show")
        return 1


def _set_key(args: list[str], verbose: bool) -> int:
    """Set API key for a provider."""
    from alienbio import config

    if len(args) < 2:
        print("Usage: bio config set-key <provider> <key>")
        print("Example: bio config set-key anthropic sk-ant-...")
        return 1

    provider, key = args[0], args[1]
    config.set_api_key(provider, key)

    # Mask key for display
    masked = key[:8] + "..." if len(key) > 11 else "***"
    print(f"Set API key for {provider}: {masked}")

    if verbose:
        print(f"Config file: {config.get_config_path()}")

    return 0


def _list_keys(verbose: bool) -> int:
    """List providers with API keys configured."""
    from alienbio import config

    providers = config.list_providers()

    if not providers:
        print("No API keys configured.")
        print("Use: bio config set-key <provider> <key>")
        return 0

    print("Configured providers:")
    for provider in providers:
        key = config.get_api_key(provider)
        if key:
            masked = key[:8] + "..." if len(key) > 11 else "***"
            # Check if from env var or config file
            source = "env" if _is_from_env(provider) else "config"
            print(f"  {provider}: {masked} ({source})")
        else:
            print(f"  {provider}: (configured)")

    default = config.get_default_agent()
    if default:
        print(f"\nDefault agent: {default}")

    return 0


def _is_from_env(provider: str) -> bool:
    """Check if provider's key comes from environment variable."""
    import os
    from alienbio.config import PROVIDER_ENV_VARS, ENV_PREFIX

    env_vars = PROVIDER_ENV_VARS.get(provider, [])
    for env_var in env_vars:
        if os.environ.get(env_var):
            return True

    generic_env = f"{ENV_PREFIX}{provider.upper()}_API_KEY"
    if os.environ.get(generic_env):
        return True

    return False


def _set_default_agent(args: list[str], verbose: bool) -> int:
    """Set the default agent provider."""
    from alienbio import config

    if len(args) < 1:
        print("Usage: bio config set-default-agent <provider>")
        print("Example: bio config set-default-agent anthropic")
        return 1

    provider = args[0]

    # Check if provider has a key configured
    if not config.get_api_key(provider):
        print(f"Warning: No API key configured for {provider}")
        print(f"Use: bio config set-key {provider} <key>")

    config.set_default_agent(provider)
    print(f"Default agent set to: {provider}")

    return 0


def _test_key(args: list[str], verbose: bool) -> int:
    """Test if an API key works."""
    from alienbio import config

    if len(args) < 1:
        print("Usage: bio config test-key <provider>")
        print("Example: bio config test-key anthropic")
        return 1

    provider = args[0]
    print(f"Testing API key for {provider}...")

    success, message = config.test_api_key(provider)

    if success:
        print(f"✓ {message}")
        return 0
    else:
        print(f"✗ {message}")
        return 1


def _show_config(verbose: bool) -> int:
    """Show current configuration."""
    from alienbio import config
    import yaml

    cfg = config.get_config()

    # Mask API keys for display
    display_cfg = cfg.copy()
    if "api_keys" in display_cfg:
        display_cfg["api_keys"] = {
            k: (v[:8] + "..." if len(v) > 11 else "***")
            for k, v in display_cfg["api_keys"].items()
        }

    print(f"Config file: {config.get_config_path()}")
    print()
    print(yaml.safe_dump(display_cfg, default_flow_style=False))

    return 0
