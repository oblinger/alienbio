"""The Python spelling — ``X`` (M47.1).

``X.<head>(*args, **kwargs)`` builds a :class:`Call`; ``X.name("a.b")`` a
:class:`Name`; ``X.quote(form)`` a :class:`Quoted`; ``X.parse(text)`` reads
the inline spelling, ``X.load(text)`` the structural one; ``X.dump(form,
style=...)`` writes either. ``X.call("name", ...)`` builds a call whose head
collides with one of these helper names.
"""

from __future__ import annotations

from typing import Any

from .form import Call, Name, Quoted
from .parse import dump as _dump_inline
from .parse import parse as _parse
from .yaml_tags import dump_structural as _dump_structural
from .yaml_tags import load_text as _load


class _X:
    def __getattr__(self, head: str) -> Any:
        if head.startswith("_"):
            raise AttributeError(head)

        def build(*args: Any, **kwargs: Any) -> Call:
            return Call(head, args, kwargs)

        return build

    @staticmethod
    def call(head: str, *args: Any, **kwargs: Any) -> Call:
        return Call(head, args, kwargs)

    @staticmethod
    def name(path: str) -> Name:
        return Name(path)

    @staticmethod
    def quote(form: Any) -> Quoted:
        return Quoted(form)

    @staticmethod
    def parse(text: str) -> Any:
        return _parse(text)

    @staticmethod
    def load(text: str) -> Any:
        return _load(text)

    @staticmethod
    def dump(form: Any, style: str = "inline") -> str:
        if style == "inline":
            return _dump_inline(form)
        if style == "structural":
            return _dump_structural(form)
        raise ValueError(f"X.dump: unknown style {style!r}; expected 'inline' or 'structural'")


X = _X()
