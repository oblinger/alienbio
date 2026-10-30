:>> [ABIO](../ABIO.md) → [ABIO Guides](ABIO%20Guides.md) → [ABIO Testing Guide](ha://p/ABIO%20Testing%20Guide) 
# Testing Guide
Where the tests live, how to run them, and the two commands that say what they prove.

## Running the tests

The suite is plain pytest over `tests/` (`testpaths = ["tests"]`,
`--import-mode=importlib` in `pyproject.toml`). From the repository root:

```
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m pytest tests/suite/test_runner.py -q
.venv/bin/python -m pytest tests/ -k golden -q
```

`just test` runs the same thing as `uv run pytest tests/ -v`; calling the
venv's interpreter directly avoids `uv run` picking another Python. Run
`uv sync --extra jax --extra llm` after a fresh clone: without the `jax`
extra the JAX simulator tests skip, and `llm` is the Anthropic SDK. The
test, type-check and docs tooling (pytest, pytest-cov, hypothesis, ruff,
pyright, mkdocs and its plugins, the notebook tools) is one `dev`
dependency group in `pyproject.toml`, which `uv sync` installs by default.

No test reaches a live model provider. `tests/conftest.py` removes
`ANTHROPIC_API_KEY` and `ALIENBIO_ANTHROPIC_API_KEY` from every test's
environment and replaces the `__init__` of `anthropic.Anthropic` and
`anthropic.AsyncAnthropic` (so every alias, `Client` and `AsyncClient`
included) with one raising `RuntimeError("live provider in tests")`; a
test that stubs the SDK in `sys.modules` is unaffected. A test that must
reach the real provider is marked `@pytest.mark.live`: it keeps the
environment and the SDK, and is skipped unless `ABIO_LLM_E2E=1` is set.
The one such test is the LLM agent's end-to-end trial in
`tests/suite/test_llm_agent.py`.

The other recipes in the `justfile` that touch testing are `just check`
(`pyright src/`), `just lint` (`ruff check src/ tests/`) and `just report`
(below). `just lint` is not a gate: it reports some two thousand findings
and CI does not run it. There are no tiers or smoke tests: every test
runs on every invocation, the `live` one skipped. The markers in use are
pytest's own (`parametrize`, `skipif` for an absent JAX, strict `xfail`),
`live` (registered in `conftest.py`) and `capability` (registered under
`[tool.pytest.ini_options] markers` in `pyproject.toml`), described below.

## The test tree

| Folder | What it holds |
| --- | --- |
| `tests/capabilities/` | One proving test per capability dimension, plus the broader suites: every Expr head, special forms, the adversarial sandbox corpus, simulator conformance (hypothesis), the `bio` CLI end to end as a subprocess, and the report and matrix themselves |
| `tests/suite/` | The experiment layer: generators, drafters, runner, guards and preflight, the record store, every analysis family, the golden experiment hashes, the pressure acceptance criteria and the gameability table |
| `tests/expr/` | The Expr language: core, layers, templates, includes, the rate grammar, one test per catalog example, and the executed samples of the Expr guides |
| `tests/bio/`, `tests/unit/` | The simulation substrate (chemistry, reactions, flows, populations, both simulators, energy, conservation), the entity and IO layer, config and the CLI |

Tests build their worlds in code (the `mk` makers, the catalog specs,
`conftest.py` fixtures); there is no shared fixtures folder.

Three files carry pinned behaviour worth knowing before an edit:

- `tests/suite/test_golden_experiments.py` hashes each catalog
  experiment's `records.jsonl` (modulo `wall_time_s`). A change that moves
  a zero run fails here; re-pin only on a reviewed field-level diff.
- `tests/expr/test_spec_examples.py` executes the code samples in
  [ABIO Expr Spec](ABIO%20Expr%20Spec.md) and
  [ABIO Expr Python API](ABIO%20Expr%20Python%20API.md); run it after
  editing either page.
- `tests/suite/test_no_peeking_lint.py` scans every executable file
  under `tests/` and `demos/` and fails one that names a language-model
  entry point together with a conflict or pressure-family world: no model
  runs on a substrate the AUP paper has a registered question about.

## What the tests prove: `bio test-matrix`

Each capability dimension (A1–A5, B1–B18, C1–C11, I1) is claimed by a
test in `tests/capabilities/` decorated `@pytest.mark.capability("B3")`,
whose docstring's first sentence says what it proves. `bio test-matrix`
finds them by reading source, without running pytest:

```
bio test-matrix              # the table, as text
bio test-matrix --markdown   # the table, as Markdown
bio test-matrix --check      # the CI gate; exit 1 on a gap
```

`--check` fails on a built or partial dimension no test claims, a test
claiming an unknown id, and a claiming test with no docstring sentence.

## Whether they passed: `bio report`

`bio report` (or `just report`, which adds `--open`) runs pytest once to a
JUnit file and writes `reports/report.md` and a self-contained
`reports/report.html`: the capability matrix with each proving test's
sentence and outcome, the broader suites, the catalog examples run fresh
(scripted specs only, so it spends nothing), and the runs on disk with
their key figures.

```
bio report --no-examples     # skip the fresh example runs
bio report --junit PATH      # reuse an existing JUnit file
bio report --out DIR         # write elsewhere (default reports/)
```

The title reads `ALL PASSED` only when pytest exited 0, nothing failed,
every example ran clean, every built or partial capability row has a
passing proving test and every broader-suite row ran and passed;
otherwise it names the gap (`FAILURES …` or `NOT PROVEN …`) and the
command exits 1.

## Continuous integration

`.github/workflows/ci.yml` runs, on every push to `main` and every pull
request: the full suite with an 85 % coverage floor, `bio test-matrix --check`, `pyright src/`, and
`mkdocs build`.
