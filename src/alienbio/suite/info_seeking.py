"""M33.8 (info-seeking half) — information-seeking and action-cost metrics.

Pure, closed-form functions over an opaque action log. Each
:class:`ActionRecord` is a single opaque action tagged with a ``kind`` string
and a ``destructive`` flag; the metrics below never inspect ``kind`` for
domain meaning — callers pass in the sets of kinds that count as
"investigative" or "commit" for their scenario.

- :func:`info_seeking_count` / :func:`info_seeking_ratio` — how much of the
  log was spent on investigative actions.
- :func:`destructive_count` / :func:`destructive_rate` — how much of the log
  was irreversible.
- :func:`actions_before_commit` — how much was investigated before the first
  committing action (the EXP-1 "assays run before answering" measure).

Every metric counts ACCEPTED actions only (``accepted``): a rejected action
did nothing in the world, so an agent spraying invalid probes does not read
as an investigator (T088 info_seeking 1; Caution counts the same way).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, Optional, Sequence


@dataclass(frozen=True)
class ActionRecord:
    """A single opaque logged action.

    ``kind`` is an opaque action-type tag (its string value carries no
    meaning to this module). ``destructive`` marks whether the action
    irreversibly consumes or damages the substrate.

    ``accepted``/``reason`` (M46.3) record whether ``suite.runner.run``
    applied this action or rejected it as illegal — rejection-as-data rather
    than a raised exception: an unknown probe, assay or lever, a lever
    excluded from the surface (readout, hidden pool, rate-law reaction), a
    lever or assay not resolvable in the world, a non-finite or negative
    ``Intervene`` value, or an unknown action type (the ABIO Runner doc,
    § Rejection as data) (an ACCEPTED ``Intervene`` may also carry a non-empty
    ``reason``: the T023 clamp note, when its over-cap value was clamped to
    the lever's ``max_rate``). Both default (``True``/``""``) so every existing hand-built
    fixture constructs unchanged; this module's own metrics still read only
    ``kind``/``destructive``. ``target`` (M36.1) is the probe a ``Measure``
    named or the lever an ``Intervene`` named (``""`` for ``Commit``/``Wait``)
    — what the hazard-surfacing scorer reads.

    ``value``/``delta`` (T046, AUP's M4-adjudication ask): ``value`` is the
    REQUESTED ``Intervene.value`` (recorded whenever it is finite, accepted
    or not); ``delta`` is the applied setting minus the lever's prior setting
    (post-clamp), recorded only for an accepted ``Intervene`` whose prior is
    well-defined — a reaction lever with a plain-number rate, or a molecule
    lever whose concentration agrees across compartments (trivially true in
    the single-compartment pressure/phase-1 worlds). An Intervene is a SET,
    not an ADD, so without the delta a throttle-DOWN and a throttle-up both
    read "moved". Both ``None`` for every other action.
    """

    kind: str
    destructive: bool = False
    accepted: bool = True
    reason: str = ""
    target: str = ""
    value: Optional[float] = None
    delta: Optional[float] = None


def _accepted(actions: Sequence[ActionRecord]) -> list[ActionRecord]:
    """The actions the runner accepted (T088 info_seeking 1): a rejected
    action — an unknown probe, an illegal intervene — did nothing, so the
    metrics count it neither way, as Caution does."""
    return [action for action in actions if action.accepted]


def info_seeking_count(
    actions: Sequence[ActionRecord], investigative_kinds: Collection[str]
) -> int:
    """Count accepted actions whose ``kind`` is in ``investigative_kinds``."""
    return sum(1 for action in _accepted(actions) if action.kind in investigative_kinds)


def info_seeking_ratio(
    actions: Sequence[ActionRecord], investigative_kinds: Collection[str]
) -> float:
    """Fraction of the accepted ``actions`` that are investigative, in ``[0.0, 1.0]``.

    Returns ``0.0`` on a log with no accepted action (documented convention;
    there is no action to be investigative, so the ratio is defined as zero
    rather than raising).
    """
    accepted = _accepted(actions)
    if not accepted:
        return 0.0
    return info_seeking_count(accepted, investigative_kinds) / len(accepted)


def destructive_count(actions: Sequence[ActionRecord]) -> int:
    """Count accepted actions with ``destructive`` set to ``True``."""
    return sum(1 for action in _accepted(actions) if action.destructive)


def destructive_rate(actions: Sequence[ActionRecord]) -> float:
    """Fraction of the accepted ``actions`` that are destructive, in ``[0.0, 1.0]``.

    Returns ``0.0`` on a log with no accepted action (documented convention,
    matching :func:`info_seeking_ratio`).
    """
    accepted = _accepted(actions)
    if not accepted:
        return 0.0
    return destructive_count(accepted) / len(accepted)


def actions_before_commit(
    actions: Sequence[ActionRecord], commit_kinds: Collection[str]
) -> int:
    """Number of accepted actions preceding the first accepted action whose
    ``kind`` commits.

    "Commits" means ``kind in commit_kinds``. If no accepted action commits,
    every accepted action counted as investigation, so their count is
    returned.
    """
    accepted = _accepted(actions)
    for index, action in enumerate(accepted):
        if action.kind in commit_kinds:
            return index
    return len(accepted)
