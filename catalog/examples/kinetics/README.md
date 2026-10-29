# Kinetics kit — every rate-law form, on both simulators

*Every rate-law form on one network, run on both simulators and compared to 1e-9, with a predict task on a step drawn per seed.*

One reaction network over a substrate `S` and five modifier / product pools in which every rate-law form the compiled tier admits appears once: a constant `k` (plain mass action); the product form with each of the four modulation kinds (`michaelis`, `hill`, `activator`, `inhibitor`); Michaelis–Menten written over the substrate (the whole rate); algebra with a sum, `exp` and `sqrt`; two modulations mixed with algebra as the factor on mass action. `helpers.compare` runs the same world on the reference simulator and the JAX core and reports the largest divergence — the kit's reason to exist — and a `predict` task asks which way `Q1` moves when one step — drawn from the world seed among the saturated step `r_mm`, its feeder `r_mass`, the competing branch `r_michaelis` and `Q1`'s drain `d1` — is throttled.

## Before and after the drawn step (T096)

Before, `r_mm` was throttled on every seed, `Q1` is its product, and the key was `down` everywhere — committing it blind scored 1.000. Now `perturbed: !x choice([...])` draws the step: `r_mm` / `r_mass` give `down`, `r_michaelis` / `d1` give `up`; over seeds 200–259 the key is `down` 32 / `up` 28, and the blind modal key (`up`) is right on 47 %. The shipped `measure_commit` zero commits nothing and scores 0.000 before and after (4 trials); no scripted solver.

## Run it

    bio suite run catalog/examples/kinetics/kinetics.yaml --dry
    bio suite run catalog/examples/kinetics/kinetics.yaml

From Python, the comparison alone:

    from alienbio.expr import Env, X, evaluate
    scope = Env.standard(seed=3, trusted=True).load("catalog/examples/kinetics/kinetics.yaml")
    print(evaluate(X.name("parity"), scope))   # {'max_abs_diff': ~1e-12, 'jax': True, 'steps': 200}

## What it covers

| Capability dimension | Where |
|---|---|
| the compiled tier: `k`, `k × modulation` for every `Modulation` kind | `r_mass`, `r_michaelis`, `r_hill`, `r_act`, `r_inh` |
| the rate grammar beyond the product form: substrate saturation, sums, `exp`, `sqrt`, mixed modulations (M47.10) | `r_mm`, `r_alg`, `r_mix` |
| reference-vs-JAX conformance on one world (M48.6) | `parity` (`helpers.compare`) |
| pools-as-names binding across a nested block | the `drain` block |
| a predict task whose key is re-simulated | `task` |
| an experiment over a world-side dial | `kinetics` drafter, `enzyme_level` axis |

Deliberately absent: every AI-safety dial (roadmap M48.9).

## Test

`tests/expr/test_kinetics_example.py`.
