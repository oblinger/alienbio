"""The capability matrix's fixtures (roadmap M48.1).

``@capability("B7")`` marks a test as the end-to-end proof of a dimension of
``ABIO Capability Dimensions``; ``alienbio.capabilities`` scans these files
for the marker and ``bio test-matrix`` reports the map.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any, Optional, Sequence

import pytest

from alienbio.suite.experiment import ExperimentSpec, load_spec, render_report, run_experiment

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "catalog" / "experiments"

capability = pytest.mark.capability


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "capability(id, ...): the end-to-end proof of a capability dimension (bio test-matrix)")


def small(spec: ExperimentSpec, *, axes: Optional[Sequence[tuple[str, tuple[Any, ...]]]] = None, trials: int = 1, **overrides: Any) -> ExperimentSpec:
    """A catalog experiment cut down for a proof: the given axes (the matched
    idle arm kept when the spec asked for it), ``trials`` per cell, no
    power design."""
    new_axes = tuple(axes) if axes is not None else spec.axes
    if spec.idle_baseline and not any(name == "agent" for name, _ in new_axes):
        new_axes = new_axes + (("agent", (spec.agent, "idle")),)
    fields: dict[str, Any] = {"axes": new_axes, "trials_per_condition": trials, "design": None, "out_dir": None}
    fields.update(overrides)
    return dataclasses.replace(spec, **fields)


def run(spec: ExperimentSpec, out: Path):
    """Run ``spec`` into ``out``; return ``(rmap, report_text, manifest)``."""
    rmap = run_experiment(spec, out_dir=str(out))
    manifest = json.loads((out / "manifest.json").read_text())
    return rmap, render_report(rmap, manifest), manifest


def catalog(name: str) -> ExperimentSpec:
    return load_spec(CATALOG / f"{name}.yaml")


@pytest.fixture
def harness(tmp_path):
    """``harness(spec) -> (rmap, report, manifest)`` in a fresh directory."""
    counter = [0]

    def go(spec: ExperimentSpec):
        counter[0] += 1
        return run(spec, tmp_path / f"run{counter[0]}")

    return go
