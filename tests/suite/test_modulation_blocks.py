"""Unit + integration tests for the F015 S2 modulation-block library
(the pattern-block half of F015 — :mod:`alienbio.suite.blocks`'s
``SignalingBlock`` / ``InhibitionBlock`` / ``EnzymeBlock`` /
``CooperativeBindingBlock``).

Two tiers, mirroring ``tests/suite/test_blocks.py``: (1) per-block unit tests
that call ``realize`` directly, checking the emitted reaction carries exactly
one modifier (never a reactant/product) plus provenance; (2) end-to-end
integration tests that wire ``Source(s) + block + Sink`` into a ``Skeleton``,
materialize, validate, simulate, and confirm the modifier ACTUALLY changes the
target reaction's behavior relative to a no-modifier-effect baseline.
"""

from __future__ import annotations

from alienbio.bio.conservation import check_conservation, validate_conservation
from alienbio.bio.molecule import MoleculeImpl
from alienbio.bio.reaction import Modulation
from alienbio.infra.mk import mk
from alienbio.suite.blocks import (
    CooperativeBindingBlock,
    EnzymeBlock,
    InhibitionBlock,
    SignalingBlock,
    SourceBlock,
    SinkBlock,
)
from alienbio.suite.dist import Constant, Seed
from alienbio.suite.skeleton import (
    PoolBinding,
    Role,
    Skeleton,
    SkeletonBlock,
)
from alienbio.suite.skeleton import final_amount
from alienbio.suite.verify import SimConfig, simulate

_SIM_CFG = SimConfig(dt=0.05, steps=300, sample_every=50)


# ═══════════════════════════════════════════════════════════════════════════
# Unit tier — realize() directly
# ═══════════════════════════════════════════════════════════════════════════


def test_signaling_block_activator_emits_one_reaction_with_modifier() -> None:
    a, b, m = mk.M("A"), mk.M("B"), mk.M("M")
    block = SignalingBlock.make("wire", kind="activator", rate=Constant(0.5), a=Constant(2.0))
    fragment = block.realize(Seed(1), "root/wire", {"in": a, "out": b, "modifier": m})

    assert len(fragment.reactions) == 1
    rxn = next(iter(fragment.reactions.values()))
    assert dict(rxn.reactants) == {a: 1.0}
    assert dict(rxn.products) == {b: 1.0}
    assert rxn.rate == 0.5
    assert set(rxn.modifiers) == {m}
    modulation = rxn.modifiers[m]
    assert isinstance(modulation, Modulation)
    assert modulation.kind == "activator"
    assert modulation.a == 2.0

    assert set(fragment.molecules) == {"A", "B", "M"}
    assert len(fragment.provenance) == 1
    assert fragment.provenance[0].reaction_id in fragment.reactions


def test_signaling_block_inhibitor_kind() -> None:
    a, b, m = mk.M("A"), mk.M("B"), mk.M("M")
    block = SignalingBlock.make("wire", kind="inhibitor", Ki=Constant(3.0))
    fragment = block.realize(Seed(1), "root/wire", {"in": a, "out": b, "modifier": m})
    rxn = next(iter(fragment.reactions.values()))
    modulation = rxn.modifiers[m]
    assert modulation.kind == "inhibitor"
    assert modulation.Ki == 3.0


def test_inhibition_block_emits_one_reaction_with_inhibitor_modifier() -> None:
    a, b, m = mk.M("A"), mk.M("B"), mk.M("I")
    block = InhibitionBlock.make("brake", rate=Constant(1.0), Ki=Constant(4.0))
    fragment = block.realize(Seed(1), "root/brake", {"in": a, "out": b, "modifier": m})
    rxn = next(iter(fragment.reactions.values()))
    assert dict(rxn.reactants) == {a: 1.0}
    assert dict(rxn.products) == {b: 1.0}
    modulation = rxn.modifiers[m]
    assert modulation.kind == "inhibitor"
    assert modulation.Ki == 4.0


def test_enzyme_block_emits_one_reaction_no_es_pool() -> None:
    s, p, e = mk.M("S"), mk.M("P"), mk.M("E")
    block = EnzymeBlock.make("cat", rate=Constant(1.0), Vmax=Constant(5.0), K=Constant(2.0))
    fragment = block.realize(Seed(1), "root/cat", {"substrate": s, "product": p, "enzyme": e})

    assert len(fragment.reactions) == 1
    rxn = next(iter(fragment.reactions.values()))
    assert dict(rxn.reactants) == {s: 1.0}
    assert dict(rxn.products) == {p: 1.0}
    assert set(fragment.molecules) == {"S", "P", "E"}  # no "ES" intermediate
    modulation = rxn.modifiers[e]
    assert modulation.kind == "michaelis"
    assert modulation.Vmax == 5.0
    assert modulation.K == 2.0


def test_cooperative_binding_block_emits_hill_modifier() -> None:
    a, b, m = mk.M("A"), mk.M("B"), mk.M("M")
    block = CooperativeBindingBlock.make(
        "coop", rate=Constant(1.0), Vmax=Constant(1.0), K=Constant(5.0), n=Constant(4.0)
    )
    fragment = block.realize(Seed(1), "root/coop", {"in": a, "out": b, "modifier": m})
    rxn = next(iter(fragment.reactions.values()))
    modulation = rxn.modifiers[m]
    assert modulation.kind == "hill"
    assert modulation.Vmax == 1.0
    assert modulation.K == 5.0
    assert modulation.n == 4.0


def test_modulation_blocks_pass_the_f012_conservation_gate() -> None:
    """Modifiers are excluded from the balance check even with no atoms at
    all (they're neither reactants nor products) — mirrors the boundary
    exemption test in ``test_blocks.py``."""
    a, b, m = mk.M("A"), mk.M("B"), mk.M("M")
    block = SignalingBlock.make("wire", kind="activator")
    fragment = block.realize(Seed(1), "ns", {"in": a, "out": b, "modifier": m})
    chem = mk.C("chem", list(fragment.molecules.values()), list(fragment.reactions.values()))
    validate_conservation(chem)  # must not raise
    assert check_conservation(chem) == []


def test_signaling_block_rejects_unknown_kind() -> None:
    import pytest
    from alienbio.suite.skeleton import SkeletonError

    with pytest.raises(SkeletonError):
        SignalingBlock.make("wire", kind="bogus")


# ═══════════════════════════════════════════════════════════════════════════
# Integration tier — Source(s) + block + Sink, materialized and simulated
# ═══════════════════════════════════════════════════════════════════════════


def _build_wired(
    block: SkeletonBlock,
    *,
    in_port: str = "in",
    out_port: str = "out",
    modifier_port: str = "modifier",
    in_source_rate: float = 5.0,
    modifier_source_rate: float = 0.0,
) -> Skeleton:
    """``source_in -> block.{in_port} -> block.{out_port} -> sink_out`` plus an
    independent ``source_mod -> block.{modifier_port}`` supply — the minimal
    wiring that satisfies ``validate()`` (every pool needs a producer AND a
    bounded fate) for a modulation block's three ports."""
    source_in = SourceBlock.make("source_in", rate=Constant(in_source_rate))
    source_mod = SourceBlock.make("source_mod", rate=Constant(modifier_source_rate))
    sink_out = SinkBlock.make("sink_out", rate=Constant(0.05))
    root = SkeletonBlock(
        name="root",
        role=Role.SUPPLY,
        children=(source_in, source_mod, block, sink_out),
        pool_bindings=(
            PoolBinding("source_in.out", f"{block.name}.{in_port}"),
            PoolBinding("source_mod.out", f"{block.name}.{modifier_port}"),
            PoolBinding(f"{block.name}.{out_port}", "sink_out.in"),
        ),
    )
    return Skeleton(root=root)


def _final_out(skeleton: Skeleton, block_name: str, out_port: str, seed: Seed) -> float:
    world = skeleton.materialize(seed)
    assert skeleton.validate() is None
    timeline = simulate(world, _SIM_CFG, seed.child("oracle-sim"))
    realized_block = next(c for c in skeleton.root.children if c.name == block_name)
    mol_id = realized_block.resolved_ports[out_port]
    return final_amount(timeline, mol_id)


def test_signaling_activator_speeds_product_formation_vs_no_modifier_baseline() -> None:
    baseline = SignalingBlock.make("wire", kind="activator", rate=Constant(0.5), a=Constant(3.0))
    activated = SignalingBlock.make("wire", kind="activator", rate=Constant(0.5), a=Constant(3.0))

    baseline_out = _final_out(
        _build_wired(baseline, modifier_source_rate=0.0), "wire", "out", Seed(10)
    )
    activated_out = _final_out(
        _build_wired(activated, modifier_source_rate=2.0), "wire", "out", Seed(10)
    )
    assert activated_out > baseline_out


def test_signaling_inhibitor_slows_product_formation_vs_no_modifier_baseline() -> None:
    baseline = SignalingBlock.make("wire", kind="inhibitor", rate=Constant(0.5), Ki=Constant(3.0))
    inhibited = SignalingBlock.make("wire", kind="inhibitor", rate=Constant(0.5), Ki=Constant(3.0))

    baseline_out = _final_out(
        _build_wired(baseline, modifier_source_rate=0.0), "wire", "out", Seed(11)
    )
    inhibited_out = _final_out(
        _build_wired(inhibited, modifier_source_rate=2.0), "wire", "out", Seed(11)
    )
    assert inhibited_out < baseline_out


def test_inhibition_block_slows_product_formation_vs_no_modifier_baseline() -> None:
    baseline = InhibitionBlock.make("brake", rate=Constant(0.5), Ki=Constant(2.0))
    braked = InhibitionBlock.make("brake", rate=Constant(0.5), Ki=Constant(2.0))

    baseline_out = _final_out(
        _build_wired(baseline, modifier_source_rate=0.0), "brake", "out", Seed(12)
    )
    braked_out = _final_out(
        _build_wired(braked, modifier_source_rate=2.0), "brake", "out", Seed(12)
    )
    assert braked_out < baseline_out


def test_enzyme_block_speeds_product_formation_with_more_enzyme() -> None:
    """No enzyme (michaelis factor is 0 at [enzyme]=0) -> no product at all;
    a modest enzyme supply switches the reaction on."""
    no_enzyme = EnzymeBlock.make("cat", rate=Constant(1.0), Vmax=Constant(5.0), K=Constant(2.0))
    with_enzyme = EnzymeBlock.make("cat", rate=Constant(1.0), Vmax=Constant(5.0), K=Constant(2.0))

    no_enzyme_out = _final_out(
        _build_wired(no_enzyme, in_port="substrate", out_port="product", modifier_port="enzyme",
                      modifier_source_rate=0.0),
        "cat", "product", Seed(13),
    )
    with_enzyme_out = _final_out(
        _build_wired(with_enzyme, in_port="substrate", out_port="product", modifier_port="enzyme",
                      modifier_source_rate=1.0),
        "cat", "product", Seed(13),
    )
    assert no_enzyme_out == 0.0
    assert with_enzyme_out > no_enzyme_out


def test_enzyme_block_saturates_with_high_enzyme_supply() -> None:
    """More enzyme still speeds product formation, monotonically, well below
    saturation (a modest [enzyme] << K)."""
    low = EnzymeBlock.make("cat", rate=Constant(1.0), Vmax=Constant(5.0), K=Constant(20.0))
    high = EnzymeBlock.make("cat", rate=Constant(1.0), Vmax=Constant(5.0), K=Constant(20.0))

    low_out = _final_out(
        _build_wired(low, in_port="substrate", out_port="product", modifier_port="enzyme",
                     modifier_source_rate=0.5),
        "cat", "product", Seed(14),
    )
    high_out = _final_out(
        _build_wired(high, in_port="substrate", out_port="product", modifier_port="enzyme",
                     modifier_source_rate=2.0),
        "cat", "product", Seed(14),
    )
    assert high_out > low_out


def test_cooperative_binding_block_is_sharper_than_the_hyperbolic_case() -> None:
    """Hill cooperativity (Q: 'sharper response than linear'): the ratio of
    product formed at a high vs a low modifier supply is more extreme for a
    steep cooperativity exponent (n=6) than for the hyperbolic case (n=1,
    == EnzymeBlock's michaelis form)."""

    def out_at(n: float, modifier_source_rate: float, seed: Seed) -> float:
        block = CooperativeBindingBlock.make(
            "coop", rate=Constant(1.0), Vmax=Constant(1.0), K=Constant(30.0), n=Constant(n)
        )
        return _final_out(
            _build_wired(block, modifier_source_rate=modifier_source_rate), "coop", "out", seed
        )

    low_n1 = out_at(1.0, 1.0, Seed(20))
    high_n1 = out_at(1.0, 6.0, Seed(21))
    low_n6 = out_at(6.0, 1.0, Seed(22))
    high_n6 = out_at(6.0, 6.0, Seed(23))

    assert low_n1 > 0.0 and low_n6 > 0.0
    ratio_n1 = high_n1 / low_n1
    ratio_n6 = high_n6 / low_n6
    assert ratio_n6 > ratio_n1


def test_modulation_blocks_are_seed_deterministic() -> None:
    block_a = SignalingBlock.make("wire", kind="activator", rate=Constant(0.5), a=Constant(2.0))
    block_b = SignalingBlock.make("wire", kind="activator", rate=Constant(0.5), a=Constant(2.0))
    out_a = _final_out(_build_wired(block_a, modifier_source_rate=1.0), "wire", "out", Seed(99))
    out_b = _final_out(_build_wired(block_b, modifier_source_rate=1.0), "wire", "out", Seed(99))
    assert out_a == out_b
