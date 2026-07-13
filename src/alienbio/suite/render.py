"""Deterministic NL rendering engine for :class:`Question` / :class:`Answer`.

This module turns a structured question/answer into faithful natural language
over a **controlled vocabulary**, and provides a lossless inverse
:func:`parse` that proves faithfulness:
``parse(render(x, v), v, kind=x.kind, as_answer=isinstance(x, Answer)) == x``.

There is **no LLM, no randomness, no network** — rendering is a fixed template
per ``(type, kind)`` with the payload's opaque tokens substituted via a
:class:`Vocabulary`. The engine carries NO domain logic: it never inspects the
meaning of a token, it only substitutes surface phrases.

The vocabulary is a bijection on the tokens it covers (its phrases must be
injective and must not contain the token separator or the empty-collection
sentinel), which is exactly what makes rendering losslessly invertible for the
fixed-vocabulary case. A token missing from the vocabulary (render) or a phrase
missing from the inverse (parse) raises rather than guessing.

Supported ``kind``s mirror the answer model:
- ``node_id`` — a single opaque token (payload: ``str``).
- ``node_set`` — an unordered set of tokens (payload: ``set[str]``; rendered
  sorted for determinism).
- ``ordered_path`` — an ordered list of tokens (payload: ``list[str]``).
- ``scalar`` — a single JSON scalar (payload: ``int``/``float``/``str``/``bool``/``None``).
- ``json`` — an arbitrary JSON-ish value (payload: any JSON value).

``scalar`` and ``json`` carry no vocabulary tokens; their payload is embedded
verbatim as canonical JSON, so no vocabulary lookup is involved for those kinds.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Union

from .types import Answer, Question

# ── Fixed lexical constants (never emitted inside a token phrase) ────────────

#: Stable separator placed between token phrases in a set / path.
SEP = " | "
#: Sentinel used to render an empty ``node_set`` / ``ordered_path``.
EMPTY = "(none)"

# The supported kinds.
_KINDS = ("node_id", "node_set", "ordered_path", "scalar", "json")

# Per-(as_answer, kind) fixed (prefix, suffix) templates. The middle between
# prefix and suffix carries the (substituted) payload.
_TEMPLATES: dict[tuple[bool, str], tuple[str, str]] = {
    # Answers (statements).
    (True, "node_id"): ("The node is ", "."),
    (True, "node_set"): ("The nodes are: ", "."),
    (True, "ordered_path"): ("The path is: ", "."),
    (True, "scalar"): ("The value is ", "."),
    (True, "json"): ("The data is ", "."),
    # Questions (prompts).
    (False, "node_id"): ("Which node matches ", "?"),
    (False, "node_set"): ("Which nodes match: ", "?"),
    (False, "ordered_path"): ("What path is: ", "?"),
    (False, "scalar"): ("What value is ", "?"),
    (False, "json"): ("What data is ", "?"),
}


@dataclass(frozen=True)
class Vocabulary:
    """A bijection between opaque tokens and fixed surface phrases.

    ``phrases`` maps ``token -> surface phrase``. It must be **injective** (no
    two tokens share a phrase) so the inverse is unambiguous, and no phrase may
    contain :data:`SEP` or equal :data:`EMPTY` (those are reserved lexical
    markers). Violations raise ``ValueError`` at construction time.
    """

    phrases: Mapping[str, str]
    _inverse: dict[str, str] = field(default_factory=dict, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        inverse: dict[str, str] = {}
        for token, phrase in self.phrases.items():
            if phrase in inverse:
                raise ValueError(
                    f"Vocabulary is not injective: phrase {phrase!r} maps from "
                    f"both {inverse[phrase]!r} and {token!r}"
                )
            if SEP in phrase:
                raise ValueError(
                    f"phrase {phrase!r} contains the reserved separator {SEP!r}"
                )
            if phrase == EMPTY:
                raise ValueError(
                    f"phrase {phrase!r} collides with the empty-collection sentinel"
                )
            inverse[phrase] = token
        object.__setattr__(self, "_inverse", inverse)

    def phrase_for(self, token: str) -> str:
        """Return the surface phrase for ``token``; raise ``KeyError`` if absent."""
        if token not in self.phrases:
            raise KeyError(f"token {token!r} is not in the vocabulary")
        return self.phrases[token]

    def token_for(self, phrase: str) -> str:
        """Return the token for ``phrase``; raise ``ValueError`` if absent."""
        if phrase not in self._inverse:
            raise ValueError(f"phrase {phrase!r} is not in the vocabulary")
        return self._inverse[phrase]


def _canonical_json(value: Any) -> str:
    """Deterministic JSON encoding (sorted keys, compact separators)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _render_payload(payload: Any, vocabulary: Vocabulary, kind: str) -> str:
    """Render the middle (substituted payload) for a given ``kind``."""
    if kind == "node_id":
        return vocabulary.phrase_for(payload)
    if kind == "node_set":
        phrases = sorted(vocabulary.phrase_for(t) for t in payload)
        return SEP.join(phrases) if phrases else EMPTY
    if kind == "ordered_path":
        phrases = [vocabulary.phrase_for(t) for t in payload]
        return SEP.join(phrases) if phrases else EMPTY
    if kind in ("scalar", "json"):
        return _canonical_json(payload)
    raise ValueError(f"unsupported kind {kind!r}")


def _parse_payload(middle: str, vocabulary: Vocabulary, kind: str) -> Any:
    """Invert :func:`_render_payload` for a given ``kind``."""
    if kind == "node_id":
        return vocabulary.token_for(middle)
    if kind == "node_set":
        if middle == EMPTY:
            return set()
        return {vocabulary.token_for(p) for p in middle.split(SEP)}
    if kind == "ordered_path":
        if middle == EMPTY:
            return []
        return [vocabulary.token_for(p) for p in middle.split(SEP)]
    if kind in ("scalar", "json"):
        return json.loads(middle)
    raise ValueError(f"unsupported kind {kind!r}")


def render(node: Union[Question, Answer], vocabulary: Vocabulary) -> str:
    """Render ``node`` to faithful text over ``vocabulary``.

    Deterministic: the same ``(node, vocabulary)`` always yields a byte-identical
    string. A token absent from ``vocabulary`` raises ``KeyError`` (never guessed).
    """
    as_answer = isinstance(node, Answer)
    kind = node.kind
    key = (as_answer, kind)
    if key not in _TEMPLATES:
        raise ValueError(f"unsupported kind {kind!r} for {'Answer' if as_answer else 'Question'}")
    prefix, suffix = _TEMPLATES[key]
    payload = node.value if as_answer else node.structured
    middle = _render_payload(payload, vocabulary, kind)
    return f"{prefix}{middle}{suffix}"


def parse(
    text: str,
    vocabulary: Vocabulary,
    *,
    kind: str,
    as_answer: bool = False,
) -> Union[Question, Answer]:
    """Inverse of :func:`render` for the fixed-vocabulary case.

    ``parse(render(x, v), v, kind=x.kind, as_answer=isinstance(x, Answer)) == x``
    for every supported ``kind``. A phrase absent from ``vocabulary`` raises
    ``ValueError`` (never guessed); malformed text (wrong template) raises
    ``ValueError``.
    """
    key = (as_answer, kind)
    if key not in _TEMPLATES:
        raise ValueError(f"unsupported kind {kind!r} for {'Answer' if as_answer else 'Question'}")
    prefix, suffix = _TEMPLATES[key]
    if not (text.startswith(prefix) and text.endswith(suffix)):
        raise ValueError(
            f"text does not match the {kind!r} "
            f"{'Answer' if as_answer else 'Question'} template: {text!r}"
        )
    middle = text[len(prefix): len(text) - len(suffix)]
    payload = _parse_payload(middle, vocabulary, kind)
    if as_answer:
        return Answer(value=payload, kind=kind)
    return Question(structured=payload, kind=kind)
