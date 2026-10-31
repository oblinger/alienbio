"""T091 AP (DoS) — verifier AP's third attack on the Expr sandbox: deep
comparisons of shared-structure lists (AP3, and the same shape built with
YAML aliases), huge integer literals and big-int division (AP4), a clock per
binding rather than per document (AP5), exponential include fan-out (AP6), no
spec size cap and three parses (AP7), and strings rendered as their repr
(AP8). The trust half is ``test_t091_ap_trust.py``.
"""

from __future__ import annotations

import time

import pytest

from alienbio.expr import Env, ExprError, X, evaluate
from alienbio.expr import heads, include, yaml_tags
from alienbio.expr.env import Limits
from alienbio.expr.parse import MAX_INT_LITERAL_BITS
from alienbio.suite.expr_experiment import load_experiment
from alienbio.suite.spec import load_spec


def _x(text: str, **bindings):
    return evaluate(X.parse(text), Env.standard(seed=1, bindings=bindings))


def _doc(text: str, *, trusted: bool = False, limits: Limits | None = None, path: str = "<t>"):
    return Env.standard(seed=1, trusted=trusted, limits=limits).load(path, text=text)


def _chain(name: str, depth: int) -> str:
    lines = [f"{name}0: !x '[0] * 10'"]
    lines += [f"{name}{i}: !x '[{name}{i - 1}] * 10'" for i in range(1, depth + 1)]
    return "\n".join(lines) + "\n"


# ---- AP3: comparisons of containers are charged the elements they visit ----


@pytest.mark.parametrize("op", ["==", "!=", "<", ">="])
def test_ap3_comparing_two_shared_structure_chains_refuses_at_once(op):
    doc = _doc(_chain("a", 10) + _chain("b", 10) + f"eq: !x 'a10 {op} b10'\n")
    t = time.monotonic()
    with pytest.raises(ExprError, match="limits.entities"):
        doc.force_all()
    assert time.monotonic() - t < 5


def test_ap3_membership_of_a_container_is_charged_the_list_it_scans():
    doc = _doc(_chain("a", 10) + _chain("b", 9) + "m: !x 'b9 in a10'\n")
    with pytest.raises(ExprError, match="limits.entities"):
        doc.force_all()


def test_ap3_ordering_container_items_is_charged():
    doc = _doc(_chain("a", 9) + _chain("b", 9) + "s: !x 'sorted([a9, b9])'\n")
    with pytest.raises(ExprError, match="limits.entities"):
        doc.force_all()


def test_ap3_small_comparisons_still_work():
    assert _x("[[1, 2], [3]] == [[1, 2], [3]]") is True
    assert _x("[1, 2] in [[1, 2], [3]]") is True
    assert _x("sorted([[3], [1], [2]])") == [[1], [2], [3]]
    assert _x("max([1], [2])") == [2]


def test_ap3_a_yaml_alias_bomb_refuses_at_load():
    lines = ["a0: &a0 [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]"]
    lines += [f"a{i}: &a{i} [{', '.join([f'*a{i - 1}'] * 10)}]" for i in range(1, 11)]
    t = time.monotonic()
    with pytest.raises(ExprError, match="MAX_DOCUMENT_NODES"):
        yaml_tags.load_text("\n".join(lines) + "\n", source="bomb.yaml")
    assert time.monotonic() - t < 5


def test_ap3_a_recursive_alias_refuses_at_load():
    with pytest.raises(ExprError, match="recursive YAML alias"):
        yaml_tags.load_text("a: &a [1, *a]\n", source="cyc.yaml")


def test_ap3_a_shared_alias_under_the_cap_still_loads():
    data = yaml_tags.load_text("d: &d {k: 1}\nx: [*d, *d]\n")
    assert data["x"] == [{"k": 1}, {"k": 1}]


# ---- AP4: integer literals capped; big-int ops bounded by bits --------------


def test_ap4_an_inline_hex_literal_past_the_cap_refuses():
    with pytest.raises(ExprError, match="MAX_INT_LITERAL_BITS"):
        X.parse("0x" + "f" * (MAX_INT_LITERAL_BITS // 4 + 1))


def test_ap4_a_yaml_int_literal_past_the_cap_refuses():
    with pytest.raises(ExprError, match="MAX_INT_LITERAL_BITS"):
        yaml_tags.load_text("a: 0x" + "f" * (MAX_INT_LITERAL_BITS // 4 + 1) + "\n")
    with pytest.raises(ExprError, match="MAX_INT_LITERAL_BITS"):
        yaml_tags.load_text("a: " + "1:" * 200_000 + "1\n")  # base 60


def test_ap4_a_literal_at_the_cap_loads():
    assert yaml_tags.load_text("a: 0x" + "f" * (MAX_INT_LITERAL_BITS // 4) + "\n")["a"].bit_length() == MAX_INT_LITERAL_BITS


@pytest.mark.parametrize("op", ["%", "//"])
def test_ap4_int_division_refuses_an_operand_past_the_cap(op):
    big = 1 << (MAX_INT_LITERAL_BITS + 8)
    with pytest.raises(ExprError, match="operand of"):
        _x(f"big {op} 7", big=big)
    with pytest.raises(ExprError, match="operand of"):
        _x(f"7 {op} big", big=big)
    assert _x(f"(2 ** 9999) {op} 7") == (2**9999 % 7 if op == "%" else 2**9999 // 7)


def test_ap4_round_to_a_huge_negative_ndigits_refuses():
    t = time.monotonic()
    with pytest.raises(ExprError, match="ndigits"):
        _x("round(7, -16000000)")
    assert time.monotonic() - t < 1
    assert _x("round(1234, -2)") == 1200
    assert _x("round(2.567, 1)") == 2.6


def test_ap4_an_int_result_past_the_cap_refuses():
    with pytest.raises(ExprError, match="exceeds"):
        _x("int(s, 16)", s="f" * (MAX_INT_LITERAL_BITS // 4 + 8))
    with pytest.raises(ExprError, match="exceeds"):
        _x("(0).from_bytes(b, 'big')", b=b"\xff" * (MAX_INT_LITERAL_BITS // 8 + 8))
    assert _x("int('ff', 16)") == 255


# ---- AP5: one clock per document load ---------------------------------------


def _slow(seconds: float):
    def slow() -> int:
        time.sleep(seconds)
        return 1

    return slow


def test_ap5_force_all_runs_every_binding_under_one_clock():
    env = Env.standard(seed=1, trusted=True, limits=Limits(seconds=0.4), bindings={"slow": _slow(0.15)})
    doc = env.load("<t>", text="".join(f"k{i}: !x slow()\n" for i in range(5)))
    with pytest.raises(ExprError, match="limits.seconds"):
        doc.force_all()


def test_ap5_each_binding_alone_is_under_the_clock():
    env = Env.standard(seed=1, trusted=True, limits=Limits(seconds=0.4), bindings={"slow": _slow(0.15)})
    doc = env.load("<t>", text="".join(f"k{i}: !x slow()\n" for i in range(5)))
    assert [doc.lookup(f"k{i}") for i in range(5)] == [1] * 5


def test_ap5_load_experiment_holds_one_clock_from_parse_to_spec(tmp_path, monkeypatch):
    (tmp_path / "slowhelp.py").write_text("import time\n\ndef slow():\n    time.sleep(0.15)\n    return 1\n")
    body = "".join(f"k{i}: !x h.slow()\n" for i in range(5))
    spec = tmp_path / "s.yaml"
    spec.write_text("h: !include slowhelp.py\n" + body)
    original = Env.standard.__func__  # type: ignore[attr-defined]

    def standard(cls, *a, **k):
        k["limits"] = Limits(seconds=0.4)
        return original(cls, *a, **k)

    monkeypatch.setattr(Env, "standard", classmethod(standard))
    with pytest.raises(ExprError, match="limits.seconds"):
        load_experiment(spec, trusted=True)


# ---- AP6: include fan-out is capped -----------------------------------------


def _fan(tmp_path, depth: int, width: int = 10):
    for i in range(depth):
        nxt = f"l{i + 1}.yaml"
        (tmp_path / f"l{i}.yaml").write_text("v: [" + ", ".join([f"!include {nxt}"] * width) + "]\n")
    (tmp_path / f"l{depth}.yaml").write_text("v: 1\n")
    top = tmp_path / "top.yaml"
    top.write_text("x: !include l0.yaml\n")
    return top


def test_ap6_an_exponential_include_tree_refuses_early(tmp_path):
    top = _fan(tmp_path, 6)
    t = time.monotonic()
    with pytest.raises(ExprError, match="MAX_INCLUDE_LOADS"):
        Env.standard(seed=0).load(top)
    assert time.monotonic() - t < 5


def test_ap6_repeated_includes_list_entries_count(tmp_path):
    (tmp_path / "x.yaml").write_text("a: 1\n")
    top = tmp_path / "top.yaml"
    top.write_text("_includes_: [" + ", ".join(["x.yaml"] * (include.MAX_INCLUDE_LOADS + 1)) + "]\n")
    with pytest.raises(ExprError, match="MAX_INCLUDE_LOADS"):
        Env.standard(seed=0).load(top)


def test_ap6_a_modest_include_tree_loads(tmp_path):
    top = _fan(tmp_path, 2)
    assert Env.standard(seed=0).load(top).force_all()["x"]["v"][0]["v"][0] == {"v": 1}


def test_ap6_the_budget_is_per_document(tmp_path):
    top = _fan(tmp_path, 2)
    for _ in range(4):  # 111 loads each: four documents, never summed
        Env.standard(seed=0).load(top)


# ---- AP7: a size cap, and one parse -----------------------------------------


def test_ap7_an_oversized_spec_refuses_before_parsing(tmp_path, monkeypatch):
    spec = tmp_path / "big.yaml"
    spec.write_text("x: [" + "1, " * (yaml_tags.MAX_SPEC_BYTES // 3 + 10) + "1]\n")
    called = []
    monkeypatch.setattr(yaml_tags.ExprLoader, "get_single_node", lambda self: called.append(1))
    with pytest.raises(ExprError, match="MAX_SPEC_BYTES"):
        load_spec(spec)
    assert not called


def test_ap7_an_oversized_include_refuses(tmp_path):
    (tmp_path / "big.yaml").write_text("x: [" + "1, " * (yaml_tags.MAX_SPEC_BYTES // 3 + 10) + "1]\n")
    (tmp_path / "top.yaml").write_text("y: !include big.yaml\n")
    with pytest.raises(ExprError, match="MAX_SPEC_BYTES"):
        Env.standard(seed=0).load(tmp_path / "top.yaml")


def test_ap7_an_experiment_file_is_parsed_once(tmp_path, monkeypatch):
    from alienbio.suite.spec import REPO_ROOT

    text = (REPO_ROOT / "catalog" / "experiments" / "exp01.yaml").read_text()
    composed = []
    original = yaml_tags.ExprLoader.get_single_node

    def counting(self):
        composed.append(1)
        return original(self)

    monkeypatch.setattr(yaml_tags.ExprLoader, "get_single_node", counting)
    load_experiment(tmp_path / "exp01.yaml", text=text)
    assert len(composed) == 1


def test_ap7_the_single_parse_still_refuses_duplicate_keys():
    with pytest.raises(ExprError, match="duplicate key 'a'"):
        yaml_tags.load_text("a: 1\na: 2\n", source="dup.yaml")


# ---- AP8: a string inside a container is charged at its repr ----------------


def test_ap8_render_bound_charges_a_contained_string_at_its_repr():
    s = "\U000e0000" * 1000
    assert heads.render_bound([s], 10**7) >= len(repr([s]))
    assert heads.render_bound(["abc"], 100) >= len(repr(["abc"]))


def test_ap8_str_of_a_repeated_nonprintable_string_refuses():
    with pytest.raises(ExprError, match="limits.entities"):
        _x("len(str([s] * 10))", s="\U000e0000" * 90_000)


def test_ap8_an_fstring_repr_of_text_is_charged_before_it_is_built():
    with pytest.raises(ExprError, match="limits.entities"):
        _x("len(f'{s!r}')", s="\U000e0000" * 200_000)
    assert _x("f'{s!r}'", s="ab") == "'ab'"
