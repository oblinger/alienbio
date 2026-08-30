# Grid — one neutral world under a full experiment

A grid of reactions — `n_nodes` parallel chains, each `complexity` steps long, every row fed and drained — is the world; the harness around it is the point. The experiment sweeps both dials, declares the comparison it exists to make as a **power design** (`suite.power` sizes the trials), draws the world from **matched seeds** across arms, adds an automatic **idle twin** to every trial (`idle_baseline: True` grows an `agent` axis), runs under **bounded concurrency**, and carries the cost fields the **dry run** reads. The agents are the example's own, registered from `helpers.py` beside the framework's: `trend_commit` watches row 0's product for one step and commits the direction it moved (a plausible heuristic that is wrong on every cell — the unperturbed trend points the other way), `prior_commit` never looks and commits the textbook answer (right on every cell, for no observed reason); both are swept against `idle`, the twin that answers nothing. The test interrupts a run, **resumes** it, **aggregates** the record store back into the reliability map, and **renders the report**.

## Run it

    bio suite run catalog/examples/grid/grid.yaml --dry      # the cost estimate ($0: scripted agents)
    bio suite run catalog/examples/grid/grid.yaml            # 36 trials into runs/examples/grid
    bio suite resume runs/examples/grid                      # after an interruption
    bio suite aggregate runs/examples/grid                    # map.json / map.csv from records.jsonl alone
    bio suite report runs/examples/grid                       # report.txt

## What it covers

| Capability dimension | Where |
|---|---|
| a condition grid over two world dials (mass trials, reliability map) | `axes`, `grid` drafter |
| a declared power design that refuses an under-powered spec (M46.9) | `design: !power` |
| matched world seeds across arms (M46.8) | `matched_dials` |
| the automatic idle baseline as an arm of the grid (M45.7) | `idle_baseline` |
| bounded concurrency (M45.6) | `concurrency` |
| cost accounting and the dry-run estimate (M45.5) | `expected_*`, `price_usd_per_mtok`, `cost_ceiling_usd` |
| the record store, manifest, resume, aggregate, report (M46.5 / M46.7 / M46.11) | `tests/expr/test_grid_example.py` |
| agents registered from a catalog file, beside the framework's own, swept as an axis | `helpers.trend_commit`, `helpers.prior_commit` |

Deliberately absent: every AI-safety dial (roadmap M48.9).

## Test

`tests/expr/test_grid_example.py`.
