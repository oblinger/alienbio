# Ecosystem — the language's own smoke test

*Every construct of the Expr language used once — on two organisms coupled through a shared waste pool, with a task and a small experiment over them.*

Two organisms, each an energy cycle feeding conversion chains, coupled through a shared waste pool that one organism's enzyme consumes; a task on the world; a small experiment over it. `ecosystem.yaml` uses every construct of the Expr language once (the comment above each node names it); `helpers.py` is the Python it leans on.

## Run it

    bio suite run catalog/examples/ecosystem/ecosystem.yaml --dry
    bio suite run catalog/examples/ecosystem/ecosystem.yaml

The file loads **trusted** because it is under `catalog/` (it executes `helpers.py`). From Python:

    from alienbio.expr import Env, X, evaluate
    scope = Env.standard(seed=11, trusted=True).load("catalog/examples/ecosystem/ecosystem.yaml")
    world = evaluate(X.name("world"), scope)
    vash = evaluate(X.organism("vash", chains=1), scope)

## What it covers

| Capability dimension | Where |
|---|---|
| bindings, lazy order-independent scope, dotted lookups | the top of the file; `!ref site_K` |
| inline expressions (`!x`): arithmetic, f-strings, conditionals, list displays, builtins, a registered `@fn` | `label`, `tags`, `weights`, `route_len` |
| quoted forms (`!q`) as Dists and as compiled rate laws | `hop_rate`, `Vmax`, `regeneration.rate` |
| the seven special forms | `template` ×2, `let`, `each` (with `key`), `if`, `run`, `seed` |
| YAML templates: positional + keyword parameters, per-call defaults, per-call seeds, instance pool namespacing, pools passed in | `energy_cycle`, `organism`; `shared_waste` shared, `krel.energy.ME1` private |
| a Python expander returning a block form | `chain` |
| guards by name and with parameters, `on_fail: retry` | `routes.body.guards` |
| constructors | `!Reaction`, `!question`, `!outcome` |
| the block library, pools as names, a skeleton, `!world` with `initial:` | `!reaction`, `!sink`, `!enzyme`, `!block`, `!skeleton`, `!world` |
| a task with an outcome objective and a `!py` scorer | `task` |
| the experiment file: quoted drafter / episode calls, axes as free names, a drafter registered from Python | `experiment`, `helpers.ecosystem` |

Deliberately **not** here: the AI-safety dials (monitoring, framing, hazard, constitution, stakes / reversibility, deception readouts) — those keep their coverage through the EXP zeros only (roadmap M48.9).

## The world carries mass

`initial:` seeds each organism's energy cycle (`krel.energy.ME1: 4.0`, `vash.energy.ME1: 4.0`) beside `shared_waste: 0.0`. Until T091 E12 it seeded only `shared_waste: 0.0` and nothing has a source, so every one of the 15 pools stayed 0 forever and every record scored 0. At seed 11, `dt` 0.05: after 20 steps all 15 pools are non-zero (`vash.energy.ME2` 0.149, `shared_waste` 0.323); after 200, the mass has run down the chains into `krel.S1` 0.725 / `vash.S1` 0.785. The experiment's act-commit scores rise from 0.000 to 0.008–0.019 (`vash.energy.ME2` / 4.0) — still no intended solver (`tests/suite/test_gameability.py`).

## Test

`tests/expr/test_ecosystem_example.py` loads the file, checks the world's pools, evaluates a template call from Python, and runs the experiment end to end through the suite harness.
