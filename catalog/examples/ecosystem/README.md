# Ecosystem — the language's own smoke test

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

## Test

`tests/expr/test_ecosystem_example.py` loads the file, checks the world's pools, evaluates a template call from Python, and runs the experiment end to end through the suite harness.
