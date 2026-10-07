:>> [[ABIO]] → [[ABIO Docs]] → [Architecture ABIO Files](ha://p/Architecture%20ABIO%20Files) 
 [[ABIO Architecture Docs]] 

# ABIO Files
The alienbio repository as it stands, file by file.

Regenerated from the tree 2026-10-07 (T065). The previous version described
the M1 design-era layout — `protocols/infra.py`, `biology/`, `generators/`,
`execution/`, a Rust crate of mirrored classes, `catalog/kegg1` — none of
which survived M47.7 (the M1 scenario runtime) or T056 (the M1 remnants).
Each entry below is a module's own one-line docstring summary, so the page
drifts only when a module's docstring does.

## src/alienbio — the package

- **`__init__.py`** — package entry point and top-level exports.
- **`cli.py`** — the `bio` front door; one `argparse` parser per verb.
- **`config.py`** — API key and provider configuration (reads the
  environment; no `.env` on disk).
- **`capabilities.py`** — the capability matrix (M48.1): the 35 dimensions
  of [[ABIO Capability Dimensions]] mapped to the tests that prove them.
- **`report.py`** — `bio report`: what the tests test and whether they
  passed, on one page.

### `bio/` — the chemistry substrate the instrument runs on

- **`atom.py`** — `AtomImpl`: chemical elements.
- **`molecule.py`** — `MoleculeImpl`: chemical species.
- **`reaction.py`** — `ReactionImpl`: transformations with numeric rates.
- **`chemistry.py`** — `ChemistryImpl`: the container for atoms, molecules
  and reactions; refuses a shared molecule/reaction id.
- **`compartment.py`** — `CompartmentImpl`: one biological compartment.
- **`compartment_tree.py`** — hierarchical compartment topology.
- **`world.py`** — a runnable world: chemistry + topology + initial state.
- **`world_state.py`** — concentration storage across compartments.
- **`world_simulator.py`** — the reference multi-compartment simulator.
- **`jax_core.py`** — the vectorized JAX primitives (M24 core).
- **`jax_simulator.py`** — `JaxWorldSimulator`: the jitted simulator.
- **`flow.py`** — transport between compartments; one rationed flow pass.
- **`population.py`** — count-based rate laws on the `multiplicity` axis.
- **`rate_expr.py`** — compiled rate expressions: the one representation of
  a rate law both simulators run (M47.10).
- **`conservation.py`** — opt-in atom/mass balance plus a total-quantity
  canary.
- **`energy.py`** — opt-in reaction free-energy accounting.
- **`makers.py`** — registers the biology makers on the `mk` pegboard.

### `suite/` — worlds, tasks, briefs, the runner, the harness

- **Data model** — `types.py` (neutral immutable value types),
  `dist.py` (distributions and deterministic seeds), `trial.py`
  (`TrialRecord`, the frozen unit of observation), `conditions.py`
  (orthogonal dial composition), `deliberation.py` (trace capture).
- **World construction** — `skeleton.py` (recursive composition),
  `blocks.py` (the engine-ready block library), `carve.py`, `cover.py`,
  `augment.py`, `perturbations.py`, `observation.py`, `pressure.py`,
  `verify.py` (reject-sampling over real physics), `boundedness.py`.
- **Generators** — `pressure_gen.py` (the instrumental-pressure world,
  W1), `w2_gen.py` (W2: depth × fan-out × disclosure, plus the harm
  ledger), `phase1_gen.py` (the conflict-free phase-1 family),
  `conflict_gen.py` (the conflict ladder), `delta_gen.py` (matched
  pairs), `generative.py`, `archetypes.py`, `arch_diagnose.py`,
  `arch_predict.py`, `arch_intervene.py`, `hazard.py`, `monitor.py`.
- **Task and brief** — `brief.py` (`TaskBrief`, the context a live agent
  gets), `naming.py` (opaque agent-facing names), `render.py` and
  `vocab.py` (deterministic NL rendering), `validity.py`, `grade.py`.
- **Running** — `runner.py` (the agent turn loop), `agent.py` (the Agent
  protocol and the scripted agent), `agents.py` (the `AGENTS` factories),
  `llm_agent.py` (the live-model agent over the `LLMFn` seam), `ops.py`,
  `mass_trial.py` (the mass-trial runner and reliability map).
- **The experiment harness** (T058 split `experiment.py` five ways) —
  `spec.py` (the spec, its validators, the dry-run cost estimate),
  `drafters.py` (every `DRAFTERS` entry and the guarded sets),
  `guards.py` (every refusal a run makes before spend, and `preflight`),
  `store.py` (record codecs, the manifest, resume drift),
  `report_text.py` (the text report), `experiment.py` (`run_experiment`,
  `aggregate`, and the re-export facade), `registration.py` (the
  registration-gated admission of awareness dials), `power.py`,
  `census.py`, `plots.py`, `realism.py`.
- **Readouts** — `dose.py`, `delta.py`, `tradeoff.py`, `caution.py`,
  `info_seeking.py`, `faking.py`, `degradation.py`, `effect_size.py`,
  `stats_summary.py`, `reliability_grid.py`, and the `score_*.py` family
  (surfacing, blind spot, conflict, divergence, calibration, failure
  mode).
- **Expr front end** — `expr_heads.py` (layers 0–2: blocks, skeletons,
  worlds), `expr_experiment.py` (layers 3–6: patterns, objectives, tasks,
  suites, experiments, briefs, episodes, agents), `rate_law.py`,
  `pipeline.py`.

### `expr/` — the Expr language (M47)

- **`form.py`** — the abstract syntax.
- **`parse.py`** — the inline spelling: Python-expression text ↔ forms.
- **`x.py`** — the Python spelling (`X`).
- **`yaml_tags.py`** — the structural spelling: the Expr YAML tags.
- **`env.py`** — bindings, heads, context.
- **`interp.py`** — `evaluate(form, env)` and the special forms.
- **`registry.py`** — how Python enters the Expr environment.
- **`heads.py`** — the builtin heads (distributions, math, `op:*`).
- **`include.py`** — includes and `!py` references, resolved at load under
  the trust gate.

### `infra/`, `protocols/`, `spec_lang/`, `commands/`

- **`infra/entity.py`** — the `Entity` base class every biology object
  carries; **`io.py`** — naming, formatting, parsing, persistence over
  dvc-dat; **`mk.py`** — the maker pegboard; **`graph_ops.py`** — the
  neutral bipartite-graph algorithms the network views share;
  **`imports.py`** — the import collector for do-system references.
- **`protocols/bio.py`** — the biology protocols;
  **`_conformance.py`** — the Protocols as a live contract under
  `TYPE_CHECKING`, so `pyright src/` defends what the package exports.
- **`spec_lang/`** — what the Expr language stands on after M47.7:
  `builtins.py` (the distribution builtins), `safe_eval.py` (the
  AST-allowlist evaluator), `scope.py`, `decorators.py`.
- **`commands/`** — `suite_cmd.py` (`bio suite run|resume|aggregate|report`
  and `models`), `report_cmd.py`, `test_matrix_cmd.py`, `config_cmd.py`.

## tests/ — the five suites

- **`tests/suite/`** (92 files) — the instrument: generators, dials,
  guards, readouts, the runner, the goldens
  (`test_golden_experiments.py` pins every catalog zero's `records.jsonl`
  modulo wall time).
- **`tests/expr/`** (19) — the language, including every example in the
  Spec executed as a test and the M1 expansions pinned as
  `m1_golden.json`.
- **`tests/capabilities/`** (13) — one end-to-end proof per capability
  dimension; `bio test-matrix --check` refuses a dimension whose proving
  test has no docstring sentence.
- **`tests/unit/`** (18) — the bio core, the CLI, the JAX parity suites,
  and the dvc-dat integration round-trip.
- **`tests/integration/`** + **`tests/fixtures/`** — the subprocess CLI
  end-to-end and the shared fixtures.

⚠️ Run `uv run pytest tests/` — a bare `uv run pytest` from the repo root
fails collection on a site-packages `tests` package.

## catalog/ — the declared experiments and examples

- **`catalog/experiments/`** — `exp01.yaml` … `exp13.yaml`, the scripted
  zeros one per EXP design, each golden-pinned, plus the live specs
  (`exp04-first-live.yaml`).
- **`catalog/examples/`** — the nine M48.9 coverage examples, each a
  runnable spec folder: `ecosystem`, `organism`, `microcosm`, `kinetics`,
  `cascade`, `pathway_puzzles`, `grid`, `agent_loop`, `stochastic`. Held
  clear of the AI-safety dials by design.
- **`catalog/registrations.yaml`** — the commit-tracked registration
  entries (`aup-awareness`, `aup-pressure`, `aup-exploration`); a live
  model reaches a guarded dial only through an entry naming it.
- **`catalog/_index.yaml`** — the catalog index.

## Everything else at the root

- **`pyproject.toml`** — dependencies and the four extras (`dev`, `jax`,
  `llm`); run `uv sync --extra jax --extra dev --extra llm` after a fresh
  clone.
- **`justfile`** — `just test`, `just check`, `just report`, `just docs`,
  `just docs-deploy`.
- **`mkdocs.yml`** — the site built from `docs/`.
- **`docs/`** — a READ-ONLY mirror of the vault's `ABIO Docs/`; edit the
  vault, then `code sync`, then `just docs-deploy`.
- **`demos/`** — the notebook gallery (`notebooks/`, `output/` and
  `scripts/` are symlinks, never mirrored).
- **`rust/`** — a `Cargo.toml` and a stub `src/`; nothing in the Python
  package calls it.
- **`src/dvc_dat`** — a gitignored dev symlink to `~/ob/grove/dvc-dat`,
  the storage layer `infra/io.py` sits on ([[ABIO DAT]]).
- **`data/`**, **`runs/`**, **`reports/`**, **`art/`**, **`site/`** —
  run outputs and stores, all gitignored.

## Structure notes

The package is layered, and the layering is the architecture: `bio/` is
physics and knows nothing about agents; `suite/` builds worlds over it and
runs agents against them; `expr/` is the language every spec is written in;
`infra/` is the entity and storage substrate all three stand on. Nothing in
`bio/` imports `suite/`. The eight subsystem docs under
[[ABIO Architecture]] carry each band's figure, seams and boundaries.

`protocols/` holds typing interfaces only, and `_conformance.py` makes them
load-bearing: a substrate that drifts from its Protocol is a pyright error,
not a runtime surprise.

## See also

- [[ABIO Architecture]] — the subsystem decomposition with figures.
- [[ABIO Modules]] — the per-module pages.
- [[ABIO DAT]] — dvc-dat integration, name resolution, `_spec_.yaml`.
- [[ABIO Data]] — the `data/` folder's intent-based categories (⚠️ still
  describes the M1-era `chem/` / `world/` / `test/` tree).
