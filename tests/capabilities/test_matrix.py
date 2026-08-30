"""The capability gate (M48.1 / M48.8): every built or partial dimension is
proven by a named test in this directory, and every claimed id exists."""

from __future__ import annotations

import subprocess
import sys

from alienbio.capabilities import BY_ID, DIMENSIONS, check, matrix, render_markdown, unknown_ids


def test_there_are_thirty_five_dimensions_in_the_design_docs_order():
    assert len(DIMENSIONS) == 35
    assert [d.group for d in DIMENSIONS] == sorted([d.group for d in DIMENSIONS], key="ABCI".index)


def test_every_built_or_partial_dimension_has_a_proof():
    missing = check()
    assert not missing, f"dimensions with no @capability test: {missing}"


def test_no_test_claims_an_unknown_dimension():
    assert unknown_ids() == []


def test_planned_and_future_dimensions_are_named_not_faked():
    for d, tests in matrix():
        if d.status in ("planned", "future"):
            assert not tests, f"{d.id} is {d.status} but has tests {tests} — mark it built"
    assert {d.id for d in DIMENSIONS if d.status == "future"} == {"B18", "C11"}
    assert {d.id for d in DIMENSIONS if d.status == "planned"} == {"B16"}


def test_the_markdown_table_and_the_cli_agree():
    table = render_markdown()
    assert table.count("\n") == 2 + len(DIMENSIONS)
    for d in DIMENSIONS:
        assert f"| {d.id} |" in table
    out = subprocess.run([sys.executable, "-m", "alienbio.cli", "test-matrix", "--check"], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "every built / partial dimension is proven" in out.stderr
    assert BY_ID["I1"].group == "I"
