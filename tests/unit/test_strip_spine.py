"""The docs build hooks (doc/_hooks/): the spine stripper and the dead-href check (T091 AE2, AE3)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]


def _hook(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "doc" / "_hooks" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


strip = _hook("strip_spine").on_page_markdown


def test_leading_spine_line_dropped_and_ha_links_unwrapped() -> None:
    page = ":>> [ABIO](../ABIO.md) → [X](ha://p/X)\n\n# T\n\nsee [A](ha://a) and [B](https://b)\n"
    assert strip(page) == "# T\n\nsee A and [B](https://b)\n"


def test_ha_links_inside_fenced_and_inline_code_are_left_alone() -> None:
    page = "# T\n```\n[X](ha://cmd)\n```\n`[Y](ha://y)` and [Z](ha://z)\n~~~\n[W](ha://w)\n~~~\n"
    assert strip(page) == "# T\n```\n[X](ha://cmd)\n```\n`[Y](ha://y)` and Z\n~~~\n[W](ha://w)\n~~~\n"


def test_ha_target_with_balanced_parentheses() -> None:
    assert strip("# T\n[A](ha://f/a (1).md) tail") == "# T\nA tail"
    assert strip("# T\n[A](<ha://f/a b.md>) tail") == "# T\nA tail"


def test_image_and_non_ha_links_untouched() -> None:
    page = "# T\n![pic](ha://img.png) [ok](x.md) [a [b] c](ha://z)\n"
    assert strip(page) == page


class _Files:
    def __init__(self, excluded: set[str]) -> None:
        self.excluded = excluded

    def get_file_from_path(self, uri: str) -> object:
        return SimpleNamespace(inclusion=SimpleNamespace(is_excluded=lambda: uri in self.excluded))


def test_head_links_to_excluded_pages_unwrapped_body_links_kept() -> None:
    page = SimpleNamespace(file=SimpleNamespace(src_uri="ABIO Ref/ABIO Ref.md"))
    files = _Files({"ABIO.md", "ABIO Design/ABIO PRD.md"})
    text = "[ABIO](../ABIO.md) · [Ok](ABIO%20Files.md)\n\n# ABIO Ref\n\n[PRD](../ABIO%20Design/ABIO%20PRD.md)\n"
    assert strip(text, page=page, files=files) == (
        "ABIO · [Ok](ABIO%20Files.md)\n\n# ABIO Ref\n\n[PRD](../ABIO%20Design/ABIO%20PRD.md)\n"
    )


def test_dead_hrefs_finds_missing_and_ha_targets(tmp_path: Path) -> None:
    dead_hrefs = _hook("dead_links").dead_hrefs
    (tmp_path / "sub").mkdir()
    (tmp_path / "ok.html").write_text("x")
    (tmp_path / "404.html").write_text('<a href="/abs/x.css">')
    (tmp_path / "sub" / "p.html").write_text(
        '<a href="../ok.html#a"><a href="../gone.html"><a href="ha://p/X"><a href="https://e.com"><a href="#top">'
    )
    assert dead_hrefs(tmp_path) == {"sub/p.html": ["../gone.html", "ha://p/X"]}
