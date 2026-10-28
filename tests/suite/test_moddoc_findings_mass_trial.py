"""Mass-trial fix round (T084, ABIO MassTrialRunner module doc).

Each section pins one finding: it failed before its fix and passes after.

A. ``_marginal_cell_means`` looked cells up by the RAW ``condition_key``
   while ``cells`` is keyed by ``bucket_key``, so a two-level axis whose
   levels are lists or mappings (``levers``, ``output_schedule``) crossed
   with any other two-level axis raised ``TypeError: unhashable`` after
   every trial had run; ``sorted`` over mapping levels raised too, and the
   contrast pooled nothing (a raw list level never equals its frozen tuple).
"""

from __future__ import annotations

import pytest

from alienbio.suite.deliberation import DeliberationTrace
from alienbio.suite.dist import Seed
from alienbio.suite.mass_trial import aggregate_records
from alienbio.suite.trial import TrialRecord, condition_key
from alienbio.suite.types import Timeline


def _record(dials, score):
    return TrialRecord(
        task_id="w",
        condition_key=condition_key(dials),
        final_timeline=Timeline(times=(), states=()),
        deliberation_trace=DeliberationTrace(),
        action_log=(),
        objective_score=score,
        terminal_reason="committed",
    )


# A ---------------------------------------------------------------------------

LEVERS = (["feed_fast"], ["feed_fast", "feed_clean"])
SCHEDULES = ({"every": 2, "deep": 400, "shallow": 50}, {"every": 4, "deep": 800, "shallow": 50})


def test_list_and_mapping_levels_aggregate_into_interactions_and_contrasts():
    axes = (("levers", LEVERS), ("output_schedule", SCHEDULES))
    records = []
    for a, lv in enumerate(LEVERS):
        for b, sched in enumerate(SCHEDULES):
            for j in range(3):
                records.append(_record({"levers": lv, "output_schedule": sched}, a + 2 * b + 0.1 * j + 0.5 * a * b))
    rmap = aggregate_records(records, axes, Seed(1), 3)

    assert len(rmap.cells) == 4
    assert rmap.interactions[("levers", "output_schedule")] == pytest.approx(0.5)
    assert ("levers", "output_schedule") in rmap.contrasts
    assert rmap.contrasts[("levers", "output_schedule")].cohens_d > 0
    rmap.to_json()
    rmap.to_csv()


def test_a_list_axis_crossed_with_a_scalar_axis_aggregates():
    axes = (("levers", LEVERS), ("pi", (0.0, 1.0)))
    records = [
        _record({"levers": lv, "pi": pi}, a + pi + 0.1 * j)
        for a, lv in enumerate(LEVERS)
        for pi in (0.0, 1.0)
        for j in range(2)
    ]
    rmap = aggregate_records(records, axes, Seed(1), 2)
    assert rmap.interactions[("levers", "pi")] == pytest.approx(0.0)
    assert ("levers", "pi") in rmap.contrasts
