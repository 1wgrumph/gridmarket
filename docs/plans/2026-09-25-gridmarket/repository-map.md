# Repository Map: GridMarket hackathon MVP

- Root: `/home/spectre/alphazede/Hackathons/Base`
- Plan directory: `docs/plans/2026-09-25-gridmarket/`
- Observed at: HEAD `378fcb993f9b6993dddae95ea02bee037ac62d66`, branch
  `gridmarket/lifecycle-setup`, 2026-09-25.
- BRAN: unavailable (no `.bran/policy.yaml` from root upward). Ordinary bounded
  discovery used.

## Discovery Bounds
- Limits: depth 2, max 40 paths, max 64 KiB, read-only.
- Used: 3 tracked or plan files, depth ≤ 2 outside the plan directory, about
  32 KiB read. Bounds not exhausted.
- Prohibited traversal (`src/`, `lib/`, `vendor/`, `docs/`) not entered, except
  the confirmed plan directory.

## Tree
```text
.
├── gridmarket-intent.html          owner intent and build specification
├── reference/
│   └── hackathon-brief.md          event rules, tracks, judging, deadline
└── docs/plans/2026-09-25-gridmarket/
    ├── journey.json                Lifecycle state and decisions
    ├── workspace.md                this node
    └── repository-map.md           this node
```

## Anchors
| Anchor | Status |
|---|---|
| Root manifest (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, others) | absent |
| Task runner (`Makefile`, `justfile`, `Taskfile`, npm scripts) | absent |
| CI entrypoint (`.github/workflows/`, others) | absent |
| Top-level instructions (`AGENTS.md`, `CLAUDE.md`, `README`) | absent in repo |
| Root test configuration | absent |

All anchors are absent because the repository is greenfield, not because
discovery bounds ran out.

## Architecture Coverage
| Source | Kind | Covers |
|---|---|---|
| `gridmarket-intent.html` §10 | intent | provider adapter contract |
| `gridmarket-intent.html` §11 | intent | public REST API surface |
| `gridmarket-intent.html` §12 | intent | order intent to policy/risk to market engine flow |
| `gridmarket-intent.html` §16 | intent | conceptual component diagram |
| `gridmarket-intent.html` §17 | intent | suggested data model |
| Realized code or model | none | nothing |

Gap: no realized or modeled architecture covers the affected scope. Systems
Modeler activation is needed. This map does not design the missing
architecture.

## Git State
- Remote: none (DEC-GM-001 defers the GitHub remote to the owner).
- Commits: 1 (`378fcb9 Add GridMarket intent and hackathon brief`).
- Working tree: `docs/` untracked; `gridmarket-intent.html` and
  `reference/hackathon-brief.md` unmodified.
