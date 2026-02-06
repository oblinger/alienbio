"""Results storage — save and load BatteryResult to/from disk.

Results are stored as YAML files with metadata (timestamp, version) and
a flat list of entry records. The Trace object is serialized as its
timeline representation.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from .battery import BatteryEntry, BatteryResult
from .types import ExperimentResults


def save_results(result: BatteryResult, path: Path, metadata: Optional[dict[str, Any]] = None) -> Path:
    """Save a BatteryResult to a YAML file.

    Args:
        result: The battery result to save.
        path: File path to write (will add .yaml suffix if missing).
        metadata: Optional extra metadata to include.

    Returns:
        The actual path written.
    """
    if path.suffix not in (".yaml", ".yml"):
        path = path.with_suffix(".yaml")
    path.parent.mkdir(parents=True, exist_ok=True)

    doc: dict[str, Any] = {
        "version": 1,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "total": result.total,
        "passed": result.passed,
        "pass_rate": result.pass_rate,
    }
    if metadata:
        doc["metadata"] = metadata

    doc["entries"] = [_entry_to_dict(e) for e in result.entries]

    with open(path, "w") as f:
        yaml.dump(doc, f, default_flow_style=False, sort_keys=False)

    return path


def load_results(path: Path) -> BatteryResult:
    """Load a BatteryResult from a YAML file.

    Args:
        path: File path to read.

    Returns:
        Reconstructed BatteryResult.

    Raises:
        FileNotFoundError: If path doesn't exist.
        ValueError: If file format is invalid.
    """
    with open(path) as f:
        doc = yaml.safe_load(f)

    if not isinstance(doc, dict) or "entries" not in doc:
        raise ValueError(f"Invalid results file: {path}")

    entries = [_dict_to_entry(d) for d in doc["entries"]]
    return BatteryResult(entries=entries)


def export_csv(result: BatteryResult, path: Optional[Path] = None) -> str:
    """Export BatteryResult as CSV.

    Args:
        result: The battery result to export.
        path: Optional file path to write. If None, returns string only.

    Returns:
        CSV content as string.
    """
    # Collect all score keys
    all_keys: set[str] = set()
    for entry in result.entries:
        all_keys.update(entry.result.scores.keys())
    score_keys = sorted(all_keys)

    lines = []
    headers = ["agent", "scenario", "seed", "passed", "status", "total_cost"] + score_keys
    lines.append(",".join(headers))

    for entry in result.entries:
        r = entry.result
        cost = r.trace.total_cost if hasattr(r.trace, "total_cost") else 0.0
        row = [
            entry.agent_name,
            r.scenario,
            str(r.seed if r.seed is not None else ""),
            str(r.passed),
            r.status,
            f"{cost:.4f}",
        ]
        for key in score_keys:
            row.append(f"{r.scores.get(key, 0.0):.4f}")
        lines.append(",".join(row))

    csv_text = "\n".join(lines) + "\n"

    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(csv_text)

    return csv_text


def export_json(result: BatteryResult, path: Optional[Path] = None) -> str:
    """Export BatteryResult as JSON.

    Args:
        result: The battery result to export.
        path: Optional file path to write. If None, returns string only.

    Returns:
        JSON content as string.
    """
    doc = {
        "total": result.total,
        "passed": result.passed,
        "pass_rate": result.pass_rate,
        "entries": [_entry_to_dict(e) for e in result.entries],
        "summary": result.summary(),
    }
    json_text = json.dumps(doc, indent=2, default=str)

    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json_text)

    return json_text


# --- Serialization helpers ---

def _entry_to_dict(entry: BatteryEntry) -> dict[str, Any]:
    """Serialize a BatteryEntry to a plain dict."""
    r = entry.result
    cost = r.trace.total_cost if hasattr(r.trace, "total_cost") else 0.0
    d: dict[str, Any] = {
        "agent": entry.agent_name,
        "scenario": r.scenario,
        "seed": r.seed,
        "passed": r.passed,
        "status": r.status,
        "scores": dict(r.scores),
        "total_cost": cost,
    }
    if r.incomplete_reason:
        d["incomplete_reason"] = r.incomplete_reason
    return d


def _dict_to_entry(d: dict[str, Any]) -> BatteryEntry:
    """Deserialize a plain dict to a BatteryEntry."""
    # Reconstruct a minimal trace-like object for total_cost
    total_cost = d.get("total_cost", 0.0)

    class _StoredTrace:
        def __init__(self, cost: float):
            self.total_cost = cost
            self.records: list[Any] = []

        def __len__(self) -> int:
            return 0

        def __iter__(self):
            return iter([])

    result = ExperimentResults(
        scenario=d["scenario"],
        seed=d.get("seed"),
        scores=d.get("scores", {}),
        trace=_StoredTrace(total_cost),
        passed=d.get("passed", False),
        status=d.get("status", "completed"),
        incomplete_reason=d.get("incomplete_reason"),
    )
    return BatteryEntry(
        agent_name=d["agent"],
        result=result,
    )
