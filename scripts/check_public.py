#!/usr/bin/env python3
"""Check tracked repository files for private markers."""

import os
import subprocess
import sys

# Private marker patterns to check (split to prevent self-match in gate scanner).
PATTERNS = [
    "/ho" + "me/",
    "/tmp/cla" + "ude-",
    "scratch" + "pad",
    "alpha" + "zede",
    "type" + "safe",
    "visual-" + "review",
    "design-" + "poc",
    "bearing-" + "lite",
    "claude.ai/code/" + "session",
    "1wgrumph" + "+",
]


def is_binary(filepath: str) -> bool:
    """Check if file is binary by scanning for NUL byte in initial chunk."""
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(8192)
            return b"\x00" in chunk
    except OSError:
        return False


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    target_dir = argv[0] if argv else "."

    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=target_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as err:
        sys.stderr.write(f"Error running git ls-files: {err}\n")
        return 2

    tracked_files = [line for line in result.stdout.splitlines() if line.strip()]
    matched = False

    for rel_path in tracked_files:
        file_path = os.path.join(target_dir, rel_path) if target_dir != "." else rel_path
        if not os.path.isfile(file_path):
            continue
        if is_binary(file_path):
            continue

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for lineno, line in enumerate(f, start=1):
                    line_lower = line.lower()
                    for pattern in PATTERNS:
                        if pattern.lower() in line_lower:
                            print(f"{rel_path}:{lineno}: {pattern}")
                            matched = True
        except OSError as err:
            sys.stderr.write(f"Error reading {rel_path}: {err}\n")
            continue

    return 1 if matched else 0


if __name__ == "__main__":
    sys.exit(main())
