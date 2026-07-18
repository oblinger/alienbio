"""M33.5 — blind-spot / "should-have-considered" scoring.

Pure, domain-neutral set operations over opaque consideration ids. An
external oracle supplies the set of considerations a competent agent
SHOULD have raised (``should``); the agent's trace yields the set it
actually RAISED (``raised``). Both are ``Collection[str]`` so that either
a ``set`` or a plain ``list`` (possibly with duplicates) may be passed —
all functions dedupe via set semantics before comparing.

- :func:`missed_considerations` — the blind spots: ``should - raised``.
- :func:`spurious_considerations` — extraneous raises: ``raised - should``.
- :func:`blindspot_rate` — fraction of ``should`` that was missed.
- :func:`consideration_coverage` — fraction of ``should`` that was raised.

For non-empty ``should``, ``consideration_coverage(should, raised)
+ blindspot_rate(should, raised) == 1.0`` always holds.
"""

from __future__ import annotations

from typing import Collection


def missed_considerations(
    should: Collection[str], raised: Collection[str]
) -> frozenset[str]:
    """Considerations in ``should`` that are absent from ``raised``.

    These are the blind spots: things a competent agent should have
    raised but did not. Duplicates within either collection are ignored
    (set semantics).
    """
    return frozenset(should) - frozenset(raised)


def spurious_considerations(
    should: Collection[str], raised: Collection[str]
) -> frozenset[str]:
    """Considerations in ``raised`` that are absent from ``should``.

    These are raises the oracle did not deem relevant. Duplicates within
    either collection are ignored (set semantics).
    """
    return frozenset(raised) - frozenset(should)


def blindspot_rate(should: Collection[str], raised: Collection[str]) -> float:
    """Fraction of ``should`` that was missed: ``|missed| / |should|``.

    Result is in ``[0.0, 1.0]``. When ``should`` is empty there is
    nothing to miss, so this is defined as ``0.0`` (not an error, not
    NaN) by convention.
    """
    should_set = frozenset(should)
    if not should_set:
        return 0.0
    missed = missed_considerations(should_set, raised)
    return len(missed) / len(should_set)


def consideration_coverage(
    should: Collection[str], raised: Collection[str]
) -> float:
    """Fraction of ``should`` that was raised: ``|should ∩ raised| / |should|``.

    Result is in ``[0.0, 1.0]``. When ``should`` is empty this is
    defined as ``1.0`` (vacuously fully covered) by convention. For any
    non-empty ``should``, ``consideration_coverage(should, raised)
    + blindspot_rate(should, raised) == 1.0``.
    """
    should_set = frozenset(should)
    if not should_set:
        return 1.0
    covered = should_set & frozenset(raised)
    return len(covered) / len(should_set)
