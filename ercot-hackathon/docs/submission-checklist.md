# GridMarket submission checklist

Base & AITX Talent Hackathon · due **Sunday 27 Sept 2026, 11:00 AM CT** · one submission per team via the Airtable form: <https://airtable.com/appWQWPtBqDUhCPPj/shrU4GuBeUnMzyrd5>

Tracks: Open Grid Data (primary), Most Commercializable. Judging runs off the demo video and the codebase.

## Required items

| Item | Status | Notes |
|---|---|---|
| Project title | Done | GridMarket |
| 2–5 min Loom demo (camera on, core loop live) | To do | Flow: team intros (≤30 s) → pitch (≤30 s) → live demo → how it's built → "so what" |
| Public repo | Owner action | `1wgrumph/gridmarket` is private. Settings → General → Danger Zone → Change visibility. Secret scan of tree and 508 commits: clean. |
| README: quick start | Done | "Run it locally" (Docker Compose) |
| README: tech stack and architecture diagram | In PR #23 | Mermaid diagram under "How it works" |
| README: reproduce the demo (env vars, keys, sample .env) | Done | `.env.example`, Worker setup in `ercot-hackathon/README.md` |
| README: datasets and provenance | Done | "What is real and what is simulated", `ercot-hackathon/public/data/PROVENANCE.md`, EIA-860 notes |
| README: known limitations and next steps | In PR #23 | |
| Deployed URL | Done | <https://ercot-hackathon.jordan-691.workers.dev/godseye/> · start link `#start` |
| Team roster | In PR #23 | William Rumph (@1wgrumph), Jordan Hill (@jhillbht) |
| 150–300 word write-up | Drafted | Paste into the Airtable form |

## Demo script (step 1: the real day)

1. Open <https://ercot-hackathon.jordan-691.workers.dev/godseye/#start>. It replays 26 Aug 2026 from 9 PM and stops on Houston **$780.46/MWh at 10:15 PM**.
2. Say the insight: demand peaked at 90.5 GW at 4:30 PM with low prices; the spike came at 73.5 GW after solar fell from 16.9 GW to zero. Every big Houston spike from June to September landed 8–11 PM.
3. Point out the simulated fleet ran down to its 20% reserve by 8:30 PM, then hand off to the dashboard Replay: move the reserve slider, knock a provider offline, rerun.
4. Place an order from the Judge sandbox.

## Links

- PR #23 (README): <https://github.com/1wgrumph/gridmarket/pull/23>
- Hackathon page: <https://common-scooter-829.notion.site/Base-AITX-Talent-Hackathon-3e01e636288e80a7b914c993f90ae6c5>
- Checklist: <https://common-scooter-829.notion.site/Submission-Checklist-3e51e636288e80868230ed0fd4a69678>
