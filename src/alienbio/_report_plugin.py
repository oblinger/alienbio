"""pytest plugin ``bio report`` loads (``-p alienbio._report_plugin``): mark a
non-strict XPASS in the JUnit file.

JUnit XML writes a non-strict XPASS as a bare ``<testcase/>``, the same as a
pass, so the report's header read ``3 passed`` where pytest's summary said
``1 passed, 2 xpassed`` (T091 AE5). This records a ``xpassed`` property on
the case, which :func:`alienbio.report.count_cases` counts apart. A strict
XPASS is already a ``<failure>`` and is left alone.
"""

from __future__ import annotations

from typing import Any, Generator

import pytest


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: Any) -> Generator[None, Any, Any]:
    report = yield
    if report.when == "call" and report.passed and hasattr(report, "wasxfail"):
        item.user_properties.append(("xpassed", "1"))
    return report
