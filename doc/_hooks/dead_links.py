"""mkdocs hook: every relative href on the built site resolves (T091 AE2).

mkdocs 1.6 reports a link to an ``exclude_docs`` page at INFO whatever
``validation.links`` says, so ``--strict`` passed with 28 dead links on the
site. After the build this walks every page's HTML and logs a WARNING for each
relative ``href`` with no file behind it (and every ``ha://`` href), so
``mkdocs build --strict`` fails on them. ``404.html`` is skipped: its asset
paths are site-absolute by design.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote

log = logging.getLogger("mkdocs.hooks.dead_links")

_HREF = re.compile(r'href="([^"]+)"')
_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)


def dead_hrefs(site: Path) -> dict[str, list[str]]:
    """Each built page's dead relative hrefs, by page path under ``site``."""
    out: dict[str, list[str]] = {}
    for page in sorted(site.rglob("*.html")):
        rel = page.relative_to(site).as_posix()
        if rel == "404.html" or rel.startswith(("assets/", "search/")):
            continue
        dead: list[str] = []
        for url in _HREF.findall(page.read_text(errors="ignore")):
            if url.startswith("ha:"):
                dead.append(url)
                continue
            if _SCHEME.match(url) or url.startswith(("#", "/")):
                continue
            path = unquote(url.split("#", 1)[0].split("?", 1)[0])
            if path and not os.path.exists(os.path.normpath(page.parent / path)):
                dead.append(url)
        if dead:
            out[rel] = sorted(set(dead))
    return out


def on_post_build(config: Any, **_: object) -> None:
    for page, urls in dead_hrefs(Path(config["site_dir"])).items():
        for url in urls:
            log.warning("dead link on the built site: '%s' links to '%s'", page, unquote(url))
