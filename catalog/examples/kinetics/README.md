# Kinetics kit — every rate-law form, on both simulators

One reaction network over a substrate `S` and five modifier / product pools in which every rate-law form the compiled tier admits appears once: a constant `k` (plain mass action); the product form with each of the four modulation kinds (`michaelis`, `hill`, `activator`, `inhibitor`); Michaelis–Menten written over the substrate (the whole rate); algebra with a sum, `exp` and `sqrt`; two modulations mixed with algebra as the factor on mass action. `helpers.compare` runs the same world on the reference simulator and the JAX core and reports the largest divergence — the kit's reason to exist — and a `predict` task asks which way a product moves when the saturated step is throttled.

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
