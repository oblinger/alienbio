# Microcosm — populations as counts on one resource

Two populations on one shared pond: a grazer in two size classes (juveniles mature into adults by a count flow) and a competitor, each growing in proportion to its count and the pond's food and drawing food *amount* as it grows, dying per capita with adults releasing part of their mass back as detritus that decays into food; an environmental drain on the food is the only pressure; and an `intervene` task on the carrying capacity — bring the pond's food to a level with the supply and the drain as levers.

## Run it

    bio suite run catalog/examples/microcosm/microcosm.yaml --dry
    bio suite run catalog/examples/microcosm/microcosm.yaml

## What it covers

| Capability dimension | Where |
|---|---|
| populations as **counts** on the compartment multiplicity axis (F017) | the three population `!Compartment`s (`multiplicity:`) |
| count rate laws: per-capita growth, death, size-class transition | `!GrowthLaw`, `!DeathLaw`, `!CountFlow` |
| mass coupling to one resource pool (growth draws it, death releases it) | `stoich:` / `release_*:` on the laws; `decay` |
| an environmental-kind pressure only | `drain` |
| an outcome-scored task with a named target on a hand-built world | `!intervene_q {binding: {target: food}}` |
| an experiment over a world-side dial | `microcosm` drafter, `feed_rate` axis |

Deliberately absent: every AI-safety dial (roadmap M48.9).

## Test

`tests/expr/test_microcosm_example.py`.
