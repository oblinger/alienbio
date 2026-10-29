# Cascade — signalling with feedback, a buffer, and an indirection dial

*A ligand-driven amplification chain of swept depth, negative feedback and a reversible buffer, with a `diagnose` task on a throttled step — scripted arms sweep depth and observability; an LLM arm must pin both.*

`cascade_children(depth)` wires the whole loop through the pattern blocks: a `signal` block (linear activator — the ligand `L` drives `R -> S0`), `depth` `enzyme` stages (`michaelis` — `S{i} -> S{i+1}` catalysed by `E`), a `cooperative` output (`hill` — the last stage drives `P -> O`), a second `signal` block closing the negative-feedback loop (`O` accelerates the drain of `S0`), and a reversible complexation `O + B <-> OB` buffering output spikes. One stage — the receptor, an amplification step or the output — is drawn from the world seed (`helpers.cascade_locus`), throttled to a quarter of its rate, and `!diagnose_q` asks which node was perturbed — the key (the stage's product: `S0`, `S{i+1}` or `O`) is bound by construction, the skeleton-oracle way.

**AUP condition (2026-08-31):** an LLM arm runs at ONE fixed `depth` and ONE fixed `observability`/`noise` setting — never sweep either axis with a live model; a model's curve along indirection depth or epistemic access is territory AUP's pre-registered awareness measures own. Scripted arms (this example's CI) are unrestricted.

## Before and after the drawn locus (T096)

Before, `amp0` was throttled on every seed, so the key was `S1` everywhere and committing it blind scored 1.000. Now the locus is drawn over the `depth + 2` stages: over seeds 200–259 the key is `S1` 26 / `S0` 20 / `O` 14 at depth 1, and `S1` 15 / `S2` 14 / `O` 13 / `S0` 10 / `S3` 8 at depth 3; the blind modal key (`S1`) is right on 43 % of depth-1 seeds. The shipped `measure_commit` zero commits nothing and scores 0.000 on every cell before and after (8 trials); the example still has no scripted solver.

## Run it

    bio suite run catalog/examples/cascade/cascade.yaml --dry
    bio suite run catalog/examples/cascade/cascade.yaml

## What it covers

| Capability dimension | Where |
|---|---|
| every S2 pattern block: `signal`, `enzyme`, `cooperative` (+ `inhibitor` form in the kinetics kit) | `receptor`, `amp{i}`, `output`, `feedback` |
| an indirection-depth dial sizing the world | `depth` axis through `cascade_children` |
| the observability dial narrowing the brief's probes (M28.2) and the noise dial (M28.3) | `brief: !q brief(observability=..., observation_noise=noise)` |
| a diagnose task whose key is the skeleton oracle's binding, drawn per seed | `locus: !x cascade_locus(depth)`, `!diagnose_q {binding: {target: …}}` |
| a perturbed world built from a clean one | `helpers.throttle` (`perturb_reaction_rate`) |
| an experiment over a world-side and a brief-side axis at once | `axes: {depth, observability}` |

Deliberately absent: every AI-safety dial (roadmap M48.9); the LLM-arm sweep restriction above.

## Test

`tests/expr/test_cascade_example.py`.
