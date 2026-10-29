"""T091 round 4, investigator C — expr findings 4, 11, 12 and infra findings
5-9: each test is a finding's repro, now refused or carried."""

from __future__ import annotations

import pytest
import yaml
from dvc_dat import Dat

from alienbio.bio.atom import COMMON_ATOMS
from alienbio.bio.compartment import CompartmentImpl
from alienbio.bio.molecule import MoleculeImpl
from alienbio.expr import Env, ExprError, evaluate, fn, load_text
from alienbio.expr.parse import dump, parse
from alienbio.infra.entity import Entity, MockDat
from alienbio.infra.io import IO


def _ev(text: str):
    return evaluate(parse(text), Env.standard(seed=1))


# ── C4: str methods that grow their output are charged before they run ──────


def test_translate_is_charged_by_its_longest_mapped_value():
    assert len(_ev("('a'*300).translate({97: 'a'*300})")) == 90_000
    with pytest.raises(ExprError, match="method translate: 27000000 elements exceeds limits.entities"):
        _ev("('a'*300).translate({97: 'a'*300}).translate({97: 'a'*300})")


def test_a_translate_table_that_is_not_a_mapping_or_list_refuses():
    with pytest.raises(ExprError, match="translate: the table must be a mapping or a list"):
        _ev("'abc'.translate(5)")


@pytest.mark.parametrize("text", [
    "('ﬃ'*400000).upper()",
    "('a'*120000).encode('unicode_escape')",
    "('a'*300000).encode('ascii', 'namereplace')",
    "'%r' % ('a'*200000,)",
])
def test_case_maps_encodings_and_reprs_are_charged_at_their_growth_bound(text):
    with pytest.raises(ExprError, match="exceeds limits.entities"):
        _ev(text)


def test_ordinary_text_methods_still_run():
    assert _ev("'abc'.upper()") == "ABC"
    assert _ev("'a-b'.translate({45: '_'})") == "a_b"
    assert _ev("'x'.zfill(3)") == "00x"


# ── C11: deep YAML and name chains stop at the Expr limits ─────────────────


def test_deeply_nested_yaml_is_an_expr_error():
    text = "x: " + "[" * 3000 + "1" + "]" * 3000
    with pytest.raises(ExprError, match="YAML nesting deeper than limits.depth"):
        load_text(text)
    with pytest.raises(ExprError, match="YAML nesting deeper than limits.depth"):
        Env.standard(seed=1).load("deep.yaml", text=text)


def test_a_chain_of_names_counts_toward_limits_depth():
    n = 200
    text = "\n".join([f"a{i}: !x a{i + 1} + 1" for i in range(n)] + [f"a{n}: 0"])
    with pytest.raises(ExprError, match="deeper than limits.depth=100"):
        Env.standard(seed=1).load("deep.yaml", text=text).lookup("a0")
    short = "\n".join([f"a{i}: !x a{i + 1} + 1" for i in range(20)] + ["a20: 0"])
    assert Env.standard(seed=1).load("deep.yaml", text=short).lookup("a0") == 20


# ── C12: a chained comparison evaluates its operands left to right ─────────

_CALLS: list = []


@fn(name="cnt_t091c")
def _cnt(v=1):
    _CALLS.append(v)
    return v


@pytest.mark.parametrize("text,calls", [
    ("(0 < cnt_t091c(1) < 2) < cnt_t091c(5) < 9", [1, 5]),
    ("cnt_t091c(1) < cnt_t091c(2) < cnt_t091c(3)", [1, 2, 3]),
    ("0 < cnt_t091c(1) < cnt_t091c(2) < 3", [1, 2]),
    ("5 < cnt_t091c(1) < cnt_t091c(2)", [1]),
])
def test_a_chained_comparison_evaluates_left_to_right_and_round_trips(text, calls):
    _CALLS.clear()
    assert _ev(text) == eval(text.replace("cnt_t091c", ""), {})  # noqa: S307 - literal test text
    assert _CALLS == calls
    form = parse(text)
    assert parse(dump(form)) == form


# ── C5 / C6: insert_refs and resolve_refs round-trip through a real dat ─────


def _dat(base, name):
    return Dat.create(path=str(base / name), spec={"name": name})


def test_an_absolute_ref_round_trips_through_a_real_dat(tmp_path):
    root = Entity("B", dat=_dat(tmp_path, "B"))
    MoleculeImpl("x", parent=root, bdepth=2)
    root.save()
    io = IO()
    x = io.lookup(f"</{tmp_path}/B.x>")
    data = {"m": x, "rows": [x, 3, "<html>"]}
    written = io.insert_refs(data)
    assert written["m"] == f"</{tmp_path}/B.x>"
    assert io.resolve_refs(written) == data
    # a fresh IO reads it back off disk to an equal entity
    back = IO().resolve_refs(written)
    assert back["m"].local_name == "x" and back["m"].bdepth == 2


def test_a_prefix_ref_round_trips_and_wins_over_the_absolute_form(tmp_path):
    root = Entity("B", dat=_dat(tmp_path, "B"))
    x = MoleculeImpl("x", parent=root)
    io = IO()
    io.bind_prefix("W", root)
    assert io.insert_refs({"m": x}) == {"m": "<W:x>"}
    assert io.resolve_refs(io.insert_refs({"m": x}))["m"] is x


def test_a_reference_insert_refs_could_not_read_back_refuses_at_write():
    root = Entity("exp1", dat=MockDat("exp1"))  # a one-segment dat root reads as markup
    with pytest.raises(ValueError, match="not a reference shape"):
        IO().insert_refs(root)


@pytest.mark.parametrize("text", [
    "<html>", "</b>", "<https://example.com/page>", "<mailto:a@b.c>", "<a b>", "<>", "</exp1>",
])
def test_markup_and_urls_pass_through(text):
    assert IO().resolve_refs({"t": text}) == {"t": text}


# ── C7: an absolute-ref child is attached by reference ─────────────────────


def test_an_absolute_child_in_args_stays_in_its_own_dat(tmp_path, monkeypatch):
    from alienbio import bio

    root_b = Entity("B", dat=_dat(tmp_path, "B"))
    MoleculeImpl("x", parent=root_b, bdepth=2)
    root_b.save()
    Entity("A", dat=_dat(tmp_path, "A")).save()
    path = tmp_path / "A" / "entities.yaml"
    data = yaml.safe_load(path.read_text())
    data["args"] = {"x": f"</{tmp_path}/B.x>"}
    path.write_text(yaml.safe_dump(data))

    io = IO()
    b = io.lookup(f"</{tmp_path}/B>")
    a = io.lookup(f"</{tmp_path}/A>")
    x = io.lookup(f"</{tmp_path}/B.x>")
    assert a.children["x"] is x and b.children["x"] is x
    assert x.parent is b and x.root() is b
    assert io.lookup(f"</{tmp_path}/A.x>") is x
    # written back as the same reference
    monkeypatch.setattr(bio, "io", io)
    assert a.to_dict(recursive=True)["args"] == {"x": f"</{tmp_path}/B.x>"}


# ── C8 / C9: save writes only what the loader reads; nested compartments ───


def test_a_compartment_tree_saves_and_loads(tmp_path):
    root = CompartmentImpl("org", volume=1.0, dat=_dat(tmp_path, "org"), kind="organism", description="d")
    cell = CompartmentImpl("cell", volume=0.5, parent=root, multiplicity=10.0, concentrations={"A": 2.0})
    assert root.children == [cell] and cell.parent is root and cell.depth() == 1
    root.save()
    back = IO().lookup(f"</{tmp_path}/org>")
    assert isinstance(back, CompartmentImpl)
    assert back.to_dict(recursive=True) == root.to_dict(recursive=True)
    assert [c.local_name for c in back.children] == ["cell"]


def test_a_molecule_with_atoms_refuses_at_save_and_writes_nothing(tmp_path):
    d = _dat(tmp_path, "mol")
    mol = MoleculeImpl("glc", dat=d, atoms={COMMON_ATOMS["C"]: 6, COMMON_ATOMS["O"]: 6})
    with pytest.raises(ValueError, match=r"cannot save 'glc' \(MoleculeImpl\).*atoms"):
        mol.save()
    assert not (tmp_path / "mol" / "entities.yaml").exists()


def test_a_compartment_carrying_membrane_flows_refuses_at_save(tmp_path):
    class _Flow:
        name = "uptake"

    comp = CompartmentImpl("cell", volume=1.0, dat=_dat(tmp_path, "cell"), membrane_flows=[_Flow()])  # type: ignore[list-item]
    with pytest.raises(ValueError, match=r"cannot save 'cell' \(CompartmentImpl\).*membrane_flows"):
        comp.save()
    assert not (tmp_path / "cell" / "entities.yaml").exists()
