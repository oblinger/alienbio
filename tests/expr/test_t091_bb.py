"""T091 round BC — older surface (b): ``functools.lru_cache`` /
``functools.cache`` on helper code.

A cached wrapper is judged by the function it caches (its ``__wrapped__``),
wherever a partial or bound method is unwrapped: a helper's cached function,
a cached ``__call__`` and ``staticmethod(lru_cache(f))`` run, while
``lru_cache(os.getcwd)`` still refuses as foreign code. No other
``__wrapped__`` is followed: a ``functools.wraps`` decorator's wrapper is the
code that runs.
"""

from __future__ import annotations

import pytest

from alienbio.expr import Env, ExprError

_HELPERS = """
import functools
import os


def hf(*a, **k):
    return "helper-ran"


def _mk(attr):
    return type("K", (), {"__call__": attr})()


class LruK:
    @functools.lru_cache(maxsize=None)
    def __call__(self, *a):
        return "lru-ran"


class CacheK:
    @functools.cache
    def __call__(self, *a):
        return "cache-ran"


def deco(f):
    @functools.wraps(f)
    def g(*a, **k):
        return f(*a, **k)
    return g


class WrapsK:
    @deco
    def __call__(self, *a):
        return "wrapsdeco-ran"


cached_fn = functools.lru_cache(maxsize=None)(hf)
cache_fn = functools.cache(hf)
s_lru = LruK()
s_cache = CacheK()
s_wrapsdeco = WrapsK()
s_static_lru = _mk(staticmethod(functools.lru_cache(maxsize=None)(hf)))
s_partial_of_lru = _mk(functools.partial(cached_fn, 1))
s_lru_foreign_call = _mk(staticmethod(functools.lru_cache(maxsize=None)(os.getcwd)))
_dressed = functools.partial(os.getcwd)
_dressed.__wrapped__ = hf
s_dressed_foreign = _mk(staticmethod(_dressed))
"""


def _load(tmp_path, body: str):
    (tmp_path / "helpers.py").write_text(_HELPERS)
    path = tmp_path / "t.yaml"
    path.write_text("h: !include helpers.py\n" + body)
    return Env.standard(seed=0, trusted=True).load(str(path)).force_all()


@pytest.mark.parametrize(
    "call, expected",
    [
        ("h.cached_fn(1)", "helper-ran"),
        ("h.cache_fn(2)", "helper-ran"),
        ("h.s_lru()", "lru-ran"),
        ("h.s_cache()", "cache-ran"),
        ("h.s_static_lru()", "helper-ran"),
        ("h.s_partial_of_lru()", "helper-ran"),
        ("h.s_wrapsdeco()", "wrapsdeco-ran"),
    ],
)
def test_a_cached_helper_function_or_call_runs(tmp_path, call, expected):
    """A helper's ``lru_cache`` / ``cache`` function, a cached ``__call__``, a static or partial cached ``__call__`` run as the helper code they cache."""
    assert _load(tmp_path, f'v: !x "{call}"\n')["v"] == expected


def test_a_cached_foreign_function_still_refuses_naming_its_module(tmp_path):
    """``staticmethod(lru_cache(os.getcwd))`` as a helper class's ``__call__`` refuses as code from ``posix``."""
    with pytest.raises(ExprError, match=r"it runs code from 'posix': only the spec's included helpers"):
        _load(tmp_path, 'v: !x "h.s_lru_foreign_call()"\n')


def test_a_wrapped_attribute_is_followed_only_on_a_cache_wrapper(tmp_path):
    """A ``__call__`` that is a partial of ``os.getcwd`` carrying a helper's ``__wrapped__`` still refuses as ``posix`` code: only the cache wrapper's ``__wrapped__`` is followed."""
    with pytest.raises(ExprError, match=r"runs code from 'posix'"):
        _load(tmp_path, 'v: !x "h.s_dressed_foreign()"\n')
