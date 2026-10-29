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

import base64
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Optional, Sequence, cast

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

Outcome = str  # "passed" | "failed" | "error" | "skipped" (an xfail reads as skipped here)


def run_pytest(junit_path: Path, extra_args: Sequence[str] = ()) -> int:
    """Run the whole suite once, writing JUnit XML; returns pytest's exit code."""
    cmd = [sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider", f"--junitxml={junit_path}", *extra_args]
    return subprocess.run(cmd, cwd=REPO).returncode


def _case_outcome(case: ET.Element) -> str:
    """One JUnit ``testcase`` as pytest's summary line counts it: an xfail is
    written as ``<skipped type="pytest.xfail">`` and is counted apart from a
    skip (the header read ``46 skipped`` for 3 skips and 43 xfails)."""
    if case.find("failure") is not None or case.find("error") is not None:
        return "failed"
    skipped = case.find("skipped")
    if skipped is not None:
        return "xfailed" if skipped.get("type") == "pytest.xfail" else "skipped"
    return "passed"


def _empty_counts() -> dict[str, int]:
    return {"passed": 0, "failed": 0, "skipped": 0, "xfailed": 0}


def count_cases(junit_path: Path) -> dict[str, int]:
    """Test cases as pytest counts them (every parametrized case is one)."""
    counts = _empty_counts()
    for case in ET.parse(junit_path).getroot().iter("testcase"):
        counts[_case_outcome(case)] += 1
    return counts


def count_module_cases(junit_path: Path) -> dict[str, dict[str, int]]:
    """``module stem -> case counts``: section 2 counts cases, not functions
    (``test_golden_experiments.py`` read ``2 passed`` for 15 hashed zeros and
    its pin test)."""
    out: dict[str, dict[str, int]] = {}
    for case in ET.parse(junit_path).getroot().iter("testcase"):
        module = (case.get("classname") or "").split(".")[-1]
        out.setdefault(module, _empty_counts())[_case_outcome(case)] += 1
    return out


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


def _function_counts(outcomes: Mapping[tuple[str, str], Outcome]) -> dict[str, dict[str, int]]:
    """``module stem -> counts`` with each function as one case — what a
    caller holding only ``parse_junit`` outcomes (no JUnit file) can say."""
    out: dict[str, dict[str, int]] = {}
    for (mod, _), outcome in outcomes.items():
        out.setdefault(mod, _empty_counts())["failed" if outcome == "error" else outcome] += 1
    return out


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
    xfailed: int = 0


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
    figure: Optional[Path] = None  # runs/<name>/key.png when the run drew one
    readout: str = ""
    caption: str = ""


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
    #: False under ``--no-examples``: section 3 is empty, so the page cannot
    #: say every example ran clean and is not titled ALL PASSED.
    examples_run: bool = True
    notes: list[str] = field(default_factory=list)
    #: The folder ``report.md`` is written to; figure links are relative to it.
    out_dir: Path = field(default_factory=lambda: REPO / "reports")

    @property
    def unproven(self) -> list[str]:
        """Built / partial dimensions whose proving tests did not pass here:
        ``not run`` (absent from the JUnit file), ``no test``, ``failed``, or
        every proving test ``skipped``."""
        return [
            r.id
            for r in self.capabilities
            if r.status in ("built", "partial") and r.outcome != "passed"
        ]

    @property
    def unrun_suites(self) -> list[str]:
        """Broader-suite rows (section 2) that did not run and pass here:
        no passing case in the JUnit file, or any failure. A JUnit file
        holding only the capability tests read ALL PASSED beside
        ``test_golden_experiments.py 0 passed`` (T091 B6)."""
        return [s.module for s in self.suites if s.passed == 0 or s.failed]

    @property
    def ok(self) -> bool:
        """The verdict, computed from what the page shows — never from the
        pytest exit code alone (T051 box 4: ``--junit`` hard-coded that exit
        to 0, and a broken example never reached it, so a page whose own
        rows read ``3 failed`` / ``error: ExprError`` was titled ALL PASSED).
        A page whose capability rows were not proven by a passing test is not
        a pass either: a JUnit file without the proving tests read ALL PASSED
        with every row ``not run`` (T088 report 1), and neither is a page
        whose broader-suite rows did not all run and pass (T091 B6), nor one whose
        examples were not run (``--no-examples``: the Testing Guide's ALL
        PASSED requires every example to have run clean)."""
        return (
            self.pytest_exit == 0
            and self.totals.get("failed", 0) == 0
            and all(not r.error and r.failed == 0 for r in self.examples)
            and not self.unproven
            and not self.unrun_suites
            and self.examples_run
        )


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


def suite_rows(outcomes: Mapping[tuple[str, str], Outcome], case_counts: Optional[Mapping[str, dict[str, int]]] = None) -> list[SuiteRow]:
    """Section 2's rows, counted per case from ``case_counts``
    (``count_module_cases``); without a JUnit file, per function."""
    by_module = case_counts if case_counts is not None else _function_counts(outcomes)
    rows = []
    for rel in SUITES:
        path = REPO / rel
        counts = by_module.get(path.stem, _empty_counts())
        rows.append(SuiteRow(rel, _module_phrase(path), counts["passed"], counts["failed"], counts["skipped"], counts.get("xfailed", 0)))
    return rows


def _readme_sentence(folder: Path) -> str:
    readme = folder / "README.md"
    if not readme.exists():
        return ""
    for line in readme.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            # the first line of the first paragraph (the README's lead line)
            return line.strip("*").replace("**", "")
    return ""


def _example_spec(folder: Path) -> Optional[Path]:
    """The spec ``bio report`` runs for an example: ``<folder name>.yaml``
    when the folder has one, else its one ``*.yaml`` — never "the
    alphabetically first", which picked ``agent_loop.yaml`` over
    ``live.yaml`` by spelling alone (T088 report 5). A folder with several
    specs and none named after it refuses."""
    named = folder / f"{folder.name}.yaml"
    if named.exists():
        return named
    specs = sorted(folder.glob("*.yaml"))
    if not specs:
        return None
    if len(specs) > 1:
        raise ValueError(
            f"{folder.name}: {len(specs)} specs and none named {folder.name}.yaml; "
            "name the one bio report runs after its folder"
        )
    return specs[0]


def example_rows(outcomes: Mapping[tuple[str, str], Outcome], runner: Optional[Callable[[Path, Path], tuple[int, int, Optional[float]]]] = None) -> list[ExampleRow]:
    """Run every example fresh into a temp dir; ``runner`` is injectable for tests."""
    runner = runner or _run_example
    rows = []
    for folder in sorted(p for p in EXAMPLES.iterdir() if p.is_dir()):
        try:
            spec = _example_spec(folder)
        except ValueError as exc:
            rows.append(ExampleRow(folder.name, _readme_sentence(folder), 0, 0, None, 0.0, "not run", error=str(exc)))
            continue
        if spec is None:
            continue
        test_outcome = _outcome_of_module(outcomes, f"test_{folder.name}_example")
        t0 = time.perf_counter()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                trials, failed, mean = runner(spec, Path(tmp) / "run")
            rows.append(ExampleRow(folder.name, _readme_sentence(folder), trials, failed, mean, time.perf_counter() - t0, test_outcome))
        except Exception as exc:  # the report must land even when an example does not
            rows.append(ExampleRow(folder.name, _readme_sentence(folder), 0, 0, None, time.perf_counter() - t0, test_outcome, error=f"{type(exc).__name__}: {exc}"))
    return rows


def _outcome_of_module(outcomes: Mapping[tuple[str, str], Outcome], module: str) -> str:
    counts = _function_counts(outcomes).get(module, _empty_counts())
    if sum(counts.values()) == 0:
        return "not run"
    if counts["failed"]:
        return "failed"
    return "passed" if counts["passed"] else "skipped"


def _run_example(spec: Path, out_dir: Path) -> tuple[int, int, Optional[float]]:
    from .suite.experiment import estimate_cost, load_spec, run_experiment

    loaded = load_spec(spec)
    # The report spends nothing: a spec with a live-model arm is an error row,
    # not a paid run (T088 report 5).
    if estimate_cost(loaded).llm_trials:
        raise ValueError(f"{spec.name} has a live-model arm; bio report runs scripted specs only")
    rmap = run_experiment(loaded, out_dir=str(out_dir))
    scores = [r.objective_score for r in rmap.records if r.terminal_reason != "error"]
    mean = sum(scores) / len(scores) if scores else None
    return len(rmap.records), rmap.provenance.failed_trials, mean


def run_rows(notes: Optional[list[str]] = None) -> list[RunRow]:
    """One row per ``runs/<name>/manifest.json``. A run whose manifest or
    ``key.json`` will not read is skipped with a named line in ``notes``
    (one corrupt file stopped the whole report after the full pytest run,
    T088 report 2)."""
    rows = []
    if not RUNS.exists():
        return rows
    for folder in sorted(RUNS.iterdir()):
        try:
            row = _run_row(folder)
        except (OSError, ValueError, TypeError, KeyError) as exc:  # JSONDecodeError is a ValueError
            if notes is not None:
                notes.append(f"runs/{folder.name} skipped: {type(exc).__name__}: {exc}")
            continue
        if row is not None:
            rows.append(row)
    rows.sort(key=lambda r: (r.kind != "live model", r.name))
    return rows


def _run_row(folder: Path) -> Optional[RunRow]:
    manifest = folder / "manifest.json"
    if not manifest.exists():
        return None
    from .suite.store import manifest_model_label, read_manifest

    m = read_manifest(manifest)
    model = manifest_model_label(m)
    # The spend is the manifest's own number (written at every landed
    # unit), not a regex over report.txt — a run with no report yet, or
    # a report format change, read as no spend at all.
    spent = m.get("cost_usd_spent")
    spend = float(spent) if isinstance(spent, (int, float)) and not isinstance(spent, bool) else None
    figure, readout, caption = None, "", ""
    if (folder / "key.png").exists():
        figure = folder / "key.png"
        if (folder / "key.json").exists():
            meta = json.loads((folder / "key.json").read_text())
            readout, caption = str(meta.get("readout", "")), str(meta.get("caption", ""))
    return RunRow(folder.name, "live model" if model else "scripted", str(model or "—"), int(m.get("trials_completed", 0)), int(m.get("failed_trials", 0)), spend, str(m.get("started_at", ""))[:10], figure, readout, caption)


def build(outcomes: Mapping[tuple[str, str], Outcome], pytest_exit: int, *, run_examples: bool = True, example_runner=None, totals: Optional[dict[str, int]] = None, case_counts: Optional[Mapping[str, dict[str, int]]] = None, out_dir: Optional[Path] = None) -> Report:
    if totals is None:
        totals = _empty_counts()
        for outcome in outcomes.values():
            totals["failed" if outcome == "error" else outcome] += 1
    rep = Report(
        generated_at=time.strftime("%Y-%m-%d %H:%M"),
        pytest_exit=pytest_exit,
        totals=totals,
        capabilities=capability_rows(outcomes),
        suites=suite_rows(outcomes, case_counts),
        examples=example_rows(outcomes, example_runner) if run_examples else [],
        runs=[],
        golden_outcome=_outcome_of_module(outcomes, "test_golden_experiments"),
        out_dir=out_dir if out_dir is not None else REPO / "reports",
        examples_run=run_examples,
    )
    rep.runs = run_rows(rep.notes)
    if not run_examples:
        rep.notes.append("examples not run (--no-examples)")
    return rep


# ---- rendering ---------------------------------------------------------------

MARK = {"passed": "✅", "failed": "❌", "error": "❌", "skipped": "⏭", "not run": "·", "no test": "⚠", "—": "—"}


def render_markdown(rep: Report) -> str:
    t = rep.totals
    if rep.ok:
        verdict = "ALL PASSED"
    elif rep.pytest_exit != 0:
        verdict = f"FAILURES (pytest exit {rep.pytest_exit})"
    elif rep.totals.get("failed", 0):
        verdict = f"FAILURES ({rep.totals['failed']} failed)"
    elif not all(not e.error and e.failed == 0 for e in rep.examples):
        verdict = "FAILURES (an example did not run clean)"
    else:
        gaps = []
        if rep.unproven:
            gaps.append(f"{len(rep.unproven)} capability rows without a passing test")
        if rep.unrun_suites:
            gaps.append(f"{len(rep.unrun_suites)} suite rows not run")
        if not rep.examples_run:
            gaps.append("examples not run")
        verdict = f"NOT PROVEN ({'; '.join(gaps)})"
    L = [f"# ABIO test report — {verdict}", "",
         f"*{rep.generated_at} · {t['passed']} passed, {t['failed']} failed, {t['skipped']} skipped, {t.get('xfailed', 0)} xfailed · `just test` is the gate; this page is what the gate tested.*", ""]
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
        L.append(f"| {mark} | `{s.module}` | {s.passed} passed{f', {s.failed} failed' if s.failed else ''}{f', {s.skipped} skipped' if s.skipped else ''}{f', {s.xfailed} xfailed' if s.xfailed else ''} | {s.phrase} |")
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
        figures = [r for r in rep.runs if r.figure is not None]
        if figures:
            L += ["", "*Each run's key figure — the one readout the experiment exists for, drawn from its record store (`key.png` beside `report.txt`). Scripted controls give the instrument's zero: the shape a live arm is read against.*"]
            for r in figures:
                L += ["", f"### `{r.name}` — {r.readout}", "", f"![{r.name} key figure]({_relative(cast(Path, r.figure), rep.out_dir)})", "", f"*{r.caption}*"]
    else:
        L.append("*(no run directories)*")
    if rep.notes:
        L += ["", *[f"*{n}*" for n in rep.notes]]
    return "\n".join(L) + "\n"


def render_html(rep: Report) -> str:
    """The Markdown page as HTML — tables, headings, paragraphs; nothing else is needed."""
    md = render_markdown(rep)
    out = ["<!doctype html><meta charset=utf-8><title>ABIO test report</title><style>",
           "body{font:14px/1.45 -apple-system,Helvetica,sans-serif;margin:28px;max-width:1400px}table{border-collapse:collapse;margin:8px 0 22px}img{max-width:100%;border:1px solid #e5e5e5;margin:4px 0}h3{font-size:14px;margin:22px 0 4px}",
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
        image = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", line.strip())
        if image:
            out.append(f'<img alt="{html.escape(image.group(1))}" src="{_data_uri(Path(os.path.normpath(rep.out_dir / image.group(2))))}">')
            continue
        if line.startswith("# "):
            out.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("### "):
            out.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.strip():
            out.append(f"<p>{_inline(line)}</p>")
    if in_table:
        out.append("</table>")
    return "\n".join(out) + "\n"


def _relative(path: Path, out_dir: Path) -> str:
    """``path`` relative to ``out_dir`` (where the Markdown lives), POSIX-style
    — it was always relative to ``reports/``, so ``--out`` elsewhere wrote
    links that pointed nowhere (T088 report 3)."""
    return os.path.relpath(path, out_dir).replace(os.sep, "/")


def _data_uri(path: Path) -> str:
    """A PNG as a self-contained ``data:`` URI, so ``report.html`` travels alone."""
    return "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode("ascii")


def _inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    return text


__all__ = ["Report", "build", "capability_rows", "count_cases", "count_module_cases", "example_rows", "parse_junit", "render_html", "render_markdown", "run_pytest", "run_rows", "suite_rows"]
