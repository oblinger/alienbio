#!/usr/bin/env python3
"""Demo 03: Perturbation — spike recovery and reaction-removal drift."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")

from _shared import make_homeostatic_system
from alienbio.viz import perturbation_response, save_or_show

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "03_perturbation"


def main() -> None:
    # Spike recovery
    sys_base = make_homeostatic_system(seed=42)
    sys_base.run(200)
    baseline_tl = sys_base.run(100)

    sys_spike = make_homeostatic_system(seed=42)
    sys_spike.run(200)
    sys_spike.state["A"] = sys_spike.state["A"] + 20.0
    spike_tl = sys_spike.run(100)

    fig1 = perturbation_response(baseline_tl, spike_tl, title="Spike Recovery")
    save_or_show(fig1, OUTPUT / "spike_recovery.png")

    # Drift from reaction removal
    from alienbio.bio import BioSystem, ChemistryImpl, StateImpl

    sys_drift_base = make_homeostatic_system(seed=42)
    sys_drift_base.run(200)
    drift_baseline_tl = sys_drift_base.run(200)

    # Remove r_bc reaction
    sys_orig = make_homeostatic_system(seed=42)
    remaining = {n: r for n, r in sys_orig.chemistry.reactions.items() if n != "r_bc"}

    class _MockDat:
        def __init__(self, p: str) -> None:
            self._path = p
        def get_path_name(self) -> str:
            return self._path
        def get_path(self) -> str:
            return f"/tmp/{self._path}"
        def save(self) -> None:
            pass

    modified_chem = ChemistryImpl(
        "abc_no_rbc",
        atoms=sys_orig.chemistry.atoms,
        molecules=sys_orig.chemistry.molecules,
        reactions=remaining,
        dat=_MockDat("chem/abc_no_rbc"),
    )
    init_concs = {m: sys_drift_base.state[m] for m in sys_drift_base.state}
    modified_state = StateImpl(modified_chem, initial=init_concs)
    sys_drift = BioSystem(modified_chem, modified_state, dt=0.1)
    drift_tl = sys_drift.run(200)

    fig2 = perturbation_response(drift_baseline_tl, drift_tl, title="Reaction Removal Drift")
    save_or_show(fig2, OUTPUT / "drift.png")

    print("demo_03_perturbation: OK")


if __name__ == "__main__":
    main()
