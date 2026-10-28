---
description: "`capabilities` + `commands/test_matrix_cmd`: the 35 capability dimensions with their status, the static scan that pairs each with its `@capability` proving test and that test's docstring sentence, the CI gate, and the `bio test-matrix` verb. Source: `src/alienbio/capabilities.py`, `src/alienbio/commands/test_matrix_cmd.py`."
---
:>>
# ABIO Capabilities
The page for the capability matrix: the fixed table of 35 dimensions, how the tests that prove them are found without running pytest, what the CI gate refuses, and the `bio test-matrix` verb that prints it.

![ABIO Capabilities](ABIO%20Capabilities.svg) 
*A static scan* is the topic behind the `ast.parse` edge: the matrix reads the test files as text and never imports or runs them, so it proves a test exists, not that it passes; *What the gate refuses* governs the three red outcomes of `--check`.

`capabilities.py` imports nothing from the library; it reads `tests/capabilities/test_*.py` relative to the repository. Its two consumers are `bio test-matrix` (this page) and `bio report`, which pairs the same matrix with JUnit outcomes ([ABIO Report](ABIO%20Report.md)); CI runs `bio test-matrix --check`, and `tests/capabilities/test_matrix.py` runs the same checks under pytest. The dimensions are the ones [ABIO Capability Dimensions](../../ABIO%20Design/ABIO%20Capability%20Dimensions.md) lists, whose generated status column `render_markdown` writes; the `@capability` marker is declared in `tests/capabilities/conftest.py`. The front door is [ABIO CLI](ABIO%20CLI.md).



## capabilities Interface
A frozen dataclass, the fixed table, and functions that each rescan the test folder on every call. Every function takes an optional `tests_dir`, which defaults to `TESTS_DIR`.

| capabilities | |
| --- | --- |
| [Dimension](#^dimension) | One row: id, group, title, status |
| [DIMENSIONS](#^dimensions) | The 35 rows, in the design doc's order |
| [BY_ID](#^by-id) | Id to dimension |
| [GLYPH](#^glyph-map) | Status to glyph |
| [TESTS_DIR](#^tests-dir) | `tests/capabilities/` |
| [scan](#^scan) | Id to the tests that claim it |
| [phrases](#^phrases) | Test to its docstring sentence |
| [undocumented](#^undocumented) | Proving tests with no sentence |
| [matrix](#^matrix) | Each dimension with its tests |
| [unknown_ids](#^unknown-ids) | Ids no dimension carries |
| [check](#^check) | Built or partial with no test |
| [check_phrases](#^check-phrases) | Alias of `undocumented` |
| [glyph](#^glyph) | The glyph a row shows |
| [render_markdown](#^render-markdown) | The generated status table |
| [render_text](#^render-text) | The terminal listing |

**Dimension**`(id: str, group: str, title: str, status: str)` (frozen dataclass)
    `status` is one of `built`, `partial`, `planned`, `future`; anything else raises `ValueError` at construction, which is at import for the table. ^dimension

**DIMENSIONS**`: tuple[Dimension, ...]`
    A1–A5 (core substrate), B1–B18 (generation and control knobs), C1–C11 (measurement and scoring), I1 (mass trials and the reliability map). At `038c399`: 30 built, 2 partial (C3, C7), 1 planned (B16), 2 future (B18, C11). Edited by hand when a dimension's status changes. ^dimensions

**BY_ID**`: Mapping[str, Dimension]`
    `{d.id: d}`. ^by-id

**GLYPH**`: Mapping[str, str]`
    `built` ✅, `partial` 🟡, `planned` ⬜, `future` 🔮; `MISSING_GLYPH` ❌ marks a built or partial row with no test. ^glyph-map

**TESTS_DIR**`: Path`
    `REPO_ROOT / "tests" / "capabilities"`, where `REPO_ROOT` is two levels above the package directory: the repository in a source checkout, an unrelated directory in an installed package (§ [Where the tests are](#where-the-tests-are)). ^tests-dir

**scan**`(tests_dir=None) -> dict[str, list[str]]`
    Parses every `test_*.py` in the folder (not recursively) with `ast` and, for every function named `test_*` at any depth, collects the string arguments of a decorator call named `capability` (`@capability("A1", "B2")` or `@pytest.mark.capability(...)`). Returns `{id: ["module::test", …]}`. An `async def`, a decorator argument that is not a string literal, or a decorator under another name is invisible. ^scan

**phrases**`(tests_dir=None) -> dict[str, str]`
    For every decorated test, the first paragraph of its docstring collapsed to one line; `""` when it has none. The sentence `bio report` prints beside the dimension. ^phrases

**undocumented**`(tests_dir=None) -> list[str]`
    Sorted decorated tests whose phrase is empty. ^undocumented

**matrix**`(tests_dir=None) -> list[tuple[Dimension, list[str]]]`
    Every dimension in table order with the tests that claim it, `[]` for none. ^matrix

**unknown_ids**`(tests_dir=None) -> list[str]`
    Ids some test claims that no dimension carries (a typo, or a retired id). ^unknown-ids

**check**`(tests_dir=None) -> list[str]`
    The ids of built or partial dimensions with no claiming test; empty means the gate passes this part. ^check

**check_phrases**`(tests_dir=None) -> list[str]`
    `undocumented(tests_dir)`, under the name the CLI uses. ^check-phrases

**glyph**`(d: Dimension, tests) -> str`
    ❌ for a built or partial dimension with no test, else its status glyph. ^glyph

**render_markdown**`(tests_dir=None) -> str`
    `| Id | Dimension | Status | Proven by |` with one row per dimension; proof is the test names in backticks, `—` for planned or future with none, `**no test**` otherwise. ^render-markdown

**render_text**`(tests_dir=None) -> str`
    One line per dimension (`id glyph status title`) followed by its tests, indented. ^render-text



## test_matrix_cmd Interface
`bio test-matrix [--markdown] [--check]`.

| test_matrix_cmd | |
| --- | --- |
| [test_matrix_command](#^test-matrix-command) | Print the matrix; gate it on `--check` |

**test_matrix_command**`(args: list[str], verbose: bool = False) -> int`
    Any token other than `--markdown` or `--check` prints the module docstring to stderr and returns 2 (so does `--help`). Prints `render_markdown()` with `--markdown`, else `render_text()`. With `--check`, also runs `check`, `unknown_ids` and `check_phrases`; any non-empty result prints a `capability gate: …` line per kind to stderr and returns 1, else prints that every built or partial dimension is proven and returns 0. ^test-matrix-command




# Capabilities Semantics

## What the gate refuses
`bio test-matrix --check` fails on three things: a built or partial dimension no test claims, a test claiming an id the table does not have, and a claiming test with no docstring sentence. A planned or future dimension may have a test or not; the module docstring's "may not" means need not. At `038c399` the gate is green: 32 dimensions carry exactly one proving test each and the three without one are B16, B18 and C11.



## A static scan
The scan reads source, so it knows a test is decorated, not whether it ran. A proving test marked `skip`, guarded by `skipif` (the `needs_jax` guard in `test_simulator_conformance.py`), or `xfail` still satisfies the gate, and a dimension whose only test always skips shows as proven here; `bio report` is where the outcome appears, as ⏭ beside the row. No proving test is skip-guarded at `038c399`.



## Where the tests are
`TESTS_DIR` is computed from the module's own file, two directories up. In a source checkout with the editable install `uv sync` makes, that is the repository root. In an installed wheel it is a directory under the environment's `lib/`, where no `tests/capabilities/` exists; `Path.glob` on a missing directory returns nothing, so every built dimension reads `**no test**` and `--check` fails, with no message saying the folder was not found.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `038c399` (read from a `git archive` export, a concurrent worker editing `src/`), with `tests/capabilities/conftest.py` read for the marker. Checked locally against the export: the matrix over that commit's tests (32 claimed, `check`, `unknown_ids` and `check_phrases` all empty), and `check` against a missing folder returning every built id. The dimension counts are from `DIMENSIONS` at that commit. Findings filed on T088.
