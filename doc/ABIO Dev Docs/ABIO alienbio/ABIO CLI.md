---
description: "`cli` + `commands`: the `bio` front door — `main(argv)`, the help it generates from the `COMMANDS` registry, how it hands everything after the verb to that verb's own parser, and the exit-code contract across the four verbs. Source: `src/alienbio/cli.py`, `src/alienbio/commands/__init__.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO CLI](ha://p/ABIO%20CLI) 
# ABIO CLI
The page for the `bio` entry point and its verb table: how one argument picks a command, what each command is handed, which parser reads the rest, and what each exit code means.

![ABIO CLI](ABIO%20CLI.svg) 
*Two parsers per call* is the topic behind the `REMAINDER` edge: the front door parses only what comes before the verb, and the verb's own parser (or hand loop) reads everything after; *Help and verbose* governs the ‡ on `config` and `test-matrix`, the two verbs whose `--help` is not argparse's.

`cli.py` is a shim and holds no logic of a verb; `commands/__init__.py` holds the registry it dispatches through. The four verbs each have a page: `suite` on [ABIO SuiteCmd](ABIO%20SuiteCmd.md), `config` on [ABIO Config](ABIO%20Config.md), `test-matrix` on [ABIO Capabilities](ABIO%20Capabilities.md), `report` on [ABIO Report](ABIO%20Report.md). `pyproject.toml` installs `bio = "alienbio.cli:main"`; the published command reference is [ABIO Commands](../../ABIO%20Ref/ABIO%20Commands.md) and the subsystem view [ABIO-Operator-Surface](../../ABIO%20Architecture/ABIO-Operator-Surface.md).



## cli Interface
One public function; the module also runs it under `__main__`.

| cli | |
| --- | --- |
| [main](#^main) | Parse the front door, run one verb |
| [_summary](#^summary) | A verb's one-line help |

**main**`(argv: list[str] | None = None) -> int`
    Builds an `argparse` parser with an optional `command` positional, an `args` `REMAINDER`, `--version` and `-v/--verbose`, its epilog listing every registered verb with its summary and three example calls. With no command, prints the help and returns 1. A registered command is called as `COMMANDS[command](args, verbose=verbose)` and its return is the exit code; an unknown one prints `bio: unknown command …` to stderr and returns 2. `--version` and `--help` exit through argparse (`SystemExit(0)`). ^main

**_summary**`(fn: object) -> str`
    The first line of the docstring of the module that defines `fn`, stripped; `""` when it has none. This is why each command module's docstring opens with its usage sentence. ^summary



## commands Interface
`alienbio.commands`: the registry and the four command functions, re-exported. Every command has the signature `(args: list[str], verbose: bool = False) -> int`.

| commands | |
| --- | --- |
| [COMMANDS](#^commands) | Verb name to command function |

**COMMANDS**`: dict[str, Callable[[list[str], bool], int]]`
    `config` → `config_command`, `report` → `report_command`, `suite` → `suite_command`, `test-matrix` → `test_matrix_command`. The front door's epilog, its `command` help line and the dispatch all read this dict, so a verb exists exactly when it has an entry. ^commands




# CLI Semantics

## Two parsers per call
The front door's `args` is an `argparse.REMAINDER`, so every token after the verb, flags included, goes to the verb untouched. Options the front door itself knows (`-v`, `--version`, `--help`) are read only before the verb; `bio -v suite run x.yaml` sets verbose through the front door, `bio suite run x.yaml -v` through the verb's subparser. A flag between the verb and its subverb belongs to neither: `bio suite -v run x.yaml` fails in the suite parser with `unrecognized arguments: -v`, exit 2.

| Verb | Parser | `--help` | Front-door `-v` |
| --- | --- | --- | --- |
| `suite` | `argparse`, one subparser per subverb | argparse, exit 0 | ORed with the subverb's `-v` |
| `report` | `argparse` | argparse, exit 0 | ignored (`del verbose`) |
| `test-matrix` | hand check: only `--markdown` and `--check` | prints the docstring, exit 2 ‡ | ignored |
| `config` | hand dispatch on the first token | `Unknown subcommand: --help`, exit 1 ‡ | passed, read by `set-key` only |



## Exit codes
0 is success. 1 is a reported user error or a failed gate: a refused preflight on `--dry`, a missing manifest, a failed `test-matrix --check`, a report whose own rows show a failure, an unknown `config` subcommand, and also the front door with no command at all (it printed the help). 2 is bad usage: an unknown verb, and anything argparse rejects. An exception no command catches ends the process with a traceback and Python's exit 1, indistinguishable by code from a reported error.



## Help and verbose
The module docstring and the epilog say each command takes `--help`. Two do not: `config` treats `--help` as an unknown subcommand and exits 1, and `test-matrix` prints its docstring to stderr and exits 2 because it refuses any token but its two flags. [ABIO-Operator-Surface](../../ABIO%20Architecture/ABIO-Operator-Surface.md) states the same claim (`--help` on every verb).



## Outside the CLI
The `justfile`'s `run` and `view-report` recipes call `python -m alienbio`, and the package has no `__main__.py`, so both fail with `No module named alienbio.__main__`; `view-report` is not a verb either. `just report` calls `bio report --open` and works.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `038c399` (read from a `git archive` export, a concurrent worker editing `src/`), with `pyproject.toml` and the `justfile` read at the same commit. Checked locally against the export: `bio config --help` (exit 1), `bio test-matrix --help` (exit 2), `bio suite -v run` (exit 2), `python -m alienbio` failing. `cli.py` and `commands/__init__.py` share this page because the registry is the front door's only data; the four verb modules are on the pages of the modules they front. Findings filed on T088.
