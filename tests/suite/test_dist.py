"""Acceptance tests for deterministic seeds, distributions, and ParamSchema."""

from __future__ import annotations

from alienbio.suite.dist import (
    Choice,
    Constant,
    LogNormal,
    Normal,
    ParamSchema,
    Seed,
    Uniform,
)


def test_seed_child_is_deterministic_and_distinct():
    root = Seed(1234)
    assert root.child("a").value == root.child("a").value
    assert root.child("a").value != root.child("b").value


def test_constant_is_seed_independent():
    c = Constant(42)
    assert c.sample(Seed(0)) == 42
    assert c.sample(Seed(999)) == 42


def test_continuous_dists_reproducible():
    seed = Seed(7)
    for dist in (Uniform(0.0, 1.0), Normal(0.0, 1.0), LogNormal(0.0, 0.5)):
        assert dist.sample(seed) == dist.sample(seed)


def test_choice_reproducible_and_weighted():
    seed = Seed(3)
    ch = Choice(("x", "y", "z"))
    assert ch.sample(seed) == ch.sample(seed)

    # A weight vector that forces a single option.
    forced = Choice(("x", "y", "z"), weights=(0.0, 1.0, 0.0))
    assert forced.sample(Seed(0)) == "y"
    assert forced.sample(Seed(500)) == "y"


def test_child_labels_give_independent_draws():
    seed = Seed(11)
    u = Uniform(0.0, 1.0)
    a = u.sample(seed.child("a"))
    b = u.sample(seed.child("b"))
    assert a != b


def test_param_schema_reproducible():
    schema = ParamSchema(
        {
            "rate": Uniform(0.0, 1.0),
            "count": Normal(10.0, 2.0),
            "nested": [Constant(5), LogNormal(0.0, 1.0)],
        }
    )
    seed = Seed(2024)
    first = schema.sample(seed)
    second = schema.sample(seed)
    assert first == second
    # Non-Dist leaves pass through; Constant leaf resolves to its value.
    assert first["nested"][0] == 5


def test_param_schema_order_independent():
    # Same leaves, different dict insertion order -> identical per-key draws.
    u = Uniform(0.0, 1.0)
    n = Normal(0.0, 1.0)
    schema_ab = ParamSchema({"a": u, "b": n})
    schema_ba = ParamSchema({"b": n, "a": u})
    seed = Seed(88)
    ra = schema_ab.sample(seed)
    rb = schema_ba.sample(seed)
    assert ra["a"] == rb["a"]
    assert ra["b"] == rb["b"]
