"""``ActionRecord`` — one opaque logged action of a trial (M33.8).

The runner writes one per action into ``TrialRecord.action_log``; ``runner``,
``store``, ``trial`` and the analysis families read it. The five generic
metrics this module carried (``info_seeking_count``/``_ratio``,
``destructive_count``/``_rate``, ``actions_before_commit``) and
``TrialRecord``'s three wrappers over them had no caller in ``src/`` or AUP and
were retired in T093; Caution counts accepted investigative and destructive
actions itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


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
    fixture constructs unchanged. ``target`` (M36.1) is the probe a ``Measure``
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
