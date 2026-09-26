# GridMarket ML report (SEIT-GM-ML-01, AC-GM-ML-01, DES-GM-ML)

Status: **FIXTURE-ONLY** — no owner-run live ERCOT Worker evidence exists
yet. The numbers below come from `backend/tests/fixtures/ml/`; replace them
with the owner-run live run when it lands (see "Live run" below).

## Open-Meteo terms check (RISK-GM-10)

Outcome: **permitted for this training context**. Basis: Open-Meteo's
published free-tier terms allow non-commercial use with attribution, and the
forecast/archive weather data carries CC BY 4.0, which the design already
records as satisfied by a README credit ("Weather data by Open-Meteo.com").
This offline, non-commercial hackathon training use with that attribution is
inside those terms, so the temperature feature stays. No live terms-page
fetch was made during S23 (live network is outside Product Implementer
authority); re-confirm against https://open-meteo.com/en/terms if the use
ever turns commercial. Attribution credit still belongs in the README
(owner/docs lane; outside this write set).

## Method

- Features per zone-hour: `hour_of_day`, `peak_flag` (NERC 5x16,
  America/Chicago, Sunday-observed holidays), `temperature`,
  `price_spread` (RT − hub), `load_pressure` (current − 24h mean),
  `outage_pressure` (current − 168h median), `congestion_pressure`
  (RT − hub + 0.1 × shadow sum), `population_weight` (WAC − RAC jobs
  summed to zones). Raw ERCOT numerators match `scoring.py`.
- Model: scikit-learn `HistGradientBoostingRegressor`, trained on ≥ 28
  days, tested on the following ≥ 7 days; Spearman vs the deterministic
  score plus permutation importances. Nothing is served by the API.
- Worker fetches (owner-run only) go through the five allowlisted report
  routes with the lane's own ≤ 5 requests/min sliding-window budget.

## Fixture results (112 train rows, 28 test rows, 2026-01-05..2026-02-08)

- Deterministic-score Spearman: **−1.0**
- Model Spearman: **0.9937**
- Permutation importances: temperature 1.856, population_weight 0.002,
  all other features 0.000 (constant in fixtures).

The model ranks the held-out week near-perfectly on fixtures because the
fixture target equals temperature exactly; treat this as a pipeline check,
not a skill claim. Real skill is unknown until the live run below.

## Live run (owner-executed, not yet run)

1. Set `GRIDMARKET_WORKER_URL` and `GRIDMARKET_WORKER_KEY`, then fetch the
   five allowlisted reports through `ml_data.fetch_report` (≤ 5 req/min;
   never during recording).
2. Build rows with `ml_data.build_features`, split 28/7 with
   `ml.split_by_date`, evaluate with `ml.evaluate`.
3. Replace the fixture table above with the live Spearman pair and
   importances, and flip the status line off FIXTURE-ONLY.

## Risks

- Fixture target equals temperature, so fixture skill does not transfer.
- The vendored peak calendar in `ml_data.py` mirrors `scoring.on_peak`;
  keep the two in sync if NERC rules change.
- `python -m gridmarket_server.ml --train-days/--test-days` from DES-GM-ML
  is not built; the S22 contract covers library calls only.
