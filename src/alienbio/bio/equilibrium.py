"""Equilibrium analysis: stability detection and homeostasis targets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .biosystem import BioSystem

from .state import StateImpl


@dataclass
class StabilityResult:
    """Result of a stability check on a timeline."""

    stable: bool
    variance: Dict[str, float]
    max_variance: float
    unstable_molecules: List[str]
    steps_run: int
    window: int


@dataclass
class HomeostasisTarget:
    """A target concentration range for a molecule."""

    molecule: str
    target: float
    tolerance: float = 0.1

    @property
    def low(self) -> float:
        return self.target * (1.0 - self.tolerance)

    @property
    def high(self) -> float:
        return self.target * (1.0 + self.tolerance)

    def check(self, concentration: float) -> bool:
        return self.low <= concentration <= self.high


def compute_variance(timeline: List[StateImpl], window: int) -> Dict[str, float]:
    """Compute variance of each molecule over the last `window` steps.

    Args:
        timeline: List of states (length >= window)
        window: Number of trailing steps to analyze

    Returns:
        Dict mapping molecule name to variance of concentration
    """
    if len(timeline) < window:
        window = len(timeline)
    if window == 0:
        return {}

    tail = timeline[-window:]
    molecules = list(tail[0])
    result: Dict[str, float] = {}

    for mol in molecules:
        values = [s[mol] for s in tail]
        mean = sum(values) / len(values)
        var = sum((v - mean) ** 2 for v in values) / len(values)
        result[mol] = var

    return result


def check_stability(
    timeline: List[StateImpl],
    window: int = 100,
    threshold: float = 1e-4,
) -> StabilityResult:
    """Check whether a simulation has reached equilibrium.

    Computes per-molecule variance over the trailing window. The system
    is considered stable when all variances are below the threshold.

    Args:
        timeline: Full simulation timeline
        window: Number of trailing steps to check
        threshold: Maximum allowed variance per molecule

    Returns:
        StabilityResult with per-molecule variance and stability flag
    """
    variance = compute_variance(timeline, window)
    unstable = [mol for mol, var in variance.items() if var >= threshold]
    max_var = max(variance.values()) if variance else 0.0

    return StabilityResult(
        stable=len(unstable) == 0,
        variance=variance,
        max_variance=max_var,
        unstable_molecules=unstable,
        steps_run=len(timeline) - 1,
        window=min(window, len(timeline)),
    )


def run_to_equilibrium(
    system: "BioSystem",
    max_steps: int = 10000,
    window: int = 100,
    threshold: float = 1e-4,
    check_interval: int = 100,
) -> tuple[List[StateImpl], StabilityResult]:
    """Run a BioSystem until equilibrium is reached or max_steps exceeded.

    Runs in chunks of `check_interval` steps, checking stability after each
    chunk. Returns the full timeline and the final stability result.

    Args:
        system: BioSystem to simulate
        max_steps: Maximum total steps to run
        window: Trailing window for variance check
        threshold: Variance threshold for stability
        check_interval: Steps between stability checks

    Returns:
        Tuple of (timeline, StabilityResult)
    """
    timeline: List[StateImpl] = [system.state.copy()]
    steps_done = 0

    while steps_done < max_steps:
        chunk = min(check_interval, max_steps - steps_done)
        chunk_timeline = system.simulator.run(system.state, chunk)
        # chunk_timeline[0] is current state (duplicate), skip it
        timeline.extend(chunk_timeline[1:])
        system.state = chunk_timeline[-1].copy()
        steps_done += chunk

        if steps_done >= window:
            result = check_stability(timeline, window, threshold)
            if result.stable:
                return timeline, result

    return timeline, check_stability(timeline, window, threshold)


def find_unstable_rates(
    system: "BioSystem",
    steps: int = 1000,
    window: int = 100,
    threshold: float = 1e-4,
) -> Dict[str, float]:
    """Return candidate reactions when the system is unstable.

    Runs the system once as a baseline. If the baseline is stable, returns
    an empty dict. If the baseline is unstable, returns every reaction with
    a currently positive rate, mapped to its rate value.

    NOTE: Despite the name/historical intent, this does NOT perform
    per-reaction ablation or localization (i.e. it never disables an
    individual reaction and re-checks stability to see whether that
    reaction is actually responsible). It has no way to narrow down which
    specific reaction(s) are causing the instability -- when the baseline
    is unstable, it simply returns all active-rate reactions as
    undifferentiated candidates. True per-reaction ablation would be a
    useful enhancement but is a new feature requiring separate design and
    approval; it is not implemented here.

    Args:
        system: BioSystem to analyze
        steps: Steps to run for the baseline
        window: Trailing window for stability check
        threshold: Variance threshold

    Returns:
        Empty dict if the baseline run is stable. Otherwise, a dict
        mapping every reaction name with a positive current rate to that
        rate value (candidates, not localized/ablated causes).
    """
    from .biosystem import BioSystem as _BioSystem

    # Baseline run
    baseline_sys = _BioSystem(
        system.chemistry, system.state.copy(),
        dt=system.simulator.dt,
    )
    baseline_timeline = baseline_sys.run(steps)
    baseline_result = check_stability(baseline_timeline, window, threshold)

    if baseline_result.stable:
        return {}

    # NOTE: No per-reaction ablation happens here -- see docstring. This is
    # an undifferentiated list of all active-rate reactions, not a
    # localized diagnosis of which reaction(s) actually cause instability.
    unstable_rates: Dict[str, float] = {}

    for rxn_name, reaction in system.chemistry.reactions.items():
        rate = reaction.get_rate(system.state)
        if rate > 0:
            unstable_rates[rxn_name] = rate

    return unstable_rates


def check_homeostasis(
    state: StateImpl,
    targets: List[HomeostasisTarget],
) -> Dict[str, bool]:
    """Check which homeostasis targets are met in the given state.

    Args:
        state: Current system state
        targets: List of homeostasis targets to check

    Returns:
        Dict mapping molecule name to whether target is met
    """
    return {t.molecule: t.check(state[t.molecule]) for t in targets}
