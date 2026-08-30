"""``bio report`` — the page that says what the tests tested: every proving
test carries a sentence, JUnit outcomes land on the right rows, and the
examples section survives an example that fails to run."""

from __future__ import annotations

from pathlib import Path

from alienbio.capabilities import DIMENSIONS, check_phrases, matrix, phrases
from alienbio.report import build, capability_rows, example_rows, parse_junit, render_html, render_markdown

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
