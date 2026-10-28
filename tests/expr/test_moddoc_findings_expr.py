"""T088 generators-and-Expr round: expr/parse, form, registry, heads,
include and yaml_tags.

Each test pins one finding from the module-doc pass (numbered as in the T088
findings doc, e.g. ``parse 1``): it failed before its fix and passes after.
"""

from __future__ import annotations

import copy
import pickle
from pathlib import Path

import pytest

from alienbio.expr import Env, ExprError, UnsafeSpecError, X, evaluate, fn
from alienbio.expr.form import Call, Quoted
from alienbio.expr.registry import Registry

_CALLS: list[int] = []


@fn(name="t088_tick")
def _tick() -> int:
    _CALLS.append(1)
    return len(_CALLS)


def _env(doc: str = "x: 0.5\n") -> Env:
    return Env.standard(seed=1).load("doc.yaml", text=doc)


# expr/parse 1–4 ---------------------------------------------------------------------


def test_a_chained_comparison_evaluates_its_middle_operand_once():
    _CALLS.clear()
    assert evaluate(X.parse("0 < t088_tick() < 2"), _env()) is True
    assert len(_CALLS) == 1  # was 2: the middle operand was emitted twice
    _CALLS.clear()
    assert evaluate(X.parse("1 < 0 < t088_tick()"), _env()) is False
    assert _CALLS == []  # short-circuits as Python does


def test_a_chained_comparison_binds_a_drawn_operand_once():
    form = X.parse("0 < normal(0, 1) < 1")
    assert form.head == "let" and list(form.kwargs["bindings"].values()) == [X.normal(0, 1)]
    assert X.parse("0 < x < 1") == X.parse("(0 < x) and (x < 1)")  # names stay the plain form


def test_a_nested_dict_comprehension_refuses_instead_of_building_a_list():
    with pytest.raises(ExprError, match="one 'for'"):
        X.parse("{a*10+b: 1 for a in [1, 2] for b in [3, 4]}")
    assert evaluate(X.parse("{a: a*2 for a in [1, 2]}"), _env()) == {1: 2, 2: 4}


@pytest.mark.parametrize(
    "text",
    [
        "[x*2 for x in xs]",
        "[x for x in xs if x > 1 if x < 5]",
        "[a+b for a in [1, 2] for b in [3, 4]]",
        "[a+b+c for a in [1] for b in [2] for c in [3, 4]]",
        "[[y for y in ys] for x in xs]",
        "{x: x*2 for x in xs}",
        "{x for x in xs}",
        "{1, 2}",
        "0 < f(1) < 2",
    ],
)
def test_dump_writes_text_parse_reads_back(text):
    form = X.parse(text)
    assert X.parse(X.dump(form)) == form  # `each(over=…, as=…)` and `op:set(…)` did not parse
    quoted = Quoted(form)
    assert X.load(X.dump(quoted, style="structural")) == quoted


# expr/form 1 ------------------------------------------------------------------------


def test_a_call_is_frozen_and_hashes_by_value():
    call = X.f(1, k=2)
    assert hash(call) == hash(X.f(1, k=2))  # raised unhashable type: 'dict'
    with pytest.raises(TypeError, match="read-only"):
        call.kwargs["k"] = 3  # type: ignore[index]
    assert call.kwargs == {"k": 2}
    assert copy.deepcopy(call) == call and pickle.loads(pickle.dumps(call)) == call


# expr/registry 1–2 -----------------------------------------------------------------


def _load_helper(tmp_path: Path, stem: str, decorator: str) -> object:
    """Execute one helper file under a fixed module name, as a catalog
    `.py` include does, registering into ``into``."""
    import runpy

    path = tmp_path / stem / "helper.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "from alienbio.expr.registry import _decorate\n"
        + decorator
        + "\ndef probe_helper(x):\n    return x + 1\n"
    )
    return runpy.run_path(str(path), run_name="t088_registry_helper", init_globals={"into": INTO})


INTO = Registry()


def test_a_multi_line_decorator_is_the_same_definition(tmp_path):
    one = "@_decorate('fn', None, name='probe_helper', guarded=False, guarded_params=(), into=into, meta={'summary': 'a'})"
    four = (
        "@_decorate(\n    'fn', None, name='probe_helper', guarded=False,\n"
        "    guarded_params=(), into=into,\n    meta={'summary': 'b'},\n)"
    )
    INTO._heads.clear()
    _load_helper(tmp_path, "one", one)
    _load_helper(tmp_path, "four", four)  # refused "already registered" before
    assert INTO.get("probe_helper").meta == {"summary": "b"}


def test_a_re_registration_cannot_quietly_change_guarded(tmp_path):
    INTO._heads.clear()
    base = "@_decorate('fn', None, name='probe_helper', guarded={g}, guarded_params=(), into=into, meta={{}})"
    _load_helper(tmp_path, "a", base.format(g=True))
    with pytest.raises(ValueError, match="different guarded"):
        _load_helper(tmp_path, "b", base.format(g=False))
    assert INTO.get("probe_helper").guarded is True


# expr/heads 1–4 ---------------------------------------------------------------------


def test_pow_by_name_has_op_pows_caps():
    with pytest.raises(ExprError, match="exceeds"):
        evaluate(X.parse("pow(3, 2000000)"), _env())  # returned a 3,169,926-bit integer
    assert evaluate(X.parse("pow(2, 10)"), _env()) == 1024
    assert evaluate(X.parse("pow(2, 10, 7)"), _env()) == 2


@pytest.mark.parametrize("text", ["'%050000000d' % 1", "'a'.ljust(50000000)", "f'{1:050000000d}'", "'ab'.expandtabs(10**7)"])
def test_formatting_and_methods_are_charged_before_they_build(text):
    with pytest.raises(ExprError, match="exceeds limits.entities"):
        evaluate(X.parse(text), _env())


def test_ordinary_formatting_and_methods_still_work():
    env = _env()
    assert evaluate(X.parse("'%d-%s' % 3 if False else '%03d' % 7"), env) == "007"
    assert evaluate(X.parse("'a'.ljust(3)"), env) == "a  "
    assert evaluate(X.parse("', '.join(['a', 'b'])"), env) == "a, b"
    assert evaluate(X.parse("f'{7:03d}'"), env) == "007"
    assert evaluate(X.parse("[3, 1].index(1)"), env) == 1


def test_a_method_cannot_mutate_a_shared_binding():
    env = _env("a: {k: 1}\nxs: [1, 2]\n")
    with pytest.raises(ExprError, match="in place"):
        evaluate(X.parse("a.clear()"), env)
    with pytest.raises(ExprError, match="in place"):
        evaluate(X.parse("xs.append(3)"), env)
    assert env.lookup("a") == {"k": 1} and env.lookup("xs") == [1, 2]


def test_flatten_is_charged_before_it_builds():
    from alienbio.expr.env import Limits

    env = Env.standard(seed=1, limits=Limits(entities=10))
    with pytest.raises(ExprError, match="flatten"):
        evaluate(Call("op:flatten", ([[0] * 6, [0] * 6],)), env)


# expr/include 1–3 ------------------------------------------------------------------


def test_an_included_files_own_includes_load(tmp_path):
    (tmp_path / "c.yaml").write_text("from_c: 3\n")
    (tmp_path / "b.yaml").write_text("_includes_: [c.yaml]\nfrom_b: 2\n")
    (tmp_path / "a.yaml").write_text("_includes_: [b.yaml]\nmain: 1\nx: !include b.yaml\n")
    env = Env.standard(seed=1).load(tmp_path / "a.yaml")
    values = env.force_all()
    assert values["from_c"] == 3 and "_includes_" not in values  # c.yaml never loaded; a stray key was bound
    assert values["x"] == {"from_c": 3, "from_b": 2}


def test_an_untrusted_python_include_is_an_expr_error(tmp_path):
    (tmp_path / "h.py").write_text("X = 1\n")
    (tmp_path / "a.yaml").write_text("_includes_: [h.py]\n")
    with pytest.raises(ExprError):
        Env.standard(seed=1).load(tmp_path / "a.yaml")
    assert issubclass(UnsafeSpecError, ExprError)


def test_two_python_includes_sharing_a_stem_refuse(tmp_path):
    for sub in ("one", "two"):
        (tmp_path / sub).mkdir()
        (tmp_path / sub / "helpers.py").write_text("VALUE = 1\n")
    (tmp_path / "a.yaml").write_text("_includes_: [one/helpers.py, two/helpers.py]\n")
    with pytest.raises(ExprError, match="same stem"):
        Env.standard(seed=1, trusted=True).load(tmp_path / "a.yaml")


# expr/yaml_tags 1–2 ----------------------------------------------------------------


@pytest.mark.parametrize("arg", [3, 0.5, 1e20, True, "", None])
def test_a_lone_scalar_argument_round_trips_its_type(arg):
    call = Call("poisson", (arg,))
    assert X.load(X.dump(call, style="structural")) == call  # `!poisson '3'` reloaded poisson('3')


def test_a_keyword_named_args_refuses_to_dump():
    with pytest.raises(ExprError, match="'args'"):
        X.dump(Call("h", (), {"args": 1}), style="structural")
