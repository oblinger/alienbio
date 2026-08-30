[[ABIO Architecture Docs]] 
# Commands

The `bio` CLI has two commands. The M1 command set (`build`, `run`, `report`, `fetch`, `store`, `hydrate`, `dehydrate`, `cd`, `agent`, `experiment`, `sim`, `scenario`, `lookup`) went with the M1 scenario runtime in M47.7 — an experiment is now one declared file run through the suite harness ([[ABIO Suite Runtime]]).

| Command | CLI | Description |
|---|---|---|
| suite | `bio suite run <spec.yaml> [--out DIR] [--dry]` | Run a declared experiment ([[ABIO Expr Spec]] § experiments): drafts the grid, runs every trial, writes `records.jsonl`, `manifest.json`, `map.json`/`map.csv`, `report.txt`. `--dry` prints the grid, the no-peeking verdict and the cost estimate without running. |
| | `bio suite resume <DIR>` | Continue a run from its record store (crashed or cost-stopped). |
| | `bio suite aggregate <DIR>` | Rebuild the reliability map from `records.jsonl` alone. |
| | `bio suite report <DIR>` | Render the text report from the record store. |
| | `bio suite models` | Refresh the recorded `models.list` snapshot (`suite/models_snapshot.json`, id → `created_at`) that lets an undated generation id count as pinned; a free call. |
| | `bio report [--open] [--no-examples]` | Run the suite once and write what it tested, and whether it passed, as one page: the capability matrix with each proving test's sentence, the broader suites, the examples run fresh, the runs on disk (`reports/report.md` + `.html`; `just report`). |
| config | `bio config [show \| set KEY VALUE]` | The framework configuration: provider keys (read from the environment), the pinned model. |

Every catalog experiment (`catalog/experiments/*.yaml`) is a `bio suite run` target; the twelve scripted zeros are pinned as golden regressions in CI.
