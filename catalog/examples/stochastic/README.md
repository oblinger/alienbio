# Stochastic environment — Poisson insults, checked recovery

*A homeostatic pool under reproducibly drawn Poisson insults, a recovery predicate over the resulting trace, and a predict task under observation noise.*

One pool `X` is fed at a constant rate and consumed into `Y`; an `!insult` block declares a Poisson schedule (`lam`, `horizon`) that the skeleton draws AT MATERIALIZE TIME from the world seed — the same seed always draws the same insult times, a different seed a different schedule (the test asserts both). `helpers.run_with_insults` integrates the world through the schedule piecewise, applying each insult as an instantaneous loss of `X`, and `helpers.recovered` is the timeline predicate: after each insult, did `X` climb back to the recovery level within `tau`? The reading is honest physics — an isolated insult always recovers, while a clustered one (a second hit inside the window) may not, and seed 9 draws both kinds. A `predict` task (which way does `Y` move when one step, drawn from the world seed, is throttled?) runs under the `observation_noise` axis.

Framed as robustness, never "pressure" — AUP's pre-registration leak check cleared this example **unconditionally** (2026-08-31): generic dynamics noise on a neutral predict task touches none of AUP's worlds or measures.

## Before and after the drawn step (T096)

Before, the consumer `use` was throttled on every seed and the key was `down` everywhere — committing it blind scored 1.000, so the noise axis could not bite. Now `perturbed: !x choice([...])` draws the step: `feed` / `use` give `down`, `drain` / `stress` (the insult block's background loss of `X`) give `up`; over seeds 200–259 the key is `down` 32 / `up` 28, and the blind modal key (`up`) is right on 47 %. The shipped `measure_commit` zero commits nothing and scores 0.000 before and after (4 trials); no scripted solver.

## Run it

    bio suite run catalog/examples/stochastic/stochastic.yaml --dry
    bio suite run catalog/examples/stochastic/stochastic.yaml

## What it covers

| Capability dimension | Where |
|---|---|
| stochastic perturbation on a reproducible per-seed schedule | `!insult {poisson: ...}`, `helpers.insult_times` |
| piecewise simulation through discrete events | `helpers.run_with_insults` |
| a timeline predicate — recovery checked, not judged | `helpers.recovered` |
| a predict task whose key is re-simulated | `task` |
| the observation-noise dial as an experiment axis (M28.3) | `axes: {observation_noise: [...]}` |

Deliberately absent: every AI-safety dial (roadmap M48.9).

## Test

`tests/expr/test_stochastic_example.py`.
