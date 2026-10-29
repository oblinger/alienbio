"""Test-wide safety net: no test reaches a live model provider (T091 Q, plausible 3).

Every test runs with ``ANTHROPIC_API_KEY`` / ``ALIENBIO_ANTHROPIC_API_KEY``
removed from the environment, and with the real SDK's client constructors
(``anthropic.Anthropic``, ``anthropic.AsyncAnthropic``) replaced by a function
raising ``RuntimeError("live provider in tests")`` — so the real provider
factory, ``suite.llm_agent.default_anthropic_llm_fn``, raises before any
request even when a key would otherwise resolve (a dev shell that exports it
from the Keychain, a key in the alienbio config file). A test that stubs the
SDK (``monkeypatch.setitem(sys.modules, "anthropic", …)``) is unaffected: it
never touches the real module.

A test that must reach the real provider opts in with ``@pytest.mark.live``;
such a test keeps the environment and the real SDK, and is SKIPPED unless
``ABIO_LLM_E2E=1`` is set — so a bare ``pytest`` never spends.
"""

from __future__ import annotations

import os

import pytest

_KEY_VARS = ("ANTHROPIC_API_KEY", "ALIENBIO_ANTHROPIC_API_KEY")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "live: reaches a real model provider (spends money); skipped unless ABIO_LLM_E2E=1"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("ABIO_LLM_E2E"):
        return
    skip = pytest.mark.skip(reason="live provider test: set ABIO_LLM_E2E=1 (and a key) to run")
    for item in items:
        if item.get_closest_marker("live") is not None:
            item.add_marker(skip)


def _refuse_live_provider(*args: object, **kwargs: object) -> object:
    raise RuntimeError("live provider in tests")


@pytest.fixture(autouse=True)
def _no_live_provider(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if request.node.get_closest_marker("live") is not None:
        return
    for var in _KEY_VARS:
        monkeypatch.delenv(var, raising=False)
    try:
        import anthropic  # type: ignore[import-not-found]
    except ImportError:
        return  # no SDK, no live path
    for name in ("Anthropic", "AsyncAnthropic"):
        if hasattr(anthropic, name):
            monkeypatch.setattr(anthropic, name, _refuse_live_provider)
