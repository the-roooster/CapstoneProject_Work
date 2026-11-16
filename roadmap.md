# Roadmap

> Provisional: the PRD is not present in this repository or the available project files, so MVP/stretch classifications below are inferred from the implementation and requests. A checked item means code is present, not that the complete deployment has passed end-to-end verification.

## MVP

- [x] Analyst sign-in, JWT protection and per-IP/email failed-login limiting.
- [x] Synthetic user/activity generation and CSV/CERT ingestion with deduplication.
- [x] User-day behavioural features, anomaly scoring, calibration and rule explanations.
- [x] Dashboard, alert filtering, user/alert detail, evidence and investigation status.
- [x] PostgreSQL schema and migrations, SQLite test support, and a guarded demo seed command.
- [x] API configuration, explicit CORS origins and generic unexpected-error responses.
- [ ] Enforce history-only training for ordinary scoring/retraining; only an explicit cutoff and the demo currently exclude the scoring date.
- [ ] Verify the full backend suite, fresh database migration and guarded demo with installed dependencies.
- [ ] Verify frontend build, tests and lint with installed dependencies.

## Stretch

- [x] Analyst summary with configured LLM provider and deterministic fallback.
- [x] Login location map and CERT upload from the UI.
- [x] Reproducible model/rules evaluation and threshold-grid report.
- [ ] Evaluate against a real CERT dataset and its answer files; current measured report is synthetic only.
- [ ] Validate the design against the source PRD and confirm which items belong in MVP versus stretch.
