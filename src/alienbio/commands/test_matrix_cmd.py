"""``bio test-matrix`` — the capability matrix (roadmap M48.1).

    bio test-matrix              the 35 dimensions and the tests that prove them
    bio test-matrix --markdown   the generated table the dimensions doc carries
    bio test-matrix --check      exit 1 if a built / partial dimension has no test
"""

from __future__ import annotations

import sys


def test_matrix_command(args: list[str], verbose: bool = False) -> int:
    from alienbio.capabilities import check, render_markdown, render_text, unknown_ids

    del verbose
    if any(a not in ("--markdown", "--check") for a in args):
        print(__doc__, file=sys.stderr)
        return 2
    if "--markdown" in args:
        print(render_markdown(), end="")
    else:
        print(render_text(), end="")
    if "--check" in args:
        missing = check()
        unknown = unknown_ids()
        if missing or unknown:
            if missing:
                print(f"capability gate: no test for {missing}", file=sys.stderr)
            if unknown:
                print(f"capability gate: tests claim unknown dimension(s) {unknown}", file=sys.stderr)
            return 1
        print("capability gate: every built / partial dimension is proven", file=sys.stderr)
    return 0
