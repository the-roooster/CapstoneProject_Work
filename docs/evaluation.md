# Evaluation

## Result: synthetic only

This report records the output of `python -m scripts.evaluate` using seed 42 and the fixed synthetic anchor date. CERT data and answer files were not available. The run used a temporary settings stub for `APP_TZ=Asia/Kolkata` and `USB_LOOKBACK_DAYS=90` because `pydantic-settings` is not installed in the execution environment; the existing generator, ingestion, feature builder, model, calibration, and rules ran against an isolated in-memory SQLite database.

The suggested percentiles are provisional observations from three seeded positive user-days, not validated production defaults. The negative control was flagged Medium at those settings.

## Reproduce

From `backend/`, with the backend dependencies installed:

```sh
python -m scripts.evaluate
python -m scripts.evaluate --cert-dir /path/to/cert --answers /path/to/answers
```

The answer path can be a CSV or a directory. Without `--answers`, the script searches for CSVs in paths containing “answer” or “insider”. Answer rows need a user identifier and either start/end dates or dated insider events. The evaluation uses all labelled insiders plus a deterministic sample of up to 200 other users.

## Captured output

```text
synthetic only
Dataset: synthetic; seed=42; timezone=Asia/Kolkata; sample=20/20 users (all labelled insiders plus up to 200 others).
Synthetic: anchor=2026-11-02, 45 preceding calendar days; EMP007, EMP013 and EMP018 are positive scenarios; EMP004 is a negative control.
Ingest: users inserted=20; events read=10358, inserted=10358, skipped=0.
Split: 32 distinct active dates; first 22 dates train (440 user-days), remaining 10 dates test (200 user-days), test starts 2026-10-20.
Test labels: 3 positive user-days across 3 insiders.
Rankings: P@10 | P@50 | recall@top5% | insiders@10 | insiders@50
Model only: 0.300 | 0.060 | 1.000 (top 10) | 3 | 3
Rules only: 0.300 | 0.060 | 1.000 (top 10) | 3 | 3
Combined (evaluation only): 0.300 | 0.060 | 1.000 (top 10) | 3 | 3
Grid: HIGH_PCT | MEDIUM_PCT | medium+high alerts/1000 | high alerts/1000 | recall (medium+high)
99.9 | 99 | 20.00 | 10.00 | 1.000
99.9 | 97 | 50.00 | 10.00 | 1.000
99.9 | 95 | 65.00 | 10.00 | 1.000
99.5 | 99 | 20.00 | 20.00 | 1.000
99.5 | 97 | 50.00 | 20.00 | 1.000
99.5 | 95 | 65.00 | 20.00 | 1.000
99 | 99 | 20.00 | 20.00 | 1.000
99 | 97 | 50.00 | 20.00 | 1.000
99 | 95 | 65.00 | 20.00 | 1.000
Suggested evaluation defaults: HIGH_PCT=99.9, MEDIUM_PCT=99 (highest measured recall, then lowest medium+high and high alert rates; not a product configuration change).
EMP004 negative control at suggested defaults: Medium (anomaly_score=0.666740).
Caveats: the time split is by distinct active dates, not a random user split; training may include labelled insiders. Evaluation labels are user-day intervals, not proof that every event in an interval is malicious.
CERT caveat: CERT imports use placeholder IP and location values; NEW_LOCATION never fires for CERT-only users. Unknown-user baselines use their first 14 days and can cross the train/test boundary.
Synthetic caveat: results describe seeded scenarios and do not establish performance on real insider threats. Combined ranking is comparison-only and is not the product score.
```

Precision is measured over the available rows in each top-k set. Recall@top5% is the fraction of all labelled positive test user-days in the highest-ranked 5% of test user-days (rounded up). Insider counts are distinct labelled users found in each top-k set. The grid's recall uses all Medium and High alerts. Combined ranking averages percentile ranks of model and rule scores; it is for comparison only.
