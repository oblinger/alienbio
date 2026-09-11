"""T051 box 5 / T057 proposal 6 — the Protocols are a live contract."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_every_protocol_export_exists():
    """`from alienbio.protocols import *` raised on three names that were never
    defined (Scenario, Region, Organism); pyright warned and CI gated errors only."""
    namespace: dict = {}
    exec("from alienbio.protocols import *", namespace)
    import alienbio.protocols as protocols

    assert set(protocols.__all__) <= set(namespace)


def test_the_conformance_file_is_type_checked_by_the_ci_gate():
    """`pyright src/` is the gate; the conformance file assigns every
    implementation to its Protocol, so a drift in either is a red check."""
    result = subprocess.run(
        [sys.executable, "-m", "pyright", str(REPO / "src" / "alienbio" / "protocols" / "_conformance.py")],
        capture_output=True, text=True, cwd=REPO,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 errors" in result.stdout


def test_both_simulators_expose_the_simulator_contract():
    from alienbio.bio import CompartmentTreeImpl, WorldSimulatorImpl, WorldStateImpl
    from alienbio.bio.jax_simulator import HAS_JAX, JaxWorldSimulator

    tree = CompartmentTreeImpl()
    tree.add_root("organism")
    state = WorldStateImpl(tree=tree, num_molecules=1)
    ref = WorldSimulatorImpl(tree, [], [], num_molecules=1, dt=0.5)
    assert ref.tree is tree and ref.dt == 0.5 and len(ref.run(state, 4, sample_every=2)) == 3
    if HAS_JAX:
        jx = JaxWorldSimulator(tree, [], num_molecules=1, dt=0.5)
        assert jx.tree is tree and jx.dt == 0.5 and len(jx.run(state, 4, sample_every=2)) == 3
