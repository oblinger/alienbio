"""T091 round AW — verifier AV's findings on the access rule.

AV1: a helper's ``Enum`` / ``IntEnum`` / ``Flag`` is callable again (the
stdlib enum metaclass ``__call__`` is a named exception), a helper's own
metaclass ``__call__`` is judged as helper code, and a foreign function
installed as a metaclass ``__call__`` refuses with a message naming it.
AV6: a ``__call__`` chain of exactly ``MAX_CALL_DEPTH`` levels is callable,
one more is refused and the refusal names the bound.
"""

from __future__ import annotations

import pytest

from alienbio.expr import Env, ExprError
from alienbio.expr.access import MAX_CALL_DEPTH

_HELPERS = """
import enum
import os


class E(enum.Enum):
    A = 1
    B = 2


class IE(enum.IntEnum):
    A = 1


class F(enum.Flag):
    A = 1
    B = 2


class OwnMeta(type):
    def __call__(cls, *a, **k):
        return ("built", super().__call__(*a, **k).n)


class ViaOwn(metaclass=OwnMeta):
    def __init__(self, n=1):
        self.n = n


class ForeignMeta(type):
    __call__ = staticmethod(os.getcwd)


class ViaForeign(metaclass=ForeignMeta):
    pass


def chain(n):
    cls = type("L0", (), {"__call__": staticmethod(lambda: 7)})
    obj = cls()
    for i in range(n - 1):
        cls = type(f"L{i + 1}", (), {"__call__": obj})
        obj = cls()
    return obj
"""


def _load(tmp_path, body: str):
    (tmp_path / "helpers.py").write_text(_HELPERS)
    path = tmp_path / "t.yaml"
    path.write_text("h: !include helpers.py\n" + body)
    return Env.standard(seed=0, trusted=True).load(str(path)).force_all()


@pytest.mark.parametrize(
    ("expr", "expected"),
    [
        ("h.E(1)", "<E.A: 1>"),
        ("h.E['A']", "<E.A: 1>"),
        ("h.IE(1)", "<IE.A: 1>"),
        ("h.IE(1) + 1", "2"),
        ("h.F(1)", "<F.A: 1>"),
        ("h.F(3)", "<F.A|B: 3>"),
    ],
)
def test_av1_a_helper_enum_is_callable_and_subscriptable_as_at_3347b5d(tmp_path, expr, expected):
    """A helper's Enum, IntEnum and Flag construct by value and look up by name exactly as they did at 3347b5d."""
    assert repr(_load(tmp_path, f'v: !x "{expr}"\n')["v"]) == expected


def test_av1_enum_member_attributes_stay_refused(tmp_path):
    """Attribute reads on a helper enum class or member refuse as they did at 3347b5d."""
    with pytest.raises(ExprError, match="attribute access"):
        _load(tmp_path, 'v: !x "h.E.A"\n')


def test_av1_a_helper_metaclass_call_of_its_own_code_runs(tmp_path):
    """A metaclass ``__call__`` the helper itself defines is helper code and runs."""
    out = _load(tmp_path, 'v: !x "h.ViaOwn(3)"\n')
    assert tuple(out["v"]) == ("built", 3)


def test_av1_a_foreign_function_as_metaclass_call_refuses_naming_it(tmp_path):
    """A function from outside the helper installed as a metaclass ``__call__`` refuses, naming the metaclass call and the module it runs."""
    with pytest.raises(ExprError, match=r"metaclass ForeignMeta\.__call__ runs code from 'posix'"):
        _load(tmp_path, 'v: !x "h.ViaForeign()"\n')


def test_av6_a_chain_of_exactly_max_call_depth_levels_runs(tmp_path):
    """A ``__call__`` chain of exactly MAX_CALL_DEPTH levels down to a function is callable."""
    out = _load(tmp_path, f"c: !x h.chain({MAX_CALL_DEPTH})\nv: !x c()\n")
    assert out["v"] == 7


def test_av6_one_level_more_refuses_and_names_the_bound(tmp_path):
    """A chain of MAX_CALL_DEPTH + 1 levels refuses with a message naming MAX_CALL_DEPTH."""
    with pytest.raises(ExprError, match=f"MAX_CALL_DEPTH={MAX_CALL_DEPTH}"):
        _load(tmp_path, f"c: !x h.chain({MAX_CALL_DEPTH + 1})\nv: !x c()\n")
