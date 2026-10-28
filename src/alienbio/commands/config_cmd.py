"""show / set the framework configuration: provider API keys.

Usage:
    bio config set-key <provider> <key>      Set API key for provider
    bio config list-keys                     List configured providers
    bio config test-key <provider>           Check the key with one live call (billed for anthropic)
    bio config show                          Show current config (keys masked)

Examples:
    bio config set-key anthropic sk-ant-api03-...
    bio config list-keys
    bio config test-key anthropic

The model a run uses comes from its spec or ``PINNED_MODEL``; there is no
default agent or model setting.
"""

from __future__ import annotations

import argparse


def _parser() -> argparse.ArgumentParser:
    """One argparse parser, as every ``bio`` verb has (``--help`` exits 0)."""
    parser = argparse.ArgumentParser(prog="bio config", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    verbs = parser.add_subparsers(dest="verb", metavar="set-key|list-keys|test-key|show")
    set_key = verbs.add_parser("set-key", help="store a provider's API key in the config file")
    set_key.add_argument("provider")
    set_key.add_argument("key")
    verbs.add_parser("list-keys", help="list configured providers")
    test_key = verbs.add_parser("test-key", help="check a key with one live call")
    test_key.add_argument("provider")
    verbs.add_parser("show", help="show the config, keys masked")
    return parser


def config_command(args: list[str], verbose: bool = False) -> int:
    """Execute ``bio config <verb> ...``.

    Returns:
        Exit code (0 success, 1 a failed key check or bad config, 2 bad usage).
    """
    parser = _parser()
    try:
        ns = parser.parse_args(args)
    except SystemExit as exc:  # argparse already printed usage (or help)
        return int(exc.code or 0)
    if ns.verb is None:
        parser.print_usage()
        return 2
    try:
        if ns.verb == "set-key":
            return _set_key(ns.provider, ns.key, verbose)
        if ns.verb == "list-keys":
            return _list_keys(verbose)
        if ns.verb == "test-key":
            return _test_key(ns.provider, verbose)
        return _show_config(verbose)
    except ValueError as exc:  # an unreadable config file names itself
        print(f"Error: {exc}")
        return 1


def _mask(key: str) -> str:
    return key[:8] + "..." if len(key) > 11 else "***"


def _set_key(provider: str, key: str, verbose: bool) -> int:
    """Set API key for a provider."""
    from alienbio import config

    config.set_api_key(provider, key)
    print(f"Set API key for {provider}: {_mask(key)}")
    if verbose:
        print(f"Config file: {config.get_config_path()}")
    return 0


def _list_keys(verbose: bool) -> int:
    """List providers with API keys configured."""
    from alienbio import config

    del verbose
    providers = config.list_providers()
    if not providers:
        print("No API keys configured.")
        print("Use: bio config set-key <provider> <key>")
        return 0

    print("Configured providers:")
    for provider in providers:
        key = config.get_api_key(provider)
        if key:
            source = "env" if _is_from_env(provider) else "config"
            print(f"  {provider}: {_mask(key)} ({source})")
        else:
            print(f"  {provider}: (configured)")
    return 0


def _is_from_env(provider: str) -> bool:
    """Check if provider's key comes from environment variable."""
    import os
    from alienbio.config import PROVIDER_ENV_VARS, ENV_PREFIX

    for env_var in PROVIDER_ENV_VARS.get(provider, []):
        if os.environ.get(env_var):
            return True
    return bool(os.environ.get(f"{ENV_PREFIX}{provider.upper()}_API_KEY"))


def _test_key(provider: str, verbose: bool) -> int:
    """Check an API key with one live call."""
    from alienbio import config

    del verbose
    print(f"Testing API key for {provider}...")
    success, message = config.check_api_key(provider)
    print(f"{'✓' if success else '✗'} {message}")
    return 0 if success else 1


def _show_config(verbose: bool) -> int:
    """Show current configuration."""
    from alienbio import config
    import yaml

    del verbose
    cfg = config.get_config()
    display_cfg = dict(cfg)
    if isinstance(display_cfg.get("api_keys"), dict):
        display_cfg["api_keys"] = {k: _mask(str(v)) for k, v in display_cfg["api_keys"].items()}

    print(f"Config file: {config.get_config_path()}")
    print()
    print(yaml.safe_dump(display_cfg, default_flow_style=False))
    return 0
