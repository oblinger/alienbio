---
description: "`config` + `commands/config_cmd`: API-key resolution (environment first, then `~/.config/alienbio/config.yaml`), the config file and its defaults, the key test, and the `bio config` verb that fronts them. Source: `src/alienbio/config.py`, `src/alienbio/commands/config_cmd.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO Config](ha://p/ABIO%20Config) 
# ABIO Config
The page for where alienbio gets an API key: the lookup order, the YAML file and how it merges onto the defaults, the file's mode, and the `bio config` subcommands.

![ABIO Config](ABIO%20Config.svg) 
*Key resolution* is the topic behind the three-step chain into `get_api_key`, the one function on this page the instrument calls. The figure predates T088's config round and still draws the removed `default_agent` / `default_model` settings.

`config.py` is module-level functions over one YAML file; `config_cmd.py` is the `bio config` verb, one `argparse` parser over those functions, kept on this page because it holds no logic of its own. The instrument's one reader is the real-model agent: `llm_agent.default_anthropic_llm_fn` and `fetch_models_snapshot` call `get_api_key("anthropic")` ([ABIO LLMAgent](../ABIO%20suite/ABIO%20LLMAgent.md)). On this machine the key lives in the macOS Keychain and reaches the process as `ANTHROPIC_API_KEY` through `~/.zshrc`, so the file is normally empty of keys. The front door is [ABIO CLI](ABIO%20CLI.md); the subsystem view is [ABIO-Operator-Surface](../../ABIO%20Architecture/ABIO-Operator-Surface.md).



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
| [check_api_key](#^check-api-key) | Try the key against the provider |

**CONFIG_FILE**`: Path`
    `CONFIG_DIR / "config.yaml"`, `CONFIG_DIR = ~/.config/alienbio`; `get_config_path()` returns it. No environment variable overrides it; tests patch the constants. ^config-file

**PROVIDER_ENV_VARS**`: dict[str, list[str]]`
    `anthropic`: `ANTHROPIC_API_KEY`, `ALIENBIO_ANTHROPIC_API_KEY`; `openai` and `google` the same shape. ^provider-env-vars

**DEFAULT_CONFIG**`: dict`
    `{"api_keys": {}}`. Never mutated: every reader gets a deep copy. ^default-config

**load_config**`() -> dict`
    A deep copy of the defaults when the file is missing; otherwise the file's YAML (an empty file reads as `{}`) merged onto a deep copy, recursing where both sides hold a dict, so a nested block adds to the defaults (T054 #8). A null where the default holds a dict reads as the default (§ [The file](#the-file)); a top level that is not a mapping raises `ValueError` naming the file. An existing file readable by group or other is chmod-ed to 0600 with a `UserWarning`. ^load-config

**save_config**`(config: dict) -> None`
    Creates the directory (chmod 0700) and writes the dict with `yaml.safe_dump`, replacing the file, which is created 0600 and tightened to 0600 if it existed looser. ^save-config

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

**check_api_key**`(provider: str) -> tuple[bool, str]`
    Resolves the key, then for `anthropic` sends one `messages.create` with `max_tokens=1` to `PINNED_MODEL` (a real, billed request of a few tokens), for `openai` lists models; any exception becomes `(False, message)`, a missing SDK `(False, "… not installed")`, any other provider `(False, "… not implemented")`. Named `check_`, not `test_` (it was `test_api_key`): pytest would collect a `test_` name a test module imported. ^check-api-key



## config_cmd Interface
`bio config <subcommand> [args]`: one `argparse` parser. `--help` prints usage and exits 0; no subcommand exits 2, an unknown one or a missing argument exits 2 (argparse); a config file that will not read exits 1 with `Error: …`.

| config_cmd | |
| --- | --- |
| [config_command](#^config-command) | Dispatch one subcommand |
| [set-key](#^set-key) | Store a key |
| [list-keys](#^list-keys) | Providers, masked keys, sources |
| [test-key](#^test-key) | `check_api_key`, ✓ or ✗ |
| [show](#^show) | The merged config, keys masked |

**config_command**`(args: list[str], verbose: bool = False) -> int`
    Parses with `argparse` and dispatches; the exit codes are the section's. ^config-command

**set-key**` <provider> <key>`
    `set_api_key`, then prints the key's first eight characters (`***` for a key of eleven or fewer); with `-v` also the file path. The key is an argument, so it lands in shell history. ^set-key

**list-keys**
    Each provider from `list_providers` with its masked key and `env` or `config` as source. ^list-keys

**test-key**` <provider>`
    Runs `check_api_key` and prints `✓` or `✗` with its message; exit 0 or 1. On `anthropic` this is a billed call. ^test-key

**show**
    The file path and the merged config as YAML, each `api_keys` value masked as `set-key` masks it. ^show




# Config Semantics

## Key resolution
`get_api_key` reads the environment before the file, and an empty variable counts as unset. On this machine `ANTHROPIC_API_KEY` is exported from the Keychain by `~/.zshrc`, so the file is the fallback for a clean shell; a process started before a key rotation keeps the old key in its environment, which wins over a newer key in the file. No `.env` file is read anywhere, a rule set after the 2026-07-16 secret-scan incident.



## The file
YAML whose one known key is `api_keys` (provider → key); other keys are kept and ignored. Merging recurses where both the default and the file hold a dict, and a null where the default holds a dict is skipped: `api_keys:` with nothing under it (what deleting the last key by hand leaves) reads as no keys (it made every reader raise until T088). A non-mapping `api_keys` or top level raises `ValueError` naming the file. The file holds keys, so it is written 0600 in a 0700 folder, and a looser existing file is tightened on read with a warning.



## No default agent or model
The model a run uses comes from the spec or `suite.llm_agent.PINNED_MODEL`. The `default_agent` and `providers.<p>.default_model` settings (and `set-default-agent`) were read by nothing that runs an experiment, so T088's config round removed them; a file still carrying them loads and ignores them.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `038c399` (read from a `git archive` export, a concurrent worker editing `src/`). Checked locally against the export, with the config paths pointed at a temporary directory and the key variables unset: an empty `api_keys:` breaking `get_api_key`, `list_providers` and `remove_api_key`; a list-valued file breaking `load_config`; a written file's mode 0644; `bio config --help` exiting 1. `test-key` was not run (it is a billed call). Readers of each setting found by grep over `src/`. Findings filed on T088.
- 2026-10-28 — T088 config round: argparse parser (`--help` exits 0), an empty `api_keys:` reads as none, the file 0600 / folder 0700 and tightened on read, `default_agent` / `default_model` / `set-default-agent` removed, `test_api_key` renamed `check_api_key` and pinged at `PINNED_MODEL`.
