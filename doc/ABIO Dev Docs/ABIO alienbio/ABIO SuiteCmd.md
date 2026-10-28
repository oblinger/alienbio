---
description: "`commands/suite_cmd`: the `bio suite` verb — `run` (and its `--dry` preflight printout), `resume`, `aggregate`, `report` and `models`, each a thin call into the experiment pipeline, with the parser, the printed plan and the exit codes. Source: `src/alienbio/commands/suite_cmd.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO SuiteCmd](ha://p/ABIO%20SuiteCmd) 
# ABIO SuiteCmd
The page for the `bio suite` verb: what each of its five subverbs calls in the experiment pipeline, what `--dry` prints and when it refuses, and what reaches the terminal and the exit code.

![ABIO SuiteCmd](ABIO%20SuiteCmd.svg) 
*The dry run* is the topic behind the `--dry` branch: it runs the same `preflight` the real run raises from, prints every verdict, and creates nothing; *What reaches the terminal* governs the ‡ on `run`, which prints nothing without `-v` and returns 0 even when the cost ceiling stopped the grid.

`suite_cmd.py` is the only verb module with logic of its own, so it has a page; it is reached from the front door ([ABIO CLI](ABIO%20CLI.md)). Everything it runs lives in `alienbio.suite`: the spec and its loader on [ABIO ExperimentSpec](../ABIO%20suite/ABIO%20ExperimentSpec.md), the guards and `preflight` on [ABIO Guards](../ABIO%20suite/ABIO%20Guards.md), the record store and manifest on [ABIO Store](../ABIO%20suite/ABIO%20Store.md), the grid on [ABIO MassTrialRunner](../ABIO%20suite/ABIO%20MassTrialRunner.md), the model snapshot on [ABIO LLMAgent](../ABIO%20suite/ABIO%20LLMAgent.md). It imports through the `suite.experiment` facade plus two private helpers of `suite/store.py`. The run directory's files are described on [ABIO Suite Runtime](../../ABIO%20Architecture/ABIO%20Suite%20Runtime.md).



## suite_cmd Interface
One public function and the five handlers it dispatches to. Every handler takes plain values from the parsed namespace and returns an exit code.

| suite_cmd | |
| --- | --- |
| [suite_command](#^suite-command) | Parse and dispatch one subverb |
| [SUITE_USAGE](#^suite-usage) | The one-line usage string |
| [_parser](#^parser) | One argparse subparser per subverb |
| [_run](#^run) | `run`, or the `--dry` printout |
| [_resume](#^resume) | Resume from the manifest's own spec |
| [_aggregate_cmd](#^aggregate-cmd) | Rebuild `map.json` / `map.csv` |
| [_report_cmd](#^report-cmd) | Print and rewrite `report.txt`, draw `key.png` |
| [_models_cmd](#^models-cmd) | Refresh the model-id snapshot |

**suite_command**`(args: list[str], verbose: bool = False) -> int`
    Parses `args`; an argparse error or `--help` returns argparse's code (2 or 0) after argparse printed. No subverb prints the usage to stderr and returns 2. `verbose` is the front door's flag ORed with the subverb's `-v`. A `FileNotFoundError`, `FileExistsError` or `ValueError` from a handler prints `Error: …` to stderr and returns 1; any other exception propagates as a traceback. ^suite-command

**SUITE_USAGE**`: str`
    `"bio suite run <spec.yaml> [--out DIR] [--dry] [-v] | resume <DIR> | aggregate <DIR> | report <DIR> | models"`. Kept for callers; the parser builds its own usage. ^suite-usage

**_parser**`() -> argparse.ArgumentParser`
    `prog="bio suite"`, the module docstring as description, and a subparser each for `run` (`spec`, `--out DIR`, `--dry`), `resume`, `aggregate` and `report` (`dir`), and `models`, every one with `-v/--verbose`. An unknown flag is an error (T057: the hand loop it replaced ran `--dryy` on a live spec). ^parser

**_run**`(spec_path, out_dir, dry, verbose) -> int`
    `load_spec(spec_path)`. With `--dry`, runs `preflight(spec, out_dir=out_dir, resume=False)` and prints the plan (§ [The dry run](#the-dry-run)), returning 1 when a check refused and 0 otherwise. Without it, calls `run_experiment(spec, out_dir=out_dir, resume=False, progress=…)`, printing progress lines only under `-v`, ignores the returned map and returns 0. A run directory that already holds records raises `FileExistsError` (exit 1); `bio suite run` never resumes. ^run

**_resume**`(out_dir, verbose) -> int`
    Reads `<DIR>/manifest.json` through `store.read_manifest`, rebuilds the spec with `spec_from_dict(manifest["spec"])` and calls `run_experiment(..., resume=True)`. A missing manifest is `FileNotFoundError`. Because the spec comes from the manifest, a resume cannot drift from the original run, and it cannot pick up an edited YAML either. ^resume

**_aggregate_cmd**`(out_dir, verbose) -> int`
    `aggregate(out_dir)` from the record store alone, then writes `map.json` and `map.csv` beside it. ^aggregate-cmd

**_report_cmd**`(out_dir, verbose) -> int`
    Requires the manifest; rebuilds the map with `aggregate`, renders it with `render_report(rmap, manifest)`, prints the text, writes `report.txt`, and draws the run's key figure with `plots.write_key_figure`, honouring the spec's `key_readout`. ^report-cmd

**_models_cmd**`(verbose) -> int`
    `llm_agent.fetch_models_snapshot()` (the provider's model list, no tokens) and `write_models_snapshot`, which writes `suite/models_snapshot.json` inside the package; prints each id with its creation date. With no API key it raises `RuntimeError`, which the dispatcher does not catch. ^models-cmd




# SuiteCmd Semantics

## The dry run
`--dry` loads the spec, runs every preflight check in `PREFLIGHT_CHECKS` order, and prints, in order: `name`, `conditions` (the product of the axis lengths), `trials planned` (conditions × `trials_per_condition`), `drafter`, `agent`, `model` (the swept levels, or the single model the manifest would record, `PINNED_MODEL` on a live arm with no `model:`), `out_dir`, one line per check (`ok`, `REFUSED — why`, `skipped (an earlier check refused)`, or `resume: skipped (not a resume)`), the cost estimate (unavailable when pricing refused, `$0.00, no llm arm`, or the dollar figure with its formula), the cost ceiling, and finally `preflight: ok` or `preflight: REFUSED — <first refusal>`. It creates nothing: `preflight` resolves the output directory exactly as the run would and only reads it.



## What reaches the terminal
A run without `-v` prints nothing and exits 0 once `run_experiment` returns, whether the grid finished or stopped at the cost ceiling (`manifest["stopped_reason"] == "cost_ceiling"`): `_run` discards the returned map. The run's account is on disk, in `report.txt`, `map.json` and the manifest. `bio suite report <DIR>` prints it afterwards.



## Errors and exit codes

| Exit | When |
| --- | --- |
| 0 | the subverb finished; `--dry` found every check ok; `--help` |
| 1 | `--dry` refused; a `FileNotFoundError`, `FileExistsError` or `ValueError` (a refused preflight, a spec that does not load, records already present, no manifest) |
| 2 | no subverb; an argparse usage error |
| traceback | any other exception: no API key on `models`, a provider error, a defect |




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `038c399` (read from a `git archive` export, a concurrent worker editing `src/`), with `suite/guards.py`'s `Preflight` and `preflight`, `suite/experiment.py`'s `run_experiment` and `suite/llm_agent.py`'s snapshot functions read beside it. Checked locally against the export with no network and no key: a malformed YAML, a spec with no `!experiment`, a missing file and an `aggregate` on a directory with no manifest each exit 1 with `Error: …`; `models` with no key raises `RuntimeError` uncaught. No run was started. Findings filed on T088.
- 2026-10-28 — T088 bio and operator round: `-v` is accepted between `suite` and its verb; `bio suite models` without a key (or on a provider error) is `Error: …`, exit 1; a cost-ceiling stop prints one stderr line (exit stays 0); a spec load error names its path once.
