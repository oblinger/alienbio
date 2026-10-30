---
description: "`commands/suite_cmd`: the `bio suite` verb — `run` (and its `--dry` preflight printout), `resume`, `aggregate`, `report` and `models`, each a thin call into the experiment pipeline, with the parser, the printed plan and the exit codes. Source: `src/alienbio/commands/suite_cmd.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO SuiteCmd](ha://p/ABIO%20SuiteCmd) 
# ABIO SuiteCmd
The page for the `bio suite` verb: what each of its five subverbs calls in the experiment pipeline, what `--dry` prints and when it refuses, and what reaches the terminal and the exit code.

![ABIO SuiteCmd](ABIO%20SuiteCmd.svg) 
*The dry run* is the topic behind the `--dry` branch: it runs the same `preflight` the real run raises from, prints every verdict, and creates nothing; *What reaches the terminal* governs the ‡ on `run`, which without `-v` prints only a stop line when the cost ceiling ended the grid, and returns 0 either way.

`suite_cmd.py` is the only verb module with logic of its own, so it has a page; it is reached from the front door ([ABIO CLI](ABIO%20CLI.md)). Everything it runs lives in `alienbio.suite`: the spec and its loader on [ABIO ExperimentSpec](../ABIO%20suite/ABIO%20ExperimentSpec.md), the guards and `preflight` on [ABIO Guards](../ABIO%20suite/ABIO%20Guards.md), the record store and manifest on [ABIO Store](../ABIO%20suite/ABIO%20Store.md), the grid on [ABIO MassTrialRunner](../ABIO%20suite/ABIO%20MassTrialRunner.md), the model snapshot on [ABIO LLMAgent](../ABIO%20suite/ABIO%20LLMAgent.md). It imports through the `suite.experiment` facade plus two private helpers of `suite/store.py` and `resolved_out_dir` from `suite/guards.py`. The run directory's files are described on [ABIO Suite Runtime](../../ABIO%20Architecture/ABIO%20Suite%20Runtime.md).



## suite_cmd Interface
One public function, the five handlers it dispatches to, and the two helpers the read-only handlers share. Every handler takes plain values from the parsed namespace and returns an exit code.

| suite_cmd | |
| --- | --- |
| [suite_command](#^suite-command) | Parse and dispatch one subverb |
| [SUITE_USAGE](#^suite-usage) | The one-line usage string |
| [_parser](#^parser) | One argparse subparser per subverb |
| [_run](#^run) | `run`, or the `--dry` printout |
| [_resume](#^resume) | Resume from the experiment file as it is now |
| [_aggregate_cmd](#^aggregate-cmd) | Rebuild `map.json` / `map.csv` |
| [_report_cmd](#^report-cmd) | Print and rewrite `report.txt`, draw `key.png` |
| [_models_cmd](#^models-cmd) | Refresh the model-id snapshot |
| [_recorded](#^recorded) | Manifest and recorded spec for a read |
| [_recorded_notes](#^recorded-notes) | Header lines naming broken run-only rules |
| [_report_stop](#^report-stop) | One stderr line for a ceiling stop |

**suite_command**`(args: list[str], verbose: bool = False) -> int`
    Parses `args`; an argparse error or `--help` returns argparse's code (2 or 0) after argparse printed. No subverb prints the usage to stderr and returns 2. `verbose` is the front door's flag ORed with a `-v` placed between `suite` and the subverb (the suite parser's own `verbose_suite`) and the subverb's `-v`. A `FileNotFoundError`, `FileExistsError` or `ValueError` from a handler prints `Error: …` to stderr and returns 1; any other exception propagates as a traceback. ^suite-command

**SUITE_USAGE**`: str`
    `"bio suite run <spec.yaml> [--out DIR] [--dry] [-v] | resume <DIR> | aggregate <DIR> | report <DIR> | models"`. Kept for callers; the parser builds its own usage. ^suite-usage

**_parser**`() -> argparse.ArgumentParser`
    `prog="bio suite"`, the module docstring as description, a suite-level `-v/--verbose` (dest `verbose_suite`, so `bio suite -v run x.yaml` works), and a subparser each for `run` (`spec`, `--out DIR`, `--dry`), `resume`, `aggregate` and `report` (`dir`), and `models`, every one with `-v/--verbose`. An unknown flag is an error (T057: the hand loop it replaced ran `--dryy` on a live spec). ^parser

**_run**`(spec_path, out_dir, dry, verbose) -> int`
    `load_spec(spec_path)`. With `--dry`, runs `preflight(spec, out_dir=out_dir, resume=R)`, `R` true when `guards.resolved_out_dir(spec, out_dir)` already holds `records.jsonl` (a resume preview, T091 Y7), and prints the plan (§ [The dry run](#the-dry-run)), returning 1 when a check refused and 0 otherwise. Without it, calls `run_experiment(spec, out_dir=out_dir, resume=False, progress=…)`, printing progress lines only under `-v`, hands the returned map to `_report_stop` and returns 0. A run directory that already holds records raises `FileExistsError` (exit 1); `bio suite run` never resumes. ^run

**_resume**`(out_dir, verbose) -> int`
    Reads `<DIR>/manifest.json` through `store.read_manifest`, rebuilds the spec with `spec_from_manifest(manifest, current=True)` and calls `run_experiment(..., resume=True, notes=print)`, then `_report_stop` against the manifest's `trials_planned`. When the manifest names a `spec_path`, that file is re-loaded as it is now (its `_includes_` helpers registered), so an edit to it is caught by the resume's drift check; a resume always reloads it, and a recorded path that no longer exists refuses, naming it. A Python-built spec (no `spec_path`) is read from the manifest's `spec`. The resume's `preflight` then refuses a store stamped with another `world_scheme`, or whose recorded worlds this code no longer re-drafts identically ([ABIO Guards](../ABIO%20suite/ABIO%20Guards.md) § Resume and the seed scheme); an unstamped store that passes is stamped, and the note saying so prints without `-v` through the `notes=` callback (T091 Y7; progress lines still need `-v`). The resume is strict: the spec is validated with `validation="run"`, so a rule the run predates refuses here though `aggregate` and `report` only note it. A missing manifest is `FileNotFoundError`. ^resume

**_aggregate_cmd**`(out_dir, verbose) -> int`
    `_recorded(out_dir, "aggregate")`, prints `_recorded_notes(spec)` to stderr, then `aggregate(out_dir, spec=spec)` from the record store alone and writes `map.json` and `map.csv` beside it. The recorded spec runs the manifest's `helper_modules` directly and never re-reads the yaml, so a deleted, moved or edited experiment file still aggregates; a missing or out-of-catalog helper refuses, naming it. ^aggregate-cmd

**_report_cmd**`(out_dir, verbose) -> int`
    `_recorded(out_dir, "report")`, rebuilds the map with `aggregate(out_dir, spec=spec)`, renders it with `render_report(rmap, manifest)` below the `_recorded_notes(spec)` lines, prints the text, writes it to `report.txt`, and draws the run's key figure with `plots.write_key_figure`, honouring the spec's `key_readout`. ^report-cmd) | Print and rewrite `report.txt`, draw `key.png` |
| [_models_cmd](#^models-cmd) | Refresh the model-id snapshot |
| [_recorded](#^recorded) | Manifest and recorded spec for a read |
| [_recorded_notes](#^recorded-notes) | Header lines naming broken run-only rules |
| [_report_stop](#^report-stop) | One stderr line for a ceiling stop |

**suite_command**`(args: list[str], verbose: bool = False) -> int`
    Parses `args`; an argparse error or `--help` returns argparse's code (2 or 0) after argparse printed. No subverb prints the usage to stderr and returns 2. `verbose` is the front door's flag ORed with a `-v` placed between `suite` and the subverb (the suite parser's own `verbose_suite`) and the subverb's `-v`. A `FileNotFoundError`, `FileExistsError` or `ValueError` from a handler prints `Error: …` to stderr and returns 1; any other exception propagates as a traceback. ^suite-command

**SUITE_USAGE**`: str`
    `"bio suite run <spec.yaml> [--out DIR] [--dry] [-v] | resume <DIR> | aggregate <DIR> | report <DIR> | models"`. Kept for callers; the parser builds its own usage. ^suite-usage

**_parser**`() -> argparse.ArgumentParser`
    `prog="bio suite"`, the module docstring as description, a suite-level `-v/--verbose` (dest `verbose_suite`, so `bio suite -v run x.yaml` works), and a subparser each for `run` (`spec`, `--out DIR`, `--dry`), `resume`, `aggregate` and `report` (`dir`), and `models`, every one with `-v/--verbose`. An unknown flag is an error (T057: the hand loop it replaced ran `--dryy` on a live spec). ^parser

**_run**`(spec_path, out_dir, dry, verbose) -> int`
    `load_spec(spec_path)`. With `--dry`, runs `preflight(spec, out_dir=out_dir, resume=R)`, `R` true when `guards.resolved_out_dir(spec, out_dir)` already holds `records.jsonl` (a resume preview, T091 Y7), and prints the plan (§ [The dry run](#the-dry-run)), returning 1 when a check refused and 0 otherwise. Without it, calls `run_experiment(spec, out_dir=out_dir, resume=False, progress=…)`, printing progress lines only under `-v`, hands the returned map to `_report_stop` and returns 0. A run directory that already holds records raises `FileExistsError` (exit 1); `bio suite run` never resumes. ^run

**_resume**`(out_dir, verbose) -> int`
    Reads `<DIR>/manifest.json` through `store.read_manifest`, rebuilds the spec with `spec_from_manifest(manifest, current=True)` and calls `run_experiment(..., resume=True, notes=print)`, then `_report_stop` against the manifest's `trials_planned`. When the manifest names a `spec_path`, that file is re-loaded as it is now (its `_includes_` helpers registered), so an edit to it is caught by the resume's drift check; a resume always reloads it, and a recorded path that no longer exists refuses, naming it. A Python-built spec (no `spec_path`) is read from the manifest's `spec`. The resume's `preflight` then refuses a store stamped with another `world_scheme`, or whose recorded worlds this code no longer re-drafts identically ([ABIO Guards](../ABIO%20suite/ABIO%20Guards.md) § Resume and the seed scheme); an unstamped store that passes is stamped, and the note saying so prints without `-v` through the `notes=` callback (T091 Y7; progress lines still need `-v`). The resume is strict: the spec is validated with `validation="run"`, so a rule the run predates refuses here though `aggregate` and `report` only note it. A missing manifest is `FileNotFoundError`. ^resume

**_aggregate_cmd**`(out_dir, verbose) -> int`
    `aggregate(out_dir)` from the record store alone, using the manifest's own spec (`spec_from_manifest`, which reloads the named spec file only when the manifest lists `helper_modules`, to register them, and then refuses one that is missing; without helpers a deleted, moved or edited yaml still aggregates), then writes `map.json` and `map.csv` beside it. ^aggregate-cmd

**_report_cmd**`(out_dir, verbose) -> int`
    Requires the manifest; rebuilds the map with `aggregate` (the manifest's own spec, as above), renders it with `render_report(rmap, manifest)`, prints the text, writes `report.txt`, and draws the run's key figure with `plots.write_key_figure`, honouring the spec's `key_readout`. ^report-cmd

**_models_cmd**`(verbose) -> int`
    `llm_agent.fetch_models_snapshot()` (the provider's model list, no tokens) and `write_models_snapshot`, which writes `suite/models_snapshot.json` inside the package; prints each id with its creation date. A missing key (`RuntimeError`) and any provider error (auth, network) are re-raised as `ValueError`, so the dispatcher prints `Error: …` and returns 1. ^models-cmd

**_recorded**`(out_dir: str, verb: str) -> tuple[dict, ExperimentSpec]`
    Reads `<DIR>/manifest.json` (`FileNotFoundError` naming the verb when absent) and returns it with `spec_from_manifest(manifest)`: `current=False`, so the spec is built with `validation="recorded"` and a run-only rule the run predates lands on `spec.recorded_warnings` rather than refusing (T091 Y2). ^recorded

**_recorded_notes**`(spec) -> list[str]`
    `[]` when `spec.recorded_warnings` is empty; else a heading line (`Recorded-spec notes — rules this run predates (read here as notes; a resume refuses them):`), one `  - <message>` per warning, and a blank line. ^recorded-notes

**_report_stop**`(rmap, trials_planned: int) -> None`
    When `rmap.provenance.stopped_early`, prints `bio suite: stopped early (cost_ceiling) after N of M trials; see manifest.json stopped_reason` to stderr. The exit code stays 0: the run did what its spec said. ^report-stop




# SuiteCmd Semantics

## The dry run
`--dry` loads the spec, runs every preflight check in `PREFLIGHT_CHECKS` order, and prints, in order: `name`, `conditions` (the product of the axis lengths), `trials planned` (conditions × `trials_per_condition`), `drafter`, `agent`, `model` (the swept levels, or the single model the manifest would record, `PINNED_MODEL` on a live arm with no `model:`), `out_dir`, one line per check (`ok`, `REFUSED — why`, `skipped (an earlier check refused)`, or `resume: skipped (not a resume)`) followed by any check's note, the cost estimate (unavailable when pricing refused, `$0.00, no llm arm`, or the dollar figure with its formula), the cost ceiling, and finally `preflight: ok` or `preflight: REFUSED — <first refusal>`. It creates nothing: `preflight` resolves the output directory exactly as the run would (`resolved_out_dir`) and only reads it. When that directory already holds `records.jsonl`, the first line is `preview: resume — <dir> already holds records.jsonl; …` and the checks run as `bio suite resume <DIR>` would run them (`records-readable`, `resume`, the re-draft check with its note), though `bio suite run` itself refuses the directory (T091 Y7).



## What reaches the terminal
A run without `-v` prints nothing and exits 0 once a grid finishes. One stopped at the cost ceiling (`manifest["stopped_reason"] == "cost_ceiling"`) also exits 0 but prints one stderr line naming the trials completed of those planned (`_report_stop`, on `run` and `resume`), so a partial grid is told from a finished one without `-v`. The run's account is on disk, in `report.txt`, `map.json` and the manifest. `bio suite report <DIR>` prints it afterwards. A resume prints a preflight note (the pre-stamp store being stamped) without `-v`; `aggregate` prints the recorded spec's notes to stderr, and `report` puts them at the top of the report and of `report.txt`.



## Errors and exit codes

| Exit | When |
| --- | --- |
| 0 | the subverb finished; `--dry` found every check ok; `--help` |
| 1 | `--dry` refused; a `FileNotFoundError`, `FileExistsError` or `ValueError` (a refused preflight, a spec that does not load, records already present, no manifest, no API key or a provider error on `models`) |
| 2 | no subverb; an argparse usage error |
| traceback | any other exception: a provider error mid-`run`, a defect |




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `038c399` (read from a `git archive` export, a concurrent worker editing `src/`), with `suite/guards.py`'s `Preflight` and `preflight`, `suite/experiment.py`'s `run_experiment` and `suite/llm_agent.py`'s snapshot functions read beside it. Checked locally against the export with no network and no key: a malformed YAML, a spec with no `!experiment`, a missing file and an `aggregate` on a directory with no manifest each exit 1 with `Error: …`; `models` with no key raises `RuntimeError` uncaught. No run was started. Findings filed on T088.
- 2026-10-28 — T088 bio and operator round: `-v` is accepted between `suite` and its verb; `bio suite models` without a key (or on a provider error) is `Error: …`, exit 1; a cost-ceiling stop prints one stderr line (exit stays 0); a spec load error names its path once.
- 2026-10-28 — refreshed against `0eb23e5`: the body states the round's outcome (`13298f0`) — suite-level `-v`, `models` refusals as `Error:` exit 1, the ceiling-stop stderr line (`_report_stop`, new member block); the figure's ‡ note updated.
- 2026-10-29 — refreshed against `661005d` (T091 E1): `_resume` reads `spec_from_manifest(manifest, current=True)` — the experiment file as it is now, so an edit is drift — while `aggregate`/`report` use the manifest's own spec; a missing spec file refuses naming the path. The figure's `_resume` box and side note were reworded to match.
- 2026-10-29 — refreshed for `fab20be` (T091 K E1): `aggregate` and `report` reload the yaml only when the manifest lists `helper_modules`; `resume` always reloads it and refuses when it is gone.
- 2026-10-29 — refreshed for `0ae30d6` and `b6d1607` (T091 R2, Y1): `_resume` names the seed-scheme and re-draft refusals and that the stamping note prints only under `-v`.
- 2026-10-29 — refreshed for `7fcdf33` (T091 Y2, Y7): `aggregate` and `report` read the recorded spec (`spec_from_manifest`, `validation="recorded"`) through the new `_recorded` and print its notes (`_recorded_notes`: stderr on aggregate, the report's head and `report.txt` on report); the resume stays strict and prints its re-draft note without `-v` (`notes=print`); `--dry` on a directory holding records previews the resume. Figure still true.
