"""suite command: run/resume/aggregate/report a declarative experiment sweep.

Usage:
    bio suite run <spec.yaml> [--out DIR] [--dry]   # Run (or dry-preview) an ExperimentSpec
    bio suite resume <DIR>                          # Resume a crashed/partial run
    bio suite aggregate <DIR>                       # Rebuild map.json/map.csv from records.jsonl alone
    bio suite report <DIR>                          # Print + rewrite report.txt from the record store

See ``alienbio.suite.experiment`` for the spec format, the ``DRAFTERS``/
``AGENTS`` registries, and the no-peeking guard.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from alienbio.suite.experiment import (
    NEUTRAL_DRAFTERS,
    aggregate,
    estimate_cost,
    load_spec,
    render_report,
    run_experiment,
    spec_from_dict,
)


def suite_command(args: list[str], verbose: bool = False) -> int:
    """Dispatch ``bio suite <verb> ...`` to its handler.

    Args:
        args: Command arguments ``[verb, ...]``.
        verbose: Enable verbose (per-trial progress) output.

    Returns:
        Exit code (0 success, 1 a reported user error, 2 bad usage).
    """
    if not args:
        _usage()
        return 2

    verb, rest = args[0], args[1:]
    try:
        if verb == "run":
            return _run(rest, verbose)
        if verb == "resume":
            return _resume(rest, verbose)
        if verb == "aggregate":
            return _aggregate_cmd(rest, verbose)
        if verb == "report":
            return _report_cmd(rest, verbose)
        _usage(f"unknown verb {verb!r}")
        return 2
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _usage(message: Optional[str] = None) -> None:
    if message:
        print(f"Error: {message}", file=sys.stderr)
    print(
        "Usage: bio suite run <spec.yaml> [--out DIR] [--dry] | "
        "resume <DIR> | aggregate <DIR> | report <DIR>",
        file=sys.stderr,
    )


def _run(rest: list[str], verbose: bool) -> int:
    out_dir: Optional[str] = None
    dry = False
    positional: list[str] = []

    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg == "--out" and i + 1 < len(rest):
            out_dir = rest[i + 1]
            i += 2
        elif arg == "--dry":
            dry = True
            i += 1
        else:
            positional.append(arg)
            i += 1

    if not positional:
        _usage("suite run requires a spec.yaml path")
        return 2

    spec = load_spec(positional[0])
    resolved_out = out_dir or spec.out_dir or f"runs/{spec.name}"
    grid_size = 1
    for _name, levels in spec.axes:
        grid_size *= len(levels)
    trials_planned = grid_size * spec.trials_per_condition
    no_peeking_ok = not (spec.agent == "llm" and spec.drafter not in NEUTRAL_DRAFTERS)

    if dry:
        print(f"name: {spec.name}")
        print(f"conditions: {grid_size}")
        print(f"trials planned: {trials_planned}")
        print(f"drafter: {spec.drafter}")
        print(f"agent: {spec.agent}")
        print(f"model: {spec.model}")
        print(f"out_dir: {resolved_out}")
        print("no-peeking: ok" if no_peeking_ok else "no-peeking: VIOLATION")
        estimate = estimate_cost(spec)
        if estimate.llm_trials == 0:
            print("estimated cost: $0.00, no llm arm")
        else:
            print(
                f"estimated cost: ${estimate.usd:.4f} for {estimate.llm_trials} llm "
                f"trials x {estimate.turns_per_trial} turns — {estimate.formula}"
            )
        ceiling = spec.cost_ceiling_usd
        print(f"cost ceiling: {'none' if ceiling is None else f'${ceiling:.4f}'}")
        return 0

    def progress(message: str) -> None:
        if verbose:
            print(message)

    run_experiment(spec, out_dir=out_dir, progress=progress)
    return 0


def _resume(rest: list[str], verbose: bool) -> int:
    if not rest:
        _usage("suite resume requires a run directory")
        return 2

    out_dir = rest[0]
    manifest_path = Path(out_dir) / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"bio suite resume: no manifest.json in {out_dir}")

    manifest = json.loads(manifest_path.read_text())
    spec = spec_from_dict(manifest["spec"])

    def progress(message: str) -> None:
        if verbose:
            print(message)

    run_experiment(spec, out_dir=out_dir, resume=True, progress=progress)
    return 0


def _aggregate_cmd(rest: list[str], verbose: bool) -> int:
    if not rest:
        _usage("suite aggregate requires a run directory")
        return 2

    out_dir = rest[0]
    rmap = aggregate(out_dir)
    (Path(out_dir) / "map.json").write_text(rmap.to_json())
    (Path(out_dir) / "map.csv").write_text(rmap.to_csv())
    if verbose:
        print(f"wrote map.json/map.csv to {out_dir}")
    return 0


def _report_cmd(rest: list[str], verbose: bool) -> int:
    if not rest:
        _usage("suite report requires a run directory")
        return 2

    out_dir = rest[0]
    manifest_path = Path(out_dir) / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"bio suite report: no manifest.json in {out_dir}")

    manifest = json.loads(manifest_path.read_text())
    rmap = aggregate(out_dir)
    text = render_report(rmap, manifest)
    print(text)
    (Path(out_dir) / "report.txt").write_text(text)
    return 0
