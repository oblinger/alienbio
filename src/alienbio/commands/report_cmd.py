"""``bio report`` — run the suite once and write what it tested, and whether it
passed, as one page (``reports/report.md`` + ``report.html``).

    bio report                      run tests, run the examples, write reports/
    bio report --open               … and open the HTML page
    bio report --no-examples        skip the fresh example runs (faster)
    bio report --junit PATH         reuse an existing JUnit file instead of running pytest
    bio report --out DIR            write elsewhere (default: reports/)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def report_command(args: list[str], verbose: bool = False) -> int:
    from alienbio.report import REPO, build, count_cases, parse_junit, render_html, render_markdown, run_pytest

    del verbose
    out_dir = REPO / "reports"
    junit: Path | None = None
    run_examples, open_after = True, False
    it = iter(args)
    for a in it:
        if a == "--open":
            open_after = True
        elif a == "--no-examples":
            run_examples = False
        elif a == "--junit":
            junit = Path(next(it, ""))
        elif a == "--out":
            out_dir = Path(next(it, ""))
        else:
            print(__doc__, file=sys.stderr)
            return 2
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
    return 0 if exit_code == 0 else 1
