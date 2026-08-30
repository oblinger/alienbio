"""M47.8 / M48.2 — the Expr Spec and Python API are the reference for shipped
code: every fenced example on those pages runs.

``docs/Guide/ABIO Expr Spec.md``: each ```yaml fence is loaded through the
Expr loader; unless its first line is ``# fragment`` it is also evaluated
(a top-level ``!experiment`` through ``load_experiment``). The page's Head
catalog must name every head the standard environment registers.
``docs/Guide/ABIO Expr Python API.md``: the ```python fences run in order in
one namespace, with the same fixture files beside them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from alienbio.expr import Env, registry
from alienbio.expr.form import Call
from alienbio.expr.yaml_tags import load_text
from alienbio.suite.expr_experiment import load_experiment

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "docs" / "Guide" / "ABIO Expr Spec.md"
API = REPO / "docs" / "Guide" / "ABIO Expr Python API.md"

HELPERS = '''
from alienbio.expr import fn, guard, GuardViolation

@fn(summary="doc helper: doubles")
def twice(x):
    return 2 * x

@guard(summary="doc helper: above a floor")
def above(value, ctx, floor: float = 0.5):
    return value > floor

@guard(summary="doc helper: every reaction has products")
def has_products(value, ctx):
    bad = [k for k, r in value.get("reactions", {}).items() if not r.get("products")]
    if bad:
        raise GuardViolation(f"reactions without products: {bad}", offenders=[f"reactions.{k}" for k in bad])
    return True

def health_score(timeline):
    return 1.0
'''


def _fences(path: Path, lang: str) -> list[tuple[int, str]]:
    text = path.read_text()
    out = []
    for m in re.finditer(r"^```" + lang + r"\n(.*?)^```", text, flags=re.S | re.M):
        line = text[: m.start()].count("\n") + 2
        out.append((line, m.group(1)))
    return out


@pytest.fixture(scope="module")
def docs_dir(tmp_path_factory):
    root = tmp_path_factory.mktemp("spec_examples")
    (root / "helpers.py").write_text(HELPERS)
    (root / "shared").mkdir()
    (root / "shared" / "defaults.yaml").write_text("k: 0.5\ntwo: !x 1 + 1\n")
    (root / "brief.md").write_text("# brief\n")
    return root


SPEC_FENCES = _fences(SPEC, "yaml") if SPEC.exists() else []


@pytest.mark.parametrize("line,text", SPEC_FENCES, ids=[f"spec-L{line}" for line, _ in SPEC_FENCES])
def test_every_spec_example_loads_and_evaluates(line, text, docs_dir):
    data = load_text(text)
    if text.lstrip().startswith("# fragment"):
        return
    env = Env.standard(seed=1, trusted=True)
    if isinstance(data, Call):
        assert data.head == "experiment", f"line {line}: a top-level call must be an !experiment"
        spec = load_experiment(f"<spec L{line}>", text=text, trusted=True)
        assert spec.name
        return
    values = env.load(str(docs_dir / f"spec_L{line}.yaml"), text=text, base=docs_dir).force_all()
    assert isinstance(values, dict)


def test_head_catalog_matches_the_registry():
    Env.standard()
    text = SPEC.read_text()
    section = text.split("## Head catalog", 1)[1].split("\n## ", 1)[0]
    listed = set(re.findall(r"`([A-Za-z_][A-Za-z_0-9]*)`", section))
    registered = {
        name for name in registry.names()
        if not name.startswith("op:")
        and (getattr(registry.get(name).fn, "__module__", "") or "").startswith(("alienbio.", "builtins", "math"))
    }
    missing = sorted(registered - listed)
    stale = sorted(n for n in listed if n not in registry and n not in {"Kind", "Heads"})
    assert not missing, f"heads registered but not in the Spec's catalog: {missing}"
    assert not stale, f"heads in the Spec's catalog but not registered: {stale}"


def test_python_api_examples_run(docs_dir, monkeypatch):
    monkeypatch.chdir(docs_dir)
    fences = _fences(API, "python")
    assert fences, "the Python API page has no ```python fences"
    namespace: dict = {"__name__": "abio_expr_api_examples"}
    for line, code in fences:
        if code.lstrip().startswith("# fragment"):
            continue
        try:
            exec(compile(code, f"ABIO Expr Python API.md:L{line}", "exec"), namespace)
        except Exception as exc:  # noqa: BLE001 — the line number is the point
            raise AssertionError(f"Python API example at line {line} failed: {exc!r}") from exc
