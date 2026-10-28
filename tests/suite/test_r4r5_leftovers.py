"""Leftovers from deep-scan rounds 4 and 5 (Tink, 2026-10-27).

Each test is one stated break, red before its fix:

1. The YAML experiment form refused a factory-dial axis (``memory``,
   ``max_tokens``, the forgetting triggers, ``output_schedule``) as "swept
   but no call reads them", though the Python form sweeps every one and the
   Suite Runtime doc calls them sweepable.
2. The manifest header said ``memory: <spec.memory>`` under a ``memory``
   axis — a setting no cell but one ran — where ``model`` already went null
   with its levels on ``models``.
3. A bare ``pytest`` from the repo root died at collection: the site-packages
   ``tests`` package of ``mkdocs_roamlinks_plugin`` shadowed ours.
4. ``world_variance`` stamped a ``k_hop`` factor on the oracle for worlds
   with no hop chain (W2 always, W1 at ``complexity 0``) — a scaling nothing
   carried.
5. On the ``compact_at`` turn the ceiling was tested on the PRE-compaction
   prompt alone, which never counted the summarizer's own prompt — so a turn
   whose summarizer call put it over the ceiling passed the pre-check, paid
   for the summarizer, then aborted on the post-check: the T066 hole again.
6. ``draft_violation`` returned ``None`` on the first non-config exception,
   so a transient failure on one condition hid every later condition's config
   refusal, and it named only the first refusing condition.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import alienbio.cli as cli
from alienbio.suite import guards
from alienbio.suite.dist import Seed
from alienbio.suite.drafters import DRAFTERS
from alienbio.suite.experiment import spec_from_dict
from alienbio.suite.expr_experiment import load_experiment, spec_to_text
from alienbio.suite.guards import draft_violation
from alienbio.suite.llm_agent import LLMAgent, is_compact_context
from alienbio.suite.pressure_gen import world_variance_factors
from alienbio.suite.runner import run
from alienbio.suite.spec import estimate_cost
from alienbio.suite.store import _build_manifest

REPO = Path(__file__).resolve().parents[2]
P1_LEVERS = ["root/uptake_route_in", "root/uptake_neutral_in"]
W1_LEVERS = ["root/crux/uptake_waste_in", "root/crux/uptake_fast_in"]


def _yaml(axes: str) -> str:
    return (
        "!experiment\n"
        "name: t\n"
        "task: !q phase1_pressure(variant='commitment_no_coupling')\n"
        "brief: !q brief(levers=[])\n"
        "agent: llm\n"
        "temperature: provider-fixed\n"
        f"axes: {axes}\n"
        "trials_per_condition: 1\n"
        "base_seed: 1\n"
    )


# 1 ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "axis, levels",
    [
        ("memory", "[2, 6]"),
        ("max_tokens", "[256, 1024]"),
        ("compact_at", "[2, 4]"),
        ("compact_budget", "[100, 200]"),
        ("history_token_limit", "[500, 2000]"),
    ],
)
def test_yaml_form_sweeps_a_factory_dial_axis(axis, levels):
    spec = load_experiment("<t>", text=_yaml(f"{{{axis}: {levels}}}"))
    assert dict(spec.axes)[axis] == tuple(int(v) for v in levels.strip("[]").split(","))
    assert axis not in spec.fixed_dials
    assert load_experiment("<t>", text=spec_to_text(spec)) == spec, "the form round-trips"


def test_yaml_memory_axis_estimates_per_level_and_dry_names_them(tmp_path, capsys):
    text = _yaml("{memory: [2, 6]}")
    spec = load_experiment("<t>", text=text)
    assert "memory=k=2/k=6" in estimate_cost(spec).formula
    path = tmp_path / "m.yaml"
    path.write_text(text)
    assert cli.main(["suite", "run", str(path), "--dry"]) == 0
    out = capsys.readouterr().out
    assert "conditions: 2" in out and "memory=k=2/k=6" in out


def test_yaml_non_factory_unread_axis_is_still_refused():
    with pytest.raises(Exception, match="swept but no call reads them"):
        load_experiment("<t>", text=_yaml("{token_ceiling: [100, 200]}"))


# 2 ---------------------------------------------------------------------------


def _llm_dict(**over):
    d = {
        "name": "t", "axes": {}, "drafter": "phase1_pressure", "agent": "llm",
        "trials_per_condition": 1, "base_seed": 1, "fixed_dials": {"levers": []},
        "drafter_kwargs": {"variant": "commitment_no_coupling"}, "temperature": "provider-fixed",
    }
    d.update(over)
    return d


def test_manifest_memory_under_a_memory_axis():
    swept = _build_manifest(spec_from_dict(_llm_dict(axes={"memory": ["none", 4]})), 2, "t")
    assert swept["memory"] is None and swept["memories"] == ["none", 4]
    fixed = _build_manifest(spec_from_dict(_llm_dict(memory=6)), 1, "t")
    assert fixed["memory"] == 6 and "memories" not in fixed


# 3 ---------------------------------------------------------------------------


def test_bare_pytest_collects_the_tests_tree():
    """``pytest --co`` with no path, from the repo root, collects as many
    items as ``pytest tests/ --co`` — the shadowing ``tests`` package no
    longer breaks collection."""

    def count(*args: str) -> str:
        out = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--co", "-p", "no:cacheprovider", *args],
            cwd=REPO, capture_output=True, text=True, timeout=300,
        ).stdout.strip().splitlines()
        return out[-1].split(" in ")[0]

    bare = count()
    assert "error" not in bare, bare
    assert bare == count("tests/")


# 4 ---------------------------------------------------------------------------


def _variance_stamp(head: str, seed: int, **dials):
    d = {"pi": 0.5, "levers": list(W1_LEVERS), "world_variance": 0.2, **dials}
    if head == "pressure_w2":
        d.update(sim_dt=0.005, sim_steps=200)
    _world, task = DRAFTERS[head](Seed(seed), d)
    return task.setup["oracle"]["pressure"]["world_variance"]["factors"]


def test_oracle_lists_only_the_variance_factors_the_world_applied():
    draw = world_variance_factors(Seed(3), 0.2)
    flat = _variance_stamp("pressure", 3, complexity=0)
    hopped = _variance_stamp("pressure", 3, complexity=1)
    w2 = _variance_stamp("pressure_w2", 3, depth=1, fan_out=0)
    assert "k_hop" not in flat and "k_hop" not in w2
    assert hopped == draw, "a hop chain carries every factor"
    # The draw itself is unchanged: every other factor is the same number.
    assert flat == {k: v for k, v in draw.items() if k != "k_hop"} == w2


# 5 ---------------------------------------------------------------------------


def _forgetting_run(ceiling, *, compact_budget=None):
    seen: list = []
    spent: list[int] = []
    agent_box: list[LLMAgent] = []

    def llm_fn(directive, context, seed):
        seen.append(context)
        spent.append(agent_box[0]._tokens_spent)
        if is_compact_context(context):
            return "s"
        return {"type": "wait", "duration": 1.0}

    dials = {"variant": "commitment_no_coupling", "levers": list(P1_LEVERS)}
    world, task = DRAFTERS["phase1_pressure"](Seed(5).child("d"), dials)
    agent = LLMAgent(
        llm_fn, Seed(5).child("llm"), memory="full", compact_at=2,
        compact_budget=compact_budget, token_ceiling=ceiling,
    )
    agent_box.append(agent)
    record = run(world, task, agent, dials, Seed(5).child("r"), max_turns=4)
    return record, seen, spent


@pytest.mark.parametrize("budget", [None, 50])
def test_compact_turn_aborts_before_paying_for_the_summarizer(budget):
    """The ceiling the turn crosses only once the summarizer's own prompt is
    counted: aborted before that call, not after it.

    The brief's other case — over the ceiling on the pre-compaction prompt,
    under it after compaction — cannot occur on the compaction turn itself:
    the turn also pays the summarizer, whose prompt re-reads the displaced
    history and the system prompt, so its cost is never below the
    pre-compaction prompt. Compaction is cheaper only on LATER turns."""
    _, seen, spent = _forgetting_run(None, compact_budget=budget)
    # spent[i] is the running total as the i-th call goes out; calls are
    # turns 0, 1, then the summarizer and turn 2.
    compact_index = next(i for i, c in enumerate(seen) if is_compact_context(c))
    through_turn_2 = spent[compact_index + 1]
    record, seen_capped, _ = _forgetting_run(through_turn_2 - 2, compact_budget=budget)
    assert not any(is_compact_context(c) for c in seen_capped), "paid for the summarizer, then aborted"
    assert record.compaction is None
    assert len(seen_capped) == compact_index


@pytest.mark.parametrize("budget", [None, 50])
def test_compact_turn_under_the_ceiling_compacts(budget):
    """No false abort: a ceiling the whole turn (summary budget included)
    fits under still compacts."""
    _, seen, spent = _forgetting_run(None, compact_budget=budget)
    compact_index = next(i for i, c in enumerate(seen) if is_compact_context(c))
    # The pre-check reserves the summary's whole budget (the real one is "s").
    record, _, _ = _forgetting_run(spent[compact_index + 1] + (budget or 0), compact_budget=budget)
    assert record.compaction is not None and record.compaction["turn"] == 2


# 6 ---------------------------------------------------------------------------


def _w1_spec(axes):
    fixed = {"levers": list(W1_LEVERS), "max_turns": 2, "sim_steps": 20}
    if "pi" not in axes:
        fixed["pi"] = 0.5
    return spec_from_dict({
        "name": "r6", "axes": axes, "drafter": "pressure", "agent": "idle",
        "trials_per_condition": 1, "base_seed": 1, "fixed_dials": fixed,
    })


def test_draft_violation_names_every_refusing_condition():
    why = draft_violation(_w1_spec({"certainty": [0.05, 0.1]}))
    assert why is not None
    assert "0.05" in why and "0.1" in why


def test_a_transient_failure_does_not_hide_a_later_config_refusal(monkeypatch):
    real = DRAFTERS["pressure"]

    def flaky(seed, dials, **kw):
        if dials["pi"] == 0.2:
            raise RuntimeError("provider hiccup")
        if dials["pi"] == 0.4:
            raise ValueError("pi 0.4 is not draftable here")
        return real(seed, dials, **kw)

    monkeypatch.setattr(guards, "DRAFTERS", {"pressure": flaky})
    why = draft_violation(_w1_spec({"pi": [0.2, 0.4]}))
    assert why is not None and "pi 0.4 is not draftable" in why
    assert "0.2" not in why.split("—")[0], "the transient condition is not a config verdict"
