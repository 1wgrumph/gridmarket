# Your first 3 minutes

**Texas home batteries, paid to help when the grid is tight.**
A simulated flexibility exchange running on real ERCOT conditions.

Start with the [local setup](../README.md#run-it-locally), then open
<http://127.0.0.1:8000/>. These three minutes begin with the app running.

1. **0:00 — Monitor.** On **Overview**, look at the Texas load zones and
   exchange tape. The population is simulated; the tape records API activity.
   Check observation timestamps: missing ERCOT data on a keyless local run
   is expected, not a measurement of an idle grid.
2. **0:40 — Forecast.** Open **Predictions**. Choose a zone and inspect the
   drivers behind its scarcity score. The score is a simulation estimate;
   real weather and ERCOT observations inform it when configured. It is
   neither guaranteed profit nor a blackout prediction.
3. **1:15 — Respond.** Open **Judge sandbox** and click **Get a sandbox key**.
   You receive $1,000 in simulated funds. Keep the page open, copy your key
   privately, then run the [SDK example](../README.md#build-a-trading-bot-or-agent)
   in a terminal. Enter the key at its prompt. It selects a currently open
   product and submits one buy order at 10 simulated cents.
4. **2:15 — Report.** Return to **Your orders** on the sandbox page. Notice
   the order status; acceptance does not guarantee a fill. Open **Market**
   to inspect the book and activity. The SDK also prints your portfolio.
   Open **Bots** to compare simulated participants and their P&L.

**What is real?** The API and matching engine run; configured ERCOT and NWS
feeds provide real observations. **What is simulated?** Homes, batteries,
procurement, Flex Credit contracts and all money. No energy is dispatched.
The demo does not establish an effect on wholesale prices or blackouts.

For developers: discover the API, get a sandbox key, make the first call,
then build with the [Python SDK or local MCP server](../README.md#build-a-trading-bot-or-agent).
