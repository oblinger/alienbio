"""T091 AT — verifier AT's findings on rounds AQ/AS, Expr side: hashing a
deep key is charged (AT2), ``_call_target`` follows ``__call__`` to the
code it runs and judges a metaclass ``__call__`` (AT3), ``element_bound`` is
total on self-similar sequences (AT4), and a long int key is an
``ExprError`` naming the file (AT5). AT1 (the drafter dials) is
``tests/suite/test_t091_at_dials.py``."""

from __future__ import annotations

import collections
import enum
import time
from collections.abc import Sequence

import pytest

from alienbio.expr import Env, ExprError, X, evaluate, heads
from alienbio.expr.access import MAX_CALL_DEPTH, callable_code_allowed, domain_types
from alienbio.expr.form import FrozenKwargs
from alienbio.suite.spec import load_spec


def _x(text: str, **bindings):
    return evaluate(X.parse(text), Env.standard(seed=1, bindings=bindings))


def _pair_chain(depth: int):
    """``(p, p)`` nested ``depth`` deep: hashing it walks 2^depth tuples."""
    p: object = 0
    for _ in range(depth):
        p = (p, p)
    return p


# ---- AT2: a deep key's hash is charged before it is hashed ----


def test_at2_the_verifiers_hash_chain_refuses_well_under_a_second(tmp_path):
    """AT's H1 file (a doubling dict-items chain hashed by dict and set) refuses on the meter, not the clock."""
    lines = ["p0: 0"] + [f'p{i}: !x "list(dict(zip([p{i - 1}], [p{i - 1}])).items())[0]"' for i in range(1, 36)]
    lines.append('h: !x "len(set([p35]))"')
    path = tmp_path / "h1.yaml"
    path.write_text("\n".join(lines) + "\n")
    t = time.process_time()
    with pytest.raises(ExprError, match="limits.entities"):
        Env.standard(seed=0).load(str(path)).force_all()
    assert time.process_time() - t < 1.0


@pytest.mark.parametrize(
    "text",
    [
        "{p}",
        "{x for x in [p]}",
        "dict([[p, 1]])",
        "dict(zip([p], [1]))",
        "m[p]",
        "m.get(p)",
        "m.fromkeys([p])",
        "s.union([p])",
        "p in fk",
        "{k: 1 for k in [p]}",
    ],
)
def test_at2_every_hashing_route_charges_a_deep_key(text):
    """Each place a container hashes an item charges the item's elements before the hash runs."""
    p = _pair_chain(40)
    t = time.process_time()
    with pytest.raises(ExprError, match="limits.entities"):
        _x(text, p=p, m={}, s=frozenset(), fk=FrozenKwargs({"a": 1}))
    assert time.process_time() - t < 1.0


def test_at2_equal_sets_of_deep_tuples_are_charged_by_the_comparison():
    """``==`` on two sets of distinct equal deep tuples is already charged their elements (AP3)."""
    a, b = {_pair_chain(22)}, {_pair_chain(22)}
    with pytest.raises(ExprError, match="limits.entities"):
        _x("a == b", a=a, b=b)


def test_at2_ordinary_hashing_is_unchanged():
    """Flat keys and small deep keys hash as before."""
    assert _x("len({1, 2, 2})") == 2
    assert _x("dict([['a', 1], ['b', 2]])") == {"a": 1, "b": 2}
    assert _x("dict(zip(['a'], [[1, 2]]))") == {"a": [1, 2]}
    assert _x("m[k]", m={(1, 2): 3}, k=(1, 2)) == 3
    assert _x("{k: 1 for k in ['x', 'y']}") == {"x": 1, "y": 1}
    assert _x("s.union([1])", s=frozenset({2})) == {1, 2}


# ---- AT3: __call__ is followed to the code it runs ----

_HELPERS = """
import os


class Inner:
    __call__ = staticmethod(os.getcwd)


class Outer:
    __call__ = Inner()


def outer():
    return Outer()


class StaticMeta(type):
    __call__ = staticmethod(os.getcwd)


class ViaStaticMeta(metaclass=StaticMeta):
    pass


class Plain:
    def __init__(self, n):
        self.n = n


class Own:
    def __call__(self, x):
        return x + 1


def own():
    return Own()
"""


def _load(tmp_path, body: str):
    (tmp_path / "helpers.py").write_text(_HELPERS)
    path = tmp_path / "t.yaml"
    path.write_text("h: !include helpers.py\n" + body)
    return Env.standard(seed=0, trusted=True).load(str(path)).force_all()


@pytest.mark.parametrize(
    "body",
    [
        "o: !x h.outer()\nv: !x o()\n",
        "o: !x h.ViaStaticMeta()\n",
    ],
)
def test_at3_a_call_chain_or_metaclass_reaching_outside_code_refuses(tmp_path, body):
    """A ``__call__`` two levels down, or a foreign function as a metaclass ``__call__``, no longer runs outside code from a helper."""
    with pytest.raises(ExprError, match="outside the spec's helpers|only the spec's included helpers"):
        _load(tmp_path, body)


def test_at3_helper_classes_and_callables_of_its_own_code_still_run(tmp_path):
    """A helper class with an ordinary metaclass and a helper callable instance are still callable."""
    out = _load(tmp_path, "c: !x h.own()\nv: !x c(1)\n")
    assert out["v"] == 2


def test_at3_a_chain_that_never_bottoms_out_is_refused():
    """A ``__call__`` chain deeper than MAX_CALL_DEPTH is not callable code."""

    class Link:
        pass

    head: object = Link()
    for _ in range(MAX_CALL_DEPTH + 2):
        nxt = type("L", (), {"__call__": head, "__module__": "alienbio_include_x"})
        head = nxt()
    assert callable_code_allowed(head) is False


def test_at3_every_domain_class_stays_callable():
    """Domain constructors (MoleculeImpl, the Enum roles) pass whatever their metaclass."""
    for cls in domain_types():
        assert callable_code_allowed(cls), cls
    assert any(isinstance(cls, enum.EnumMeta) for cls in domain_types())


# ---- AT4: element_bound is total ----


class _SelfSimilar(Sequence):
    def __len__(self):
        return 2

    def __getitem__(self, i):
        if i >= 2:
            raise IndexError(i)
        return _SelfSimilar()


def test_at4_element_bound_stops_on_a_self_similar_sequence():
    """A sequence whose items are fresh copies of itself is bounded by entries walked, not by identity."""
    t = time.process_time()
    assert heads.element_bound(_SelfSimilar(), 10_000) == 10_001
    assert time.process_time() - t < 2.0


def test_at4_a_userstring_is_text():
    """A ``UserString`` is a leaf, like ``str``: its comparison is not a deep walk."""
    t = time.process_time()
    assert heads.element_bound(collections.UserString("ab"), 10**6) == 1
    assert _x("u == u", u=collections.UserString("ab")) is True
    assert time.process_time() - t < 1.0


# ---- AT5: a long int key is an ExprError naming the file ----


def test_at5_an_int_key_past_the_str_limit_names_the_file(tmp_path):
    """A 20 000-hex-digit top-level key is refused as an ExprError naming the file, not a bare ValueError."""
    path = tmp_path / "k.yaml"
    path.write_text("? 0x" + "f" * 20_000 + "\n: 1\n")
    with pytest.raises(ExprError, match=r"k\.yaml: a top-level key \(int\) cannot be rendered"):
        load_spec(str(path))
