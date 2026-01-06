"""Report command: Run a scenario and create an Excel report.

This is the primary CLI command for running scenarios. It:
1. Runs the entity's run() method
2. Creates an Excel/CSV report with results
3. Opens the report file
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path
from typing import Any


def report_command(args: list[str], verbose: bool = False) -> int:
    """Run a scenario and create an Excel report.

    Args:
        args: Command arguments [path]
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from dvc_dat import Dat

    if not args:
        print("Error: report command requires a path", file=sys.stderr)
        print("Usage: bio report <path>", file=sys.stderr)
        return 1

    job_path = args[0]
    path = Path(job_path)

    # Handle relative paths - look in catalog/jobs if not found directly
    if not path.exists():
        catalog_path = Path("catalog/jobs") / path
        if catalog_path.exists():
            path = catalog_path
        else:
            print(f"Error: Path not found: {job_path}", file=sys.stderr)
            return 1

    # Check for index.yaml
    index_file = path / "index.yaml"
    if not index_file.exists():
        print(f"Error: No index.yaml found in: {path}", file=sys.stderr)
        return 1

    if verbose:
        print(f"Running: {path}")

    # Load and run the DAT
    try:
        dat = Dat.load(str(path))
        success, result = dat.run()

        # Create report file
        report_path = path / "report.csv"
        _write_report(result, report_path)

        print(f"Report written to: {report_path}")

        # Open the report
        _open_file(report_path)

        return 0 if success else 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _write_report(result: dict[str, Any], path: Path) -> None:
    """Write results to a CSV report file.

    Args:
        result: Result dict from running the entity
        path: Path to write the report
    """
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(["Scenario Report"])
        writer.writerow([])

        # Final state
        if "final_state" in result:
            writer.writerow(["Final State"])
            writer.writerow(["Molecule", "Concentration"])
            for mol, conc in result["final_state"].items():
                writer.writerow([mol, f"{conc:.6f}"])
            writer.writerow([])

        # Scores
        if "scores" in result:
            writer.writerow(["Scores"])
            writer.writerow(["Metric", "Value"])
            for name, value in result["scores"].items():
                if isinstance(value, float):
                    writer.writerow([name, f"{value:.6f}"])
                else:
                    writer.writerow([name, value])
            writer.writerow([])

        # Passing score
        if "passing_score" in result:
            writer.writerow(["Passing Score", result["passing_score"]])
            writer.writerow([])

        # Verification results
        if "verify_results" in result:
            writer.writerow(["Verification Results"])
            writer.writerow(["Assertion", "Passed", "Message"])
            for v in result["verify_results"]:
                passed = "PASS" if v.get("passed") else "FAIL"
                writer.writerow([v.get("assert", ""), passed, v.get("message", "")])
            writer.writerow([])

        # Overall success
        writer.writerow(["Success", "PASS" if result.get("success") else "FAIL"])


def _open_file(path: Path) -> None:
    """Open a file with the system default application.

    Args:
        path: Path to the file to open
    """
    try:
        if sys.platform == "darwin":  # macOS
            subprocess.run(["open", str(path)], check=True)
        elif sys.platform == "win32":  # Windows
            subprocess.run(["start", "", str(path)], shell=True, check=True)
        else:  # Linux
            subprocess.run(["xdg-open", str(path)], check=True)
    except subprocess.CalledProcessError:
        print(f"Could not open file automatically: {path}")
