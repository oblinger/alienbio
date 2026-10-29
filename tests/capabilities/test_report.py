"""``bio report`` — the page that says what the tests tested: every proving
test carries a sentence, JUnit outcomes land on the right rows, and the
examples section survives an example that fails to run."""

from __future__ import annotations

from pathlib import Path

from alienbio.capabilities import DIMENSIONS, check_phrases, matrix, phrases
from alienbio.report import SUITES, build, capability_rows, example_rows, parse_junit, render_html, render_markdown

_JUNIT = """<?xml version="1.0"?>
<testsuites><testsuite name="pytest">
<testcase classname="tests.capabilities.test_a_substrate" name="test_a1_engine_runs_reactions_modulations_and_compiled_rate_laws_on_both_simulators"/>
<testcase classname="tests.capabilities.test_b_generation" name="test_b2_every_record_carries_the_ground_truth_oracle_the_agent_never_sees"><failure message="boom"/></testcase>
<testcase classname="tests.capabilities.test_heads" name="test_x[a]"/>
<testcase classname="tests.capabilities.test_heads" name="test_x[b]"><skipped/></testcase>
<testcase classname="tests.expr.test_ecosystem_example" name="test_it_runs"/>
</testsuite></testsuites>
"""


def test_every_proving_test_carries_a_sentence_for_the_report():
    assert check_phrases() == []
    sentences = phrases()
    for d, tests in matrix():
        for t in tests:
            assert sentences[t] and sentences[t][0].isupper() and len(sentences[t]) < 160, (d.id, t)


def test_junit_outcomes_land_on_the_matrix_rows(tmp_path):
    junit = tmp_path / "junit.xml"
    junit.write_text(_JUNIT)
    outcomes = parse_junit(junit)
    assert outcomes[("test_heads", "test_x")] == "passed"  # one param passed, one skipped: the function passed
    rows = {r.id: r for r in capability_rows(outcomes)}
    assert rows["A1"].outcome == "passed" and rows["B2"].outcome == "failed"
    assert rows["A2"].outcome == "not run"  # in the matrix, absent from this JUnit
    assert all(r.outcome == "—" for r in rows.values() if r.status in ("planned", "future"))
    assert rows["A1"].phrase.startswith("Concentrations")


def test_the_page_renders_and_an_example_that_cannot_run_is_reported_not_raised(tmp_path):
    junit = tmp_path / "junit.xml"
    junit.write_text(_JUNIT)
    outcomes = parse_junit(junit)

    def runner(spec: Path, out_dir: Path):
        if spec.parent.name == "grid":
            raise RuntimeError("nope")
        return 4, 0, 0.5

    rows = {r.name: r for r in example_rows(outcomes, runner)}
    assert rows["ecosystem"].trials == 4 and rows["ecosystem"].test_outcome == "passed" and rows["ecosystem"].phrase
    assert rows["grid"].error.startswith("RuntimeError")
    rep = build(outcomes, pytest_exit=1, example_runner=runner)
    md = render_markdown(rep)
    assert "FAILURES" in md and "| ❌ | B2 |" in md and "`grid`" in md and "error: RuntimeError" in md
    page = render_html(rep)
    assert "<table>" in page and "&lt;" not in md and len(DIMENSIONS) == 35


def test_the_verdict_is_read_off_the_page_not_the_pytest_exit_code(tmp_path):
    """T051 box 4 — ``bio report --junit`` hard-coded the pytest exit to 0
    and a broken example never reached it, so a page whose own rows read
    ``1 failed`` or ``error: RuntimeError`` was titled ALL PASSED and the
    command exited 0. The verdict now comes from the totals and the example
    rows; the command exits 1 on either."""
    from alienbio.commands.report_cmd import report_command

    junit = tmp_path / "junit.xml"
    junit.write_text(_JUNIT)
    outcomes = parse_junit(junit)

    with_failures = build(outcomes, pytest_exit=0, run_examples=False)
    assert with_failures.totals["failed"] == 1
    assert with_failures.ok is False
    assert render_markdown(with_failures).startswith("# ABIO test report — FAILURES")

    clean = {k: v for k, v in outcomes.items() if v != "failed"}

    def broken(spec: Path, out_dir: Path):
        raise RuntimeError("nope")

    example_broke = build(clean, pytest_exit=0, example_runner=broken)
    assert example_broke.totals["failed"] == 0
    assert example_broke.ok is False
    assert "FAILURES" in render_markdown(example_broke).splitlines()[0]

    def fine(spec: Path, out_dir: Path):
        return 4, 0, 0.5

    # T088 report 1: a clean JUnit file that lacks the proving tests is not
    # a pass — every built row reads "not run", so the page says NOT PROVEN.
    unproven = build(clean, pytest_exit=0, example_runner=fine)
    assert unproven.ok is False and "A2" in unproven.unproven
    assert render_markdown(unproven).startswith("# ABIO test report — NOT PROVEN")
    proven = dict(clean)
    for _d, tests in matrix():
        for t in tests:
            module, name = t.split("::", 1)
            proven[(module, name)] = "passed"
    # T091 B6: the capability tests alone are not a pass — every broader
    # suite row must have run and passed too.
    cap_only = build(proven, pytest_exit=0, example_runner=fine)
    assert cap_only.ok is False and cap_only.unrun_suites
    assert render_markdown(cap_only).startswith("# ABIO test report — NOT PROVEN")
    for rel in SUITES:
        proven[(Path(rel).stem, "test_ran")] = "passed"
    assert build(proven, pytest_exit=0, example_runner=fine).ok is True

    assert report_command(["--junit", str(junit), "--no-examples", "--out", str(tmp_path / "out")]) == 1
    assert (tmp_path / "out" / "report.md").read_text().startswith("# ABIO test report — FAILURES")
    assert report_command(["--junit"]) == 2


def test_a_corrupt_run_manifest_is_a_named_note_not_a_crash(tmp_path, monkeypatch):
    """T088 report 2 — one unreadable ``runs/*/manifest.json`` raised out of
    ``build`` after the full pytest run, so nothing was written. The run is
    skipped and the page names it."""
    import alienbio.report as report

    runs = tmp_path / "runs"
    (runs / "bad").mkdir(parents=True)
    (runs / "bad" / "manifest.json").write_text("{not json")
    monkeypatch.setattr(report, "RUNS", runs)
    rep = build({}, pytest_exit=0, run_examples=False)
    assert rep.runs == []
    assert any(n.startswith("runs/bad skipped: JSONDecodeError") for n in rep.notes)
    assert "runs/bad skipped" in render_markdown(rep)


def test_figure_links_are_relative_to_the_output_folder(tmp_path, monkeypatch):
    """T088 report 3 — a figure link was made relative to ``reports/``
    whatever ``--out`` said, so a page written elsewhere linked nowhere."""
    import json

    import alienbio.report as report

    runs = tmp_path / "runs"
    run = runs / "r1"
    run.mkdir(parents=True)
    (run / "manifest.json").write_text(json.dumps({"spec": {}, "trials_completed": 1}))
    (run / "key.png").write_bytes(b"\x89PNG")
    (run / "key.json").write_text(json.dumps({"readout": "x", "caption": "c"}))
    monkeypatch.setattr(report, "RUNS", runs)
    out = tmp_path / "elsewhere" / "deep"
    rep = build({}, pytest_exit=0, run_examples=False, out_dir=out)
    md = render_markdown(rep)
    assert "](../../runs/r1/key.png)" in md
    assert (out / "../../runs/r1/key.png").resolve() == (run / "key.png").resolve()
    assert "data:image/png;base64," in render_html(rep)


def test_bio_report_runs_the_spec_named_after_its_folder_and_never_a_live_one(tmp_path, monkeypatch):
    """T088 report 5 — the alphabetically first ``*.yaml`` was run with no
    cost check; ``agent_loop/live.yaml`` was safe only by spelling."""
    import alienbio.report as report

    seen = []

    def runner(spec: Path, out_dir: Path):
        seen.append(spec)
        return 1, 0, 0.0

    example_rows({}, runner)
    by_folder = {p.parent.name: p.name for p in seen}
    assert by_folder["agent_loop"] == "agent_loop.yaml"
    assert by_folder["pathway_puzzles"] == "puzzles.yaml"

    with __import__("pytest").raises(ValueError, match="live-model arm"):
        report._run_example(report.EXAMPLES / "agent_loop" / "live.yaml", tmp_path / "run")


def test_suite_rows_count_cases_and_xfails_are_not_skips(tmp_path):
    """T091 U11 — section 2 counted functions (``test_golden_experiments.py``
    read ``2 passed`` for 15 hashed zeros and the pin test), and the header
    folded 43 xfails into ``46 skipped``."""
    from alienbio.report import count_cases, count_module_cases

    junit = tmp_path / "junit.xml"
    junit.write_text("""<?xml version="1.0"?>
<testsuites><testsuite name="pytest">
<testcase classname="tests.suite.test_golden_experiments" name="test_pin"/>
<testcase classname="tests.suite.test_golden_experiments" name="test_zero[exp01]"/>
<testcase classname="tests.suite.test_golden_experiments" name="test_zero[exp02]"/>
<testcase classname="tests.suite.test_golden_experiments" name="test_zero[exp03]"/>
<testcase classname="tests.suite.test_golden_experiments" name="test_gap"><skipped type="pytest.xfail" message="known"/></testcase>
<testcase classname="tests.suite.test_golden_experiments" name="test_off"><skipped type="pytest.skip" message="no jax"/></testcase>
</testsuite></testsuites>
""")
    totals = count_cases(junit)
    assert totals == {"passed": 4, "failed": 0, "skipped": 1, "xfailed": 1}
    rep = build(parse_junit(junit), pytest_exit=0, run_examples=False, totals=totals, case_counts=count_module_cases(junit))
    row = next(s for s in rep.suites if s.module.endswith("test_golden_experiments.py"))
    assert (row.passed, row.skipped, row.xfailed) == (4, 1, 1)
    md = render_markdown(rep)
    assert "4 passed, 0 failed, 1 skipped, 1 xfailed" in md.splitlines()[2]
    assert "| 4 passed, 1 skipped, 1 xfailed |" in md


def test_no_examples_is_never_titled_all_passed(tmp_path):
    """T091 U12 — the Testing Guide's ALL PASSED requires every example to
    have run clean; ``--no-examples`` ran none, so the page is NOT PROVEN."""
    proven: dict = {}
    for _d, tests in matrix():
        for t in tests:
            module, name = t.split("::", 1)
            proven[(module, name)] = "passed"
    for rel in SUITES:
        proven[(Path(rel).stem, "test_ran")] = "passed"
    rep = build(proven, pytest_exit=0, run_examples=False)
    assert rep.ok is False
    assert render_markdown(rep).startswith("# ABIO test report — NOT PROVEN (examples not run)")
