"""The no-peeking lint — a guard for the owner's 2026-08-27 ruling.

**The rule** (ABIO Experiment Catalog § *The no-peeking rule*): no language
model is ever run on a substrate the Alignment Under Pressure paper has a
registered question about, until that paper has published. World-property
tests and scripted-agent tests are fine — they characterise the world. Any
LLM trial is not, whatever it measures: even a "does it emit valid JSON"
check produces a transcript of a model reasoning about that world under that
dial, and that transcript is the peek.

**The guard.** A written rule that nothing checks is a guard that passes
without protecting, so this test statically scans every executable file under
``tests/``, ``demos/`` and ``docs/`` (``.py`` and ``.ipynb`` — notebooks
included because an illustrative demo is the likeliest accident) and fails if
any one file names an LLM entry point *and* a conflict/pressure-family
drafter. It reads source text only: no key, no network, and it cannot itself
peek. It runs in ordinary CI.

Keep LLM harness validation on the neutral capability substrates
(``identify_pathway`` and the H1–H5 hello-world progression); that is where
the one opt-in real-model test already lives.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Names that put a language model in the loop.
LLM_ENTRY_POINTS: tuple[str, ...] = ("LLMAgent", "default_anthropic_llm_fn")

#: Drafters of the substrates AUP has registered questions about — the
#: M31 conflict / pressure / delta generators.
GUARDED_DRAFTERS: tuple[str, ...] = (
    "draft_pressure_world",
    "draft_conflict_world",
    "draft_delta_pair",
)

#: Directories whose executable files are scanned, relative to the repo root.
SCANNED_DIRS: tuple[str, ...] = ("tests", "demos", "docs")

#: Executable file kinds. Markdown prose is deliberately not scanned — the
#: catalog and the architecture docs name both sides of the rule in order to
#: state it.
SCANNED_SUFFIXES: frozenset[str] = frozenset({".py", ".ipynb"})

RULE_MESSAGE = (
    "NO-PEEKING RULE VIOLATED (owner ruling 2026-08-27; see ABIO Experiment "
    "Catalog § The no-peeking rule): a language model may not be run on a "
    "conflict/pressure/delta substrate until Alignment Under Pressure has "
    "published. These files pair an LLM entry point with a guarded drafter:\n"
)


def _word_pattern(names: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(r"\b(" + "|".join(re.escape(n) for n in names) + r")\b")


def scan(root: Path = REPO_ROOT) -> list[tuple[Path, set[str], set[str]]]:
    """Every scanned file naming both an LLM entry point and a guarded drafter.

    Returns ``(path, llm_names_found, drafter_names_found)`` triples. Pure and
    importable so a caller can inspect the scan; the test below asserts it is
    empty.
    """
    llm_re = _word_pattern(LLM_ENTRY_POINTS)
    drafter_re = _word_pattern(GUARDED_DRAFTERS)
    self_path = Path(__file__).resolve()
    offenders: list[tuple[Path, set[str], set[str]]] = []
    for rel in SCANNED_DIRS:
        base = root / rel
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in SCANNED_SUFFIXES or not path.is_file():
                continue
            if path.resolve() == self_path:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            llm_hits = set(llm_re.findall(text))
            if not llm_hits:
                continue
            drafter_hits = set(drafter_re.findall(text))
            if drafter_hits:
                offenders.append((path, llm_hits, drafter_hits))
    return offenders


def test_no_executable_file_pairs_an_llm_entry_point_with_a_guarded_drafter() -> None:
    offenders = scan()
    if offenders:
        lines = [
            f"  {p.relative_to(REPO_ROOT)}: {sorted(llm)} with {sorted(drafters)}"
            for p, llm, drafters in offenders
        ]
        raise AssertionError(RULE_MESSAGE + "\n".join(lines))


def test_lint_actually_sees_the_scanned_tree() -> None:
    """The guard is only worth anything if it reads real files: the existing
    opt-in LLM test and the existing pressure-generator tests must both be
    within its reach (each alone is fine; only their pairing is forbidden)."""
    llm_re = _word_pattern(LLM_ENTRY_POINTS)
    drafter_re = _word_pattern(GUARDED_DRAFTERS)
    scanned = [
        p
        for rel in SCANNED_DIRS
        for p in (REPO_ROOT / rel).rglob("*")
        if p.suffix in SCANNED_SUFFIXES and p.is_file()
    ]
    texts = [p.read_text(encoding="utf-8", errors="replace") for p in scanned]
    assert any(llm_re.search(t) for t in texts), "no LLM entry point in reach"
    assert any(drafter_re.search(t) for t in texts), "no guarded drafter in reach"
