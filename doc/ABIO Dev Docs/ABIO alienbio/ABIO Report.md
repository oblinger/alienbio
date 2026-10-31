---
description: "`report` + `commands/report_cmd`: `bio report` — one pytest run to JUnit, the four sections it lays out (the capability matrix with each proving test's sentence and outcome, the broader suites, the examples run fresh, the runs on disk), the verdict read off the page, and the Markdown and self-contained HTML it writes. Source: `src/alienbio/report.py`, `src/alienbio/commands/report_cmd.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO Report](ha://p/ABIO%20Report) 
# ABIO Report
The page for `bio report`: where each row's outcome and sentence come from, what the four sections hold, how the verdict in the title is decided, and what is written where.

![ABIO Report](ABIO%20Report.svg) 
*The JUnit file is the truth* is the topic behind the `parse_junit` box: every ✓ and ✗ on the page is read from one XML file, keyed by module stem and test name; *The verdict* governs the ‡ on `Report.ok`, which also requires every built or partial capability row and every broader-suite row to have passed.

`report.py` builds a `Report` and renders it twice; `report_cmd.py` is the verb, an `argparse` parser around one call sequence, kept on this page. The matrix and the sentences come from [ABIO Capabilities](ABIO%20Capabilities.md); the examples run through `suite.experiment.run_experiment` and the runs are read through `suite.store.read_manifest` ([ABIO Store](../ABIO%20suite/ABIO%20Store.md)); each run's key figure is the `key.png` that `bio suite report` draws ([ABIO SuiteCmd](ABIO%20SuiteCmd.md)). `just report` runs `bio report --open`; `just test` stays the gate and CI never runs this. The subsystem view is [ABIO-Operator-Surface](../../ABIO%20Architecture/ABIO-Operator-Surface.md).



## report Interface
Path constants, the outcome readers, four row builders, `build`, and the two renderers.

| report | |
| --- | --- |
| [REPO](#^repo) | Repository root and its subfolders |
| [SUITES](#^suites) | The broader suites listed in section 2 |
| [run_pytest](#^run-pytest) | Run the whole suite to JUnit |
| [count_cases](#^count-cases) | Totals, one per parametrized case |
| [count_module_cases](#^count-module-cases) | Case counts per module stem |
| [parse_junit](#^parse-junit) | Outcome per test function |
| [capability_rows](#^capability-rows) | Section 1 |
| [suite_rows](#^suite-rows) | Section 2 |
| [example_rows](#^example-rows) | Section 3, each example run fresh |
| [run_rows](#^run-rows) | Section 4, from `runs/*/manifest.json` |
| [build](#^build) | All four sections into a `Report` |
| [render_markdown](#^render-markdown) | The page as Markdown |
| [render_html](#^render-html) | The same page as one HTML file |

**REPO**`: Path`
    `Path(__file__).resolve().parents[2]`, with `TESTS`, `EXAMPLES = catalog/examples` and `RUNS = runs` under it. A source checkout is assumed, as for the capability matrix. ^repo

**SUITES**`: tuple[str, ...]`
    Eight test modules by path: every-head coverage, special forms, the adversarial sandbox corpus, simulator conformance, the CLI end to end, the executed spec examples, the golden experiments, the no-peeking lint. Their sentences are their module docstrings. ^suites

**run_pytest**`(junit_path: Path, extra_args=()) -> int`
    `python -m pytest tests -q -p no:cacheprovider -p alienbio._report_plugin --junitxml=<path>` in `REPO`, with the interpreter running `bio`; returns pytest's exit code. The plugin (`src/alienbio/_report_plugin.py`) records an `xpassed` property on a non-strict XPASS, which JUnit otherwise writes as a bare pass (T091 AE5). ^run-pytest

**count_cases**`(junit_path) -> dict[str, int]`
    `passed`, `failed` (failures and errors), `skipped`, `xfailed` and `xpassed`, counting every test case. JUnit writes an xfail as `<skipped type="pytest.xfail">`; it is counted apart from a skip, as pytest's summary line does (the header read `46 skipped` for 3 skips and 43 xfails until `9b66478`). A case carrying the plugin's `xpassed` property is counted apart from passed (the header read `3 passed` where pytest said `1 passed, 2 xpassed` until `76fa1d6`); a `--junit` file written without the plugin counts a non-strict XPASS as passed. These are the totals on the page. ^count-cases

**count_module_cases**`(junit_path) -> dict[str, dict[str, int]]`
    The same four counts per module stem (the last segment of `classname`), one per test case. `report_cmd` passes it to `build` as `case_counts` for section 2. Since `9b66478` (T091 U9). ^count-module-cases

**parse_junit**`(junit_path) -> dict[tuple[str, str], str]`
    `(module, name) → outcome` with `module` the last dotted segment of the case's `classname` and the parametrize suffix stripped from `name`, so the cases of one function collapse onto it and the worst wins (failed or error over passed over skipped). § [The JUnit file is the truth](#the-junit-file-is-the-truth). ^parse-junit

**capability_rows**`(outcomes) -> list[CapabilityRow]`
    One row per dimension: id, title, status, its tests, their docstring sentences joined (`—` for planned or future, `(no docstring sentence)` otherwise when empty), and an outcome: `no test`, `not run` when any proving test is missing from the JUnit file, `failed`, `skipped` when all skipped, else `passed`; `—` for a planned or future dimension with no test. ^capability-rows

**suite_rows**`(outcomes, case_counts=None) -> list[SuiteRow]`
    Passed, failed, skipped, xfailed and xpassed counts per `SUITES` module (by stem) and its docstring's first paragraph, a leading milestone tag (`M48.5 — `) removed. The counts are per test case from `case_counts`; without it (no JUnit file), one per function from `outcomes`. Until `9b66478` they were per function, so `test_golden_experiments.py` read `2 passed` for fifteen hashed zeros and its pin test. ^suite-rows

**example_rows**`(outcomes, runner=None) -> list[ExampleRow]`
    For each folder under `catalog/examples/` with a YAML file, runs `<folder>.yaml` (else its one `*.yaml`; several with none named after the folder is an `error` row) with `run_experiment` into a temporary directory, refusing a spec whose `estimate_cost` counts any live-model trial as an `error` row, and records trials, failed trials, the mean objective score over non-error records, wall time, the outcome of its `test_<folder>_example` module, and the first non-heading line of its README. An exception becomes an `error` row instead of stopping the report. `runner` is injectable for tests. ^example-rows

**run_rows**`(notes=None) -> list[RunRow]`
    For each `runs/<name>/manifest.json`: the model label (a live run has one, a scripted run none), trials completed and failed, the aborted trials (non-error lines of `records.jsonl` carrying `aborted` — a token-ceiling or parse-exhaustion abort; the manifest counts errors, not aborts; an unparsable line is not counted), `cost_usd_spent` from the manifest, the start date, and `key.png` with the readout and caption from `key.json` when present. Live runs sort first. A folder whose manifest or `key.json` will not read (`OSError`, `ValueError`, `TypeError`, `KeyError`) is skipped with a `runs/<name> skipped: …` line appended to `notes`. ^run-rows

**build**`(outcomes, pytest_exit, *, run_examples=True, example_runner=None, totals=None, case_counts=None, out_dir=None) -> Report`
    Assembles the four sections and the golden-zeros outcome (`test_golden_experiments`), stamps the time, records `out_dir` (default `REPO/reports`) and `examples_run`, passes `case_counts` to `suite_rows` and its `notes` to `run_rows`, and notes `--no-examples`. Raises `FileNotFoundError` when `tests/capabilities/` is missing. `totals` defaults to counting `outcomes`, which collapses parametrized cases; `report_cmd` passes `count_cases`. ^build

**render_markdown**`(rep: Report) -> str`
    The page: a title carrying the verdict, a totals line (passed, failed, skipped, xfailed, and `, N xpassed` when non-zero), then the four sections as tables, each run's key figure as an image link relative to `rep.out_dir`. The title is `ALL PASSED`, or the first failing reason: pytest's exit, the failed count, an example, else `NOT PROVEN (…)` naming the gaps joined by `; `: `N capability rows without a passing test`, `N suite rows not run`, `examples not run`. A section-4 row is ✅ only when nothing failed or aborted: a failure or no trials is ❌, an abort is ⚠ with `P passed, F failed, A aborted` in the trials cell, and a run whose every trial aborted reads `(all aborted)`, never ✅ (T091 Y6: an all-aborted live run read ✅ `0 failed`). ^render-markdown

**render_html**`(rep: Report) -> str`
    Converts the Markdown line by line (tables, headings, paragraphs, inline code, bold, italic), embedding each image as a base64 `data:` URI read from `rep.out_dir / <link>`, so `report.html` stands alone. ^render-html



## Report Interface
A dataclass of the four row lists, the totals and the pytest exit code. The row types are frozen dataclasses: `CapabilityRow`, `SuiteRow`, `ExampleRow`, `RunRow`.

| Report | |
| --- | --- |
| [ok](#^ok) | The verdict ‡ |
| [unproven](#^unproven) | Capability rows without a passing test |
| [unrun_suites](#^unrun-suites) | Broader-suite rows that did not run and pass |
| [notes](#^notes) | Footnotes printed at the end |
| [out_dir](#^out-dir) | Where `report.md` is written |
| [examples_run](#^examples-run) | False under `--no-examples` |

**ok**`: bool` (property)
    True when the pytest exit was 0, the totals show no failure, the examples ran (`examples_run`) each without an error or a failed trial, and `unproven` and `unrun_suites` are both empty (§ [The verdict](#the-verdict)). ^ok

**unproven**`: list[str]` (property)
    The ids of built or partial dimensions whose outcome is not `passed`: `not run`, `no test`, `failed`, or every proving test `skipped`. ^unproven

**unrun_suites**`: list[str]` (property)
    The module of every broader-suite row (section 2) with no passing case in the JUnit file, or with any failure. ^unrun-suites

**notes**`: list[str]`
    Printed in italics at the bottom; `build` adds one when examples were skipped, `run_rows` one per unreadable run folder. ^notes

**out_dir**`: Path = REPO / "reports"`
    The folder the Markdown lands in; figure links are made relative to it and the HTML resolves them against it. ^out-dir

**examples_run**`: bool = True`
    False under `--no-examples`: section 3 is empty, so the page cannot say every example ran clean; `ok` is False, the title reads `NOT PROVEN (examples not run)` and the command exits 1. Since `9b66478` (T091 U12). ^examples-run



## report_cmd Interface
`bio report [--open] [--no-examples] [--junit PATH] [--out DIR]`.

| report_cmd | |
| --- | --- |
| [report_command](#^report-command) | Run, build, write, print |

**report_command**`(args: list[str], verbose: bool = False) -> int`
    Parses the flags (argparse; a usage error returns 2). Creates `--out` (default `reports/` under `REPO`); without `--junit`, runs the suite to `<out>/junit.xml` and keeps pytest's exit code, with `--junit` uses that file and an exit code of 0. A missing JUnit file returns 1, as does a missing `tests/capabilities/` (printed as `bio report: …`). Builds the report with `out_dir` set to the output folder, writes `report.md` and `report.html` to the output folder, prints the Markdown to stdout, opens the HTML on macOS with `--open`, and returns 0 when `Report.ok`, else 1. `-v` is accepted by the front door and ignored. ^report-command




# Report Semantics

## The four sections

| Section | Rows | Sentence from | Outcome from |
| --- | --- | --- | --- |
| 1. Capability matrix | 35 dimensions | the proving test's docstring | JUnit, by `(stem, test)` |
| 2. Broader suites | the eight `SUITES` modules | the module docstring | JUnit, counted per stem |
| 3. Examples | each `catalog/examples/` folder | its README's first line | a fresh run, and its test module |
| 4. Runs on disk | each `runs/*` with a manifest | the manifest | trials and failures in the manifest, aborts from `records.jsonl` |

No sentence is kept in a list of its own; each lives beside the thing it describes, which is why `bio test-matrix --check` refuses a proving test with no docstring.



## The JUnit file is the truth
Outcomes are keyed by the last segment of `classname` and the bare test name. For a module-level test that segment is the module stem, which is how the matrix's `module::test` names match. Two cases do not match: a test method in a class (the segment is the class name, so its capability row reads `not run`), and two test modules sharing a stem in different folders (their outcomes merge, the worst winning). Neither occurs at `038c399`.



## The verdict
The title reads `ALL PASSED` when `Report.ok` holds, else names the reason (pytest's exit, the failed count, an example, or `NOT PROVEN`). A page written with `--no-examples` is `NOT PROVEN (examples not run)`, exit 1: it did not run the examples it would have to vouch for. `ok` reads the pytest exit, the totals, the examples and the capability rows, computed from what the page shows rather than from the exit code alone (T051 box 4). A built or partial row that did not pass — absent from the JUnit file, without a test, failed, or only skipped — makes the page `NOT PROVEN` and the exit 1, so a `--junit` file lacking the proving tests, or a pytest run that deselects them, no longer reads `ALL PASSED`. The broader suites are held the same way (T091 B6): a section-2 row with no passing case or with a failure is listed by `unrun_suites` and also titles the page `NOT PROVEN`, so a JUnit file holding only the capability tests does not read `ALL PASSED` beside `test_golden_experiments.py 0 passed`.



## Where it writes
`report.md` and `report.html` go to `--out` (default `reports/`), `junit.xml` too when the suite is run. Image links in the Markdown are computed relative to `--out` (`Report.out_dir`), so a page written anywhere links its figures correctly; the HTML resolves each link against the same folder and embeds the bytes. The examples run into temporary folders and leave nothing behind.



## Cost
Every example under `catalog/examples/` runs fresh: the spec named after its folder, else its only spec. A spec whose `estimate_cost` counts a live-model trial is refused as an `error` row before anything runs, so `bio report` spends nothing whatever the file names (`agent_loop/live.yaml` is never chosen: `agent_loop.yaml` is named after the folder).




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `038c399` (read from a `git archive` export, a concurrent worker editing `src/`), with the example folders listed at that commit. Checked locally against the export, with no pytest run: a one-test JUnit file building a report titled `ALL PASSED` with every capability row `not run`; a corrupt `manifest.json` under `runs/` raising `JSONDecodeError` out of `run_rows`; the figure link computed relative to `reports/`. Findings filed on T088.
- 2026-10-28 — T088 bio and operator round: `Report.ok` also requires every built / partial capability row to have passed (`Report.unproven`; title `NOT PROVEN (…)`, exit 1); an unreadable run folder is skipped with a `runs/<name> skipped: …` note; figure links are relative to `--out`; each example runs `<folder>.yaml` (else its one spec) and a spec with a live-model arm is an error row, never a paid run.
- 2026-10-28 — refreshed against `0eb23e5`: the body states the round's outcome (`13298f0`) — `Report.unproven` and `out_dir` (new member blocks), the `NOT PROVEN` title, `run_rows(notes)` skipping a bad run folder, figure links relative to `--out`, example selection by name with live specs refused; the figure's ‡ and notes updated.
- 2026-10-29 — refreshed against `342a77b` (T091 B6): `ALL PASSED` also requires every broader-suite row to have run and passed (`Report.unrun_suites`, new member block); otherwise `NOT PROVEN`, exit 1.
- 2026-10-29 — refreshed for `9b66478` (T091 U9, U12) and `113029c` (T091 Y6): section 2 and the totals count cases with xfails apart from skips (`count_module_cases`, `case_counts`); `--no-examples` titles `NOT PROVEN (examples not run)`, exit 1 (`examples_run`); a section-4 row counts aborted trials apart (⚠, `(all aborted)`). Figure still true.
- 2026-10-30 — refreshed for `76fa1d6` (T091 AE5): `run_pytest` loads `alienbio._report_plugin`; `count_cases`, the suite rows and the header count a non-strict XPASS as `xpassed`, the header showing `, N xpassed` when non-zero. Figure still true.
