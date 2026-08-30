"""The capability matrix (roadmap M48.1): the 35 capability dimensions of
``ABIO Capability Dimensions`` mapped to the tests that prove them.

A dimension is proven by a test in ``tests/capabilities/`` decorated
``@capability("<id>")``. :func:`matrix` scans those files statically (no
pytest import, no collection) and pairs every dimension with its tests;
:func:`render_markdown` is the generated status table the dimensions doc
carries; :func:`check` names every built dimension nobody proves — the CI
gate (``bio test-matrix --check``, ``tests/capabilities/test_matrix.py``).

Status vocabulary: ``built`` (end-to-end capability on ``main``),
``partial`` (the primitive exists; its end-to-end wiring does not),
``planned`` (nothing yet), ``future`` (out of the near term). ``built`` and
``partial`` dimensions must have a test; ``planned`` / ``future`` may not.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = REPO_ROOT / "tests" / "capabilities"

GLYPH: Mapping[str, str] = {"built": "✅", "partial": "🟡", "planned": "⬜", "future": "🔮"}
MISSING_GLYPH = "❌"


@dataclass(frozen=True)
class Dimension:
    id: str
    group: str
    title: str
    status: str

    def __post_init__(self) -> None:
        if self.status not in GLYPH:
            raise ValueError(f"{self.id}: unknown status {self.status!r}")


#: The 35 dimensions, in the order the design doc lists them.
DIMENSIONS: tuple[Dimension, ...] = (
    # A. Core substrate
    Dimension("A1", "A", "Molecular simulation engine", "built"),
    Dimension("A2", "A", "Parameterized world generation from spec", "built"),
    Dimension("A3", "A", "Region isolation + per-molecule permeability", "built"),
    Dimension("A4", "A", "Partial-observability sensing model", "built"),
    Dimension("A5", "A", "Action execution with reversibility semantics", "built"),
    # B. Generation & control knobs
    Dimension("B1", "B", "Taint-free / guaranteed-novel generation", "built"),
    Dimension("B2", "B", "Asymmetric knowledge + ground-truth oracle", "built"),
    Dimension("B3", "B", "Controllable-complexity dial", "built"),
    Dimension("B4", "B", "Constitution / objective injection", "built"),
    Dimension("B5", "B", "Objective instrumentation by required reasoning depth", "built"),
    Dimension("B6", "B", "Objective-type taxonomy generation", "built"),
    Dimension("B7", "B", "Multi-objective conflict engineering", "built"),
    Dimension("B8", "B", "Emergent-instrumental-pressure worlds", "built"),
    Dimension("B9", "B", "Fixed-model / vary-world harness (Delta)", "built"),
    Dimension("B10", "B", "Environmental-pressure injection library", "built"),
    Dimension("B11", "B", "Hidden inter-species interdependency generation", "built"),
    Dimension("B12", "B", "Epistemic-accessibility control", "built"),
    Dimension("B13", "B", "Independent stakes dial + reversibility dial", "built"),
    Dimension("B14", "B", "Deliberation-budget / time-pressure control", "built"),
    Dimension("B15", "B", "Monitoring / observability-signal injection", "built"),
    Dimension("B16", "B", "User-preference / sycophancy injection", "planned"),
    Dimension("B17", "B", "Explicit-hint / framing-variation controls", "built"),
    Dimension("B18", "B", "Iterative multi-generation alignment-adjustment loop", "future"),
    # C. Measurement & scoring
    Dimension("C1", "C", "Deliberation-trace capture", "built"),
    Dimension("C2", "C", "Ground-truth behavioral-alignment scoring", "built"),
    Dimension("C3", "C", "Failure-mode classification", "partial"),
    Dimension("C4", "C", "Per-objective surfacing detection + convergence", "built"),
    Dimension("C5", "C", "Blind-spot external verification", "built"),
    Dimension("C6", "C", "Conflict-resolution scoring", "built"),
    Dimension("C7", "C", "Threshold / erosion + recovery measurement", "partial"),
    Dimension("C8", "C", "Calibration measurement", "built"),
    Dimension("C9", "C", "Degradation-pattern detection", "built"),
    Dimension("C10", "C", "Paired-condition divergence measurement", "built"),
    Dimension("C11", "C", "Trajectory / attractor / perturbation analysis", "future"),
    # Integrative end-state
    Dimension("I1", "I", "Mass-trial automation + cross-dimensional reliability map", "built"),
)

BY_ID: Mapping[str, Dimension] = {d.id: d for d in DIMENSIONS}


def _decorator_ids(node: ast.FunctionDef) -> list[str]:
    """The ids named by ``@capability("A1")`` / ``@capability("A1", "B2")``
    (or ``@pytest.mark.capability(...)``) on a test function."""
    ids: list[str] = []
    for dec in node.decorator_list:
        if not isinstance(dec, ast.Call):
            continue
        func = dec.func
        name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if name != "capability":
            continue
        for arg in dec.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                ids.append(arg.value)
    return ids


def scan(tests_dir: Optional[Path] = None) -> dict[str, list[str]]:
    """``dimension id -> ["module::test", ...]`` from the decorated tests."""
    root = tests_dir or TESTS_DIR
    found: dict[str, list[str]] = {}
    for path in sorted(root.glob("test_*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                for cid in _decorator_ids(node):
                    found.setdefault(cid, []).append(f"{path.stem}::{node.name}")
    return found


def matrix(tests_dir: Optional[Path] = None) -> list[tuple[Dimension, list[str]]]:
    """Every dimension with its tests, in the design doc's order."""
    found = scan(tests_dir)
    return [(d, found.get(d.id, [])) for d in DIMENSIONS]


def unknown_ids(tests_dir: Optional[Path] = None) -> list[str]:
    """Ids a test claims that no dimension carries."""
    return sorted(cid for cid in scan(tests_dir) if cid not in BY_ID)


def check(tests_dir: Optional[Path] = None) -> list[str]:
    """The built / partial dimensions with no test — empty means the gate passes."""
    return [d.id for d, tests in matrix(tests_dir) if d.status in ("built", "partial") and not tests]


def glyph(d: Dimension, tests: Iterable[str]) -> str:
    if d.status in ("built", "partial") and not list(tests):
        return MISSING_GLYPH
    return GLYPH[d.status]


def render_markdown(tests_dir: Optional[Path] = None) -> str:
    """The generated status table (the dimensions doc's column)."""
    rows = ["| Id | Dimension | Status | Proven by |", "|---|---|---|---|"]
    for d, tests in matrix(tests_dir):
        proof = ", ".join(f"`{t}`" for t in tests) if tests else ("—" if d.status in ("planned", "future") else "**no test**")
        rows.append(f"| {d.id} | {d.title} | {glyph(d, tests)} {d.status} | {proof} |")
    return "\n".join(rows) + "\n"


def render_text(tests_dir: Optional[Path] = None) -> str:
    lines = []
    for d, tests in matrix(tests_dir):
        lines.append(f"{d.id:4s} {glyph(d, tests)} {d.status:8s} {d.title}")
        for t in tests:
            lines.append(f"       {t}")
    return "\n".join(lines) + "\n"


__all__ = ["DIMENSIONS", "BY_ID", "Dimension", "check", "matrix", "render_markdown", "render_text", "scan", "unknown_ids"]
