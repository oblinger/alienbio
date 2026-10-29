"""T091 round I and round D's leftovers: the rendered question is the same
text under every hash seed; the resume cost ceiling is the directory's
budget; the intervene scorer's compartment rule reads the chemistry and
refuses at construction."""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from alienbio.suite.experiment import AGENTS, ExperimentSpec, run_experiment

REPO = Path(__file__).resolve().parents[2]


# ---- D-left 1: a set-valued question renders sorted ------------------------

_RENDER = """
from alienbio.suite.brief import build_brief, render_brief
from alienbio.suite.dist import Seed
from alienbio.suite.experiment import DRAFTERS
from alienbio.suite.runner import Budget, narrow_observation
from alienbio.suite.verify import SimConfig
seed = Seed(3)
world, task = DRAFTERS["diagnose"](seed, {})
first = narrow_observation(world.initial_state, {}, seed.child("turn/0/observe"))
brief = build_brief(task, world.chemistry, first, {}, Budget(), 8, SimConfig(), seed=seed.child("brief"))
assert isinstance(brief.question, (set, frozenset)) and len(brief.question) > 2, brief.question
print(render_brief(brief).splitlines()[0])
"""


def _question_line(hashseed: str) -> str:
    env = {**os.environ, "PYTHONHASHSEED": hashseed, "PYTHONPATH": str(REPO / "src")}
    out = subprocess.run([sys.executable, "-c", _RENDER], env=env, capture_output=True, text=True, check=True, cwd=REPO)
    return out.stdout.strip()


def test_a_set_valued_question_renders_the_same_under_every_hash_seed():
    lines = {_question_line(h) for h in ("0", "1", "12345")}
    assert len(lines) == 1, lines
    (line,) = lines
    assert line.startswith("Question: ")
    members = json.loads(line[len("Question: "):]).strip("{}").split(", ")
    assert members == sorted(members)


# ---- D-left 2: the ceiling is the directory's budget -----------------------


def test_the_resume_ceiling_counts_every_retried_dollar(monkeypatch, tmp_path):
    """Press 2 moves press 1's paid error lines to records.retried.jsonl and
    leaves records.jsonl empty; press 3 must still see their spend — in the
    guard (a ceiling below it refuses) and in the runtime counter (at the
    spend, nothing runs). Before, both read records.jsonl alone: press 3 saw
    $0 and re-spent the whole ceiling."""

    class _SpendThenFail:
        def act(self, observation):
            raise RuntimeError("provider 500 after a paid call")

        @property
        def usage(self):
            return {"calls": 1, "input_tokens": 1_000_000, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0}

    monkeypatch.setitem(AGENTS, "idle", lambda spec: (lambda seed, dials: _SpendThenFail()))
    spec = ExperimentSpec(
        name="dir-budget",
        axes=(("rung", ("single",)),),
        drafter="conflict",
        agent="idle",
        trials_per_condition=4,
        base_seed=1,
        price_usd_per_mtok=(3.0, 15.0),
        cost_ceiling_usd=4.0,
        fixed_dials={"levers": []},
    )
    out = tmp_path / "run"
    run_experiment(spec, out_dir=str(out))
    spent = json.loads((out / "manifest.json").read_text())["cost_usd_spent"]
    assert spent == pytest.approx(6.0)  # two $3 trials: the second crossed $4

    at_spend = dataclasses.replace(spec, cost_ceiling_usd=spent)
    run_experiment(at_spend, out_dir=str(out), resume=True)  # press 2: moves the lines, runs nothing
    assert not (out / "records.jsonl").read_text().strip()
    assert (out / "records.retried.jsonl").read_text().count("\n") == 2

    with pytest.raises(ValueError, match=r"already spent \$6\.0000 — the ceiling is the directory's budget"):
        run_experiment(dataclasses.replace(spec, cost_ceiling_usd=5.0), out_dir=str(out), resume=True)
    third = run_experiment(at_spend, out_dir=str(out), resume=True)
    manifest = json.loads((out / "manifest.json").read_text())
    assert len(third.records) == 0 and third.provenance.stopped_early is True
    assert manifest["cost_usd_spent"] == pytest.approx(6.0)
    assert manifest["stopped_reason"] == "cost_ceiling"
