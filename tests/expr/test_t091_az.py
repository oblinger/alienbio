"""T091 round BA — verifier AZ's findings on the access rule.

AZ4: a property, descriptor or non-callable set directly as a metaclass
``__call__`` refuses with that reason. AZ5: every refusal reason is true — a
non-callable ``__call__`` is named as not callable, a C wrapper as a C
wrapper, and the depth text appears only past ``MAX_CALL_DEPTH``. AZ6: a
``__call__`` whose type defines ``__get__`` is refused as a descriptor,
callable or not.
"""

from __future__ import annotations

import pytest

from alienbio.expr import Env, ExprError
from alienbio.expr.access import MAX_CALL_DEPTH

_HELPERS = """
import functools
import os


def hf(*a, **k):
    return "helper-ran"


class Other:
    def m(self, *a):
        return "bound-ran"


def _mk(attr):
    return type("K", (), {"__call__": attr})()


class CallDesc:
    def __get__(self, obj, owner=None):
        return os.getcwd

    def __call__(self, *a):
        return "calldesc-call-ran"


class DataDesc:
    def __get__(self, obj, owner=None):
        return hf

    def __set__(self, obj, v):
        pass


class PropK:
    @property
    def __call__(self):
        return hf


class NoneK:
    __call__ = None


class Lvl0:
    def __call__(self, *a):
        return "depth-ran"


def chain(n):
    inst = Lvl0()
    for i in range(n):
        inst = type(f"L{i + 1}", (), {"__call__": inst})()
    return inst


s_function = _mk(hf)
s_builtin_len = _mk(len)
s_bound_method = _mk(Other().m)
s_partial = _mk(functools.partial(hf, 1))
s_staticmethod = _mk(staticmethod(hf))
s_classmethod = _mk(classmethod(hf))
s_property = PropK()
s_data_desc = _mk(DataDesc())
s_callable_desc = _mk(CallDesc())
s_non_callable_int = _mk(5)
s_none = NoneK()
s_slot_wrapper = _mk(object.__repr__)
s_method_wrapper = _mk(object().__repr__)
s_partialmethod = _mk(functools.partialmethod(hf))
for _n in range(1, 10):
    globals()[f"s_depth{_n}"] = chain(_n)


class PropDesc:
    @property
    def __call__(self):
        return hf


class MProp(type):
    @property
    def __call__(cls):
        return hf


class MInt(type):
    __call__ = 5


class MInst(type):
    __call__ = PropDesc()


class CProp(metaclass=MProp):
    pass


class CInt(metaclass=MInt):
    pass


class CInst(metaclass=MInst):
    pass
"""

_DESCRIPTOR = "is a property or other descriptor (its type defines __get__"

#: AZ's 23 ``__call__`` shapes: the verdict (a value ran, or the refusal's
#: reason). Only ``callable_desc`` changed verdict (AZ6).
_SHAPES = [
    ("function", "helper-ran"),
    ("builtin_len", "it runs code from 'builtins'"),
    ("bound_method", "bound-ran"),
    ("partial", "helper-ran"),
    ("staticmethod", "helper-ran"),
    ("classmethod", "helper-ran"),
    ("property", f"its __call__ {_DESCRIPTOR}"),
    ("data_desc", f"its __call__ {_DESCRIPTOR}"),
    ("callable_desc", f"its __call__ {_DESCRIPTOR}"),
    ("non_callable_int", "its __call__ is int, which is not callable"),
    ("none", "its __call__ is None, which is not callable"),
    ("slot_wrapper", "its __call__ is a C wrapper_descriptor (object.__repr__), which runs no code the guard can judge"),
    ("method_wrapper", "its __call__ is a C method-wrapper (object.__repr__), which runs no code the guard can judge"),
    ("partialmethod", f"its __call__ {_DESCRIPTOR}"),
] + [(f"depth{n}", "depth-ran") for n in range(1, 8)] + [
    (f"depth{n}", f"its __call__ chain does not reach a function within MAX_CALL_DEPTH={MAX_CALL_DEPTH} levels")
    for n in (8, 9)
]


def _load(tmp_path, body: str):
    (tmp_path / "helpers.py").write_text(_HELPERS)
    path = tmp_path / "t.yaml"
    path.write_text("h: !include helpers.py\n" + body)
    return Env.standard(seed=0, trusted=True).load(str(path)).force_all()


@pytest.mark.parametrize(("shape", "expected"), _SHAPES, ids=[s for s, _ in _SHAPES])
def test_az5_az6_each_call_shape_gets_its_verdict_and_a_true_reason(tmp_path, shape, expected):
    """Each of AZ's 23 ``__call__`` shapes runs or refuses as before (``callable_desc`` now refuses), and each refusal states its true reason."""
    body = f'v: !x "h.s_{shape}()"\n'
    if expected in ("helper-ran", "bound-ran", "depth-ran"):
        assert _load(tmp_path, body)["v"] == expected
        return
    with pytest.raises(ExprError) as info:
        _load(tmp_path, body)
    message = str(info.value)
    assert expected in message
    if not shape.startswith("depth"):
        assert "MAX_CALL_DEPTH" not in message


def test_az6_a_callable_descriptor_call_never_runs_what_its_get_returns(tmp_path):
    """A callable descriptor ``__call__`` whose ``__get__`` returns ``os.getcwd`` refuses as a descriptor instead of running it."""
    with pytest.raises(ExprError, match=r"__get__"):
        _load(tmp_path, 'v: !x "h.s_callable_desc()"\n')


@pytest.mark.parametrize(
    ("cls", "expected"),
    [
        ("CProp", f"its metaclass MProp.__call__ {_DESCRIPTOR}"),
        ("CInt", "its metaclass MInt.__call__ is int, which is not callable"),
        ("CInst", f"its metaclass MInst.__call__.__call__ {_DESCRIPTOR}"),
    ],
)
def test_az4_a_metaclass_call_attribute_is_judged_itself(tmp_path, cls, expected):
    """A property, an int or a descriptor-backed instance as a metaclass ``__call__`` refuses naming what that attribute is, never "runs code from None"."""
    with pytest.raises(ExprError) as info:
        _load(tmp_path, f'v: !x "h.{cls}()"\n')
    message = str(info.value)
    assert expected in message and "from None" not in message
