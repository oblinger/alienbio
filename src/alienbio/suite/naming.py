"""suite.naming — opaque agent-facing names (M45.15).

A generated world's ids say what its parts *are* (``root/crux/sink_byproduct_in``,
``route_clean/rxn``): a model shown them has the answer before it has measured
anything, and the verbalised measure is satisfiable by reading the observation
aloud. So on a non-neutral world the runner speaks to the agent through a
seed-deterministic :class:`NameMap` — every molecule ``m01…``, every reaction
``r01…``, shuffled — and translates at the boundary in both directions:

- **outbound** (:func:`surface_brief`, :func:`surface_observation`): the brief
  the agent is told and every observation it sees carry surface names only
  (affordances, question, constitution/framing text, irreversible levers);
- **inbound** (:func:`structural_action`): the agent's ``Measure`` probe,
  ``Intervene`` lever, ``Commit`` answer and reasoning ``refs`` come back as
  structural ids, so the runner, the graders and every scorer keep working on
  the world's own names; reasoning *content* stays verbatim (the model's
  words) and scorers that scan it accept the surface alias via the map.

:class:`OpaqueAgent` is the wrapper that does this around any agent; the
record carries ``name_map`` (structural → surface) so an offline reader can
translate the prompts and the trace back. The taint audit scans a prompt for
the *surface* form of every secret and for any structural id at all — a
structural id reaching a prompt is itself the leak.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping, Optional

from .agent import Action, ActionOutcome, Commit, Intervene, Measure, ReasoningStep, SessionAgent, Wait
from .brief import Affordances, TaskBrief
from .dist import Seed
from .observation import Observation
from .types import Answer

if TYPE_CHECKING:
    from ..bio.chemistry import ChemistryImpl


@dataclass(frozen=True)
class NameMap:
    """An injective structural → surface map over one world's ids (and back)."""

    to_surface: Mapping[str, str]
    to_structural: Mapping[str, str]
    _pattern: "re.Pattern[str]" = dataclasses.field(repr=False, compare=False)
    _back_pattern: "re.Pattern[str]" = dataclasses.field(repr=False, compare=False)

    @staticmethod
    def of(mapping: Mapping[str, str]) -> "NameMap":
        back = {v: k for k, v in mapping.items()}
        if len(back) != len(mapping):
            raise ValueError("NameMap: the surface names collide")
        return NameMap(dict(mapping), back, _id_pattern(mapping), _id_pattern(back))

    def surface(self, structural: str) -> str:
        return self.to_surface.get(structural, structural)

    def structural(self, surface: str) -> str:
        return self.to_structural.get(surface, surface)

    def surface_text(self, text: str) -> str:
        """Every structural id in ``text``, as a whole token, replaced by its surface name."""
        return self._pattern.sub(lambda m: self.to_surface[m.group(0)], text) if self.to_surface else text

    def structural_text(self, text: str) -> str:
        return self._back_pattern.sub(lambda m: self.to_structural[m.group(0)], text) if self.to_structural else text

    def surface_value(self, value: Any) -> Any:
        """Translate every string inside a JSON-ish value (keys included)."""
        return _map_value(value, self.surface_text)

    def structural_value(self, value: Any) -> Any:
        return _map_value(value, self.structural_text)


#: Whole-token boundaries for an id in free text. The character class
#: excludes ``.`` so that a token is not matched inside a DOTTED id
#: (``m01`` must not match in ``m01.rate``) — but a bare ``(?!…\.…)`` also
#: refuses a `.` that is sentence punctuation, which is where T066 (deep
#: scan round 2) found a leak: ``surface_text("Never drain root/harm_in.")``
#: returned the structural id unchanged, and the taint audit, which spells
#: the same boundary, then read the prompt as clean. A structural id reached
#: a live model on an opaque-named world with ``taint_hits == ()``.
#:
#: So the dot is excluded only when it CONTINUES the id — ``.`` followed by
#: another id character. A trailing period, comma or end of string is a
#: boundary, and ``task_note`` / ``stakes`` / ``constitution`` / ``protocol``
#: text that ends a sentence on an id is surfaced and audited like any other.
_BOUNDARY_L = r"(?<![A-Za-z0-9_/-])(?<![A-Za-z0-9_/-]\.)"
_BOUNDARY_R = r"(?![A-Za-z0-9_/-])(?!\.[A-Za-z0-9_/-])"


def token_pattern(token: str) -> "re.Pattern[str]":
    """``token`` as a whole id in free text, with :data:`_BOUNDARY_L` /
    :data:`_BOUNDARY_R`. The one spelling of the boundary — the runner's
    taint audit scans with this, so the audit and the surfacing can never
    disagree about what counts as a whole id (T066: they did, and the
    disagreement was a silent leak)."""
    return re.compile(_BOUNDARY_L + re.escape(token) + _BOUNDARY_R)


def _id_pattern(mapping: Mapping[str, str]) -> "re.Pattern[str]":
    if not mapping:
        return re.compile(r"(?!x)x")  # matches nothing
    ids = sorted(mapping, key=len, reverse=True)  # longest first: an id may prefix another
    return re.compile(_BOUNDARY_L + "(?:" + "|".join(re.escape(i) for i in ids) + ")" + _BOUNDARY_R)


def _map_value(value: Any, f: Any) -> Any:
    if isinstance(value, str):
        return f(value)
    if isinstance(value, Mapping):
        return {_map_value(k, f): _map_value(v, f) for k, v in value.items()}
    if isinstance(value, tuple):
        return tuple(_map_value(v, f) for v in value)
    if isinstance(value, list):
        return [_map_value(v, f) for v in value]
    if isinstance(value, (set, frozenset)):
        return type(value)(_map_value(v, f) for v in value)
    return value


def build_name_map(chemistry: "ChemistryImpl", seed: Seed) -> NameMap:
    """``m01…`` for molecules and ``r01…`` for reactions, assigned in a
    seed-shuffled order so the surface name carries neither the structure
    nor the generator's ordering. Deterministic in ``(ids, seed)``."""
    import random

    shared = chemistry.molecules.keys() & chemistry.reactions.keys()
    if shared:
        # Belt and braces beside ChemistryImpl's refusal: this is the place that
        # silently LOSES an entry, since both loops write into one dict.
        raise ValueError(
            f"build_name_map: id(s) {sorted(shared)!r} name both a molecule and a "
            "reaction; one surface name cannot stand for two entities"
        )

    out: dict[str, str] = {}
    for prefix, ids, salt in (("m", sorted(chemistry.molecules), "molecules"), ("r", sorted(chemistry.reactions), "reactions")):
        order = list(ids)
        random.Random(seed.child(f"names/{salt}").value).shuffle(order)
        width = max(2, len(str(len(order))))
        for i, structural in enumerate(order, start=1):
            out[structural] = f"{prefix}{i:0{width}d}"
    return NameMap.of(out)


def surface_brief(brief: TaskBrief, nm: NameMap) -> TaskBrief:
    """The brief as the agent is told it: every id and every id inside its text in surface form."""
    aff = brief.affordances
    return dataclasses.replace(
        brief,
        question=nm.surface_value(brief.question),
        constitution=nm.surface_text(brief.constitution) if brief.constitution else brief.constitution,
        framing=nm.surface_text(brief.framing) if brief.framing else brief.framing,
        # T047 — W2's in-world stakes name the tracked pool and the custodial
        # reserve; every free-text field an id can ride is surfaced.
        stakes=nm.surface_text(brief.stakes) if brief.stakes else brief.stakes,
        reversibility=nm.surface_text(brief.reversibility) if brief.reversibility else brief.reversibility,
        task_note=nm.surface_text(brief.task_note) if brief.task_note else brief.task_note,
        affordances=Affordances(
            probes=tuple(nm.surface(p) for p in aff.probes),
            levers=tuple(nm.surface(l) for l in aff.levers),
            assays=tuple(nm.surface(a) for a in aff.assays),
            max_rates={nm.surface(l): cap for l, cap in aff.max_rates.items()},
        ),
        irreversible=tuple(nm.surface(l) for l in brief.irreversible),
    )


def surface_observation(observation: Observation, nm: NameMap) -> Observation:
    return tuple({nm.surface(k): v for k, v in compartment.items()} for compartment in observation)


def structural_action(action: Action, nm: NameMap) -> Action:
    """The agent's (surface-named) action as the runner applies it."""
    if isinstance(action, Measure):
        return dataclasses.replace(action, probe=nm.structural(action.probe))
    if isinstance(action, Intervene):
        return dataclasses.replace(action, lever=nm.structural(action.lever))
    if isinstance(action, Commit):
        answer = action.answer
        return dataclasses.replace(action, answer=Answer(value=nm.structural_value(answer.value), kind=answer.kind))
    if isinstance(action, Wait):
        return action
    return action


def surface_action(action: Action, nm: NameMap) -> Action:
    if isinstance(action, Measure):
        return dataclasses.replace(action, probe=nm.surface(action.probe))
    if isinstance(action, Intervene):
        return dataclasses.replace(action, lever=nm.surface(action.lever))
    if isinstance(action, Commit):
        answer = action.answer
        return dataclasses.replace(action, answer=Answer(value=nm.surface_value(answer.value), kind=answer.kind))
    return action


class OpaqueAgent:
    """Wrap ``agent`` so it sees and speaks surface names while the runner
    sees structural ids. Implements :class:`~alienbio.suite.agent.SessionAgent`
    (``begin``/``notice`` pass through, translated); every other attribute a
    runner reads off an agent (``usage``, ``prompt_texts``, ``parse_failures``,
    ``aborted`` …) is forwarded untouched."""

    def __init__(self, agent: Any, name_map: NameMap) -> None:
        self.inner = agent
        self.name_map = name_map

    def begin(self, brief: TaskBrief) -> None:
        if isinstance(self.inner, SessionAgent):
            self.inner.begin(surface_brief(brief, self.name_map))

    def notice(self, outcome: ActionOutcome) -> None:
        if isinstance(self.inner, SessionAgent):
            nm = self.name_map
            self.inner.notice(
                dataclasses.replace(
                    outcome,
                    action=surface_action(outcome.action, nm),
                    reason=nm.surface_text(outcome.reason) if outcome.reason else outcome.reason,
                )
            )

    def probe(self, text: str) -> Optional[str]:
        """T026 — a discarded-branch probe, translated at the boundary like
        everything else: the agent is asked in surface names and its answer
        comes back in structural ids (so the record and every scorer read
        world names; the record's ``name_map`` recovers what the agent saw).
        ``None`` when the wrapped agent cannot answer probes."""
        nm = self.name_map
        inner_probe = getattr(self.inner, "probe", None)
        if inner_probe is None:
            return None
        answer = inner_probe(nm.surface_text(text))
        return nm.structural_text(answer) if isinstance(answer, str) else answer

    def act(self, observation: Observation) -> tuple[Action, tuple[ReasoningStep, ...]]:
        nm = self.name_map
        action, steps = self.inner.act(surface_observation(observation, nm))
        back = tuple(dataclasses.replace(s, refs=tuple(nm.structural(r) for r in s.refs)) for s in steps)
        return structural_action(action, nm), back

    def __getattr__(self, name: str) -> Any:  # forwarded diagnostics (usage, prompt_texts, …)
        return getattr(self.inner, name)


def opaque_names_requested(task_setup: Any, dials: Mapping[str, Any]) -> bool:
    """Whether a trial runs under opaque names: the dial ``opaque_names`` wins
    when given (``True``/``False``); else the task's own ``setup["opaque_names"]``
    (every guarded drafter's task sets it)."""
    dial: Optional[Any] = dials.get("opaque_names")
    if dial is not None:
        return bool(dial)
    return bool(isinstance(task_setup, Mapping) and task_setup.get("opaque_names"))


__all__ = [
    "NameMap",
    "OpaqueAgent",
    "build_name_map",
    "opaque_names_requested",
    "structural_action",
    "surface_action",
    "surface_brief",
    "surface_observation",
]
