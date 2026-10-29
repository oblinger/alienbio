"""T088 entity 3-4: head collisions are refused, a MockDat root does not save."""

from __future__ import annotations

import pytest

from alienbio.infra.entity import (
    Entity,
    MockDat,
    _head_registry,
    get_entity_class,
    register_head,
)


@pytest.fixture
def clean_heads():
    before = dict(_head_registry)
    yield
    _head_registry.clear()
    _head_registry.update(before)


def test_same_class_reregister_is_a_noop(clean_heads):
    class T088Same(Entity):
        pass

    register_head("T088Same", T088Same)
    assert get_entity_class("T088Same") is T088Same
    assert T088Same("x", dat=MockDat("t/x")).head == "T088Same"


def test_different_class_under_taken_name_is_refused_naming_both(clean_heads):
    class T088First(Entity):
        pass

    class Other(Entity):
        pass

    with pytest.raises(ValueError, match=r"T088First.*Other.*replace=True"):
        register_head("T088First", Other)
    assert get_entity_class("T088First") is T088First
    assert T088First("x", dat=MockDat("t/x")).head == "T088First"


def test_subclass_path_refuses_a_taken_head(clean_heads):
    class T088Mol(Entity, head="T088Mol"):
        pass

    with pytest.raises(ValueError, match="already registered"):
        class Shadow(Entity, head="T088Mol"):  # noqa: F841
            pass

    assert get_entity_class("T088Mol") is T088Mol
    assert T088Mol("x", dat=MockDat("t/x")).head == "T088Mol"


def test_replace_true_shadows_on_purpose(clean_heads):
    class T088Rep(Entity):
        pass

    class Newer(Entity):
        pass

    register_head("T088Rep", Newer, replace=True)
    assert get_entity_class("T088Rep") is Newer

    class Newest(Entity, head="T088Rep", replace_head=True):
        pass

    assert get_entity_class("T088Rep") is Newest
    assert Newest("x", dat=MockDat("t/x")).head == "T088Rep"


def test_save_on_a_mockdat_root_refuses_naming_the_mock():
    root = Entity("world", dat=MockDat("world/w"))
    Entity("child", parent=root)
    with pytest.raises(TypeError, match=r"MockDat\('world/w'\)"):
        root.save()
