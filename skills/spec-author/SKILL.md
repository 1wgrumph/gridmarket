---
name: spec-author
description: Write or revise a section of a GridMarket-style architecture specification from spec/template/ and build the single Markdown file. Use when adding, editing, or rebuilding specification sections. Do not use for figures (spec-diagram) or for checking a finished section alone (spec-lint).
---

# spec-author

## Procedure

1. Start a new specification by copying `spec/template/` to `spec/<name>/`.
   Fill `spec.yaml` (title, document_id, revisions; add one revision per
   published change).
2. Each section source is one file `NN[.n[.n]]-<slug>.md` with exactly one
   heading. Files build in numeric order (`04.1.2` after `04.1`). Copy
   `04.1.1-feature.md` once per feature as `04.1.<n>-<feature>.md`.
3. Write each section as:
   - YAML front matter `requirements:` listing at most 5 requirement ids it
     binds. Never batch requirements into one section to save space.
   - `**BLUF:**` one assertive sentence in the architect's voice.
   - `**Frame**` list with `**Who:**`, `**What:**`, `**Why:**`, `**How:**`,
     `**When:**`, `**Where:**`.
   - Prose, no word limit.
   - One captioned table when 3 or more items share 2 or more attributes:
     `Table (Tn): <caption>` then a Markdown table. Classes: T1 Requirements,
     T2 Interface signature, T3 Budget, T4 Trade/comparison, T5 Data
     dictionary, T6 Threat/control, T7 Open items, T8 Glossary.
   - One captioned figure when 3 or more entities have a relationship, a time
     order, or states: `Figure (Fn): <caption>` then `![...](figures/<x>.svg)`.
     Draw it with the spec-diagram skill.
4. Keep the COE-ASA-001 floor subsections the template carries (Identification,
   System context, Baselines, Purpose and scope, Stakeholders and their
   concerns, Requirements, Risks and unresolved evidence, Operational concept,
   Allocation, Interfaces and contracts, Architecture views, Model
   correspondence, Rationale, Verification approach). Do not rename them.
5. Build: `uv run --project backend --frozen python tools/spec_build.py spec/<name>/ spec/<Name>-Specification.md`.
   The front matter, numbering, and Appendix A traceability are generated;
   never edit the built file by hand.

## Pass rule

The build exits 0, a second build leaves the output byte-identical
(`git diff --exit-code` on the built file), and the spec-lint skill passes.
