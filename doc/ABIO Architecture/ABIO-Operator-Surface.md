---
description: "the bio CLI, the capability matrix, the one-page report, config resolution, and the gates (justfile, CI). Source: cli.py, commands/, report.py, capabilities.py, config.py, justfile, .github/workflows/ci.yml."
---
:>> [ABIO](../ABIO.md) → [ABIO Architecture](ABIO%20Architecture.md) → [ABIO-Operator-Surface](ha://p/ABIO-Operator-Surface) 
# ABIO-Operator-Surface
Thin, but it is the surface an operator reads before spending and the surface CI trusts.

![[ABIO-Operator-Surface.svg|2400]] 

`bio` is an argparse shim: the first positional selects a verb from `COMMANDS` (its help is generated from that registry) and everything after it is passed through to the command's own `argparse` parser (T057 — `-v` after the verb works, `--help` on every verb, an unknown flag is exit 2). `suite_cmd` runs `run | resume | aggregate | report | models` over `ABIO-Experiment`'s `load_spec`, `run_experiment`, `aggregate`, `render_report` and `write_key_figure`; `--dry` runs the run's own `preflight()`, prints every verdict and the cost estimate, creates nothing, and exits 1 when the run would refuse. `config_cmd` fronts `config.py`, where provider env vars win over `ALIENBIO_<PROVIDER>_API_KEY`, which wins over `~/.config/alienbio/config.yaml`; nothing reads a `.env`. `test_matrix_cmd --check` is the CI gate that refuses a built dimension without a proving test, a test claiming an unknown id, or a proving test without a docstring sentence. `bio report` runs the whole suite fresh to JUnit, pairs the 35 `DIMENSIONS` with their proving tests by an AST scan of `tests/capabilities/`, runs every example under `catalog/examples/` fresh, scans `runs/*/manifest.json`, and writes `reports/report.md` and a standalone `report.html` with each run's `key.png` as a data URI.

## Commands

| COMMAND | Flags | Calls |
| --- | --- | --- |
| `bio suite run <spec>` | `--out DIR` `--dry` `-v` | `load_spec` → `preflight` → `run_experiment` (or the dry printout) |
| `bio suite resume <DIR>` | — | `spec_from_dict(manifest)` → `run_experiment(resume=True)` |
| `bio suite aggregate <DIR>` | — | `aggregate` → `map.json` / `map.csv` |
| `bio suite report <DIR>` | — | `aggregate` → `render_report` → `write_key_figure` |
| `bio suite models` | — | `fetch_models_snapshot` → `models_snapshot.json` |
| `bio config set-key \| list-keys \| test-key \| show` | — | `config.py`; `test-key` makes one live call |
| `bio test-matrix` | `--markdown` `--check` | `capabilities.render_*`, `check`, `unknown_ids`, `check_phrases` |
| `bio report` | `--open` `--no-examples` `--junit PATH` `--out DIR` | `report.run_pytest` → `parse_junit` → `build` → `render_markdown` / `render_html` |

Exit codes: 0, 1 for a reported user error or gate failure, 2 for bad usage.

## Gates

| GATE | Steps |
| --- | --- |
| `justfile` | `test` (pytest) · `check` (pyright `src/`) · `report` (`bio report --open`) · `fmt` · `lint` · `docs` (mkdocs) · `docs-deploy` (rsync `site/` to `oblinger.github.io/abio-docs`, commit, push) |
| `ci.yml` (one job, push to main + PR) | `uv sync --extra dev --extra jax --extra llm` → `pytest --cov-fail-under=85` → `bio test-matrix --check` → `pyright src/` → `mkdocs build` |

`bio report` is not in CI; it is a local operator artifact.

## Modules

| MODULE | LOC | Role |
| --- | --- | --- |
| `cli.py` | 98 | `main(argv)`; `bio = "alienbio.cli:main"` in `pyproject.toml`. |
| `commands/` | ~520 | `COMMANDS` registry;<br>`suite_cmd`, `config_cmd`, `report_cmd`, `test_matrix_cmd` — one `argparse` parser per verb. |
| `report.py` | 442 | `run_pytest`, `parse_junit` (worst outcome wins per function), `capability_rows`, `suite_rows`, `example_rows`, `run_rows`, `build`, `Report.ok` (the verdict is read off the page: failures, errored examples), `render_markdown`, `render_html`. |
| `capabilities.py` | 192 | The 35 `Dimension`s, `scan`, `phrases`, `matrix`, `check`; imports nothing from the library. |
| `config.py` | 279 | `get_api_key`, `set_api_key`, `list_providers`, `check_api_key`, `DEFAULT_CONFIG`; the file is written 0600. |

## Where the surface could mislead an operator

Box 4 hypotheses (2026-09-10) — all six confirmed and fixed: the swallowed flags and the stale front door (T054/T057, `argparse` per verb, help from `COMMANDS`), `--dry` vs the run (T057, one `preflight`), the ALL PASSED banner and the broken example (box 4, `Report.ok`), the shallow config merge (T054).

| HYPOTHESIS | Why it would be quiet | Where |
| --- | --- | --- |
| Flags after the verb are swallowed | `-v` after `suite run` never sets verbose; the hand loop sends any unknown token to `positional`, so a typo'd flag becomes the spec path; `resume`/`aggregate`/`report` ignore trailing args | `cli.py` ~66; `suite_cmd.py` ~81–92, ~142–177 |
| `--dry` reimplements the real path | the printed `out_dir` is a re-derivation, not the value `run_experiment` will use | `suite_cmd.py` ~99, ~133 |
| A JUnit file full of failures renders ALL PASSED | with `--junit PATH`, `exit_code` is hard-coded 0 and the banner reads only `pytest_exit` | `report_cmd.py` ~43; `report.py` ~320 |
| A broken example never fails the command | every fresh example run is wrapped in a bare `except`; the exit code reflects only the pytest run | `report.py` ~244 |
| Shallow config merge | a partial `providers:` block replaces the whole defaults sub-dict; `DEFAULT_CONFIG.copy()` shares nested dicts; `test_api_key` hard-codes its model | `config.py` ~80, ~256 |
| The front-door help is stale | the docstring documents `bio build \| cd \| expand \| fetch \| hydrate \| run \| store`; only `config`, `report`, `suite`, `test-matrix` exist; the suite usage omits `models` | `cli.py` ~1–23; `suite_cmd.py` ~70 |
