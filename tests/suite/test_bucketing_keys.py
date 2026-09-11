"""T051 box 4 — every summary family buckets on a hashable condition key.

The 2026-08-31 fix (``hashable_condition_key``) reached caution, degradation
and realism; nine more sites still bucketed on the raw key and raised
``TypeError: unhashable type: 'list'`` on any direct ``runner.run`` record
(``levers`` is a list on every pressure trial — AUP's shape)."""

from __future__ import annotations

import pytest

from alienbio.suite.census import census_summary, outcome_distribution
from alienbio.suite.delta import delta_pairs
from alienbio.suite.dose import pressure_summary
from alienbio.suite.faking import monitoring_summary
from alienbio.suite.hazard import blindspot_summary, consideration_summary
from alienbio.suite.tradeoff import conflict_summary
from tests.suite.test_realism import _pressure_record

FAMILIES = [
    pressure_summary,
    census_summary,
    outcome_distribution,
    conflict_summary,
    monitoring_summary,
    delta_pairs,
    consideration_summary,
    blindspot_summary,
]


@pytest.mark.parametrize("summarize", FAMILIES, ids=lambda f: f.__name__)
def test_every_summary_family_accepts_a_list_valued_dial(summarize):
    record = _pressure_record()
    assert any(isinstance(v, list) for _n, v in record.condition_key), "repro precondition"
    out = summarize([record])
    keys = out[0] if isinstance(out, tuple) else out
    for key in keys:
        hash(key)


def test_pressure_and_census_families_bucket_the_direct_runner_record():
    record = _pressure_record()
    (key,) = pressure_summary([record])
    assert len(pressure_summary([record])[key]) == 1
    (ckey,) = census_summary([record])
    assert census_summary([record])[ckey].n == 1
