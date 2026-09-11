"""run / resume / aggregate / report a declared experiment; models refreshes the pin snapshot.

Usage:
    bio suite run <spec.yaml> [--out DIR] [--dry] [-v]   # Run (or dry-preview) an ExperimentSpec
    bio suite resume <DIR>                          # Resume a crashed/partial run
    bio suite aggregate <DIR>                       # Rebuild map.json/map.csv from records.jsonl alone
    bio suite report <DIR>                          # Print + rewrite report.txt (and key.png) from the record store
    bio suite models                                # Refresh the recorded models.list snapshot (T016; free)

See ``alienbio.suite.experiment`` for the spec format, the ``DRAFTERS``/
``AGENTS`` registries, and the no-peeking guard.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from alienbio.suite.experiment import (
    aggregate,
    load_spec,
    preflight,
    render_report,
    run_experiment,
    spec_from_dict,
)


SUITE_USAGE = (
    "bio suite run <spec.yaml> [--out DIR] [--dry] [-v] | resume <DIR> | "
    "aggregate <DIR> | report <DIR> | models"
)


def _parser() -> argparse.ArgumentParser:
    """One argparse parser per verb (T057 proposal 7). The hand-rolled loop
    this replaces sent any unknown token to the positional list, so
    ``--dryy`` on a live spec ran it for real, a bare ``--out`` became "no
    ``--out``", and ``-v`` after the verb was silently lost."""
    parser = argparse.ArgumentParser(prog="bio suite", description=__doc__, add_help=True,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    verbs = parser.add_subparsers(dest="verb", metavar="run|resume|aggregate|report|models")

    def verbose(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("-v", "--verbose", action="store_true", help="per-trial progress")

    run = verbs.add_parser("run", help="run (or --dry preview) an ExperimentSpec")
    run.add_argument("spec", help="path to the experiment .yaml")
    run.add_argument("--out", metavar="DIR", help="run directory (default: runs/<name>)")
    run.add_argument("--dry", action="store_true", help="print the plan and every preflight verdict; run nothing")
    verbose(run)
    for verb, doc in (
        ("resume", "resume a crashed or partial run from its manifest"),
        ("aggregate", "rebuild map.json/map.csv from records.jsonl alone"),
        ("report", "print and rewrite report.txt (and key.png) from the record store"),
    ):
        sub = verbs.add_parser(verb, help=doc)
        sub.add_argument("dir", help="the run directory")
        verbose(sub)
    verbose(verbs.add_parser("models", help="refresh the recorded models.list snapshot (free)"))
    return parser


def suite_command(args: list[str], verbose: bool = False) -> int:
    """Dispatch ``bio suite <verb> ...`` to its handler.

    Args:
        args: Command arguments ``[verb, ...]``.
        verbose: Enable verbose (per-trial progress) output.

    Returns:
        Exit code (0 success, 1 a reported user error, 2 bad usage).
    """
    parser = _parser()
    try:
        ns = parser.parse_args(args)
    except SystemExit as exc:  # argparse already printed usage + the error
        return int(exc.code or 0)
    if ns.verb is None:
        parser.print_usage(sys.stderr)
        return 2
    verbose = verbose or bool(getattr(ns, "verbose", False))
    try:
        if ns.verb == "run":
            return _run(ns.spec, ns.out, ns.dry, verbose)
        if ns.verb == "resume":
            return _resume(ns.dir, verbose)
        if ns.verb == "aggregate":
            return _aggregate_cmd(ns.dir, verbose)
        if ns.verb == "report":
            return _report_cmd(ns.dir, verbose)
        return _models_cmd(verbose)
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _run(spec_path: str, out_dir: Optional[str], dry: bool, verbose: bool) -> int:
    spec = load_spec(spec_path)
    grid_size = 1
    for _name, levels in spec.axes:
        grid_size *= len(levels)
    trials_planned = grid_size * spec.trials_per_condition

    if dry:
        # T057 — the same preflight the run makes, every verdict printed;
        # exit 1 when the run would refuse (it used to print two of the
        # guards and exit 0 on a spec the run then refused).
        flight = preflight(spec, out_dir=out_dir)
        print(f"name: {spec.name}")
        print(f"conditions: {grid_size}")
        print(f"trials planned: {trials_planned}")
        print(f"drafter: {spec.drafter}")
        print(f"agent: {spec.agent}")
        print(f"model: {spec.model}")
        print(f"out_dir: {flight.out_dir}")
        for line in flight.lines():
            print(line)
        estimate = flight.estimate
        if estimate is None:
            print("estimated cost: unavailable (pricing refused above)")
        elif estimate.llm_trials == 0:
            print("estimated cost: $0.00, no llm arm")
        else:
            print(
                f"estimated cost: ${estimate.usd:.4f} for {estimate.llm_trials} llm "
                f"trials x {estimate.turns_per_trial} turns — {estimate.formula}"
            )
        ceiling = spec.cost_ceiling_usd
        print(f"cost ceiling: {'none' if ceiling is None else f'${ceiling:.4f}'}")
        if not flight.ok:
            print(f"preflight: REFUSED — {flight.refusal}")
            return 1
        print("preflight: ok")
        return 0

    def progress(message: str) -> None:
        if verbose:
            print(message)

    run_experiment(spec, out_dir=out_dir, progress=progress)
    return 0


def _resume(out_dir: str, verbose: bool) -> int:
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


def _aggregate_cmd(out_dir: str, verbose: bool) -> int:
    rmap = aggregate(out_dir)
    (Path(out_dir) / "map.json").write_text(rmap.to_json())
    (Path(out_dir) / "map.csv").write_text(rmap.to_csv())
    if verbose:
        print(f"wrote map.json/map.csv to {out_dir}")
    return 0


def _report_cmd(out_dir: str, verbose: bool) -> int:
    manifest_path = Path(out_dir) / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"bio suite report: no manifest.json in {out_dir}")

    manifest = json.loads(manifest_path.read_text())
    rmap = aggregate(out_dir)
    text = render_report(rmap, manifest)
    print(text)
    (Path(out_dir) / "report.txt").write_text(text)
    from alienbio.suite.plots import write_key_figure

    png = write_key_figure(rmap, out_dir, readout=(manifest.get("spec") or {}).get("key_readout"))
    if png is not None and verbose:
        print(f"bio suite report: wrote {png}")
    return 0


def _models_cmd(verbose: bool) -> int:
    """``bio suite models`` — refresh the recorded ``models.list`` snapshot
    that lets an undated generation id count as pinned (T016)."""
    del verbose
    from ..suite.llm_agent import fetch_models_snapshot, write_models_snapshot

    models = fetch_models_snapshot()
    path = write_models_snapshot(models)
    for model_id, created in models.items():
        print(f"{model_id}  {created}")
    print(f"{len(models)} models recorded -> {path}")
    return 0
