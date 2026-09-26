"""CLI: ``python -m azdiagram render SRC... [--out DIR]`` and ``python -m azdiagram lint PATH...``."""

import argparse
import sys
from pathlib import Path

from azdiagram import lint, render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="azdiagram")
    sub = parser.add_subparsers(dest="command", required=True)
    render_cmd = sub.add_parser("render", help="write <stem>.svg and <stem>.drawio")
    render_cmd.add_argument("src", nargs="+", type=Path)
    render_cmd.add_argument(
        "--out", type=Path, help="output directory (default: beside SRC)"
    )
    lint_cmd = sub.add_parser(
        "lint", help="check YAML inputs, .drawio files, or directories"
    )
    lint_cmd.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args(argv)

    if args.command == "render":
        for src in args.src:
            result = render(src, args.out or src.parent)
            print(f"{result.engine}: {result.svg} {result.drawio}")
        return 0
    findings = lint(args.paths)
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
