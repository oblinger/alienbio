"""``bio report`` — what the tests test, and whether they passed, on one page.

``just test`` answers *did everything pass*. This module answers *what was
exercised*: it runs the suite once (a JUnit file is the source of truth for
every ✓ / ✗), then lays out

1. the **capability matrix** — the 35 dimensions, each with the one-line
   sentence its proving test carries and that test's outcome;
2. the **broader suites** — every-head coverage, special forms, the hostile
   sandbox corpus, simulator conformance, the executed docs, the golden
   zeros, the no-peeking lint, the CLI end to end — with pass counts;
3. the **examples** under ``catalog/examples/`` — each run fresh right here,
   with the sentence from its README and the numbers it produced;
4. the **experiment runs** on disk under ``runs/`` — the scripted zeros and
   any live-model trial, with trials, spend and model.

The phrases are never kept in a separate list: a capability row's sentence
is the first paragraph of its test's docstring, a suite's is its module
docstring, an example's is its README — so they cannot rot apart from the
thing they describe. ``bio test-matrix --check`` refuses a proving test
with no sentence.
"""

from __future__ import annotations

import html
import json
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Optional, Sequence

from .capabilities import DIMENSIONS, GLYPH, matrix, phrases

REPO = Path(__file__).resolve().parents[2]
TESTS = REPO / "tests"
EXAMPLES = REPO / "catalog" / "examples"
RUNS = REPO / "runs"

#: The broader suites the report lists beside the matrix: test module → what it proves
#: is read from the module docstring, so the list here is only *which* modules.
SUITES: tuple[str, ...] = (
    "tests/capabilities/test_heads.py",
    "tests/capabilities/test_special_forms.py",
    "tests/capabilities/test_sandbox_adversarial.py",
    "tests/capabilities/test_simulator_conformance.py",
    "tests/capabilities/test_cli_end_to_end.py",
    "tests/expr/test_spec_examples.py",
    "tests/suite/test_golden_experiments.py",
    "tests/suite/test_no_peeking_lint.py",
)


# ---- outcomes: the JUnit file is the truth --------------------------------

Outcome = str  # "passed" | "failed" | "error" | "skipped"


def run_pytest(junit_path: Path, extra_args: Sequence[str] = ()) -> int:
    """Run the whole suite once, writing JUnit XML; returns pytest's exit code."""
    cmd = [sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider", f"--junitxml={junit_path}", *extra_args]
    return subprocess.run(cmd, cwd=REPO).returncode


def count_cases(junit_path: Path) -> dict[str, int]:
    """Test cases as pytest counts them (every parametrized case is one)."""
    counts = {"passed": 0, "failed": 0, "skipped": 0}
    for case in ET.parse(junit_path).getroot().iter("testcase"):
        if case.find("failure") is not None or case.find("error") is not None:
            counts["failed"] += 1
        elif case.find("skipped") is not None:
            counts["skipped"] += 1
        else:
            counts["passed"] += 1
    return counts


def parse_junit(junit_path: Path) -> dict[tuple[str, str], Outcome]:
    """``(module stem, test name) -> outcome`` for every test case in the file.
    Parametrized cases collapse onto their function: one failure fails it."""
    out: dict[tuple[str, str], Outcome] = {}
    root = ET.parse(junit_path).getroot()
    for case in root.iter("testcase"):
        module = (case.get("classname") or "").split(".")[-1]
        name = re.sub(r"\[.*\]$", "", case.get("name") or "")
        if case.find("failure") is not None:
            outcome = "failed"
        elif case.find("error") is not None:
            outcome = "error"
        elif case.find("skipped") is not None:
            outcome = "skipped"
        else:
            outcome = "passed"
        key = (module, name)
        prev = out.get(key)
        rank = {"failed": 3, "error": 3, "passed": 1, "skipped": 0}
        if prev is None or rank[outcome] > rank[prev]:
            out[key] = outcome
    return out


def _module_counts(outcomes: Mapping[tuple[str, str], Outcome], module: str) -> dict[str, int]:
    counts = {"passed": 0, "failed": 0, "skipped": 0}
    for (mod, _), outcome in outcomes.items():
        if mod == module:
            counts["failed" if outcome == "error" else outcome] += 1
    return counts


# ---- the four sections ------------------------------------------------------

@dataclass(frozen=True)
class CapabilityRow:
    id: str
    title: str
    status: str
    tests: tuple[str, ...]
    phrase: str
    outcome: str  # passed | failed | skipped | not run | no test | —


@dataclass(frozen=True)
class SuiteRow:
    module: str
    phrase: str
    passed: int
    failed: int
    skipped: int


@dataclass(frozen=True)
class ExampleRow:
    name: str
    phrase: str
    trials: int
    failed: int
    mean_score: Optional[float]
    seconds: float
    test_outcome: str
    error: str = ""


@dataclass(frozen=True)
class RunRow:
    name: str
    kind: str  # "live model" | "scripted"
    model: str
    trials: int
    failed: int
    spend_usd: Optional[float]
    started: str


@dataclass
class Report:
    generated_at: str
    pytest_exit: int
    totals: dict[str, int]
    capabilities: list[CapabilityRow]
    suites: list[SuiteRow]
    examples: list[ExampleRow]
    runs: list[RunRow]
    golden_outcome: str = "not run"
    notes: list[str] = field(default_factory=list)


def _outcome_of(tests: Sequence[str], outcomes: Mapping[tuple[str, str], Outcome]) -> str:
    seen = [outcomes.get(tuple(t.split("::", 1))) for t in tests]  # type: ignore[arg-type]
    if not tests:
        return "no test"
    if any(o is None for o in seen):
        return "not run"
    if any(o in ("failed", "error") for o in seen):
        return "failed"
    if all(o == "skipped" for o in seen):
        return "skipped"
    return "passed"


def capability_rows(outcomes: Mapping[tuple[str, str], Outcome]) -> list[CapabilityRow]:
    sentence = phrases()
    rows = []
    for d, tests in matrix():
        phrase = " ".join(sentence.get(t, "") for t in tests).strip() or ("—" if d.status in ("planned", "future") else "(no docstring sentence)")
        outcome = "—" if (d.status in ("planned", "future") and not tests) else _outcome_of(tests, outcomes)
        rows.append(CapabilityRow(d.id, d.title, d.status, tuple(tests), phrase, outcome))
    return rows


def _module_phrase(path: Path) -> str:
    import ast

    doc = ast.get_docstring(ast.parse(path.read_text())) or ""
    para = " ".join(doc.strip().split("\n\n", 1)[0].split())
    para = re.sub(r"^M\d+(?:\.\d+)?(?:\s*/\s*M\d+(?:\.\d+)?)*\s+—\s+", "", para)  # the milestone tag is bookkeeping, not the sentence
    return para[:1].upper() + para[1:]


def suite_rows(outcomes: Mapping[tuple[str, str], Outcome]) -> list[SuiteRow]:
    rows = []
    for rel in SUITES:
        path = REPO / rel
        counts = _module_counts(outcomes, path.stem)
        rows.append(SuiteRow(rel, _module_phrase(path), counts["passed"], counts["failed"], counts["skipped"]))
    return rows


def _readme_sentence(folder: Path) -> str:
    readme = folder / "README.md"
    if not readme.exists():
        return ""
    for line in readme.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            # the first sentence of the first paragraph
            return line.strip("*").replace("**", "")
    return ""


def example_rows(outcomes: Mapping[tuple[str, str], Outcome], runner: Optional[Callable[[Path, Path], tuple[int, int, Optional[float]]]] = None) -> list[ExampleRow]:
    """Run every example fresh into a temp dir; ``runner`` is injectable for tests."""
    runner = runner or _run_example
    rows = []
    for folder in sorted(p for p in EXAMPLES.iterdir() if p.is_dir()):
        specs = sorted(folder.glob("*.yaml"))
        if not specs:
            continue
        test_outcome = _outcome_of_module(outcomes, f"test_{folder.name}_example")
        t0 = time.perf_counter()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                trials, failed, mean = runner(specs[0], Path(tmp) / "run")
            rows.append(ExampleRow(folder.name, _readme_sentence(folder), trials, failed, mean, time.perf_counter() - t0, test_outcome))
        except Exception as exc:  # the report must land even when an example does not
            rows.append(ExampleRow(folder.name, _readme_sentence(folder), 0, 0, None, time.perf_counter() - t0, test_outcome, error=f"{type(exc).__name__}: {exc}"))
    return rows


def _outcome_of_module(outcomes: Mapping[tuple[str, str], Outcome], module: str) -> str:
    counts = _module_counts(outcomes, module)
    if sum(counts.values()) == 0:
        return "not run"
    if counts["failed"]:
        return "failed"
    return "passed" if counts["passed"] else "skipped"


def _run_example(spec: Path, out_dir: Path) -> tuple[int, int, Optional[float]]:
    from .suite.experiment import load_spec, run_experiment

    rmap = run_experiment(load_spec(spec), out_dir=str(out_dir))
    scores = [r.objective_score for r in rmap.records if r.terminal_reason != "error"]
    mean = sum(scores) / len(scores) if scores else None
    return len(rmap.records), rmap.provenance.failed_trials, mean


def run_rows() -> list[RunRow]:
    rows = []
    if not RUNS.exists():
        return rows
    for folder in sorted(RUNS.iterdir()):
        manifest = folder / "manifest.json"
        if not manifest.exists():
            continue
        m = json.loads(manifest.read_text())
        model = m.get("model")
        spend = None
        report = folder / "report.txt"
        if report.exists():
            hit = re.search(r"spent \$([0-9.]+)", report.read_text())
            spend = float(hit.group(1)) if hit else None
        rows.append(RunRow(folder.name, "live model" if model else "scripted", str(model or "—"), int(m.get("trials_completed", 0)), int(m.get("failed_trials", 0)), spend, str(m.get("started_at", ""))[:10]))
    rows.sort(key=lambda r: (r.kind != "live model", r.name))
    return rows


def build(outcomes: Mapping[tuple[str, str], Outcome], pytest_exit: int, *, run_examples: bool = True, example_runner=None, totals: Optional[dict[str, int]] = None) -> Report:
    if totals is None:
        totals = {"passed": 0, "failed": 0, "skipped": 0}
        for outcome in outcomes.values():
            totals["failed" if outcome == "error" else outcome] += 1
    rep = Report(
        generated_at=time.strftime("%Y-%m-%d %H:%M"),
        pytest_exit=pytest_exit,
        totals=totals,
        capabilities=capability_rows(outcomes),
        suites=suite_rows(outcomes),
        examples=example_rows(outcomes, example_runner) if run_examples else [],
        runs=run_rows(),
        golden_outcome=_outcome_of_module(outcomes, "test_golden_experiments"),
    )
    if not run_examples:
        rep.notes.append("examples not run (--no-examples)")
    return rep


# ---- rendering ---------------------------------------------------------------

MARK = {"passed": "✅", "failed": "❌", "error": "❌", "skipped": "⏭", "not run": "·", "no test": "⚠", "—": "—"}


def render_markdown(rep: Report) -> str:
    t = rep.totals
    verdict = "ALL PASSED" if rep.pytest_exit == 0 else f"FAILURES (pytest exit {rep.pytest_exit})"
    L = [f"# ABIO test report — {verdict}", "",
         f"*{rep.generated_at} · {t['passed']} passed, {t['failed']} failed, {t['skipped']} skipped · `just test` is the gate; this page is what the gate tested.*", ""]
    L += ["## 1. Capability matrix — the 35 dimensions and the sentence each proving test carries", "",
          "| | Id | Dimension | What the test proves |", "|---|---|---|---|"]
    for r in rep.capabilities:
        mark = MARK.get(r.outcome, r.outcome)
        status = "" if r.status == "built" else f" *({r.status})*"
        L.append(f"| {mark} | {r.id} | {r.title}{status} | {r.phrase} |")
    L += ["", "## 2. Broader suites — what the rest of the tree exercises", "",
          "| | Suite | Tests | What it exercises |", "|---|---|---|---|"]
    for s in rep.suites:
        mark = "❌" if s.failed else ("✅" if s.passed else "·")
        L.append(f"| {mark} | `{s.module}` | {s.passed} passed{f', {s.failed} failed' if s.failed else ''}{f', {s.skipped} skipped' if s.skipped else ''} | {s.phrase} |")
    L += ["", "## 3. Examples — `catalog/examples/`, each run fresh for this report", "",
          "*Scores here are scripted controls' (idle / measure / survey agents commit nothing), so 0.00 is the expected zero, not a defect; a live-model arm is what would score.*", ""]
    if rep.examples:
        L += ["| | Example | This run | What it demonstrates |", "|---|---|---|---|"]
        for e in rep.examples:
            if e.error:
                mark, numbers = "❌", f"error: {e.error}"
            else:
                mark = "✅" if e.failed == 0 and e.test_outcome != "failed" else "❌"
                score = f", mean score {e.mean_score:.2f}" if e.mean_score is not None else ""
                numbers = f"{e.trials} trials, {e.failed} failed{score}, {e.seconds:.1f} s, $0"
            L.append(f"| {mark} | `{e.name}` | {numbers} | {e.phrase} |")
    else:
        L.append("*(not run)*")
    L += ["", f"## 4. Experiment runs on disk — `runs/` (golden zeros: {MARK.get(rep.golden_outcome, rep.golden_outcome)} {rep.golden_outcome})", ""]
    if rep.runs:
        L += ["| | Run | Kind | Model | Trials | Spend | Started |", "|---|---|---|---|---|---|---|"]
        for r in rep.runs:
            mark = "✅" if r.failed == 0 and r.trials else "❌"
            spend = f"${r.spend_usd:.4f}" if r.spend_usd is not None else "—"
            L.append(f"| {mark} | `{r.name}` | {r.kind} | `{r.model}` | {r.trials} ({r.failed} failed) | {spend} | {r.started} |")
    else:
        L.append("*(no run directories)*")
    if rep.notes:
        L += ["", *[f"*{n}*" for n in rep.notes]]
    return "\n".join(L) + "\n"


def render_html(rep: Report) -> str:
    """The Markdown page as HTML — tables, headings, paragraphs; nothing else is needed."""
    md = render_markdown(rep)
    out = ["<!doctype html><meta charset=utf-8><title>ABIO test report</title><style>",
           "body{font:14px/1.45 -apple-system,Helvetica,sans-serif;margin:28px;max-width:1400px}table{border-collapse:collapse;margin:8px 0 22px}",
           "td,th{border:1px solid #ddd;padding:5px 9px;vertical-align:top;text-align:left}th{background:#f3f3f3}code{background:#f5f5f5;padding:1px 4px}h1{font-size:22px}h2{font-size:17px;margin-top:26px}",
           "</style>"]
    in_table = False
    for line in md.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-") for c in cells):
                continue
            if not in_table:
                out.append("<table>"); in_table = True
                out.append("<tr>" + "".join(f"<th>{_inline(c)}</th>" for c in cells) + "</tr>")
            else:
                out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>")
            continue
        if in_table:
            out.append("</table>"); in_table = False
        if line.startswith("# "):
            out.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.strip():
            out.append(f"<p>{_inline(line)}</p>")
    if in_table:
        out.append("</table>")
    return "\n".join(out) + "\n"


def _inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    return text


__all__ = ["Report", "build", "capability_rows", "count_cases", "example_rows", "parse_junit", "render_html", "render_markdown", "run_pytest", "run_rows", "suite_rows"]
