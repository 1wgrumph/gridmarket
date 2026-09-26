**REPAIR_REQUIRED**

Reviewed `gridmarket/lifecycle-setup` at `4defcb4535ca16d70918d3e597599ed26b03028e` only. Plan-package check: PASS, manifest digest `1a0b6c0d3c93140e283901801f1f6947ce04f9c483ba2c056f4a84838e215260`. OCR: typed gap (Markdown excluded); those files were read directly. Reverify: not applicable (documents only). BRAN: unavailable (no `.bran/policy.yaml`).

### F1 — P1 — S17 is dispatched onto the stretch branch that S16 also writes

`implementation.json:2321-2324` sets S17 `lane`/`worktree`/`branch` to `stretch` / `base-gridmarket-stretch` / `gridmarket/lane-stretch`, `branch_base` the S09 exit, `parallel_safe: true`. S16 is the same worktree and branch (`implementation.json:2178-2184`), also `parallel_safe`, and both become ready when S15 exits (S17 also waits on the S14 slot). `slice-graph.md:76` repeats lane `stretch`.

The same package tells assembly to merge a different branch: `implementation.json:2667-2668` and `specialists/integration-plan.md:80` and `:245` put S17 alone on `gridmarket/lane-rust` from the S15 exit. Wave 3 lists a `rust` lane (`implementation.json:366`) that the slice record never uses. `slice-graph.md:92-96` treats rust `{S17}` as a separate slot from stretch `{S15, S16}`.

Two implementers will commit to one branch, and S18-D merges `lane-rust`, which the slice never creates. Rust then cannot be dropped on its own (RISK-GM-11).

**Repair:** Set S17 `lane` to `rust`, worktree `base-gridmarket-rust`, branch `gridmarket/lane-rust`, `branch_base` to the S15 exit. Make the S17 row in `slice-graph.md` match. Re-render the DoD manifest.

### F2 — P1 — Three Worker report paths are still placeholders, and only wave 1 can write the allowlist

`design.md:196-198` leaves NP3-565-CD, NP3-233-CD, and NP6-86-CD as `/api/report/<emil-id>/<report>`. `design.md:187-188` defers the real slugs to the data lane. S25 is the only slice that may edit `ercot-hackathon/` (`slice-graph.md:81`), and it does not depend on S06. `seit.json:411` calls those routes in PROC-ERCOT-LIVE-CHECK with no report suffix, so the live check is not a runnable URL. A wrong allowlist 404s load-forecast, outage, and shadow-price polls (AC-GM-DATA-01); no later slice can fix the Worker.

**Repair:** Replace the three `<report>` tokens in DES-GM-ERCOT and CONTRACT-GM-WORKER with the exact ERCOT report slugs, and copy those five full paths into the S24, S25, S03, and S06 goals and into the PROC-ERCOT-LIVE-CHECK command.

### Checked, no finding

All 47 `AC-GM-*` rows are on a slice and in the SEIT matrix, including atomic capacity (concurrent sells, SEIT market row), API-key hashes, idempotency, market rate limits, and DEC-GM-022 (S24–S25: allowlist, `MARKET_KEY`, 30/60s per client, 25/60s upstream). Phase 1 is scheduled Sat 14:00 CDT, freeze Sun 07:00, submission 11:00. Jordan’s Worker commits are after 2026-09-25 17:00 CDT. Owner/Jordan actions (tunnel, accept runs, publication, Loom, `wrangler deploy`) are not slice commands. Other wave-3 file write sets are disjoint once S17 is on `lane-rust`.

Candidate revision: `4defcb4535ca16d70918d3e597599ed26b03028e`  
Manifest digest: `1a0b6c0d3c93140e283901801f1f6947ce04f9c483ba2c056f4a84838e215260`
