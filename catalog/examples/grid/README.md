# Grid — one neutral world under a full experiment

*A neutral world under the full experiment harness: two axes, a power design, matched seeds, an idle twin, bounded concurrency, and a run that is interrupted, resumed, aggregated and reported.*

A grid of reactions — `n_nodes` parallel chains, each `complexity` steps long, every row fed and drained — is the world; the harness around it is the point. The experiment sweeps both dials, declares the comparison it exists to make as a **power design** (`suite.power` sizes the trials), draws the world from **matched seeds** across arms, adds an automatic **idle twin** to every trial (`idle_baseline: True` grows an `agent` axis), runs under **bounded concurrency**, and carries the cost fields the **dry run** reads. The agents are the example's own, registered from `helpers.py` beside the framework's: `trend_commit` watches row 0's product for one step and commits the direction it moved (the unperturbed trend: `up`), `prior_commit` never looks and commits the textbook answer (`down`); both are swept against `idle`, the twin that answers nothing. The throttled reaction is drawn from the world seed — row 0's first step (`down`), row 0's drain (`up`) or row 1's first step, which never reaches `P0` (`same`) — so each control is right only where its one answer happens to be the key. The test interrupts a run, **resumes** it, **aggregates** the record store back into the reliability map, and **renders the report**.

## Before and after the drawn reaction (T096)

Before, row 0's first step was throttled on every seed and the key was `down` in every cell, so `prior_commit` scored 1.000 everywhere and `trend_commit` 0.000 — the grid's 36 trials could not tell a reasoning agent from a constant. Now `perturbed: !x choice([...])` draws the reaction: over seeds 200–259 the key is `up` 22 / `same` 20 / `down` 18, and the blind modal key (`same`) is right on 33 %. The base seed moved 17 → 22: the world seed is matched across the `complexity` / `n_nodes` cells, so a run draws three worlds, and at 17 all three drew the drain; at 22 they draw one of each.

| Arm (each of the 4 cells, 3 trials) | before | after |
|---|---|---|
| `prior_commit` | 1.000 | 0.333 |
| `trend_commit` | 0.000 | 0.333 |
| `idle` | 0.000 | 0.000 |

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
