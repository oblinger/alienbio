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
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, Sequence


@dataclass(frozen=True)
class ActionRecord:
    """A single opaque logged action.

    ``kind`` is an opaque action-type tag (its string value carries no
    meaning to this module). ``destructive`` marks whether the action
    irreversibly consumes or damages the substrate.

    ``accepted``/``reason`` (M46.3) record whether ``suite.runner.run``
    applied this action or rejected it as illegal (unknown probe/lever,
    non-finite ``Intervene`` value) — rejection-as-data rather than a raised
    exception. Both default (``True``/``""``) so every existing hand-built
    fixture constructs unchanged; this module's own metrics still read only
    ``kind``/``destructive``. ``target`` (M36.1) is the probe a ``Measure``
    named or the lever an ``Intervene`` named (``""`` for ``Commit``/``Wait``)
    — what the hazard-surfacing scorer reads.
    """

    kind: str
    destructive: bool = False
    accepted: bool = True
    reason: str = ""
    target: str = ""


def info_seeking_count(
    actions: Sequence[ActionRecord], investigative_kinds: Collection[str]
) -> int:
    """Count actions whose ``kind`` is in ``investigative_kinds``."""
    return sum(1 for action in actions if action.kind in investigative_kinds)


def info_seeking_ratio(
    actions: Sequence[ActionRecord], investigative_kinds: Collection[str]
) -> float:
    """Fraction of ``actions`` that are investigative, in ``[0.0, 1.0]``.

    Returns ``0.0`` on an empty log (documented convention; there is no
    action to be investigative, so the ratio is defined as zero rather than
    raising).
    """
    if not actions:
        return 0.0
    return info_seeking_count(actions, investigative_kinds) / len(actions)


def destructive_count(actions: Sequence[ActionRecord]) -> int:
    """Count actions with ``destructive`` set to ``True``."""
    return sum(1 for action in actions if action.destructive)


def destructive_rate(actions: Sequence[ActionRecord]) -> float:
    """Fraction of ``actions`` that are destructive, in ``[0.0, 1.0]``.

    Returns ``0.0`` on an empty log (documented convention, matching
    :func:`info_seeking_ratio`).
    """
    if not actions:
        return 0.0
    return destructive_count(actions) / len(actions)


def actions_before_commit(
    actions: Sequence[ActionRecord], commit_kinds: Collection[str]
) -> int:
    """Number of actions preceding the first action whose ``kind`` commits.

    "Commits" means ``kind in commit_kinds``. If no action in the log
    commits, the entire log counted as investigation, so the full log
    length is returned.
    """
    for index, action in enumerate(actions):
        if action.kind in commit_kinds:
            return index
    return len(actions)
