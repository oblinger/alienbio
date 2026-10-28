"""T088 infra and protocols round: each test is a finding's repro, now refused
or carried (`doc/ABIO Track/ABIO Backlog/ABIO088 …` § infra/…, § protocols)."""

from __future__ import annotations

import subprocess
import sys

import pytest

from alienbio.infra.entity import Entity, MockDat
from alienbio.infra.graph_ops import GraphView
from alienbio.infra.io import IO
from alienbio.infra.mk import Pegboard


# ── infra/entity 1–2 ─────────────────────────────────────────────────────────


def test_refused_reparent_by_name_clash_leaves_the_entity_where_it_was():
    p1 = Entity("p1", dat=MockDat("t/p1"))
    p2 = Entity("p2", dat=MockDat("t/p2"))
    x = Entity("x", parent=p1)
    other = Entity("x", parent=p2)
    with pytest.raises(ValueError, match="already has child named 'x'"):
        x.set_parent(p2)
    assert x.parent is p1 and p1.children["x"] is x and p2.children["x"] is other


def test_reparent_under_a_descendant_refuses_before_mutating():
    a = Entity("a", parent=Entity("top", dat=MockDat("t/top")))
    b = Entity("b", parent=a)
    with pytest.raises(ValueError, match="descendants"):
        a.set_parent(b)
    assert a.parent is not None and a.parent.local_name == "top" and b.parent is a


def test_a_root_cannot_become_its_childs_child_or_its_own_parent():
    root = Entity("root", dat=MockDat("t/root"))
    child = Entity("c", parent=root)
    with pytest.raises(ValueError, match="descendants"):
        root.set_parent(child)
    with pytest.raises(ValueError, match="descendants"):
        root.set_parent(root)
    assert root.parent is None and list(root.descendants()) == [child]


def test_reparent_to_the_same_parent_is_a_no_op():
    p = Entity("p", dat=MockDat("t/p"))
    x = Entity("x", parent=p)
    x.set_parent(p)
    assert p.children == {"x": x}


# ── infra/io 1, 3, 4, 6 ──────────────────────────────────────────────────────


def _dat(tmp_path, name):
    from dvc_dat import Dat

    return Dat.create(path=str(tmp_path / name), spec={"name": name})


def test_save_load_round_trip_carries_subclass_fields(tmp_path):
    from alienbio.bio import MoleculeImpl

    dat = _dat(tmp_path, "mols")
    mol = MoleculeImpl("A", dat=dat, bdepth=3)
    mol.save()
    loaded = IO()._load_dat_entity(str(tmp_path / "mols"))
    assert isinstance(loaded, MoleculeImpl) and loaded.bdepth == 3


def test_an_unknown_head_refuses_rather_than_loading_a_plain_entity():
    with pytest.raises(KeyError, match="Unknown entity head: 'NoSuchHead'"):
        IO()._create_entity_from_dict(
            {"head": "NoSuchHead", "name": "x"}, dat=MockDat("t/x")
        )


def test_a_dotted_dat_path_name_refuses_at_write():
    world = Entity("w", dat=MockDat("runs/v1.2"))
    with pytest.raises(ValueError, match="contains '.'"):
        IO().ref(Entity("c", parent=world), absolute=True)


def test_a_string_binding_and_an_absolute_ref_give_one_object(tmp_path):
    _dat(tmp_path, "exp1")
    io = IO()
    io.bind_prefix("X", str(tmp_path / "exp1"))
    assert io.resolve_prefix("X") is io.lookup(f"</{tmp_path}/exp1>")


def test_resolve_refs_passes_angle_bracketed_text_through():
    io = IO()
    w = Entity("w", dat=MockDat("runs/w"))
    Entity("g", parent=w)
    io.bind_prefix("W", w)
    out = io.resolve_refs({"a": "<html>", "b": "<a b>", "c": "<W:g>", "d": "<>"})
    assert out["a"] == "<html>" and out["b"] == "<a b>" and out["d"] == "<>"
    assert out["c"] is w.children["g"]
    with pytest.raises(KeyError, match="not bound"):
        io.resolve_refs("<Q:g>")


def test_str_no_longer_hides_an_error_inside_an_attached_io(monkeypatch):
    from alienbio import bio

    class Broken(IO):
        def ref(self, entity, prefer_short=True, absolute=False):
            raise KeyError("broken binding")

    monkeypatch.setattr(bio, "io", Broken())
    with pytest.raises(KeyError, match="broken binding"):
        str(Entity("w", dat=MockDat("runs/w")))
    monkeypatch.setattr(bio, "io", None)
    assert str(Entity("w", dat=MockDat("runs/w"))) == "runs/w"


# ── infra/imports (io 7) ─────────────────────────────────────────────────────


def test_import_alienbio_outside_the_repo_binds_no_tests_package(tmp_path):
    code = "import sys, alienbio; print('tests' in sys.modules)"
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "False"


# ── infra/mk 1–2 ─────────────────────────────────────────────────────────────


def _board():
    board = Pegboard()

    def build(name, anchor, **kw):
        return Entity(name, **anchor, **kw)

    board.register("E", prefix="ent", build=build)
    return board, build


def test_mk_with_dat_and_parent_builds_what_the_constructor_builds():
    board, _ = _board()
    p = Entity("p", dat=MockDat("t/p"))
    d = MockDat("t/sub")
    x = board.E("x", dat=d, parent=p)
    assert x.parent is p and p.children["x"] is x and x.dat() is d


def test_mk_reregistering_one_build_under_another_prefix_refuses():
    board, build = _board()
    board.register("E", prefix="ent", build=build)  # identical: idempotent
    with pytest.raises(ValueError, match="prefix 'ent', not 'other'"):
        board.register("E", prefix="other", build=build)


# ── infra/graph_ops 1 ────────────────────────────────────────────────────────


def test_graph_view_refuses_an_id_in_both_namespaces():
    with pytest.raises(ValueError, match=r"\['A'\] name both a species and a reaction"):
        GraphView(("A", "B"), ("A",), {"A": frozenset({"A", "B"})})


# ── protocols 1 ──────────────────────────────────────────────────────────────


def test_simulator_is_runtime_checkable_like_the_other_eight():
    from alienbio.bio import CompartmentTreeImpl, WorldSimulatorImpl
    from alienbio.protocols import Simulator

    tree = CompartmentTreeImpl()
    tree.add_root("organism")
    assert isinstance(WorldSimulatorImpl(tree, [], [], num_molecules=1, dt=0.5), Simulator)
    assert not isinstance(object(), Simulator)
