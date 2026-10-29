:>> [ABIO](../ABIO.md) → [ABIO Ref](ABIO%20Ref.md) → [ABIO Commands](ha://p/ABIO%20Commands) 
# Commands
The reference for the `bio` CLI's four commands — `suite`, `report`, `test-matrix` and `config` — with their subcommands and flags.

| Command | CLI | Description |
|---|---|---|
| suite | `bio suite run <spec.yaml> [--out DIR] [--dry] [-v]` | Run a declared experiment ([Expr Spec](../ABIO%20Guides/ABIO%20Expr%20Spec.md) § experiments): drafts the grid, runs every trial, writes `records.jsonl`, `manifest.json`, `map.json`/`map.csv`, `report.txt`, and the run's one key figure `key.png` (+ `key.json`: readout and caption). `--dry` prints the grid, every preflight verdict and the cost estimate without running, and exits 1 when the run would refuse. |
| | `bio suite resume <DIR>` | Continue a run from its record store (crashed or cost-stopped). |
| | `bio suite aggregate <DIR>` | Rebuild the reliability map from `records.jsonl` alone. |
| | `bio suite report <DIR>` | Render the text report and the key figure (`key.png`, `key.json`) from the record store alone. |
| | `bio suite models` | Refresh the recorded `models.list` snapshot (`suite/models_snapshot.json`, id → `created_at`) that lets an undated generation id count as pinned; a free call. |
| report | `bio report [--open] [--no-examples] [--junit PATH] [--out DIR]` | Run the suite once and write what it tested, and whether it passed, as one page: the capability matrix with each proving test's sentence, the broader suites, the examples run fresh, the runs on disk — each with its key figure embedded (`reports/report.md` + `.html`, the HTML self-contained; `just report`). `--junit` reuses a JUnit file instead of running pytest. |
| test-matrix | `bio test-matrix [--markdown] [--check]` | The 35 capability dimensions and the tests that prove them; `--markdown` prints the table the dimensions doc carries, `--check` exits 1 when a built or partial dimension has no test or a proving test has no docstring sentence (a CI gate). |
| config | `bio config set-key <provider> <key>` | Store a provider's API key in `~/.config/alienbio/config.yaml` (the environment's `ANTHROPIC_API_KEY` is read too). |
| | `bio config list-keys` | List the configured providers. |
| | `bio config test-key <provider>` | Check a key with one live call — billed for `anthropic`. |
| | `bio config show` | Show the config, keys masked. There is no default agent or model setting: a run's model comes from its spec or `PINNED_MODEL`. |

Every verb takes `--help`; `-v` goes before the command or after a `suite` verb.

The M1 command set (`build`, `run`, `report`, `fetch`, `store`, `hydrate`, `dehydrate`, `cd`, `agent`, `experiment`, `sim`, `scenario`, `lookup`) went with the M1 scenario runtime in M47.7 — an experiment is now one declared file run through the suite harness ([Suite Runtime](../ABIO%20Architecture/ABIO%20Suite%20Runtime.md)); today's `bio report` is the test report, not the M1 verb.

Every catalog experiment (`catalog/experiments/*.yaml`) is a `bio suite run` target; the fifteen scripted zeros (all but the paid `exp04-first-live`) are pinned as golden regressions in CI (`tests/suite/test_golden_experiments.py`).
