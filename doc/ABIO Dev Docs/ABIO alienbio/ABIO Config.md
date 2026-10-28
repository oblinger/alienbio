---
description: "`config` + `commands/config_cmd`: API-key resolution (environment first, then `~/.config/alienbio/config.yaml`), the config file and its defaults, the key test, and the `bio config` verb that fronts them. Source: `src/alienbio/config.py`, `src/alienbio/commands/config_cmd.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO Config](ha://p/ABIO%20Config) 
# ABIO Config
The page for where alienbio gets an API key and its provider defaults: the lookup order, the YAML file and how it merges onto the defaults, what reads each setting, and the `bio config` subcommands.

![ABIO Config](ABIO%20Config.svg) 
*Key resolution* is the topic behind the three-step chain into `get_api_key`, the one function on this page the instrument calls; *What reads the defaults* governs the ‡ on `default_agent` and `default_model`, which nothing that runs an experiment reads.

`config.py` is module-level functions over one YAML file; `config_cmd.py` is the `bio config` verb, a hand dispatch over those functions, kept on this page because it holds no logic of its own. The instrument's one reader is the real-model agent: `llm_agent.default_anthropic_llm_fn` and `fetch_models_snapshot` call `get_api_key("anthropic")` ([ABIO LLMAgent](../ABIO%20suite/ABIO%20LLMAgent.md)). On this machine the key lives in the macOS Keychain and reaches the process as `ANTHROPIC_API_KEY` through `~/.zshrc`, so the file is normally empty of keys. The front door is [ABIO CLI](ABIO%20CLI.md); the subsystem view is [ABIO-Operator-Surface](../../ABIO%20Architecture/ABIO-Operator-Surface.md).



## config Interface
Every function re-reads the file on each call; nothing is cached. The paths are module constants fixed at import from `Path.home()`.

| config | |
| --- | --- |
| [CONFIG_FILE](#^config-file) | `~/.config/alienbio/config.yaml` |
| [PROVIDER_ENV_VARS](#^provider-env-vars) | Environment variables per provider |
| [DEFAULT_CONFIG](#^default-config) | The defaults the file merges onto |
| [load_config](#^load-config) | Defaults deep-merged with the file |
| [save_config](#^save-config) | Write the whole dict back |
| [get_config](#^get-config) | Alias of `load_config` |
| [get_api_key](#^get-api-key) | Environment, then the file |
| [set_api_key](#^set-api-key) | Store a key in the file |
| [remove_api_key](#^remove-api-key) | Delete a stored key |
| [list_providers](#^list-providers) | Providers with a key anywhere |
| [get_default_agent](#^get-default-agent) | The `default_agent` setting |
| [set_default_agent](#^set-default-agent) | Set it |
| [get_default_model](#^get-default-model) | A provider's `default_model` |
| [set_default_model](#^set-default-model) | Set it |
| [test_api_key](#^test-api-key) | Try the key against the provider |

**CONFIG_FILE**`: Path`
    `CONFIG_DIR / "config.yaml"`, `CONFIG_DIR = ~/.config/alienbio`; `get_config_path()` returns it. No environment variable overrides it; tests patch the constants. ^config-file

**PROVIDER_ENV_VARS**`: dict[str, list[str]]`
    `anthropic`: `ANTHROPIC_API_KEY`, `ALIENBIO_ANTHROPIC_API_KEY`; `openai` and `google` the same shape. ^provider-env-vars

**DEFAULT_CONFIG**`: dict`
    `api_keys: {}`, `default_agent: None`, `providers.anthropic.default_model: "claude-sonnet-5"`, `providers.openai.default_model: "gpt-4o"`. Never mutated: every reader gets a deep copy. ^default-config

**load_config**`() -> dict`
    A deep copy of the defaults when the file is missing; otherwise the file's YAML (an empty file reads as `{}`) merged onto a deep copy, recursing where both sides hold a dict, so a file naming only one provider keeps the other's default (T054 #8). A file whose top level is not a mapping raises `AttributeError`; a key set to null replaces the default with `None` (§ [The file](#the-file)). ^load-config

**save_config**`(config: dict) -> None`
    Creates the directory and writes the dict with `yaml.safe_dump`, replacing the file. The file gets the process's default mode (0644 here), so a stored key is readable by any local user. ^save-config

**get_config**`() -> dict`
    `load_config()`. ^get-config

**get_api_key**`(provider: str) -> Optional[str]`
    The first non-empty of: the provider's `PROVIDER_ENV_VARS` in order, `ALIENBIO_<PROVIDER>_API_KEY`, then `api_keys[provider]` in the file; `None` when none is set. For the three listed providers the second step repeats a name already in the first. § [Key resolution](#key-resolution). ^get-api-key

**set_api_key**`(provider: str, key: str) -> None`
    Loads, sets `api_keys[provider]`, saves the whole merged dict, defaults included. ^set-api-key

**remove_api_key**`(provider: str) -> bool`
    Deletes `api_keys[provider]` from the file and saves; `False` when the file holds none. An environment key is not touched and still wins afterwards. ^remove-api-key

**list_providers**`() -> list[str]`
    Sorted union of the providers with a key in the file and those with a `PROVIDER_ENV_VARS` variable set. The generic `ALIENBIO_<P>_API_KEY` of an unlisted provider is not counted, though `get_api_key` honours it. ^list-providers

**get_default_agent**`() -> Optional[str]`
    The file's `default_agent`. Read by `bio config list-keys` only. ^get-default-agent

**set_default_agent**`(provider: str) -> None`
    Writes `default_agent`. ^set-default-agent

**get_default_model**`(provider: str) -> Optional[str]`
    `providers[provider].default_model`. Read by `test_api_key` only. ^get-default-model

**set_default_model**`(provider: str, model: str) -> None`
    Writes it, creating the provider's block. No `bio config` subcommand calls it. ^set-default-model

**test_api_key**`(provider: str) -> tuple[bool, str]`
    Resolves the key, then for `anthropic` sends one `messages.create` with `max_tokens=1` to the configured default model (a real, billed request of a few tokens), for `openai` lists models; any exception becomes `(False, message)`, a missing SDK `(False, "… not installed")`, any other provider `(False, "… not implemented")`. Its `test_` prefix means a test module that imports it by name would have pytest collect and run it. ^test-api-key



## config_cmd Interface
`bio config <subcommand> [args]`: a dispatch on the first token, no argparse. Every subcommand prints and returns 0 on success, 1 on a usage error.

| config_cmd | |
| --- | --- |
| [config_command](#^config-command) | Dispatch one subcommand |
| [set-key](#^set-key) | Store a key |
| [list-keys](#^list-keys) | Providers, masked keys, sources |
| [set-default-agent](#^set-default-agent-cmd) | Store the default provider |
| [test-key](#^test-key) | `test_api_key`, ✓ or ✗ |
| [show](#^show) | The merged config, keys masked |

**config_command**`(args: list[str], verbose: bool = False) -> int`
    No arguments prints the subcommand list and returns 1; an unknown first token (including `--help`) prints `Unknown subcommand: …` and returns 1. ^config-command

**set-key**` <provider> <key>`
    `set_api_key`, then prints the key's first eight characters (`***` for a key of eleven or fewer); with `-v` also the file path. The key is an argument, so it lands in shell history. ^set-key

**list-keys**
    Each provider from `list_providers` with its masked key and `env` or `config` as source, then the default agent. ^list-keys

**set-default-agent**` <provider>`
    Warns when the provider has no key, then stores it. ^set-default-agent-cmd

**test-key**` <provider>`
    Runs `test_api_key` and prints `✓` or `✗` with its message; exit 0 or 1. On `anthropic` this is a billed call. ^test-key

**show**
    The file path and the merged config as YAML, each `api_keys` value masked as `set-key` masks it. ^show




# Config Semantics

## Key resolution
`get_api_key` reads the environment before the file, and an empty variable counts as unset. On this machine `ANTHROPIC_API_KEY` is exported from the Keychain by `~/.zshrc`, so the file is the fallback for a clean shell; a process started before a key rotation keeps the old key in its environment, which wins over a newer key in the file. No `.env` file is read anywhere, a rule set after the 2026-07-16 secret-scan incident.



## The file
YAML with three top-level keys, each optional: `api_keys` (provider → key), `default_agent`, `providers` (provider → `default_model`). Merging recurses only where both the default and the file hold a dict, so a key the file sets to null wins: a file containing `api_keys:` with nothing under it (what deleting the last key by hand leaves) makes `api_keys` `None`, after which `get_api_key` raises `AttributeError` once the environment is empty, `list_providers` raises, and `remove_api_key` raises `TypeError`. A file whose top level is a list or scalar fails in `_merge`.



## What reads the defaults
`default_agent` is printed by `list-keys` and set by `set-default-agent`; no runner, agent factory or spec reads it. `providers.<p>.default_model` is read by `test_api_key` alone; the model a run uses comes from the spec or `suite.llm_agent.PINNED_MODEL`, so changing the configured default changes which model `test-key` pings and nothing else. Both settings look like they configure the instrument and do not.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `038c399` (read from a `git archive` export, a concurrent worker editing `src/`). Checked locally against the export, with the config paths pointed at a temporary directory and the key variables unset: an empty `api_keys:` breaking `get_api_key`, `list_providers` and `remove_api_key`; a list-valued file breaking `load_config`; a written file's mode 0644; `bio config --help` exiting 1. `test-key` was not run (it is a billed call). Readers of each setting found by grep over `src/`. Findings filed on T088.
