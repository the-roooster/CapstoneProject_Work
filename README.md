# SentinelAI

SentinelAI is an insider-threat monitoring application for ingesting activity, scoring user-days and investigating alerts with evidence-linked reasons.

## Prerequisites and configuration

Use Python 3.11+, Node.js/npm and a disposable PostgreSQL database. Copy `.env.example` to `backend/.env` and to `.env` at the repository root. In the backend copy set `DATABASE_URL` (using a SQLAlchemy PostgreSQL/psycopg URL), a `JWT_SECRET` of at least 32 characters, `DEMO_EMAIL`, `DEMO_PASSWORD`, and `CORS_ORIGINS` to the frontend's actual origin. In the root copy set `VITE_API_URL` to the backend API URL, for example `http://localhost:8000/api/v1`. LLM settings are optional; the summary falls back to a template.

## Backend setup

From the repository root:

```sh
python -m venv ../sentinel-venv
# macOS/Linux:
source ../sentinel-venv/bin/activate
# Windows PowerShell instead: ..\sentinel-venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
cd backend
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

In a separate terminal, with the same environment active and from `backend/`, seed the demo:

```sh
python -m scripts.seed_demo --yes
```

**This resets the configured database to Alembic base before reseeding. Use a disposable database.** The script prints the scenario results and returns non-zero if the headline checks fail.

## Frontend setup and tests

From the repository root in another terminal:

```sh
npm i
npm run dev
npm test
npm run build
npm run lint
```

For backend tests, activate the Python environment and run `python -m pytest` from `backend/`.

The following journeys follow the current UI; the AppFlow source was not available for comparison.

## Demo journey A — seeded alert review

1. Run the guarded seed command above and start both services.
2. Open the frontend and sign in with `DEMO_EMAIL` and `DEMO_PASSWORD`.
3. On **Dashboard**, inspect the risk distribution and top users; select an alert from **Alerts**.
4. Open EMP007's alert, review its reasons and related events, and select **Generate summary**.
5. Select **Mark reviewed** or **Escalate**, then open the user profile to inspect history and baseline.

## Demo journey B — import and investigate

1. Sign in and open **Import**.
2. Choose available CERT `logon.csv`, `device.csv`, and/or `file.csv`, then select **Import and score**.
3. Wait for the ingest report and scoring job to finish in the log.
4. Open **Alerts**, filter by level, department, status and dates, then open an alert.
5. Open **Login map** to inspect reported locations.

## Known deviations from BAD v1

See [BAD v2](docs/BAD-v2.md#deviations-from-bad-v1) for the implemented deviations and the current training limitation.

## Screenshots

Placeholder.
