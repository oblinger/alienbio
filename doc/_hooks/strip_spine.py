"""mkdocs hook: drop the vault's navigation marks from pages at build time.

The vault daemon writes a ``:>> A → B → C`` breadcrumb (with ``ha://`` links)
onto the first line of doc pages and rewrites it when deleted (T070 removed
44; they came back), and masthead tables carry ``[X](ha://…)`` crumbs. On the
published site the line renders as literal noise and an ``ha://`` href is
dead, so the build drops the line and unwraps each ``ha://`` link to its
label; the files keep whatever the daemon writes.
"""

from __future__ import annotations

import re

_HA_LINK = re.compile(r"\[([^\]]*)\]\(ha://[^)]*\)")


def on_page_markdown(markdown: str, **_: object) -> str:
    """Return ``markdown`` without its leading ``:>>`` line or ``ha://`` links."""
    lines = markdown.split("\n")
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].lstrip().startswith(":>>"):
        del lines[i]
        while i < len(lines) and not lines[i].strip():
            del lines[i]
    return _HA_LINK.sub(r"\1", "\n".join(lines))
