"""mkdocs hook: drop the vault's navigation marks from pages at build time.

The vault daemon writes a ``:>> A → B → C`` breadcrumb (with ``ha://`` links)
onto the first line of doc pages and rewrites it when deleted (T070 removed
44; they came back), and masthead tables carry ``[X](ha://…)`` crumbs. On the
published site the line renders as literal noise and an ``ha://`` href is
dead, so the build drops the line and unwraps each ``ha://`` link to its
label; the files keep whatever the daemon writes.

The head of a page — every line above its first ``# `` heading: the parent
link, the masthead and its machine-computed ``...`` cell — is vault
navigation the daemon owns, so a link there to a page ``exclude_docs`` keeps
off the site (``ABIO.md``, ``ABIO Design/…``) is unwrapped to its label too.
A link in the BODY to an excluded page is left alone: it is a real dead link,
and ``dead_links.py`` reports it as a warning, so ``--strict`` fails on it.

Fenced code and inline code spans are never rewritten (T091 AE3), and a link
target may carry balanced parentheses (``[A](ha://f/a (1).md)``).
"""

from __future__ import annotations

import posixpath
import re
from typing import Any, Callable, Optional
from urllib.parse import unquote

_FENCE = re.compile(r"^\s*(```+|~~~+)")
_INLINE_CODE = re.compile(r"(`+)(?:.+?)\1")
_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)


def _link_end(text: str, start: int) -> Optional[int]:
    """The index just past the ``)`` closing a link destination whose ``(`` is
    at ``start``; parentheses inside it balance, ``<…>`` is taken whole."""
    i = start + 1
    if i < len(text) and text[i] == "<":
        close = text.find(">", i)
        if close < 0 or close + 1 >= len(text) or text[close + 1] != ")":
            return None
        return close + 2
    depth = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                return i + 1
            depth -= 1
        i += 1
    return None


def _rewrite_links(text: str, unwrap: Callable[[str], bool]) -> str:
    """``text`` with every ``[label](target)`` whose target ``unwrap`` accepts
    replaced by its label (an image ``![…](…)`` is never touched)."""
    out: list[str] = []
    i = 0
    while True:
        open_ = text.find("[", i)
        close = text.find("]", open_ + 1) if open_ >= 0 else -1
        if open_ < 0 or close < 0:
            out.append(text[i:])
            return "".join(out)
        if "[" in text[open_ + 1 : close] or close + 1 >= len(text) or text[close + 1] != "(":
            out.append(text[i : open_ + 1])
            i = open_ + 1
            continue
        end = _link_end(text, close + 1)
        if end is None:
            out.append(text[i : close + 1])
            i = close + 1
            continue
        target = text[close + 2 : end - 1].strip()
        if target.startswith("<") and target.endswith(">"):
            target = target[1:-1]
        image = open_ > 0 and text[open_ - 1] == "!"
        if not image and unwrap(target):
            out.append(text[i:open_])
            out.append(text[open_ + 1 : close])
        else:
            out.append(text[i:end])
        i = end


def _outside_code(markdown: str, fn: Callable[[str, int], str]) -> str:
    """Apply ``fn(segment, line_no)`` to every stretch outside fenced code and
    inline code spans; code passes through untouched."""
    lines = markdown.split("\n")
    fence: Optional[str] = None
    for n, line in enumerate(lines):
        m = _FENCE.match(line)
        if fence is not None:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            continue
        if m:
            fence = m.group(1)
            continue
        parts: list[str] = []
        last = 0
        for code in _INLINE_CODE.finditer(line):
            parts.append(fn(line[last : code.start()], n))
            parts.append(code.group(0))
            last = code.end()
        parts.append(fn(line[last:], n))
        lines[n] = "".join(parts)
    return "\n".join(lines)


def _is_ha(target: str) -> bool:
    return target.startswith("ha://")


def _excluded(page: Any, files: Any) -> Callable[[str], bool]:
    """Whether a relative link target on ``page`` names a page the build excludes."""

    def check(target: str) -> bool:
        if page is None or files is None or _SCHEME.match(target) or target.startswith(("/", "#")):
            return False
        path = unquote(target.split("#", 1)[0])
        if not path:
            return False
        uri = posixpath.normpath(posixpath.join(posixpath.dirname(page.file.src_uri), path))
        hit = files.get_file_from_path(uri)
        return hit is not None and hit.inclusion.is_excluded()

    return check


def on_page_markdown(markdown: str, page: Any = None, files: Any = None, **_: object) -> str:
    """Return ``markdown`` without its leading ``:>>`` line or ``ha://`` links,
    and with head links to excluded pages unwrapped to their labels."""
    lines = markdown.split("\n")
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].lstrip().startswith(":>>"):
        del lines[i]
        while i < len(lines) and not lines[i].strip():
            del lines[i]
    h1 = next((n for n, line in enumerate(lines) if line.startswith("# ")), 0)
    excluded = _excluded(page, files)

    def rewrite(segment: str, line_no: int) -> str:
        if line_no < h1:
            return _rewrite_links(segment, lambda t: _is_ha(t) or excluded(t))
        return _rewrite_links(segment, _is_ha)

    return _outside_code("\n".join(lines), rewrite)
