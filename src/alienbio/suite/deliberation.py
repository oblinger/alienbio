"""Deliberation-trace capture data model (M33.1).

A domain-neutral, immutable record of a reasoning/action stream: a sequence
of :class:`DeliberationStep` entries grouped into a :class:`DeliberationTrace`.
``kind`` and ``refs`` are opaque tags — this module never inspects or
branches on their meaning, it only stores, filters, and indexes them. This is
the keystone that later scorers read to judge surfacing depth, kind mix, and
reference timing, without this module knowing what any of it means.

Both types are frozen dataclasses: every "mutating" method (``append`` /
``extend``) returns a NEW :class:`DeliberationTrace` rather than mutating in
place.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class DeliberationStep:
    """One reasoning/action step in a deliberation trace.

    ``kind`` is an opaque tag (e.g. ``"reason"`` / ``"act"`` / ``"observe"``)
    never inspected for meaning. ``content`` is opaque text. ``refs`` are
    opaque ids this step references or surfaces (e.g. objective ids).
    """

    turn: int
    kind: str
    content: str
    refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class DeliberationTrace:
    """An ordered, immutable sequence of :class:`DeliberationStep` entries."""

    steps: tuple[DeliberationStep, ...] = ()

    def append(self, step: DeliberationStep) -> DeliberationTrace:
        """Return a NEW trace with ``step`` appended; ``self`` is unchanged."""
        return DeliberationTrace(steps=self.steps + (step,))

    def extend(self, steps: Iterable[DeliberationStep]) -> DeliberationTrace:
        """Return a NEW trace with ``steps`` appended in order; ``self`` is unchanged."""
        return DeliberationTrace(steps=self.steps + tuple(steps))

    def steps_of_kind(self, kind: str) -> tuple[DeliberationStep, ...]:
        """Steps whose ``kind`` matches, in original order."""
        return tuple(step for step in self.steps if step.kind == kind)

    def first_ref_turn(self, ref: str) -> Optional[int]:
        """The ``turn`` of the earliest step whose ``refs`` contains ``ref``.

        ``None`` if ``ref`` is never referenced. This is the surfacing-depth
        primitive: it tells a scorer the first turn at which an opaque id was
        surfaced in the trace.
        """
        for step in self.steps:
            if ref in step.refs:
                return step.turn
        return None

    def refs_by_turn(self) -> dict[int, frozenset[str]]:
        """Map each turn to the union of ``refs`` across steps at that turn."""
        result: dict[int, set[str]] = {}
        for step in self.steps:
            result.setdefault(step.turn, set()).update(step.refs)
        return {turn: frozenset(refs) for turn, refs in result.items()}

    def all_refs(self) -> frozenset[str]:
        """Every ref referenced anywhere in the trace, unioned."""
        result: set[str] = set()
        for step in self.steps:
            result.update(step.refs)
        return frozenset(result)

    def depth(self) -> int:
        """Number of steps in the trace."""
        return len(self.steps)
