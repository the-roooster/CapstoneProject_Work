"""Reset and seed the demo: from backend/, run python -m scripts.seed_demo --yes.

This command downgrades the configured database to Alembic base before upgrading
to head. Set DEMO_EMAIL and DEMO_PASSWORD, and use only a disposable database.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ANCHOR = date(2026, 11, 2)
SEED = 42
DAYS = 45
USERS = ("EMP004", "EMP007", "EMP013", "EMP018")


def run_demo(*, confirmed=False, output_dir=None):
    if not confirmed:
        raise ValueError("Refusing to reset the database without --yes")

    # Imports follow the confirmation guard so even startup cannot touch the DB.
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import select

    from app.config import settings
    from app.db import SessionLocal
    from app.explain.run import explain_all
    from app.features.build_features import build_features
    from app.features.columns import FEATURE_COLUMNS
    from app.ingest.ingest import load_events_csv, load_users_csv
    from app.ingest.synthetic import generate_synthetic
    from app.ml.registry import load_latest
    from app.ml.scoring import score_features
    from app.ml.train import train
    from app.models import Feature, RiskScore
    from scripts.seed_analyst import seed_analyst

    if not settings.DEMO_EMAIL.strip() or not settings.DEMO_PASSWORD:
        raise ValueError("DEMO_EMAIL and DEMO_PASSWORD must be set before resetting the database")

    backend = Path(__file__).resolve().parents[1]
    output = Path(output_dir) if output_dir is not None else backend.parent / "data" / "synthetic"
    config = Config(str(backend / "alembic.ini"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    with SessionLocal() as db:
        seed_analyst(db, settings.DEMO_EMAIL, settings.DEMO_PASSWORD)
        generate_synthetic(output, seed=SEED, anchor_date=ANCHOR, days=DAYS)
        user_report = load_users_csv(db, output / "users.csv")
        event_report = load_events_csv(db, output / "events.csv")
        if user_report.skipped_by_reason or event_report.skipped_by_reason:
            raise RuntimeError(f"Demo ingestion skipped rows: users={user_report.skipped_by_reason}, events={event_report.skipped_by_reason}")
        build_features(db)
        version = train(db, before=ANCHOR)
        artifact = load_latest()
        if artifact["version"] != version:
            raise RuntimeError("The newly trained model is not the latest registry version")
        score_features(db)
        explain_all(db)
        calibration = artifact["calibration"]

        rows = {}
        for user_id in USERS:
            score = db.scalar(select(RiskScore).where(RiskScore.user_id == user_id, RiskScore.date == ANCHOR))
            feature = db.scalar(select(Feature).where(Feature.user_id == user_id, Feature.date == ANCHOR))
            rows[user_id] = (score, feature)

        print(f"{'User':<8} {'Level':<8} {'Score':>5}  Reasons")
        print("-" * 78)
        for user_id, (score, _) in rows.items():
            if score is None:
                print(f"{user_id:<8} {'MISSING':<8} {'-':>5}  -")
            else:
                codes = ", ".join(reason["code"] for reason in score.reasons)
                print(f"{user_id:<8} {score.risk_level:<8} {score.risk_score:>5}  {codes}")

        failures = {}
        def check(user_id, minimum, required, any_of=()):
            score, feature = rows[user_id]
            if score is None or feature is None:
                return ["missing score or feature row"]
            problems = []
            rank = {"Low": 0, "Medium": 1, "High": 2}
            if rank.get(score.risk_level, -1) < rank[minimum]:
                problems.append(f"expected {minimum} or higher, got {score.risk_level}")
            codes = {reason["code"] for reason in score.reasons}
            missing = set(required) - codes
            if missing:
                problems.append("missing reasons: " + ", ".join(sorted(missing)))
            if any_of and not codes.intersection(any_of):
                problems.append("expected one of: " + ", ".join(any_of))
            return problems

        checks = {
            "EMP007": check("EMP007", "High", ("MASS_DOWNLOAD", "FIRST_USB", "NEW_DEVICE"), ("LATE_LOGIN", "OFF_HOURS")),
            "EMP013": check("EMP013", "Medium", ("FAILED_LOGINS", "NEW_LOCATION")),
            "EMP018": check("EMP018", "Medium", ()),
        }
        failures = {user_id: problems for user_id, problems in checks.items() if problems}
        for user_id, problems in failures.items():
            score, feature = rows[user_id]
            print(f"\nFAILED {user_id}: {'; '.join(problems)}", file=sys.stderr)
            details = {"feature_row": {"user_id": feature.user_id, "date": feature.date.isoformat(), **{name: getattr(feature, name) for name in FEATURE_COLUMNS}} if feature else None,
                       "anomaly_score": score.anomaly_score if score else None,
                       "risk_score": score.risk_score if score else None,
                       "cutoffs": {"lo": calibration.lo, "medium_cut": calibration.med_cut,
                                   "high_cut": calibration.high_cut, "hi": calibration.hi}}
            print(json.dumps(details, sort_keys=True), file=sys.stderr)
        return not failures


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reset and seed the SentinelAI demo database")
    parser.add_argument("--yes", action="store_true", help="confirm the destructive database reset")
    args = parser.parse_args(argv)
    if not args.yes:
        parser.error("Refusing to reset the database without --yes")
    try:
        return 0 if run_demo(confirmed=True) else 1
    except Exception as exc:
        print(f"Demo failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
