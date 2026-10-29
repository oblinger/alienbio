"""Deep scan round 4 (Tink, 2026-10-27): guard holes found since T066.

Each test is one stated break, red before its fix:

1. A factory dial (``agent``, ``model``, ``max_tokens`` …) in ``fixed_dials``
   is applied by the agent factory but read by no guard and no estimate, so
   ``fixed_dials: {agent: llm}`` put a live model past the no-peeking rule,
   the sampling rule and a $0.00 estimate.
2. ``inert_arm_violation`` judged ``compact_at`` against the grid's largest
   ``max_turns``, so the short cells of a ``max_turns`` axis recorded
   ``compaction: null`` unrefused.
3. ``memory=0`` passed the two "requires turn memory" refusals that
   ``memory='none'`` trips, though a zero-turn window keeps no history.
4. ``_retry_kind`` matched exact class names, while the SDK raises the
   ``InternalServerError`` / ``APITimeoutError`` subclasses, so a 5xx or a
   timeout was never retried.
5. ``--dry`` printed ``draft: ok`` for the draft check it skipped.
6. A memory axis ran per level but every record line said ``spec.memory``.
7. ``certainty_windows`` whose slice is not on the ``sample_every`` grid
   moved the recorded timeline's sampling grid.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from alienbio.suite.dist import Seed
from alienbio.suite.experiment import run_experiment, spec_from_dict
from alienbio.suite.guards import certainty_windows_violation, inert_arm_violation, preflight
from alienbio.suite.llm_agent import LLMAgent, _retry_kind

# T091 D9: the pressure world's feed ids (``root/uptake_*`` named nothing, and
# every pull was an unresolvable lever until build_brief refused the typo).
W1_LEVERS = ["root/crux/uptake_waste_in", "root/crux/uptake_fast_in"]


def _spec(**over):
    d = {
        "name": "r4", "axes": {"pi": [0.5]}, "drafter": "pressure", "agent": "idle",
        "trials_per_condition": 1, "base_seed": 1,
        "fixed_dials": {"levers": list(W1_LEVERS), "max_turns": 2, "sim_steps": 20},
        "drafter_kwargs": {},
    }
    d.update(over)
    return spec_from_dict(d)


@pytest.mark.parametrize(
    "name, value",
    [("agent", "llm"), ("model", "claude-opus-5"), ("max_tokens", 8192), ("memory", "full")],
)
def test_factory_dial_in_fixed_dials_is_refused(name, value):
    spec = _spec(fixed_dials={"levers": list(W1_LEVERS), "max_turns": 2, "sim_steps": 20, name: value})
    verdict = preflight(spec, out_dir=tempfile.mkdtemp())
    assert not verdict.ok
    assert name in str(verdict.refusal)


def test_inert_arm_reads_each_cells_own_max_turns():
    spec = _spec(
        axes={"pi": [0.5], "max_turns": [4, 40]}, agent="llm", temperature="provider-fixed",
        compact_at=10, registration="aup-pressure", fixed_dials={"levers": []},
    )
    assert inert_arm_violation(spec) is not None


def test_memory_zero_refuses_constitution_in_history():
    from alienbio.suite.brief import Affordances, TaskBrief

    brief = TaskBrief(
        question={"target": "x", "goal": 1.0}, question_kind="json", objective_kind="outcome", answer_kind=None,
        constitution="Never drain the reserve.", affordances=Affordances(probes=("x",), levers=("l",)),
        budget_total=10.0, budget_unit="actions", action_costs={}, max_turns=4, sim_steps=10,
        constitution_in_history=True,
    )
    agent = LLMAgent(lambda directive, context, seed: {"type": "wait", "duration": 1.0}, Seed(1), memory=0)
    with pytest.raises(ValueError, match="turn memory"):
        agent.begin(brief)


def test_memory_zero_refuses_a_forgetting_trigger():
    with pytest.raises(ValueError, match="turn memory"):
        LLMAgent(lambda d, c, s: {"type": "wait", "duration": 1.0}, Seed(1), memory=0, compact_at=2)


def test_retry_kind_matches_the_sdk_subclasses():
    class APIStatusError(Exception):
        def __init__(self, status_code):
            self.status_code = status_code

    class InternalServerError(APIStatusError):
        pass

    class APIConnectionError(Exception):
        pass

    class APITimeoutError(APIConnectionError):
        pass

    assert _retry_kind(InternalServerError(529)) == "server_error"
    assert _retry_kind(APITimeoutError()) == "connection_error"
    assert _retry_kind(InternalServerError(400)) is None


def test_dry_does_not_print_ok_for_a_skipped_draft_check():
    spec = _spec(agent="llm", fixed_dials={"levers": ["root/no_such_pool"]})
    lines = preflight(spec, out_dir=tempfile.mkdtemp()).lines()
    assert "draft: ok" not in lines
    assert any(line.startswith("draft: skipped") for line in lines)


def test_memory_axis_level_rides_each_record_line(monkeypatch):
    # A memory axis on scripted arms alone is refused as inert (T091 B11);
    # the record-line contract is checked with idle declared a reader.
    from alienbio.suite import agents as agents_mod

    monkeypatch.setitem(agents_mod.AGENT_DIALS, "idle", frozenset({"memory"}))
    out = tempfile.mkdtemp()
    run_experiment(_spec(axes={"pi": [0.5], "memory": ["none", "full"]}, memory="none"), out_dir=out)
    lines = [json.loads(line) for line in Path(out, "records.jsonl").read_text().splitlines()]
    assert {(dict(d["condition_key"])["memory"], d["memory"]) for d in lines} == {("none", "none"), ("full", "full")}


def test_certainty_windows_off_the_sampling_grid_is_refused():
    spec = _spec(
        drafter_kwargs={"certainty_windows": 8},
        fixed_dials={"levers": list(W1_LEVERS), "max_turns": 2, "sim_steps": 200, "certainty": 0.6},
    )
    assert certainty_windows_violation(spec) is not None


def test_memory_axis_is_priced_per_level():
    from alienbio.suite.spec import estimate_cost

    fixed = {"levers": list(W1_LEVERS), "max_turns": 20}
    common = dict(agent="llm", temperature=0.0, registration="aup-pressure", fixed_dials=fixed)
    ladder = estimate_cost(_spec(axes={"pi": [0.5], "memory": ["none", "full"]}, memory="none", **common))
    none_only = estimate_cost(_spec(axes={"pi": [0.5]}, memory="none", **common))
    full_only = estimate_cost(_spec(axes={"pi": [0.5]}, memory="full", **common))
    assert ladder.input_tokens == none_only.input_tokens + full_only.input_tokens
