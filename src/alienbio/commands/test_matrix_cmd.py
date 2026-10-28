"""the capability matrix: dimensions and the tests that prove them (--check gates CI).

    bio test-matrix              the 35 dimensions and the tests that prove them
    bio test-matrix --markdown   the generated table the dimensions doc carries
    bio test-matrix --check      exit 1 if a built / partial dimension has no test, or a
                                 proving test has no docstring sentence for `bio report`
"""

from __future__ import annotations

import argparse
import sys


def _parser() -> argparse.ArgumentParser:
    """One argparse parser, as every ``bio`` verb has: ``--help`` prints the
    usage to stdout and exits 0 (it printed the docstring to stderr, exit 2)."""
    parser = argparse.ArgumentParser(prog="bio test-matrix", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--markdown", action="store_true", help="print the generated Markdown table")
    parser.add_argument("--check", action="store_true", help="exit 1 when the capability gate fails")
    return parser


def test_matrix_command(args: list[str], verbose: bool = False) -> int:
    from alienbio.capabilities import check, check_phrases, render_markdown, render_text, unknown_ids

    del verbose
    try:
        ns = _parser().parse_args(args)
    except SystemExit as exc:  # argparse already printed usage (or help)
        return int(exc.code or 0)
    try:
        print(render_markdown() if ns.markdown else render_text(), end="")
        if not ns.check:
            return 0
        missing = check()
        unknown = unknown_ids()
        mute = check_phrases()
    except FileNotFoundError as exc:  # no tests/capabilities/ outside a checkout
        print(f"capability gate: {exc}", file=sys.stderr)
        return 1
    if missing or unknown or mute:
        if missing:
            print(f"capability gate: no test for {missing}", file=sys.stderr)
        if unknown:
            print(f"capability gate: tests claim unknown dimension(s) {unknown}", file=sys.stderr)
        if mute:
            print(f"capability gate: no docstring sentence for the report on {mute}", file=sys.stderr)
        return 1
    print("capability gate: every built / partial dimension is proven", file=sys.stderr)
    return 0
