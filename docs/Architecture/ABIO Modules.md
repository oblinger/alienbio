:>> [[ABIO]] → [[ABIO Docs]] → [ABIO Modules](ha://p/ABIO%20Modules) 
 [[ABIO Architecture Docs]] 

# Modules

Code organization for alienbio (`src/alienbio/`, ~35k LOC), as of T056 (2026-09-10). The design-level view is [[ABIO Architecture]]; this page is the tree.

## Source Tree

Top level — the public surface (`__init__.py`), the `bio` front door (`cli.py`, whose command list is `COMMANDS`), `config.py` (API keys and the default agent/model), `capabilities.py` (the 35 capability dimensions behind `bio test-matrix`) and `report.py` (`bio report`).

```
src/alienbio/
├── bio/         the chemistry substrate
├── suite/       the instrument
├── expr/        the Expr language: loader, evaluator, sandbox
├── spec_lang/   the AST allowlist, Scope, @biotype
├── infra/       Entity, IO, the mk pegboard, graph_ops
├── protocols/   the Protocols the substrate implements
└── commands/    bio suite | config | test-matrix | report
```

**`bio/`** — `atom` `molecule` `reaction` `chemistry` (the entities, plus `Modulation`); `compartment` `compartment_tree` `world_state`; `world` (`WorldImpl`, the declarative world and its one resolution point); `rate_expr` (the compiled rate grammar; `ROUNDING_FLOOR`, `RATE_CAP`); `world_simulator` (the reference stepper: reactions, flows, populations); `jax_core` `jax_simulator` (the JAX stepper, parity to 1e-9); `flow` (`TransportFlux`, `GeneralFlow`); `population` (`PerCapitaGrowth` / `PerCapitaDeath` / `CountFlow` and the shared summed-demand ration); `conservation` `energy` (the canaries); `makers` (`mk.M` / `mk.R` / `mk.C`).

**`suite/`** — `experiment` (the spec, `preflight`, the drafter heads, the record store, `run_experiment`, `render_report`); `expr_experiment` (`!experiment` and its heads); `registration` (`catalog/registrations.yaml`, the no-peeking licence); the runtime `runner` `agent` `llm_agent` `brief` `naming` `trial` `mass_trial`; composition `skeleton` `blocks`; the drafters `pressure_gen` `phase1_gen` `conflict_gen` `delta_gen` `arch_diagnose` `arch_predict` `arch_intervene` `hazard`; analysis `dose` `delta` `caution` `degradation` `faking` `tradeoff` `census` `realism` `plots` and the `score_*` primitives; `expr_heads` `rate_law` `verify` `dist`. See [[ABIO Suite Runtime]].

**`expr/`** — `yaml_tags` `parse` `env` `interp` `registry` `heads` `include` `x`. See [[ABIO Expr Spec]].

`catalog/` holds the experiments (`experiments/*.yaml`, golden-pinned), the examples (`examples/*/`) and `registrations.yaml`; `runs/` the record stores. The M1 layout this page used to list (`spec_lang/bio.py`, `run.py`, `bio/state.py`, `bio/simulator.py`, the `bio build|run|expand` verbs) was deleted in M47.7 and T056.
