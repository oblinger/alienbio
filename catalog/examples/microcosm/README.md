# Microcosm — populations as counts on one resource

*Populations as counts — growth, death, maturation — mass-coupled to one resource, with an intervene task on the carrying capacity.*

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

## The score reads the pond

The `intervene` scorer reads `food` in ONE compartment — the pond, because the binding names it (`compartment: pond`). The food supply runs in every compartment, so all four can hold `food` (`arch_intervene.target_holders`), and a target held in several compartments with none named refuses at draft (`arch_intervene.target_compartment`). Until T091 E2 it summed `food` over all four compartments, whose volumes differ (10.0 against 0.1–0.2), and so ranked the worse feed rate higher. `bio suite run` at base seed 5 (2 s, 4 turns × 10 steps), goal 6.0:

| feed_rate | pond `food` | adults / juveniles / rivals `food` | score, summed (before) | score, pond (now) |
|---|---|---|---|---|
| 0.3 | 4.154 | 0.552 / 0.589 / 0.589 | 0.896 | 0.351 |
| 0.9 | 5.286 | 1.654 / 1.766 / 1.766 | 0.183 | 0.584 |

⚠️ The three reactions (`supply`, `drain`, `decay`) still run in **every** compartment, not only the pond: a world-level chemistry applies everywhere, and the engine has no way to confine a reaction to one compartment yet (`ReactionSpec.compartments` exists but no world or YAML path sets it). That is why the population compartments carry the `food` amounts in the table — food made inside the grazers, read by nothing now that the score reads the pond. Confining the chemistry to the pond needs that primitive (T091 E3, open).

## Test

`tests/expr/test_microcosm_example.py`.
