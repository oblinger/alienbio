"""M46.9 — statistical design fixed before the spend.

Closed-form, dependency-free power arithmetic for the two-sample comparison a
reliability-map contrast makes (:func:`~alienbio.suite.effect_size.cohens_d`
/ :func:`~alienbio.suite.effect_size.welch_t`). Nothing here sizes a run for
you silently: an :class:`~alienbio.suite.experiment.ExperimentSpec` that
declares a :class:`PowerDesign` and asks for fewer trials per condition than
that design needs is refused at load, and the design (target effect, alpha,
power, primary contrast, multiple-comparison policy, the required n) is
written into the run manifest so the claim a run supports is stated before
a dollar is spent.

The formula is the standard normal approximation for a two-sided two-sample
test on means with equal group sizes::

    n_per_group = 2 * ((z_{1-alpha/2} + z_{power}) / d) ** 2

rounded up — a slight underestimate of the exact non-central-t answer for
small n, which is why :func:`trials_for_effect` adds one and never returns
fewer than 2 (a confidence interval and a variance need two observations).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist
from typing import Any, Mapping, Optional

_Z = NormalDist()

#: Multiple-comparison policies the design accepts. ``"none"`` reports the
#: raw alpha; ``"bonferroni"`` divides it by the number of contrasts the map
#: computes (every 2x2 axis pair with two levels apiece — see
#: ``mass_trial._aggregate``).
MULTIPLE_COMPARISON_POLICIES: frozenset[str] = frozenset({"none", "bonferroni"})


def z_quantile(p: float) -> float:
    """The standard-normal quantile at probability ``p`` (0 < p < 1)."""
    if not (0.0 < p < 1.0):
        raise ValueError(f"z_quantile: p must be in (0, 1), got {p!r}")
    return _Z.inv_cdf(p)


def trials_for_effect(
    d: float, *, alpha: float = 0.05, power: float = 0.8, two_sided: bool = True
) -> int:
    """Trials per condition needed to detect a standardized effect ``d``.

    Raises:
        ValueError: ``d`` is not positive, or ``alpha``/``power`` are outside
            ``(0, 1)`` — a design that cannot be sized must not pass quietly.
    """
    if not (d > 0.0) or math.isinf(d) or math.isnan(d):
        raise ValueError(f"trials_for_effect: target effect d must be > 0, got {d!r}")
    if not (0.0 < alpha < 1.0) or not (0.0 < power < 1.0):
        raise ValueError(
            f"trials_for_effect: alpha and power must be in (0, 1), got alpha={alpha!r}, power={power!r}"
        )
    z_alpha = z_quantile(1.0 - alpha / 2.0) if two_sided else z_quantile(1.0 - alpha)
    z_power = z_quantile(power)
    n = 2.0 * ((z_alpha + z_power) / d) ** 2
    return max(2, math.ceil(n) + 1)


def detectable_effect(n: int, *, alpha: float = 0.05, power: float = 0.8, two_sided: bool = True) -> float:
    """The smallest standardized effect ``n`` trials per condition can detect
    at the given ``alpha``/``power`` — the inverse of :func:`trials_for_effect`."""
    if n < 2:
        raise ValueError(f"detectable_effect: n must be >= 2, got {n!r}")
    z_alpha = z_quantile(1.0 - alpha / 2.0) if two_sided else z_quantile(1.0 - alpha)
    z_power = z_quantile(power)
    return (z_alpha + z_power) * math.sqrt(2.0 / n)


def bonferroni_alpha(alpha: float, comparisons: int) -> float:
    """``alpha / comparisons`` (``alpha`` itself when there is at most one)."""
    if comparisons <= 1:
        return alpha
    return alpha / comparisons


@dataclass(frozen=True)
class PowerDesign:
    """The statistical design a run is committed to before it starts.

    ``primary_contrast`` names the ONE comparison the run exists to make:
    ``{"axis": <dial>, "low": <level>, "high": <level>}`` — the reliability
    map's other contrasts are exploratory and are reported under the
    multiple-comparison policy. ``target_effect_d`` is the Cohen's d the run
    must be able to detect at ``alpha`` / ``power``.
    """

    target_effect_d: float
    alpha: float = 0.05
    power: float = 0.8
    primary_contrast: Optional[Mapping[str, Any]] = None
    multiple_comparison: str = "none"

    def __post_init__(self) -> None:
        trials_for_effect(self.target_effect_d, alpha=self.alpha, power=self.power)  # validates
        if self.multiple_comparison not in MULTIPLE_COMPARISON_POLICIES:
            raise ValueError(
                f"PowerDesign: multiple_comparison must be one of "
                f"{sorted(MULTIPLE_COMPARISON_POLICIES)}, got {self.multiple_comparison!r}"
            )
        pc = self.primary_contrast
        if pc is not None and (not isinstance(pc, Mapping) or {"axis", "low", "high"} - set(pc)):
            raise ValueError(
                "PowerDesign: primary_contrast must be a mapping with 'axis', 'low' and 'high'"
            )

    @property
    def required_trials_per_condition(self) -> int:
        return trials_for_effect(self.target_effect_d, alpha=self.alpha, power=self.power)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_effect_d": self.target_effect_d,
            "alpha": self.alpha,
            "power": self.power,
            "primary_contrast": dict(self.primary_contrast) if self.primary_contrast else None,
            "multiple_comparison": self.multiple_comparison,
            "required_trials_per_condition": self.required_trials_per_condition,
        }

    @staticmethod
    def from_dict(d: Mapping[str, Any]) -> "PowerDesign":
        unknown = sorted(set(d) - {"target_effect_d", "alpha", "power", "primary_contrast", "multiple_comparison"})
        if unknown:
            raise ValueError(f"PowerDesign: unknown design key(s): {unknown}")
        if "target_effect_d" not in d:
            raise ValueError("PowerDesign: 'target_effect_d' is required")
        return PowerDesign(
            target_effect_d=float(d["target_effect_d"]),
            alpha=float(d.get("alpha", 0.05)),
            power=float(d.get("power", 0.8)),
            primary_contrast=d.get("primary_contrast"),
            multiple_comparison=str(d.get("multiple_comparison", "none")),
        )
