"""run the suite once and write what it tested, and whether it passed (reports/).

    bio report                      run tests, run the examples, write reports/
    bio report --open               … and open the HTML page
    bio report --no-examples        skip the fresh example runs (faster)
    bio report --junit PATH         reuse an existing JUnit file instead of running pytest
    bio report --out DIR            write elsewhere (default: reports/)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    """One argparse parser (T057 proposal 7): the ``next(it)`` loop this
    replaces let ``--junit`` eat ``--no-examples`` and a bare ``--out``
    write the report into the working directory."""
    parser = argparse.ArgumentParser(prog="bio report", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--open", action="store_true", help="open the HTML page afterwards (macOS)")
    parser.add_argument("--no-examples", action="store_true", help="skip the fresh example runs")
    parser.add_argument("--junit", metavar="PATH", type=Path, help="reuse an existing JUnit file instead of running pytest")
    parser.add_argument("--out", metavar="DIR", type=Path, help="write elsewhere (default: reports/)")
    return parser


def report_command(args: list[str], verbose: bool = False) -> int:
    from alienbio.report import REPO, build, count_cases, parse_junit, render_html, render_markdown, run_pytest

    del verbose
    try:
        ns = _parser().parse_args(args)
    except SystemExit as exc:  # argparse already printed usage + the error
        return int(exc.code or 0)
    out_dir: Path = ns.out if ns.out is not None else REPO / "reports"
    junit: Path | None = ns.junit
    run_examples, open_after = not ns.no_examples, ns.open
    out_dir.mkdir(parents=True, exist_ok=True)
    if junit is None:
        junit = out_dir / "junit.xml"
        print(f"bio report: running the suite -> {junit}", file=sys.stderr)
        exit_code = run_pytest(junit)
    else:
        exit_code = 0
    if not junit.exists():
        print(f"bio report: no JUnit file at {junit}", file=sys.stderr)
        return 1
    rep = build(parse_junit(junit), exit_code, run_examples=run_examples, totals=count_cases(junit))
    md, html_page = out_dir / "report.md", out_dir / "report.html"
    md.write_text(render_markdown(rep))
    html_page.write_text(render_html(rep))
    print(render_markdown(rep))
    print(f"bio report: wrote {md} and {html_page}", file=sys.stderr)
    if open_after and sys.platform == "darwin":
        subprocess.run(["open", str(html_page)], check=False)
    return 0 if rep.ok else 1
