---
description: "`cli` + `commands`: the `bio` front door — `main(argv)`, the help it generates from the `COMMANDS` registry, how it hands everything after the verb to that verb's own parser, and the exit-code contract across the four verbs. Source: `src/alienbio/cli.py`, `src/alienbio/commands/__init__.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO CLI](ha://p/ABIO%20CLI) 
# ABIO CLI
The page for the `bio` entry point and its verb table: how one argument picks a command, what each command is handed, which parser reads the rest, and what each exit code means.

![ABIO CLI](ABIO%20CLI.svg) 
*Two parsers per call* is the topic behind the `REMAINDER` edge: the front door parses only what comes before the verb, and the verb's own parser (or hand loop) reads everything after; *Help and verbose* governs which verbs read the front door's `-v` (every verb's `--help` is argparse's).

`cli.py` is a shim and holds no logic of a verb; `commands/__init__.py` holds the registry it dispatches through. The four verbs each have a page: `suite` on [ABIO SuiteCmd](ABIO%20SuiteCmd.md), `config` on [ABIO Config](ABIO%20Config.md), `test-matrix` on [ABIO Capabilities](ABIO%20Capabilities.md), `report` on [ABIO Report](ABIO%20Report.md). `pyproject.toml` installs `bio = "alienbio.cli:main"`; the published command reference is [ABIO Commands](../../ABIO%20Ref/ABIO%20Commands.md) and the subsystem view [ABIO-Operator-Surface](../../ABIO%20Architecture/ABIO-Operator-Surface.md).



## cli Interface
One public function; the module also runs it under `__main__`.

| cli | |
| --- | --- |
| [main](#^main) | Parse the front door, run one verb |
| [_summary](#^summary) | A verb's one-line help |

**main**`(argv: list[str] | None = None) -> int`
    Builds an `argparse` parser with an optional `command` positional, an `args` `REMAINDER`, `--version` and `-v/--verbose`, its epilog listing every registered verb with its summary and three example calls. With no command, prints the help and returns 2 (usage). A registered command is called as `COMMANDS[command](args, verbose=verbose)` and its return is the exit code; an unknown one prints `bio: unknown command …` to stderr and returns 2. `--version` and `--help` exit through argparse (`SystemExit(0)`). ^main

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
The front door's `args` is an `argparse.REMAINDER`, so every token after the verb, flags included, goes to the verb untouched. Options the front door itself knows (`-v`, `--version`, `--help`) are read only before the verb; `bio -v suite run x.yaml` sets verbose through the front door, `bio suite run x.yaml -v` through the verb's subparser. Between `suite` and its subverb the suite parser takes `-v` itself (its own `verbose_suite` dest), so `bio suite -v run x.yaml` is verbose too; any other flag there is the suite parser's to refuse.

| Verb | Parser | `--help` | Front-door `-v` |
| --- | --- | --- | --- |
| `suite` | `argparse`, one subparser per subverb | argparse, exit 0 | ORed with the suite-level and subverb `-v` |
| `report` | `argparse` | argparse, exit 0 | ignored (`del verbose`) |
| `test-matrix` | `argparse`: `--markdown`, `--check` | argparse, exit 0 | ignored |
| `config` | `argparse`, one subparser per subverb | argparse, exit 0 | passed, read by `set-key` only |



## Exit codes
0 is success. 1 is a reported user error or a failed gate: a refused preflight on `--dry`, a missing manifest, a failed `test-matrix --check`, a report whose own rows show a failure or an unproven capability, a missing `tests/capabilities/` folder, a refused provider call on `bio suite models`. 2 is bad usage: the front door with no command (after the help), a verb with no subverb, an unknown verb, and anything argparse rejects. An exception no command catches ends the process with a traceback and Python's exit 1, indistinguishable by code from a reported error.



## Help and verbose
The module docstring and the epilog say each command takes `--help`, and each does: all four verbs build an `argparse` parser, so `--help` prints usage to stdout and exits 0 ([ABIO-Operator-Surface](../../ABIO%20Architecture/ABIO-Operator-Surface.md) states the same). The front door's `-v` reaches only `suite` (ORed with its own `-v`) and `config set-key`; `report` and `test-matrix` discard it.



## Outside the CLI
The package has no `__main__.py`; the `justfile`'s `run` recipe calls `bio` and `just report` calls `bio report --open`, so every recipe goes through the installed entry point.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `038c399` (read from a `git archive` export, a concurrent worker editing `src/`), with `pyproject.toml` and the `justfile` read at the same commit. Checked locally against the export: `bio config --help` (exit 1), `bio test-matrix --help` (exit 2), `bio suite -v run` (exit 2), `python -m alienbio` failing. `cli.py` and `commands/__init__.py` share this page because the registry is the front door's only data; the four verb modules are on the pages of the modules they front. Findings filed on T088.
- 2026-10-28 — T088 bio and operator round: every verb takes `--help` (exit 0): `config` and `test-matrix` have `argparse` parsers; a bare `bio` exits 2; the justfile's `run` calls `bio` and `view-report` is gone (no `__main__.py`, as the rest of the justfile already assumed).
- 2026-10-28 — refreshed against `0eb23e5`: the body now states the round's outcome — every verb's `--help` is argparse's, `bio suite -v run` is verbose, a bare `bio` exits 2, the justfile's `run` calls `bio` (`13298f0`); the figure's ‡ marks removed.
