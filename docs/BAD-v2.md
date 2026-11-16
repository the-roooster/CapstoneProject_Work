# BAD v2 — implemented system

## Components and flow

```text
[Analyst browser] --> [FastAPI + JWT] --> [PostgreSQL]
                            |                 ^
                            v                 |
                  [ingest -> features -> model -> rules]
                            |
                    [optional LLM summary]
```

CSV ingestion validates and deduplicates events; features aggregate each user's activity by local day; the trained Isolation Forest scores those rows, calibration assigns the display score and level, and rules add evidence-linked reasons. Jobs run in memory; model artifacts are saved locally. PostgreSQL uses the `sentinel` schema; SQLite is supported for tests.

| Area | Current implementation |
|---|---|
| Access | Analyst login with bcrypt and HS256 JWT; all application routes except login and health require a token. |
| Features | 18 user-day features use prior active-day history and configured timezone. |
| Model | Isolation Forest; training-derived percentiles default to Medium 97 and High 99.5; calibrated display anchors are 40/70. |
| Operations | In-memory ingestion/scoring jobs; optional OpenAI/Gemini summary falls back to a template. |

## API inventory

All paths start with `/api/v1`.

| Method and path | Why |
|---|---|
| GET /health | Check service availability. |
| POST /auth/login | Obtain an analyst token. |
| GET /users | Filter users and show their latest risk. |
| GET /users/{user_id} | Show a profile, baseline and risk history. |
| GET /events | Filter and page activity. |
| GET /events/by-ids | Retrieve evidence for reasons. |
| GET /events/trend | Chart daily activity counts. |
| GET /events/locations | Show login geography. |
| GET /alerts | Filter and sort non-Low user-days. |
| GET /alerts/summary | Populate dashboard totals and highest-risk users. |
| GET /alerts/{score_id} | Inspect an alert and suggested action. |
| PATCH /alerts/{score_id}/status | Record triage status. |
| POST /alerts/{score_id}/summary | Generate or template an analyst briefing. |
| GET /meta | Retrieve model cutoffs and display scale. |
| POST /ingest/run | Start CSV ingestion. |
| POST /score/run | Start feature building, optional training, scoring and explanations. |
| GET /jobs/{job_id} | Poll background-job progress. |

## Deviations from BAD v1

| Deviation | Justification |
|---|---|
| Reasons are objects | Codes, text, severity and event IDs preserve explainable evidence. |
| 99.5/97 percentile cutoffs replace 5%/15% | Training-derived cutoffs support adjustable alert volumes without a per-run fixed quota. |
| Calibrated 0–100 risk scale | Training anchors retain comparable 40/70 display thresholds across scoring runs. |
| History-only training is available, not enforced | `--before` and the seeded demo exclude the anchor date, but ordinary retraining currently uses all available feature rows. |
| Own PostgreSQL | The backend controls its data model and writes independently of the retired service. |
| Additional endpoints | Dashboard, workflow, evidence, import and model metadata need explicit API operations. |
| `activity_type` plus canonical activities | A broad category supports filtering while specific activity names retain meaning. |
