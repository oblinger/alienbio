"""Quiescence detection: run simulation until a measure stabilizes."""

from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .biosystem import BioSystem


class QuiescenceTimeout(Exception):
    """Raised when quiescence is not reached within the timeout."""


def run_until_quiet(
    system: "BioSystem",
    *,
    measure: str = "all_concentrations",
    measure_params: Optional[Dict[str, Any]] = None,
    delta: float = 0.01,
    span: int = 50,
    timeout: int = 10000,
) -> int:
    """Run simulation until a measurement stabilizes.

    Runs the system step by step, checking whether the measurement
    has changed by less than `delta` over the last `span` consecutive steps.

    Args:
        system: The biological system to simulate
        measure: Measurement name (via AgentInterface)
        measure_params: Parameters for the measurement
        delta: Maximum allowed change for stability
        span: Number of consecutive stable steps required
        timeout: Maximum steps before raising QuiescenceTimeout

    Returns:
        Number of steps taken to reach quiescence

    Raises:
        QuiescenceTimeout: If quiescence not reached within timeout
    """
    from .agent_interface import AgentInterface

    iface = AgentInterface(system)
    params = measure_params or {}

    prev_value = iface.measure(measure, **params)
    stable_count = 0

    for step in range(1, timeout + 1):
        system.step()
        current_value = iface.measure(measure, **params)

        change = _measure_change(prev_value, current_value)
        if change <= delta:
            stable_count += 1
        else:
            stable_count = 0

        if stable_count >= span:
            return step

        prev_value = current_value

    raise QuiescenceTimeout(
        f"Quiescence not reached after {timeout} steps "
        f"(delta={delta}, span={span})"
    )


def _measure_change(prev: Any, current: Any) -> float:
    """Compute the magnitude of change between two measurements."""
    if isinstance(prev, (int, float)) and isinstance(current, (int, float)):
        return abs(current - prev)

    if isinstance(prev, dict) and isinstance(current, dict):
        total = 0.0
        for key in prev:
            if key in current:
                total += abs(current[key] - prev[key])
        return total

    # Fallback: treat as different
    return float("inf") if prev != current else 0.0
