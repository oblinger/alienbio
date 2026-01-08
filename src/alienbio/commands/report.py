"""Report command: Run a scenario and create a report.

This is the primary CLI command for running scenarios. It:
1. Runs the entity's run() method
2. Prints results table to stdout
3. Saves Excel file to temp directory (viewable via `just view-report`)
"""

from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# Location to store path to last generated report
LAST_REPORT_PATH = Path(tempfile.gettempdir()) / "alienbio_last_report_path.txt"


def report_command(args: list[str], verbose: bool = False) -> int:
    """Run a scenario and create a report.

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

        # Print table to stdout
        _print_table(result, path.name)

        # Save Excel to temp directory
        excel_path = _save_excel(result, path.name)
        _save_last_report_path(excel_path)

        if verbose:
            print(f"\nExcel report saved to: {excel_path}")
            print("Run `just view-report` to open in spreadsheet app")

        return 0 if success else 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _print_table(result: dict[str, Any], scenario_name: str) -> None:
    """Print results as a formatted table to stdout.

    Args:
        result: Result dict from running the entity
        scenario_name: Name of the scenario for the header
    """
    # Overall status
    success = result.get("success", False)
    status = "PASSED" if success else "FAILED"

    print(f"\n{'=' * 60}")
    print(f"  Scenario: {scenario_name}")
    print(f"  Status: {status}")
    print(f"{'=' * 60}")

    # Final state table
    if "final_state" in result:
        print("\n  Final State:")
        print(f"  {'-' * 30}")
        print(f"  {'Molecule':<15} {'Concentration':>12}")
        print(f"  {'-' * 30}")
        for mol, conc in result["final_state"].items():
            print(f"  {mol:<15} {conc:>12.4f}")

    # Scores table
    if "scores" in result:
        print("\n  Scores:")
        print(f"  {'-' * 30}")
        print(f"  {'Metric':<15} {'Value':>12}")
        print(f"  {'-' * 30}")
        for name, value in result["scores"].items():
            if isinstance(value, float):
                print(f"  {name:<15} {value:>12.4f}")
            else:
                print(f"  {name:<15} {str(value):>12}")

        # Show passing threshold
        if "passing_score" in result:
            print(f"  {'-' * 30}")
            print(f"  {'Passing':<15} {result['passing_score']:>12.4f}")

    # Verification results
    if "verify_results" in result and result["verify_results"]:
        print("\n  Verifications:")
        print(f"  {'-' * 50}")
        for v in result["verify_results"]:
            passed = v.get("passed", False)
            mark = "+" if passed else "x"
            msg = v.get("message", v.get("assert", ""))
            print(f"  [{mark}] {msg}")

    print()


def _save_excel(result: dict[str, Any], scenario_name: str) -> Path:
    """Save results to an Excel file in temp directory.

    Args:
        result: Result dict from running the entity
        scenario_name: Name of the scenario for the filename

    Returns:
        Path to the saved Excel file
    """
    # Use CSV format (Excel-compatible) to avoid openpyxl dependency
    temp_dir = Path(tempfile.gettempdir())
    excel_path = temp_dir / f"alienbio_{scenario_name}_report.csv"

    with open(excel_path, "w", newline="") as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(["Scenario Report", scenario_name])
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

    return excel_path


def _save_last_report_path(path: Path) -> None:
    """Save the path to the last generated report.

    Args:
        path: Path to the report file
    """
    LAST_REPORT_PATH.write_text(str(path))


def view_report_command(args: list[str], verbose: bool = False) -> int:
    """Open the last generated report in the default spreadsheet application.

    Args:
        args: Command arguments (unused)
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    if not LAST_REPORT_PATH.exists():
        print("No report has been generated yet.", file=sys.stderr)
        print("Run `bio report <path>` first.", file=sys.stderr)
        return 1

    report_path = Path(LAST_REPORT_PATH.read_text().strip())

    if not report_path.exists():
        print(f"Report file not found: {report_path}", file=sys.stderr)
        print("The temp file may have been cleaned up. Run the report again.", file=sys.stderr)
        return 1

    print(f"Opening: {report_path}")
    _open_file(report_path)
    return 0


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
