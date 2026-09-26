---
name: spec-lint
description: Check specification section sources and figures against the section rules (BLUF, Frame, at most 5 requirements, T1-T8/F1-F8 classes, table and figure triggers) and the figure lint. Use before committing any specification change. Do not use to write sections or draw figures.
---

# spec-lint

## Procedure

1. Section rules: `uv run --project backend --frozen python tools/spec_lint.py spec/<name>/`.
   Each finding names the file and the defect: missing front matter, not
   exactly one heading, missing BLUF, missing Frame field, more than 5
   requirements, a class outside T1-T8 or F1-F8, a caption not followed by
   its table or image, a list of 3+ items sharing 2+ attributes with no
   table, or 3+ related entities (`->` list or ordered steps) with no figure.
2. Figures: `PYTHONPATH=tools uv run --project backend --frozen python -m azdiagram lint spec/<name>/`.
3. Staleness: rebuild with `tools/spec_build.py` and run
   `git diff --exit-code` on the built specification.
4. Fix each finding in the section source or figure YAML, then rerun all
   three. Do not weaken a trigger by rewording a list to dodge it.

## Pass rule

All three commands exit 0 with no findings. Any finding, a stale built file,
or a command that could not run fails.
