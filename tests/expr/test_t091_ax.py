"""T091 round AY — verifier AX's findings on the access rule.

AX2: the sandbox's stated boundary — a foreign function a helper author
wires into a protocol hook other than ``__call__`` runs as helper code, a
foreign ``__call__`` still refuses. AX5: a property or descriptor
``__call__`` refuses with its own reason, not the depth-bound text.
"""

from __future__ import annotations

import pytest

from alienbio.expr import Env, ExprError

_HELPERS = """
import os


class Sub:
    __getitem__ = staticmethod(os.path.basename)

    def __call__(self):  # helper code: makes the instance a readable reference
        return 1


class Call:
    __call__ = staticmethod(os.path.basename)


class Desc:
    def __get__(self, obj, owner=None):
        return os.getcwd


class WithDesc:
    __call__ = Desc()


class WithProp:
    @property
    def __call__(self):
        return os.getcwd


sub = Sub()
call = Call()
wd = WithDesc()
wp = WithProp()
"""


def _load(tmp_path, body: str):
    (tmp_path / "helpers.py").write_text(_HELPERS)
    path = tmp_path / "t.yaml"
    path.write_text("h: !include helpers.py\n" + body)
    return Env.standard(seed=0, trusted=True).load(str(path)).force_all()


def test_ax2_a_helper_wired_subscript_runs_and_a_foreign_call_still_refuses(tmp_path):
    """A foreign function the helper wired into ``__getitem__`` runs as helper code; the same function as ``__call__`` refuses."""
    assert _load(tmp_path, "v: !x \"h.sub['/a/b']\"\n")["v"] == "b"
    with pytest.raises(ExprError, match="posixpath"):
        _load(tmp_path, "v: !x \"h.call('/a/b')\"\n")


@pytest.mark.parametrize("name", ["wd", "wp"])
def test_ax5_a_descriptor_call_refuses_with_its_own_reason(tmp_path, name):
    """A property or non-callable descriptor ``__call__`` refuses naming the descriptor, not MAX_CALL_DEPTH."""
    with pytest.raises(ExprError, match="property or other descriptor") as info:
        _load(tmp_path, f"v: !x \"h.{name}()\"\n")
    assert "MAX_CALL_DEPTH" not in str(info.value)
